from fastapi.testclient import TestClient
from orbitlab_backend.api.app import create_app


def test_root_serves_ui():
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200
    assert "OrbitLab" in r.text


def test_static_live_page_and_adapter():
    client = TestClient(create_app())
    page = client.get("/orbitlab-live.html")
    assert page.status_code == 200
    assert "ui_adapter.js" in page.text
    js = client.get("/ui_adapter.js")
    assert js.status_code == 200
    assert "OrbitLabAdapter" in js.text
    assert "localhost:8000" not in js.text or "LOCALHOST_FALLBACK" in js.text


def test_health_still_ok_with_static_mounted():
    client = TestClient(create_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
