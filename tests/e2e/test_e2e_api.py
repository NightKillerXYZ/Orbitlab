"""E2E: API behaviour through the real routes (404, 422, store bound, WS, concurrency)."""
import pytest

from fastapi.testclient import TestClient

import orbitlab_backend.api.app as app_module
from orbitlab_backend.api.store import JobStore
from tests.e2e.helpers import (
    assert_explained, canned_for, client_for, extracted_for,
    run_text, sent_kepler,
)


def test_unknown_experiment_id_404():
    app_module.store = JobStore()
    client = TestClient(app_module.create_app())
    r = client.get("/api/experiments/does-not-exist")
    assert r.status_code == 404


def test_empty_text_422():
    app_module.store = JobStore()
    client = TestClient(app_module.create_app())
    assert client.post("/api/experiments", json={"text": ""}).status_code == 422
    assert client.post("/api/experiments", json={"text": "   "}).status_code == 422


def test_job_store_bounded():
    from orbitlab_backend.api import store as storemod
    st = storemod.JobStore()
    for _ in range(storemod.MAX_JOBS + 25):
        j = st.create("x")
        st.update(j.id, status="success", result={})
    assert len(st.jobs) <= storemod.MAX_JOBS
    running = [j for j in st.jobs.values() if j.status not in ("success", "failed")]
    assert running == []


def test_websocket_late_join_gets_final():
    sent = sent_kepler("E2ELate", "Earth", 6778.136, 0.0, 0.0, 500, 2, "hours", "ElapsedHours")
    bad = canned_for(sent_kepler("E2ELate", "Earth", 7000.0, 0.0, 0.0, 500, 2, "hours", "ElapsedHours"),
                     "EarthMJ2000Eq")
    routes = [(sent["experimentName"], bad)]
    client = client_for(routes, {"CASE-LATE": extracted_for(sent)})
    job = run_text(client, "CASE-LATE")
    assert job["status"] == "failed"
    with client.websocket_connect("/ws/experiments/%s" % job["id"]) as ws:
        events = []
        for _ in range(60):
            try:
                m = ws.receive_json()
            except Exception:
                break
            events.append(m)
            if m.get("type") == "final":
                break
    assert events, "late joiner got nothing"
    assert events[-1]["type"] == "final"
    assert_explained(events[-1]["error"], stage="verify", code="interpreter_mismatch")


def test_two_runs_do_not_mix_results():
    sent_a = sent_kepler("E2EA", "Earth", 6778.136, 0.0, 0.0, 500, 2, "hours", "ElapsedHours")
    sent_b = sent_kepler("E2EB", "Earth", 7000.0, 0.0, 0.0, 500, 2, "hours", "ElapsedHours")
    routes = [(sent_a["experimentName"], canned_for(sent_a, "EarthMJ2000Eq")),
              (sent_b["experimentName"], canned_for(sent_b, "EarthMJ2000Eq"))]
    extracted = {"TEXT-A": extracted_for(sent_a), "TEXT-B": extracted_for(sent_b)}
    client = client_for(routes, extracted)
    ja = client.post("/api/experiments", json={"text": "TEXT-A"}).json()["id"]
    jb = client.post("/api/experiments", json={"text": "TEXT-B"}).json()["id"]
    from tests.e2e.helpers import wait_for_job
    ra = wait_for_job(client, ja)
    rb = wait_for_job(client, jb)
    assert ra["status"] == "success" and rb["status"] == "success"
    assert ra["result"]["experiment"]["experimentName"] == "E2EA"
    assert rb["result"]["experiment"]["experimentName"] == "E2EB"
    first = ra["result"]["experiment"]["initialOrbit"]["elements"]["semiMajorAxisKm"]
    second = rb["result"]["experiment"]["initialOrbit"]["elements"]["semiMajorAxisKm"]
    assert (first, second) == (6778.136, 7000.0)
