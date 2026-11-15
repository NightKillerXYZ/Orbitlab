"""Unit tests for scripts/desktop_app.py (no GUI, no external network).

Loopback-only socket use is confined to find_free_port itself; the
health-wait tests inject a fake fetch/clock so they open no sockets.
"""
import importlib.util
import pathlib
import socket
import sys
import types

import pytest


def _load():
    path = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "desktop_app.py"
    spec = importlib.util.spec_from_file_location("desktop_app", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_free_port_is_a_loopback_port():
    mod = _load()
    port = mod.find_free_port()
    assert isinstance(port, int) and 1 <= port <= 65535
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(ConnectionRefusedError):
            probe.connect(("127.0.0.1", port))
    finally:
        probe.close()


def test_wait_for_health_ok():
    mod = _load()
    seen = []

    def fetch(url):
        seen.append(url)
        return True

    assert mod.wait_for_health("http://127.0.0.1:9", timeout=5, fetch=fetch) is True
    assert seen == ["http://127.0.0.1:9/api/health"]


def test_wait_for_health_retries_then_ok():
    mod = _load()
    calls = []
    now = [100.0]

    def fetch(url):
        calls.append(url)
        if len(calls) < 3:
            raise ConnectionError("not yet")
        return True

    ok = mod.wait_for_health("http://127.0.0.1:9/base/", timeout=30, fetch=fetch,
                             clock=lambda: now[0],
                             pause=lambda s: now.__setitem__(0, now[0] + s))
    assert ok is True
    assert len(calls) == 3
    assert all(u == "http://127.0.0.1:9/base/api/health" for u in calls)


def test_wait_for_health_timeout_message():
    mod = _load()
    now = [0.0]
    with pytest.raises(TimeoutError, match=r"did not answer GET .*/api/health within 1 s"):
        mod.wait_for_health("http://127.0.0.1:9", timeout=1,
                             fetch=lambda url: False,
                             clock=lambda: now[0],
                             pause=lambda s: now.__setitem__(0, now[0] + s))


def test_missing_pywebview_message_and_exit_code(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setitem(sys.modules, "webview", None)
    with pytest.raises(SystemExit) as err:
        mod.require_webview()
    assert err.value.code == 1
    captured = capsys.readouterr()
    assert "python -m pip install pywebview" in captured.err


def test_main_exits_1_without_starting_a_server(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setitem(sys.modules, "webview", None)
    with pytest.raises(SystemExit) as err:
        mod.main([])
    assert err.value.code == 1


def test_main_rejects_out_of_range_port(capsys):
    mod = _load()
    with pytest.raises(SystemExit) as err:
        mod.main(["--port", "99999"])
    assert err.value.code == 2


def test_backend_stop_hook_never_raises():
    mod = _load()

    class Server:
        def __init__(self):
            self.should_exit = False

    class Thread:
        def __init__(self):
            self.joined = None

        def join(self, timeout=None):
            self.joined = timeout

    server, thread = Server(), Thread()
    mod.Backend(server, thread).stop()
    assert server.should_exit is True
    assert thread.joined == 10
    mod.Backend(None, None).stop()


def test_apply_flags_demo(monkeypatch):
    mod = _load()
    # NOTE: apply_flags() writes os.environ directly (untracked by monkeypatch),
    # so the SUT-set value is removed explicitly in a finally: a second
    # monkeypatch.delenv here would record "true" and resurrect it at teardown,
    # leaking ORBITLAB_DEMO_MODE into later tests (see phase4_backend/
    # test_leak_report.md).
    monkeypatch.delenv("ORBITLAB_DEMO_MODE", raising=False)
    try:
        mod.apply_flags(types.SimpleNamespace(demo=True))
        assert mod.os.environ["ORBITLAB_DEMO_MODE"] == "true"
    finally:
        mod.os.environ.pop("ORBITLAB_DEMO_MODE", None)
    mod.apply_flags(types.SimpleNamespace(demo=False))
    assert "ORBITLAB_DEMO_MODE" not in mod.os.environ

def test_repo_path_setup_puts_both_folders_first():
    import os
    mod = _load()
    repo = os.path.normcase(os.path.abspath(pathlib.Path(__file__).resolve().parent.parent))
    backend = os.path.normcase(os.path.abspath(str(pathlib.Path(__file__).resolve().parent.parent / "phase4_backend")))
    assert os.path.normcase(mod.sys.path[0]) == repo
    assert os.path.normcase(mod.sys.path[1]) == backend
    assert mod.sys.path.count(mod.sys.path[0]) == 1
    assert mod.REPO_ROOT and mod.BACKEND_DIR


def test_ps1_sets_repo_root_and_backend_on_pythonpath():
    text = (pathlib.Path(__file__).resolve().parent.parent / "scripts" / "start_desktop.ps1").read_text(encoding="utf-8")
    assert "Join-Path $repoRoot 'phase4_backend'" in text
    assert "@($repoRoot" in text
    assert "PYTHONPATH" in text


def test_thread_death_message_includes_exception_class():
    mod = _load()
    err = "ModuleNotFoundError: No module named 'phase3_ai_interpreter'"
    assert mod.Backend(None, None, [err]).last_error() == err
    assert mod.Backend(None, None).last_error() == ""
    msg = mod.describe_wait_failure("http://127.0.0.1:9", 30, err)
    assert "ModuleNotFoundError" in msg and "No module named" in msg
    assert "/api/health" in msg
    plain = mod.describe_wait_failure("http://127.0.0.1:9", 30, "")
    assert "Server thread failed" not in plain


def test_imports_work_from_unrelated_cwd(tmp_path, monkeypatch):
    import subprocess
    import sys
    _load()
    monkeypatch.delenv("PYTHONPATH", raising=False)
    scripts_dir = str(pathlib.Path(__file__).resolve().parent.parent / "scripts")
    code = ("import sys; sys.path.insert(0, %r); import desktop_app; "
            "import phase3_ai_interpreter, orbitlab_backend; print('IMPORTS_OK')" % scripts_dir)
    proc = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path),
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "IMPORTS_OK" in proc.stdout
