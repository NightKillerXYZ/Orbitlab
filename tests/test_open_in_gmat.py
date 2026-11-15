"""Open-in-GMAT tests: local-only launcher, fake process, no real GMAT."""
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from orbitlab_backend import config as cfg
from orbitlab_backend.api import app as app_module
from orbitlab_backend.api.app import _is_local_request, resolve_gmat_gui
from orbitlab_backend.api.store import JobStore
from orbitlab_backend.orchestrator.pipeline import Pipeline as RealPipeline

TEXT = "Put a 500 kg satellite in a circular orbit at 400 km altitude around Earth for 1 day."


class _Req:
    def __init__(self, host):
        self.client = type("C", (), {"host": host})() if host is not None else None


def test_is_local_request():
    assert _is_local_request(_Req("127.0.0.1")) is True
    assert _is_local_request(_Req("::1")) is True
    assert _is_local_request(_Req("testclient")) is False
    assert _is_local_request(_Req("192.168.1.2")) is False
    assert _is_local_request(_Req(None)) is False
    assert _is_local_request(object()) is False


def test_resolve_gmat_gui_prefers_explicit(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setenv("ORBITLAB_GMAT_GUI_PATH", str(tmp_path / "custom" / "GMAT.exe"))
    monkeypatch.setenv("GMAT_PATH", str(tmp_path / "bin" / "GmatConsole.exe"))
    cfg.reset_settings()
    try:
        assert resolve_gmat_gui() == str(tmp_path / "custom" / "GMAT.exe")
    finally:
        cfg.reset_settings()


def test_resolve_gmat_gui_defaults_to_sibling_if_present(tmp_path, monkeypatch):
    from pathlib import Path
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "GmatConsole.exe").write_text("x")
    (bindir / "GMAT.exe").write_text("x")
    monkeypatch.delenv("ORBITLAB_GMAT_GUI_PATH", raising=False)
    monkeypatch.setenv("GMAT_PATH", str(bindir / "GmatConsole.exe"))
    cfg.reset_settings()
    try:
        assert resolve_gmat_gui() == str(bindir / "GMAT.exe")
    finally:
        cfg.reset_settings()


def test_resolve_gmat_gui_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.delenv("ORBITLAB_GMAT_GUI_PATH", raising=False)
    monkeypatch.setenv("GMAT_PATH", str(tmp_path / "bin" / "GmatConsole.exe"))
    cfg.reset_settings()
    try:
        assert resolve_gmat_gui() is None
    finally:
        cfg.reset_settings()


@pytest.fixture()
def demo_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ORBITLAB_DEMO_MODE", "true")
    monkeypatch.setenv("ORBITLAB_RUN_DIR", str(tmp_path))
    cfg.reset_settings()
    orig_pipeline, orig_store = app_module.Pipeline, app_module.store
    app_module.Pipeline = RealPipeline
    app_module.store = JobStore()
    try:
        yield
    finally:
        app_module.Pipeline = orig_pipeline
        app_module.store = orig_store
        cfg.reset_settings()


def _client():
    return TestClient(app_module.create_app())


def _run(client, text, timeout_s=60):
    jid = client.post("/api/experiments", json={"text": text}).json()["id"]
    job = None
    for _ in range(int(timeout_s * 2)):
        job = client.get(f"/api/experiments/{jid}").json()
        if job["status"] in ("success", "failed"):
            break
        time.sleep(0.5)
    return job


def _local(monkeypatch):
    monkeypatch.setattr(app_module, "_is_local_request", lambda req: True)


def test_open_forbidden_when_disabled(demo_env):
    client = _client()
    r = client.post("/api/experiments/nope/open-in-gmat")
    assert r.status_code == 403


def test_open_forbidden_when_not_local(demo_env, monkeypatch):
    monkeypatch.setenv("ORBITLAB_ALLOW_OPEN_GMAT", "true")
    cfg.reset_settings()
    client = _client()
    r = client.post("/api/experiments/nope/open-in-gmat")
    assert r.status_code == 403


def test_open_unknown_id_404(demo_env, monkeypatch):
    monkeypatch.setenv("ORBITLAB_ALLOW_OPEN_GMAT", "true")
    cfg.reset_settings()
    _local(monkeypatch)

    def _boom(*a, **k):
        raise AssertionError("launcher must not run for unknown ids")

    monkeypatch.setattr(subprocess, "Popen", _boom)
    client = _client()
    r = client.post("/api/experiments/no-such-job/open-in-gmat")
    assert r.status_code == 404
    # path traversal never reaches the launcher (router rejects it)
    assert client.post("/api/experiments/../x/open-in-gmat").status_code in (404, 405)


def test_open_missing_script_404(demo_env, monkeypatch):
    monkeypatch.setenv("ORBITLAB_ALLOW_OPEN_GMAT", "true")
    cfg.reset_settings()
    _local(monkeypatch)
    client = _client()
    job = _run(client, "hello")
    assert job["status"] == "failed", job
    r = client.post(f"/api/experiments/{job['id']}/open-in-gmat")
    assert r.status_code == 404


def test_open_starts_gui_with_exact_argv_no_shell(demo_env, monkeypatch, tmp_path):
    gui = tmp_path / "GMAT.exe"
    gui.write_text("fake")
    monkeypatch.setenv("ORBITLAB_ALLOW_OPEN_GMAT", "true")
    monkeypatch.setenv("ORBITLAB_GMAT_GUI_PATH", str(gui))
    cfg.reset_settings()
    _local(monkeypatch)
    calls = []

    class FakePopen:
        def __init__(self, args, **kw):
            calls.append((list(args), dict(kw)))

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    client = _client()
    job = _run(client, TEXT)
    assert job["status"] == "success", job
    r = client.post(f"/api/experiments/{job['id']}/open-in-gmat")
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "started"}
    assert len(calls) == 1
    args, kw = calls[0]
    assert args[0] == str(gui)
    assert args[1] == "--run"
    assert args[2].endswith("experiment.script") and job["id"] in args[2]
    assert "shell" not in kw


def test_open_missing_gui_exe_500(demo_env, monkeypatch, tmp_path):
    monkeypatch.setenv("ORBITLAB_ALLOW_OPEN_GMAT", "true")
    monkeypatch.setenv("ORBITLAB_GMAT_GUI_PATH", str(tmp_path / "nope" / "GMAT.exe"))
    monkeypatch.delenv("GMAT_PATH", raising=False)
    cfg.reset_settings()
    _local(monkeypatch)
    client = _client()
    job = _run(client, TEXT)
    assert job["status"] == "success", job
    r = client.post(f"/api/experiments/{job['id']}/open-in-gmat")
    assert r.status_code == 500
    assert "GMAT.exe" in r.json()["detail"]


def test_health_reports_feature_only_when_enabled(demo_env, monkeypatch, tmp_path):
    gui = tmp_path / "GMAT.exe"
    gui.write_text("fake")
    monkeypatch.setenv("ORBITLAB_GMAT_GUI_PATH", str(gui))
    monkeypatch.delenv("ORBITLAB_ALLOW_OPEN_GMAT", raising=False)
    cfg.reset_settings()
    assert "openInGmat" not in _client().get("/api/health").json()
    monkeypatch.setenv("ORBITLAB_ALLOW_OPEN_GMAT", "true")
    cfg.reset_settings()
    assert _client().get("/api/health").json().get("openInGmat") is True
