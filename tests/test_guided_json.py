"""ORBITLAB_GUIDED_JSON flag coverage (mocked HTTP transport, no network).

- Flag off (default): request payload is byte-identical to previous behavior
  (exactly model/messages/temperature/max_tokens, no response_format).
- Flag on: request includes the experiment JSON schema via response_format
  json_schema, generated from the live pydantic model.
- A schema-violating mock response with the flag on is still caught by
  verify/validate (SchemaError), not passed through.
"""
import asyncio
import json

import pytest


def _patched_client(monkeypatch, handler, timeout_s=2):
    from httpx import AsyncClient, MockTransport
    import orbitlab_backend.clients.interpreter_client as ic
    from orbitlab_backend.clients.interpreter_client import HttpInterpreterClient

    class PatchedClient(AsyncClient):
        def __init__(self, *a, **kw):
            super().__init__(transport=MockTransport(handler), timeout=kw.get("timeout"))

    monkeypatch.setattr(ic.httpx, "AsyncClient", PatchedClient)
    return HttpInterpreterClient(model_url="http://fake/interpreter", model_key="k",
                                 timeout_s=timeout_s)


def _good_experiment():
    return {"version": "1.0", "experimentName": "G", "spacecraft": {"name": "SC_G", "dryMassKg": 500},
            "centralBody": "Earth",
            "initialOrbit": {"type": "Keplerian", "coordinateSystem": "EarthMJ2000Eq",
                             "elements": {"semiMajorAxisKm": 6778.136, "eccentricity": 0,
                                          "inclinationDeg": 0, "raanDeg": 0,
                                          "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}},
            "forceModel": {"gravityDegree": 4, "gravityOrder": 4, "pointMasses": ["Luna", "Sun"],
                           "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
                           "solarRadiationPressure": True},
            "propagation": {"integrator": "RungeKutta89",
                            "stopCondition": {"type": "ElapsedHours", "value": 2}, "stepSizeSecs": 60},
            "maneuvers": []}


def _set_guided(monkeypatch, value):
    from orbitlab_backend import config as cfg
    if value is None:
        monkeypatch.delenv("ORBITLAB_GUIDED_JSON", raising=False)
    else:
        monkeypatch.setenv("ORBITLAB_GUIDED_JSON", value)
    cfg.reset_settings()


@pytest.mark.asyncio
async def test_flag_off_payload_byte_identical(monkeypatch):
    from httpx import Response, Request
    seen = {}

    async def handler(request: Request):
        seen["body"] = json.loads(request.content.decode())
        return Response(200, json={"choices": [{"message": {"content": json.dumps(_good_experiment())}}]})

    _set_guided(monkeypatch, None)
    client = _patched_client(monkeypatch, handler)
    try:
        out = await client.interpret_prompt("hello")
    finally:
        _set_guided(monkeypatch, None)
    assert out["experimentName"] == "G"
    assert set(seen["body"].keys()) == {"model", "messages", "temperature", "max_tokens"}
    assert "response_format" not in seen["body"]
    assert seen["body"]["model"] == "orbitlab-interpreter"
    assert seen["body"]["temperature"] == 0
    assert seen["body"]["max_tokens"] == 1500
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]


@pytest.mark.asyncio
async def test_flag_on_includes_schema(monkeypatch):
    from httpx import Response, Request
    seen = {}

    async def handler(request: Request):
        seen["body"] = json.loads(request.content.decode())
        return Response(200, json={"choices": [{"message": {"content": json.dumps(_good_experiment())}}]})

    _set_guided(monkeypatch, "true")
    client = _patched_client(monkeypatch, handler)
    try:
        out = await client.interpret_prompt("hello")
    finally:
        _set_guided(monkeypatch, None)
    assert out["experimentName"] == "G"
    rf = seen["body"]["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "orbitlab_experiment"
    assert rf["json_schema"]["strict"] is True
    schema = rf["json_schema"]["schema"]
    assert schema["title"] == "OrbitLabExperiment"
    assert "experimentName" in schema["required"]
    assert "centralBody" in schema["properties"]


def test_schema_violating_response_still_rejected(monkeypatch):
    from httpx import Response, Request
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.clients.explainer_client import MockExplainer
    from orbitlab_backend.orchestrator.pipeline import Pipeline
    from orbitlab_backend.orchestrator.errors import PipelineError

    async def handler(request: Request):
        return Response(200, json={"choices": [{"message": {"content": json.dumps(
            {"version": "1.0", "experimentName": "Bad"})}}]})

    _set_guided(monkeypatch, "true")
    client = _patched_client(monkeypatch, handler)
    extracted = {"centralBody": "Earth", "dryMassKg": 500,
                 "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"},
                 "duration": {"value": 2, "unit": "hours"}, "integrator": "RungeKutta89",
                 "forces": None, "maneuvers": [], "cartesian": None}
    ext = FrontStepExtractor()
    ext._fallback_extract = lambda t: dict(extracted)
    pipe = Pipeline(extractor=ext, interpreter=client, explainer=MockExplainer())
    try:
        with pytest.raises(PipelineError) as exc_info:
            asyncio.run(pipe.run("dummy"))
        assert exc_info.value.stage in ("verify", "validate"), exc_info.value.stage
    finally:
        _set_guided(monkeypatch, None)
