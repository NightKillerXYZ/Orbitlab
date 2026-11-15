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
