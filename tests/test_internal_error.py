"""Safety net: unexpected stage exceptions become typed internal_error results.

No raw Python (tracebacks, unpack errors) may reach the user-facing result;
the full traceback goes to the server log only. No network, no GMAT.
"""
import pytest

from orbitlab_backend.orchestrator.pipeline import PipelineEvent


class _BoomPipeline:
    """Emits one stage_started event for the given stage, then explodes."""

    def __init__(self, stage):
        self._stage = stage

    async def run(self, text, event_cb=None):
        if event_cb is not None:
            await event_cb(PipelineEvent(type="stage_started", stage=self._stage,
                                          duration=0.0, message="starting"))
        raise RuntimeError("cannot unpack non-iterable NoneType object")


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["extract", "interpret", "verify", "validate",
                                   "compile", "simulate", "parse", "explain"])
async def test_unexpected_stage_error_becomes_internal_error(stage, monkeypatch):
    from orbitlab_backend.api import app as app_module
    from orbitlab_backend.api.store import JobStore
    orig_pipeline, orig_store = app_module.Pipeline, app_module.store
    boom = _BoomPipeline(stage)
    app_module.Pipeline = lambda *a, **k: boom
    app_module.store = JobStore()
    try:
        job = app_module.store.create("doomed prompt")
        await app_module.run_job(job.id, "doomed prompt")
        got = app_module.store.get(job.id)
        assert got.status == "failed"
        err = got.error
        assert err["code"] == "internal_error"
        assert err["stage"] == stage
        assert "cannot unpack" not in err["message"]
        assert "Traceback" not in err["message"]
        assert "boom" not in (err.get("message") or "")
        if stage == "extract":
            assert err["message"] == ("Something went wrong while reading your request "
                                      "(stage: extract). Please try rephrasing.")
        else:
            assert stage in err["message"]
            assert "rephrase" in err["message"]
    finally:
        app_module.Pipeline = orig_pipeline
        app_module.store = orig_store


@pytest.mark.asyncio
async def test_unexpected_error_before_any_stage_is_unknown():
    from orbitlab_backend.api import app as app_module
    from orbitlab_backend.api.store import JobStore

    class SilentBoom:
        async def run(self, text, event_cb=None):
            raise ValueError("weird failure with no events")

    orig_pipeline, orig_store = app_module.Pipeline, app_module.store
    app_module.Pipeline = SilentBoom
    app_module.store = JobStore()
    try:
        job = app_module.store.create("doomed prompt")
        await app_module.run_job(job.id, "doomed prompt")
        err = app_module.store.get(job.id).error
        assert err["code"] == "internal_error"
        assert err["stage"] == "unknown"
        assert "weird failure" not in err["message"]
    finally:
        app_module.Pipeline = orig_pipeline
        app_module.store = orig_store
