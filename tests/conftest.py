"""Suite-wide guard against environment/config leaks between tests.

Some tests flip backend mode switches (ORBITLAB_DEMO_MODE, EXTRACTOR_*,
ORBITLAB_MODEL_*) and the backend caches them via cfg.reset_settings().
This autouse fixture scrubs those variables before every test, restores the
original values afterwards with plain os.environ operations (order-proof
against each test's own monkeypatch undo), and re-syncs the settings cache.
GMAT_PATH is deliberately untouched (e2e tests need it).
"""
import os

import pytest

_SCRUBBED = (
    "ORBITLAB_DEMO_MODE",
    "EXTRACTOR_BASE_URL",
    "EXTRACTOR_API_KEY",
    "EXTRACTOR_MODEL",
    "ORBITLAB_MODEL_URL",
    "ORBITLAB_MODEL_KEY",
)


def _reset_settings():
    try:
        from orbitlab_backend import config as cfg
    except Exception:
        return
    try:
        cfg.reset_settings()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _clean_backend_env(monkeypatch):
    saved = {key: os.environ.get(key) for key in _SCRUBBED}
    for key in _SCRUBBED:
        monkeypatch.delenv(key, raising=False)
    _reset_settings()
    yield
    # Direct os.environ writes (not monkeypatch methods): the shared
    # monkeypatch teardown runs after this finalizer and restores whatever
    # each test recorded, so restoring here converges in every order.
    for key in _SCRUBBED:
        if saved[key] is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = saved[key]
    _reset_settings()
