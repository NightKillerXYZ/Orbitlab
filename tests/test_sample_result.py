from fastapi.testclient import TestClient

from orbitlab_backend.api.app import create_app


def test_main_pages_still_200():
    c = TestClient(create_app())
    assert c.get("/").status_code == 200
    r = c.get("/main", follow_redirects=False)
    assert r.status_code in (200, 301, 302, 303, 307)


def test_sample_result_serves_fixture_only():
    c = TestClient(create_app())
    r = c.get("/sample-result")
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"]
    body = r.json()
    assert body["status"] == "success"
    assert body["result"]["experiment"]["centralBody"] == "Earth"
    assert body["result"]["experiment"]["initialOrbit"]["elements"]["semiMajorAxisKm"] == 6778.136
    assert len(body["result"]["trajectory"]["points"]) > 1000
