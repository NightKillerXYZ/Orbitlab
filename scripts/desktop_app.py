"""OrbitLab desktop launcher: backend + Edge WebView2 window, no browser.

Starts ``orbitlab_backend.api.app:app`` with uvicorn on a free 127.0.0.1 port
in a background thread, waits for GET /api/health, then shows the existing
Main UI (/main) in its own resizable pywebview window. When the window
closes, the server is shut down.

Never prints environment variables, keys, tokens or headers.
"""
import argparse
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request


def _repo_paths():
    """(repo root, phase4_backend), absolute, derived from this file."""
    here = os.path.abspath(os.path.dirname(__file__))
    root = os.path.abspath(os.path.join(here, os.pardir))
    return root, os.path.join(root, "phase4_backend")


def ensure_repo_on_path():
    """Insert repo root + phase4_backend at the front of sys.path.

    Makes ``python scripts/desktop_app.py`` work from any working directory
    (uvicorn's thread otherwise cannot import orbitlab_backend's
    phase3_ai_interpreter dependency). Idempotent, absolute paths only.
    """
    root, backend = _repo_paths()
    # Insert backend first so the repo root ends up at position 0.
    for entry in (backend, root):
        try:
            while entry in sys.path:
                sys.path.remove(entry)
        except Exception:
            pass
        try:
            sys.path.insert(0, entry)
        except Exception:
            pass
    return root, backend


REPO_ROOT, BACKEND_DIR = ensure_repo_on_path()

import uvicorn

APP_MODULE = "orbitlab_backend.api.app:app"
WINDOW_TITLE = "OrbitLab"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
HEALTH_TIMEOUT_S = 30.0
PYWEBVIEW_PIP = "python -m pip install pywebview"


def find_free_port(host="127.0.0.1"):
    """Return a currently free TCP port on the loopback interface only."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def fetch_health(url):
    """True when GET <url> answers HTTP 200, else False (never raises)."""
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return int(getattr(resp, "status", 0)) == 200
    except Exception:
        return False


def wait_for_health(base_url, timeout=HEALTH_TIMEOUT_S, fetch=None,
                    clock=None, pause=None):
    """Wait until GET <base_url>/api/health answers.

    Raises TimeoutError with a clear message after ``timeout`` seconds.
    ``fetch``/``clock``/``pause`` are injectable so tests need no network.
    """
    fetch = fetch or fetch_health
    clock = clock or time.monotonic
    pause = pause or (lambda s: time.sleep(s))
    health_url = base_url.rstrip("/") + "/api/health"
    deadline = clock() + timeout
    while True:
        try:
            if fetch(health_url):
                return True
        except Exception:
            pass
        if clock() >= deadline:
            raise TimeoutError(
                "OrbitLab backend did not answer GET %s within %.0f s. "
                "Check the server log above for the startup error."
                % (health_url, timeout))
        pause(0.25)


def require_webview():
    """Import pywebview or exit 1 with the exact install command."""
    try:
        import webview
        return webview
    except ImportError:
        print("pywebview is not installed. Install the desktop extra with:",
              file=sys.stderr)
        print("    " + PYWEBVIEW_PIP, file=sys.stderr)
        raise SystemExit(1)


class Backend:
    """A background uvicorn server plus its thread."""

    def __init__(self, server, thread, errors=None):
        self.server = server
        self.thread = thread
        self._errors = errors if errors is not None else []

    def last_error(self):
        """Last server-thread failure line (class + message), else ""."""
        try:
            if self._errors:
                return str(self._errors[-1])
        except Exception:
            pass
        return ""

    def stop(self):
        """Ask the server loop to exit and wait for the thread (never raises)."""
        try:
            if self.server is not None:
                self.server.should_exit = True
        except Exception:
            pass
        try:
            if self.thread is not None:
                self.thread.join(timeout=10)
        except Exception:
            pass


def start_server(port):
    """Start uvicorn bound to 127.0.0.1 only; return a Backend."""
    config = uvicorn.Config(APP_MODULE, host="127.0.0.1", port=port,
                            log_level="warning")
    server = uvicorn.Server(config)
    errors = []

    def _run():
        try:
            server.run()
        except BaseException as exc:  # noqa: BLE001 - record, then let the thread end
            try:
                errors.append("%s: %s" % (type(exc).__name__, exc))
            except Exception:
                pass

    thread = threading.Thread(target=_run, daemon=True,
                              name="orbitlab-backend")
    thread.start()
    return Backend(server, thread, errors)


def describe_wait_failure(base_url, timeout, detail):
    """Timeout message; appends the server thread's last error line if any.

    Only the exception class name and message are included (never values,
    keys, tokens or headers).
    """
    msg = ("OrbitLab backend did not answer GET %s/api/health within %.0f s. "
           "Check the server log above for the startup error."
           % (base_url.rstrip("/"), timeout))
    if detail:
        msg += " Server thread failed: %s" % detail
    return msg


def apply_flags(args):
    """Apply CLI flags to the process environment (no values are printed)."""
    if getattr(args, "demo", False):
        os.environ["ORBITLAB_DEMO_MODE"] = "true"


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run OrbitLab in its own desktop window (no browser).")
    parser.add_argument("--demo", action="store_true",
                        help="set ORBITLAB_DEMO_MODE=true before starting")
    parser.add_argument("--port", type=int, default=0,
                        help="local port to bind (default 0 = pick a free one)")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.port < 0 or args.port > 65535:
        parser.error("--port must be between 0 and 65535")
    apply_flags(args)
    webview = require_webview()
    port = args.port if args.port else find_free_port()
    base_url = "http://127.0.0.1:%d" % port
    print("Starting OrbitLab backend on %s ..." % base_url)
    backend = start_server(port)
    try:
        wait_for_health(base_url, HEALTH_TIMEOUT_S)
    except TimeoutError as exc:
        detail = backend.last_error()
        backend.stop()
        print(describe_wait_failure(base_url, HEALTH_TIMEOUT_S, detail),
              file=sys.stderr)
        return 1
    print("Backend is up. Opening the OrbitLab window ...")
    try:
        webview.create_window(WINDOW_TITLE, base_url + "/main",
                              width=WINDOW_WIDTH, height=WINDOW_HEIGHT,
                              resizable=True)
        webview.start()
    finally:
        backend.stop()
    print("OrbitLab window closed. Backend stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
