"""Script route tests: kept compiled script served read-only per job."""
import time

import pytest
from fastapi.testclient import TestClient

from orbitlab_backend import config as cfg
from orbitlab_backend.api import app as app_module
from orbitlab_backend.api.store import JobStore
from orbitlab_backend.orchestrator.pipeline import Pipeline as RealPipeline

TEXT = "Put a 500 kg satellite in a circular orbit at 400 km altitude around Earth for 1 day."


@pytest.fixture()
def demo_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITLAB_DEMO_MODE", "true")
    monkeypatch.setenv("ORBITLAB_RUN_DIR", str(tmp_path))
    cfg.reset_settings()
    # Other e2e modules rebind app_module.Pipeline globally; pin the real one.
    orig_pipeline, orig_store = app_module.Pipeline, app_module.store
    app_module.Pipeline = RealPipeline
    app_module.store = JobStore()
    try:
        yield TestClient(app_module.create_app())
    finally:
        app_module.Pipeline = orig_pipeline
        app_module.store = orig_store
        cfg.reset_settings()


def _run(client, text, timeout_s=60):
    jid = client.post("/api/experiments", json={"text": text}).json()["id"]
    job = None
    for _ in range(int(timeout_s * 2)):
        job = client.get(f"/api/experiments/{jid}").json()
        if job["status"] in ("success", "failed"):
            break
        time.sleep(0.5)
    return job


def test_script_served_exact_and_flagged(demo_client):
    job = _run(demo_client, TEXT)
    assert job["status"] == "success", job
    assert job["result"].get("hasScript") is True
    jid = job["id"]
    r = demo_client.get(f"/api/experiments/{jid}/script")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    # exact text: matches an independent recompile of the served experiment
    from orbitlab_core.ast.models import OrbitLabExperiment
    from orbitlab_core.compiler.generator import GmatScriptCompiler
    assert r.text, "empty script"
    exp = OrbitLabExperiment.model_validate(job["result"]["experiment"])
    assert r.text == GmatScriptCompiler().compile_to_string(exp)


def test_script_404_unknown_id(demo_client):
    assert demo_client.get("/api/experiments/no-such-job/script").status_code == 404
    assert demo_client.get("/api/experiments/../x/script").status_code == 404
    assert demo_client.get("/api/experiments/./script").status_code == 404


def test_script_404_when_missing(demo_client):
    job = _run(demo_client, "hello")
    assert job["status"] == "failed", job
    assert demo_client.get(f"/api/experiments/{job['id']}/script").status_code == 404
