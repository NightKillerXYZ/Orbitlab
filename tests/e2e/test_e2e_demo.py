"""E2E: demo mode (no keys, no language models) through the real API + GMAT."""
import os

import pytest
from fastapi.testclient import TestClient

from orbitlab_backend import config as cfg
from orbitlab_backend.api import app as app_module
from orbitlab_backend.api.store import JobStore
from tests.e2e.helpers import NEEDS_GMAT, run_text

PROMPTS = [
    # (label, text) — every scenario is at most 2 days or 5 orbits.
    ("earth-circular-1d",
     "Put a 500 kg satellite in a circular orbit at 400 km altitude around Earth for 1 day."),
    ("moon-6h",
     "Moon orbit, 100 km altitude, 500 kg, 6 hours"),
    ("mars-periapsis-2d",
     "Create a 1200 kg spacecraft around Mars with periapsis altitude 300 km and eccentricity 0.2 for 2 days."),
    ("venus-sma-5orbits",
     "800 kg spacecraft around Venus with semi-major axis 9000 km, eccentricity 0.05 and inclination 30 degrees for 5 orbits."),
    ("mercury-circular-2d",
     "300 kg probe around Mercury in a circular orbit at 500 km altitude for 2 days."),
    ("jupiter-circular-2d",
     "1200 kg spacecraft around Jupiter in a circular orbit at 2000 km altitude for 2 days."),
    ("sun-sma-2d",
     "900 kg spacecraft around the Sun with semi-major axis 7000000 km for 2 days."),
    ("earth-hohmann-2d",
     "500 kg satellite around Earth in a 7000 km circular orbit, Hohmann transfer to 9000 km at periapsis, 2 days"),
    ("mars-burn-apoapsis-2d",
     "800 kg spacecraft around Mars with periapsis altitude 300 km and eccentricity 0.2, burn at apoapsis to 5000 km, for 2 days."),
    ("earth-seconds",
     "200 kg satellite around Earth in a circular orbit at 400 km altitude for 90 seconds."),
    ("moon-exact-6h",
     "Moon orbit, 100 km altitude, 500 kg, 6 hours"),
    ("lunar-12h",
     "450 kg lunar orbiter, circular orbit at 150 km altitude, for 12 hours."),
]

CLARIFY = [
    ("satellite around Earth", {"dryMassKg", "orbit", "duration"}),
    ("500 kg satellite for 2 days", {"centralBody", "orbit"}),
    ("500 kg satellite around Earth in a 7000 km circular orbit", {"duration"}),
    ("500 kg satellite around Earth for 2 days", {"orbit"}),
]


# Function scope (not module): the suite-wide autouse env guard in
# tests/conftest.py scrubs ORBITLAB_DEMO_MODE before every test, so a
# module-scoped fixture would lose its demo setting after the first test's
# setup. Rebuilding the TestClient per test is cheap next to the pipelines.
@pytest.fixture(scope="function")
def demo_client():
    os.environ["ORBITLAB_DEMO_MODE"] = "true"
    cfg.reset_settings()
    # Other e2e modules rebind app_module.Pipeline globally; pin the real one.
    from orbitlab_backend.orchestrator.pipeline import Pipeline as RealPipeline
    orig_pipeline, orig_store = app_module.Pipeline, app_module.store
    app_module.Pipeline = RealPipeline
    app_module.store = JobStore()
    try:
        yield TestClient(app_module.create_app())
    finally:
        app_module.Pipeline = orig_pipeline
        app_module.store = orig_store
        del os.environ["ORBITLAB_DEMO_MODE"]
        cfg.reset_settings()


@NEEDS_GMAT
@pytest.mark.parametrize("label,text", PROMPTS)
def test_demo_prompt_succeeds(demo_client, label, text):
    job = run_text(demo_client, text, timeout_s=300)
    assert job["status"] == "success", (label, job)
    res = job["result"]
    assert res.get("mode") == "demo", label
    assert res.get("explanationSource") == "fallback", label
    assert res["trajectory"]["full_count"] > 0, label


@pytest.mark.parametrize("text,missing", CLARIFY)
def test_demo_incomplete_needs_clarification(demo_client, text, missing):
    job = run_text(demo_client, text, timeout_s=60)
    assert job["status"] == "failed", job
    err = job["error"]
    assert err["code"] == "needs_clarification", err
    assert set(err["details"]["missing"]) == missing, err


def test_demo_validator_violation_explained(demo_client):
    job = run_text(demo_client,
                   "500 kg satellite around Earth, 50 km circular orbit, for 2 days",
                   timeout_s=60)
    assert job["status"] == "failed", job
    err = job["error"]
    assert err["stage"] == "validate", err
    assert err["code"] == "validation_failed", err
    assert isinstance((err.get("details") or {}).get("explanation"), str)
    assert (err.get("details") or {})["explanation"], err
