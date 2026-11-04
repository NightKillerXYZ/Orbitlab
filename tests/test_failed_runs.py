import json, time
import pytest
from fastapi.testclient import TestClient
import orbitlab_backend.api.app as app_module
from orbitlab_backend.api.store import JobStore
from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.clients.explainer_client import MockExplainer
from orbitlab_backend.orchestrator.pipeline import Pipeline


def _good_exp(sma=6778.136):
    return {"version": "1.0", "experimentName": "T", "spacecraft": {"name": "SC_T", "dryMassKg": 500}, "centralBody": "Earth", "initialOrbit": {"type": "Keplerian", "coordinateSystem": "EarthMJ2000Eq", "elements": {"semiMajorAxisKm": sma, "eccentricity": 0, "inclinationDeg": 0, "raanDeg": 0, "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}}, "forceModel": {"gravityDegree": 4, "gravityOrder": 4, "pointMasses": ["Luna", "Sun"], "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"}, "solarRadiationPressure": True}, "propagation": {"integrator": "RungeKutta89", "stopCondition": {"type": "ElapsedHours", "value": 2}, "stepSizeSecs": 60}, "maneuvers": []}


def _extracted_for(exp):
    el = exp["initialOrbit"]["elements"]
    sc = exp["propagation"]["stopCondition"]
    unit = {"ElapsedHours": "hours", "ElapsedSeconds": "seconds", "ElapsedDays": "days", "OrbitPeriods": "orbits"}[sc["type"]]
    return {"experimentName": "T", "spacecraftName": "T", "centralBody": exp["centralBody"], "dryMassKg": 500, "orbit": {"kind": "semiMajorAxisKm", "value": el["semiMajorAxisKm"], "unit": "km"}, "eccentricity": el["eccentricity"], "inclinationDeg": 0, "raanDeg": 0, "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0, "duration": {"value": sc["value"], "unit": unit}, "integrator": "RungeKutta89", "forces": None, "maneuvers": [], "cartesian": None}


class _FailGmat:
    async def execute(self, req):
        raise RuntimeError("GMAT run error: bad script (simulated)")


def _run_through_routes(canned, extracted=None, gmat_runner=None):
    app_module.store = JobStore()
    canned_s = json.dumps(canned)
    s = extracted if extracted is not None else _extracted_for(canned)
    def factory(*a, **k):
        ext = FrontStepExtractor()
        ext._fallback_extract = lambda t, s=s: dict(s)
        return Pipeline(extractor=ext, interpreter=MockInterpreterClient(canned_json=canned_s), explainer=MockExplainer(), gmat_runner=gmat_runner)
    app_module.Pipeline = factory
    client = TestClient(app_module.create_app())
    try:
        jid = client.post("/api/experiments", json={"text": "dummy"}).json()["id"]
        g = None
        for _ in range(200):
            time.sleep(0.05)
            g = client.get(f"/api/experiments/{jid}").json()
            if g["status"] in ("success", "failed"):
                break
        assert g["status"] == "failed"
        with client.websocket_connect(f"/ws/experiments/{jid}") as ws:
            final = None
            for _ in range(60):
                try:
                    m = ws.receive_json()
                except Exception:
                    break
                if m.get("type") == "final":
                    final = m
                    break
        assert final is not None and "error" in final
        return g["error"], final["error"]
    finally:
        import importlib
        importlib.reload(app_module)


def _assert_explained(err, stage, code):
    assert err["stage"] == stage
    assert err["code"] == code
    assert isinstance(err["message"], str) and len(err["message"]) > 0
    assert isinstance(err["details"], dict)
    assert isinstance(err.get("explanation"), str) and len(err["explanation"]) > 0
    assert isinstance(err["details"].get("explanation"), str) and len(err["details"]["explanation"]) > 0


def test_failed_validation_run_contains_explanation():
    bad = _good_exp(sma=6448.136)
    http_err, ws_err = _run_through_routes(bad)
    for err in (http_err, ws_err):
        _assert_explained(err, "validate", "validation_failed")
        assert "errors" in err["details"] and "warnings" in err["details"]
        assert any("70.00" in e for e in err["details"]["errors"])


def test_failed_mismatch_run_contains_explanation():
    canned = _good_exp(sma=7000.0)
    extracted = _extracted_for(_good_exp(sma=6778.136))
    http_err, ws_err = _run_through_routes(canned, extracted=extracted)
    for err in (http_err, ws_err):
        _assert_explained(err, "verify", "interpreter_mismatch")
        assert "mismatches" in err["details"]


def test_failed_gmat_run_contains_explanation():
    http_err, ws_err = _run_through_routes(_good_exp(), gmat_runner=_FailGmat())
    for err in (http_err, ws_err):
        _assert_explained(err, "simulate", "gmat_run_error")
