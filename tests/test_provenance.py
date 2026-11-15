"""Provenance fields on pipeline results (Step 2 of the UI audit).

fromCache/elapsedSeconds mark live vs cached runs; run_job stamps jobId.
No network, no GMAT (stub extractor/interpreter/GMAT runner like
test_pipeline.py and test_long_runs.py).
"""
import json

import pytest

from orbitlab_backend.orchestrator.pipeline import Pipeline
from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.clients.explainer_client import MockExplainer


def _stubbed_pipeline(monkeypatch=None):
    extracted = {"centralBody": "Earth", "dryMassKg": 500,
                 "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"},
                 "duration": {"value": 2, "unit": "hours"}, "integrator": "RungeKutta89",
                 "inclinationDeg": 28.5, "raanDeg": 0, "argumentOfPeriapsisDeg": 0,
                 "trueAnomalyDeg": 0, "forces": None, "maneuvers": [],
                 "cartesian": None}
    ext = FrontStepExtractor()
    ext._fallback_extract = lambda t: extracted
    correct = {"version": "1.0", "experimentName": "TestExp",
               "spacecraft": {"name": "SC_TestExp", "dryMassKg": 500},
               "centralBody": "Earth",
               "initialOrbit": {"type": "Keplerian", "coordinateSystem": "EarthMJ2000Eq",
                                "elements": {"semiMajorAxisKm": 6778.136, "eccentricity": 0,
                                             "inclinationDeg": 28.5, "raanDeg": 0,
                                             "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}},
               "forceModel": {"gravityDegree": 4, "gravityOrder": 4,
                              "pointMasses": ["Luna", "Sun"],
                              "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
                              "solarRadiationPressure": True},
               "propagation": {"integrator": "RungeKutta89",
                               "stopCondition": {"type": "ElapsedHours", "value": 2},
                               "stepSizeSecs": 60},
               "maneuvers": []}
    interp = MockInterpreterClient(canned_json=json.dumps(correct))
    return Pipeline(extractor=ext, interpreter=interp,
                    explainer=MockExplainer(), gmat_runner=None)


@pytest.mark.asyncio
async def test_live_run_marks_from_cache_false_with_wall_time():
    pipeline = _stubbed_pipeline()
    res = await pipeline.run("500 kg satellite around Earth, 400 km circular, for 2 hours")
    assert res["status"] == "success"
    assert res["fromCache"] is False
    assert isinstance(res["elapsedSeconds"], float) and res["elapsedSeconds"] >= 0
    assert "jobId" not in res


@pytest.mark.asyncio
async def test_second_identical_run_comes_from_cache():
    pipeline = _stubbed_pipeline()
    text = "500 kg satellite around Earth, 400 km circular, for 2 hours"
    first = await pipeline.run(text)
    second = await pipeline.run(text)
    assert second["status"] == "success"
    assert second["fromCache"] is True
    assert second["elapsedSeconds"] == first["elapsedSeconds"]
    assert second["prompt"] == first["prompt"]


@pytest.mark.asyncio
async def test_run_job_stamps_job_id():
    from orbitlab_backend.api import app as app_module
    from orbitlab_backend.api.store import JobStore
    orig_pipeline, orig_store = app_module.Pipeline, app_module.store

    class FakePipeline:
        def __init__(self, *a, **k):
            pass

        async def run(self, text, event_cb=None):
            return {"status": "success",
                    "experiment": {"centralBody": "Earth"},
                    "fromCache": False, "elapsedSeconds": 1.5,
                    "prompt": text}

    try:
        app_module.Pipeline = FakePipeline
        app_module.store = JobStore()
        job = app_module.store.get(app_module.store.create("hello earth").id)
        await app_module.run_job(job.id, "hello earth")
        got = app_module.store.get(job.id)
        assert got.status == "success"
        assert got.result["jobId"] == job.id
        assert got.result["fromCache"] is False
        assert got.result["elapsedSeconds"] == 1.5
    finally:
        app_module.Pipeline = orig_pipeline
        app_module.store = orig_store
