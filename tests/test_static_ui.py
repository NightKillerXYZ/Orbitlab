from fastapi.testclient import TestClient
from orbitlab_backend.api.app import create_app


def test_root_serves_main_ui():
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200
    assert "MISSION ASSISTANT" in r.text
    assert "ui_adapter.js" in r.text


def test_adapter_served_without_hardcoded_localhost():
    client = TestClient(create_app())
    js = client.get("/ui_adapter.js")
    assert js.status_code == 200
    assert "OrbitLabAdapter" in js.text
    assert "localhost:8000" not in js.text or "LOCALHOST_FALLBACK" in js.text


def test_health_still_ok_with_static_mounted():
    client = TestClient(create_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_main_entry_returns_200_with_adapter():
    from fastapi.testclient import TestClient
    from orbitlab_backend.api.app import create_app
    client = TestClient(create_app())
    page = client.get("/main")
    assert page.status_code == 200
    assert "ui_adapter.js" in page.text
    assert client.get("/").status_code == 200
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_main_page_redirect_and_assets():
    from fastapi.testclient import TestClient
    from orbitlab_backend.api.app import create_app
    client = TestClient(create_app())
    r = client.get("/main", follow_redirects=False)
    assert r.status_code in (301, 302, 303, 307)
    page = client.get("/OrbitlabUI%20Main/")
    assert page.status_code == 200
    assert "MISSION ASSISTANT" in page.text
    assert "ui_adapter.js" in page.text
    css = client.get("/OrbitlabUI%20Main/styles.css")
    assert css.status_code == 200
    js = client.get("/OrbitlabUI%20Main/app.js")
    assert js.status_code == 200
