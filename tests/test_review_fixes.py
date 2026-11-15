import asyncio, json, os
import pytest

def _patched_client(monkeypatch, handler, timeout_s=2):
    from httpx import AsyncClient, MockTransport
    import orbitlab_backend.clients.interpreter_client as ic
    from orbitlab_backend.clients.interpreter_client import HttpInterpreterClient
    class PatchedClient(AsyncClient):
        def __init__(self, *a, **kw):
            super().__init__(transport=MockTransport(handler), timeout=kw.get("timeout"))
    monkeypatch.setattr(ic.httpx, "AsyncClient", PatchedClient)
    return HttpInterpreterClient(model_url="http://fake/interpreter", model_key="k", timeout_s=timeout_s)

@pytest.mark.asyncio
async def test_no_retry_on_400(monkeypatch):
    from httpx import Response, Request
    calls = [0]
    async def handler(request: Request):
        calls[0] += 1
        return Response(400, json={"error": "bad request"})
    client = _patched_client(monkeypatch, handler)
    with pytest.raises(Exception):
        await client.interpret_prompt("hi")
    assert calls[0] == 1

@pytest.mark.asyncio
async def test_no_retry_on_invalid_json_string(monkeypatch):
    from httpx import Response, Request
    calls = [0]
    async def handler(request: Request):
        calls[0] += 1
        return Response(200, json={"output": "not json {{{"})
    client = _patched_client(monkeypatch, handler)
    with pytest.raises(Exception):
        await client.interpret_prompt("hi")
    assert calls[0] == 1

def test_cors_default_is_not_star():
    from orbitlab_backend.config import Settings
    s = Settings()
    origins = s.cors_origins_list()
    assert origins != ["*"] and "*" not in origins
    assert any("localhost" in o or "127.0.0.1" in o for o in origins)

def test_cors_env_override(monkeypatch):
    monkeypatch.setenv("ORBITLAB_CORS_ORIGINS", "https://example.com")
    from orbitlab_backend.config import Settings
    assert Settings().cors_origins_list() == ["https://example.com"]

@pytest.mark.asyncio
async def test_background_task_failure_marks_job_failed():
    import orbitlab_backend.api.app as app_module
    from orbitlab_backend.api.app import run_job
    from orbitlab_backend.api.store import JobStore
    app_module.store = JobStore()
    class Boom:
        def __init__(self, *a, **k): pass
        async def run(self, text, event_cb=None):
            raise RuntimeError("boom")
    app_module.Pipeline = Boom
    try:
        job = app_module.store.create("x")
        await run_job(job.id, "x")
        got = app_module.store.get(job.id)
        assert got.status == "failed"
        assert got.error and got.error.get("code") == "internal_error"
        assert "boom" not in got.error["message"]
        assert "Traceback" not in got.error.get("message", "")
        assert any(e.get("type") == "final" for e in got.events)
    finally:
        import importlib
        importlib.reload(app_module)

def test_websocket_late_and_double_subscriber():
    from orbitlab_backend.api.store import JobStore
    st = JobStore()
    job = st.create("x")
    st.add_event(job.id, {"type": "stage_completed", "stage": "extract"})
    st.update(job.id, status="success", result={"ok": True})
    st.add_event(job.id, {"type": "final", "result": {"ok": True}})
    q1 = st.subscribe(job.id)
    q2 = st.subscribe(job.id)
    got1 = [q1.get_nowait() for _ in range(q1.qsize())]
    got2 = [q2.get_nowait() for _ in range(q2.qsize())]
    assert len(got1) == 3 and len(got2) == 3
    assert got1[-1]["type"] == "final" and got2[-1]["type"] == "final"

def _base_sent():
    return {"experimentName": "E", "spacecraftName": "E", "centralBody": "Earth", "dryMassKg": 500, "semiMajorAxisKm": 6778.136, "eccentricity": 0.01, "inclinationDeg": 28.5, "raanDeg": 10, "argumentOfPeriapsisDeg": 20, "trueAnomalyDeg": 30, "integrator": "RungeKutta89", "durationValue": 2, "durationUnit": "hours", "stopConditionType": "ElapsedHours", "forces": None, "maneuvers": []}

def _base_returned():
    return {"experimentName": "E", "spacecraft": {"name": "SC_E", "dryMassKg": 500}, "centralBody": "Earth", "initialOrbit": {"type": "Keplerian", "elements": {"semiMajorAxisKm": 6778.136, "eccentricity": 0.01, "inclinationDeg": 28.5, "raanDeg": 10, "argumentOfPeriapsisDeg": 20, "trueAnomalyDeg": 30}}, "propagation": {"integrator": "RungeKutta89", "stopCondition": {"type": "ElapsedHours", "value": 2}}, "forceModel": {"gravityDegree": 4, "gravityOrder": 4}, "maneuvers": []}

def test_verify_compares_every_physics_field():
    from orbitlab_backend.frontstep.verify import verify_experiment, apply_frontstep_names
    import copy
    sent = _base_sent()
    patches = [
        ("centralBody", {"centralBody": "Mars"}, "centralBody"),
        ("dryMassKg", {"dryMassKg": 501}, "dryMassKg"),
        ("sma", {"sma": 7000}, "semiMajorAxisKm"),
        ("ecc", {"ecc": 0.5}, "eccentricity"),
        ("inc", {"inc": 99}, "inclinationDeg"),
        ("raan", {"raanDeg": 77}, "raanDeg"),
        ("aop", {"aop": 71}, "argumentOfPeriapsisDeg"),
        ("ta", {"ta": 45}, "trueAnomalyDeg"),
        ("integrator", {"integrator": "PrinceDormand78"}, "integrator"),
        ("stopType", {"stopType": "ElapsedDays"}, "stopCondition.type"),
        ("stopVal", {"stopVal": 5}, "stopCondition.value"),
        ("maneuver", {"maneuver": True}, "maneuvers.count"),
    ]
    for label, patch, field in patches:
        ret = copy.deepcopy(_base_returned())
        if "centralBody" in patch:
            ret["centralBody"] = patch["centralBody"]
        if "dryMassKg" in patch:
            ret["spacecraft"]["dryMassKg"] = patch["dryMassKg"]
        els = ret["initialOrbit"]["elements"]
        if "sma" in patch:
            els["semiMajorAxisKm"] = patch["sma"]
        if "ecc" in patch:
            els["eccentricity"] = patch["ecc"]
        if "inc" in patch:
            els["inclinationDeg"] = patch["inc"]
        if "raanDeg" in patch:
            els["raanDeg"] = patch["raanDeg"]
        if "aop" in patch:
            els["argumentOfPeriapsisDeg"] = patch["aop"]
        if "ta" in patch:
            els["trueAnomalyDeg"] = patch["ta"]
        if "integrator" in patch:
            ret["propagation"]["integrator"] = patch["integrator"]
        if "stopType" in patch:
            ret["propagation"]["stopCondition"]["type"] = patch["stopType"]
        if "stopVal" in patch:
            ret["propagation"]["stopCondition"]["value"] = patch["stopVal"]
        if "maneuver" in patch:
            ret["maneuvers"] = [{"id": "M1", "type": "ImpulsiveBurn"}]
        ret, _ = apply_frontstep_names(sent, ret)
        ms = verify_experiment(sent, ret)
        assert any(m["field"] == field for m in ms), label

def test_store_bounded():
    from orbitlab_backend.api import store as storemod
    st = storemod.JobStore()
    for _ in range(storemod.MAX_JOBS + 50):
        j = st.create("x")
        st.update(j.id, status="success", result={})
    assert len(st.jobs) <= storemod.MAX_JOBS

@pytest.mark.asyncio
async def test_failed_runs_not_cached_and_cache_bounded():
    import json
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
    from orbitlab_backend.clients.explainer_client import MockExplainer
    from orbitlab_backend.orchestrator import pipeline as pipemod
    from orbitlab_backend.orchestrator.pipeline import Pipeline
    extracted = {"centralBody": "Earth", "dryMassKg": 500, "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"}, "duration": {"value": 2, "unit": "hours"}, "integrator": "RungeKutta89", "forces": None, "maneuvers": [], "cartesian": None, "experimentName": "T", "spacecraftName": "T"}
    bad = {"version": "1.0", "experimentName": "T", "spacecraft": {"name": "SC_T", "dryMassKg": 500}, "centralBody": "Earth", "initialOrbit": {"type": "Keplerian", "coordinateSystem": "EarthMJ2000Eq", "elements": {"semiMajorAxisKm": 7000, "eccentricity": 0, "inclinationDeg": 0, "raanDeg": 0, "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}}, "forceModel": {"gravityDegree": 4, "gravityOrder": 4, "pointMasses": ["Luna", "Sun"], "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"}, "solarRadiationPressure": True}, "propagation": {"integrator": "RungeKutta89", "stopCondition": {"type": "ElapsedHours", "value": 2}, "stepSizeSecs": 60}, "maneuvers": []}
    ext = FrontStepExtractor()
    ext._fallback_extract = lambda t: extracted
    pipe = Pipeline(extractor=ext, interpreter=MockInterpreterClient(canned_json=json.dumps(bad)), explainer=MockExplainer())
    for _ in range(2):
        with pytest.raises(Exception):
            await pipe.run("dummy")
    assert len(pipe.cache) == 0
    for i in range(pipemod.MAX_CACHE_ENTRIES + 50):
        pipe.cache[f"k{i}"] = {"status": "success"}
    good = dict(bad)
    good["initialOrbit"] = {"type": "Keplerian", "coordinateSystem": "EarthMJ2000Eq", "elements": {"semiMajorAxisKm": 6778.136, "eccentricity": 0, "inclinationDeg": 0, "raanDeg": 0, "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}}
    pipe2 = Pipeline(extractor=ext, interpreter=MockInterpreterClient(canned_json=json.dumps(good)), explainer=MockExplainer(), cache=pipe.cache)
    await pipe2.run("dummy")
    assert len(pipe2.cache) <= pipemod.MAX_CACHE_ENTRIES
