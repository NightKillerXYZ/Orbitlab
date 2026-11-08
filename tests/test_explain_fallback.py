"""Step 7 tests: explainer fallback, retry, digest cap, explanationSource."""
import json
import logging

import pytest

from orbitlab_backend.orchestrator.pipeline import Pipeline
from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.clients.explainer_client import (
    MockExplainer,
    OpenAIExplainer,
    build_explain_digest,
    fallback_explanation,
    failure_explanation,
    get_explainer,
)

EARTH_EXP = {
    "spacecraft": {"name": "SC", "dryMassKg": 500},
    "centralBody": "Earth",
    "initialOrbit": {"type": "Keplerian", "coordinateSystem": "EarthMJ2000Eq",
                     "elements": {"semiMajorAxisKm": 6778.136, "eccentricity": 0,
                                  "inclinationDeg": 28.5, "raanDeg": 0,
                                  "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}},
    "forceModel": {"gravityDegree": 4, "gravityOrder": 4, "pointMasses": ["Luna", "Sun"],
                   "atmosphericDrag": {"enabled": False}, "solarRadiationPressure": True},
    "propagation": {"integrator": "RungeKutta89",
                    "stopCondition": {"type": "ElapsedHours", "value": 2}},
    "maneuvers": [],
}

MARS_EXP = {
    "spacecraft": {"name": "SC", "dryMassKg": 1200},
    "centralBody": "Mars",
    "initialOrbit": {"type": "Keplerian", "coordinateSystem": "MarsMJ2000Eq",
                     "elements": {"semiMajorAxisKm": 4611.875, "eccentricity": 0.2,
                                  "inclinationDeg": 10.0, "raanDeg": 0,
                                  "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}},
    "forceModel": {"gravityDegree": 4, "gravityOrder": 4, "pointMasses": ["Sun"],
                   "atmosphericDrag": {"enabled": False}, "solarRadiationPressure": True},
    "propagation": {"integrator": "RungeKutta89",
                    "stopCondition": {"type": "ElapsedDays", "value": 3}},
    "maneuvers": [],
}

HOHMANN_EXP = dict(EARTH_EXP, maneuvers=[{
    "id": "M1", "type": "TargetedHohmannTransfer",
    "trigger": {"condition": "AtPeriapsis"},
    "targetObjectives": {"targetOrbitRadiusKm": 9000}}])

EXTRACTED = {"centralBody": "Earth", "dryMassKg": 500,
             "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"},
             "duration": {"value": 2, "unit": "hours"}, "integrator": "RungeKutta89",
             "inclinationDeg": 28.5, "raanDeg": 0, "argumentOfPeriapsisDeg": 0,
             "trueAnomalyDeg": 0, "forces": None, "maneuvers": [], "cartesian": None}


def _pipeline_with(explainer):
    ext = FrontStepExtractor()
    ext._fallback_extract = lambda t: dict(EXTRACTED)
    interp = MockInterpreterClient(canned_json=json.dumps(EARTH_EXP))
    return Pipeline(extractor=ext, interpreter=interp, explainer=explainer, gmat_runner=None)


def _patch_transport(monkeypatch, handler):
    from httpx import AsyncClient, MockTransport
    import orbitlab_backend.clients.explainer_client as ec

    class PatchedClient(AsyncClient):
        def __init__(self, *a, **kw):
            super().__init__(transport=MockTransport(handler), timeout=kw.get("timeout"))

    monkeypatch.setattr(ec.httpx, "AsyncClient", PatchedClient)


def _fake_explainer():
    return OpenAIExplainer(base_url="http://fake/explainer", api_key="k",
                           model="m", timeout_s=5)


# ---------- deterministic fallback text ----------

def test_fallback_earth_circular_period():
    text = fallback_explanation(EARTH_EXP, "success", None, [], None)
    assert "1.54 hours" in text
    assert "400.0 km" in text
    assert "nearly circular" in text
    n_sentences = len([s for s in text.split(". ") if s.strip()])
    assert 4 <= n_sentences <= 6


def test_fallback_elliptical_mars():
    text = fallback_explanation(MARS_EXP, "success", None, [], None)
    assert "Mars" in text
    assert "elliptical" in text
    assert "hours" in text


def test_fallback_hohmann():
    text = fallback_explanation(HOHMANN_EXP, "success", None, [], None)
    assert "Hohmann" in text
    assert "9000" in text


def test_failure_explanation_one_sentence_capped():
    text = failure_explanation("validate", "x" * 900)
    assert text.startswith("The run stopped at the validate stage: ")
    assert len(text) <= len("The run stopped at the validate stage: ") + 600 + 1
    assert text.endswith(".")


def test_digest_cap_with_huge_trajectory():
    huge = {"num_points": 10, "blob": "x" * 200000,
            "min_altitude_km": 390.0, "max_altitude_km": 410.0,
            "final_altitude_km": 400.0, "final_speed_km_s": 7.67}
    digest = build_explain_digest(EARTH_EXP, "success", None, [], huge)
    assert len(digest) <= 1500
    assert "400.0 km" in digest


# ---------- request shape ----------

@pytest.mark.asyncio
async def test_request_body_small_temp_and_tokens(monkeypatch):
    from httpx import Response, Request
    seen = {}
    huge = {"num_points": 10, "points": ["y" * 200000],
            "min_altitude_km": 390.0, "max_altitude_km": 410.0}

    async def handler(request: Request):
        seen["body"] = json.loads(request.content.decode())
        seen["raw_len"] = len(request.content)
        return Response(200, json={"choices": [{"message": {"content": "model says stable"}}]})

    _patch_transport(monkeypatch, handler)
    client = _fake_explainer()
    out = await client.explain(EARTH_EXP, "success", None, [], huge)
    assert out == "model says stable"
    assert seen["raw_len"] <= 3000
    assert seen["body"]["max_tokens"] == 400
    assert seen["body"]["temperature"] == 0.2
    assert "No markdown headings" in seen["body"]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_failure_request_uses_temp_zero_and_capped_error(monkeypatch):
    from httpx import Response, Request
    seen = {}

    async def handler(request: Request):
        seen["body"] = json.loads(request.content.decode())
        return Response(200, json={"choices": [{"message": {"content": "model failure note"}}]})

    _patch_transport(monkeypatch, handler)
    client = _fake_explainer()
    out = await client.explain(EARTH_EXP, "validate", "e" * 900, ["w1"])
    assert out == "model failure note"
    assert seen["body"]["temperature"] == 0
    assert seen["body"]["messages"][1]["content"].count("e" * 50) <= 12  # ~600 chars, not 900


# ---------- pipeline: explain never fails a success ----------

@pytest.mark.asyncio
async def test_pipeline_unconfigured_explainer_uses_fallback():
    pipeline = _pipeline_with(MockExplainer())
    events = []
    res = await pipeline.run("dummy", event_cb=events.append)
    assert res["status"] == "success"
    assert res["explanationSource"] == "fallback"
    assert isinstance(res["explanation"], str) and res["explanation"]
    explain_done = [e for e in events if e.type == "stage_completed" and e.stage == "explain"]
    assert len(explain_done) == 1
    assert "automatic summary" in explain_done[0].message
    assert not [e for e in events if e.type == "stage_failed" and e.stage == "explain"]


@pytest.mark.asyncio
async def test_pipeline_timeout_twice_fallback_and_warning(monkeypatch, caplog):
    import httpx

    async def handler(request):
        raise httpx.ReadTimeout("simulated timeout")

    _patch_transport(monkeypatch, handler)
    pipeline = _pipeline_with(_fake_explainer())
    with caplog.at_level(logging.WARNING, logger="orbitlab.explainer"):
        res = await pipeline.run("dummy")
    assert res["status"] == "success"
    assert res["explanationSource"] == "fallback"
    assert isinstance(res["explanation"], str) and res["explanation"]
    assert "explainer failed" in caplog.text
    assert "Bearer" not in caplog.text and "Authorization" not in caplog.text


@pytest.mark.asyncio
async def test_pipeline_503_then_model_success(monkeypatch):
    from httpx import Response
    calls = []

    async def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return Response(503, json={"error": "warming up"})
        return Response(200, json={"choices": [{"message": {"content": "Model says stable orbit."}}]})

    _patch_transport(monkeypatch, handler)
    res = await _pipeline_with(_fake_explainer()).run("dummy")
    assert res["status"] == "success"
    assert res["explanationSource"] == "model"
    assert res["explanation"] == "Model says stable orbit."
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_pipeline_400_fallback_and_warning(monkeypatch, caplog):
    from httpx import Response
    calls = []

    async def handler(request):
        calls.append(1)
        return Response(400, json={"error": "bad request"})

    _patch_transport(monkeypatch, handler)
    with caplog.at_level(logging.WARNING, logger="orbitlab.explainer"):
        res = await _pipeline_with(_fake_explainer()).run("dummy")
    assert res["status"] == "success"
    assert res["explanationSource"] == "fallback"
    assert len(calls) == 1  # no retry on 400
    assert "explainer failed" in caplog.text


@pytest.mark.asyncio
async def test_pipeline_empty_reply_falls_back(monkeypatch):
    from httpx import Response

    async def handler(request):
        return Response(200, json={"choices": [{"message": {"content": "   "}}]})

    _patch_transport(monkeypatch, handler)
    res = await _pipeline_with(_fake_explainer()).run("dummy")
    assert res["status"] == "success"
    assert res["explanationSource"] == "fallback"
    assert res["explanation"]


@pytest.mark.asyncio
async def test_pipeline_model_answer_source_model(monkeypatch):
    from httpx import Response

    async def handler(request):
        return Response(200, json={"choices": [{"message": {"content": "A calm circular flight."}}]})

    _patch_transport(monkeypatch, handler)
    res = await _pipeline_with(_fake_explainer()).run("dummy")
    assert res["status"] == "success"
    assert res["explanationSource"] == "model"
    assert res["explanation"] == "A calm circular flight."


# ---------- failure paths keep a deterministic explanation ----------

@pytest.mark.asyncio
async def test_failed_run_explainer_error_still_explained():
    ext = FrontStepExtractor()
    ext._fallback_extract = lambda t: dict(EXTRACTED)
    mismatch = dict(EARTH_EXP)
    mismatch["initialOrbit"] = dict(EARTH_EXP["initialOrbit"],
                                    elements=dict(EARTH_EXP["initialOrbit"]["elements"],
                                                  semiMajorAxisKm=7000.0))
    interp = MockInterpreterClient(canned_json=json.dumps(mismatch))

    class RaisingExplainer(MockExplainer):
        async def explain(self, experiment, stage, error, warnings, trajectory_summary=None):
            raise RuntimeError("boom")

    pipeline = Pipeline(extractor=ext, interpreter=interp,
                        explainer=RaisingExplainer(), gmat_runner=None)
    with pytest.raises(Exception) as exc:
        await pipeline.run("dummy")
    details = exc.value.details or {}
    assert isinstance(details.get("explanation"), str) and details["explanation"]
    assert "verify" in details["explanation"]


def test_get_explainer_unconfigured_returns_mock(monkeypatch):
    from orbitlab_backend import config as cfg
    for var in ("EXTRACTOR_BASE_URL", "EXTRACTOR_API_KEY", "EXTRACTOR_MODEL"):
        monkeypatch.delenv(var, raising=False)
    cfg.reset_settings()
    try:
        assert isinstance(get_explainer(), MockExplainer)
    finally:
        cfg.reset_settings()
