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

    def __init__(self, server, thread):
        self.server = server
        self.thread = thread

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
    thread = threading.Thread(target=server.run, daemon=True,
                              name="orbitlab-backend")
    thread.start()
    return Backend(server, thread)


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
        backend.stop()
        print(str(exc), file=sys.stderr)
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
