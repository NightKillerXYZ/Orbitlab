"""Step 4 tests: extractor cold-start retry, extractor_unavailable, fallback rules."""
import json
import logging
import time

import pytest

from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.orchestrator.pipeline import Pipeline
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.clients.explainer_client import MockExplainer
from orbitlab_backend.clients.extractor_client import OpenAIExtractor
from orbitlab_backend.orchestrator.errors import ExtractorUnavailable

READABLE = "500 kg satellite around Earth, 400 km circular, for 2 days"
UNREADABLE = "blorple wibble zorp"

GOOD_JSON = json.dumps({
    "centralBody": "Earth", "dryMassKg": 500,
    "orbit": {"quantity": "altitude", "valueKm": 400, "eccentricity": None},
    "inclinationDeg": None, "raanDeg": None, "argumentOfPeriapsisDeg": None,
    "trueAnomalyDeg": None,
    "duration": {"value": 2, "unit": "days"}, "maneuvers": []})


def _patch(monkeypatch, handler):
    from httpx import AsyncClient, MockTransport
    import orbitlab_backend.clients.extractor_client as ec

    class PatchedClient(AsyncClient):
        def __init__(self, *a, **kw):
            super().__init__(transport=MockTransport(handler), timeout=kw.get("timeout"))

    monkeypatch.setattr(ec.httpx, "AsyncClient", PatchedClient)


def _client():
    return OpenAIExtractor(base_url="http://fake/extractor", api_key="k", model="m")


async def _aprocess(client, text):
    return await FrontStepExtractor(extractor_client=client).process(text)


@pytest.mark.asyncio
async def test_timeout_then_success_two_attempts(monkeypatch):
    import httpx
    from httpx import Response
    calls = []

    async def handler(request):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("cold model")
        return Response(200, json={"choices": [{"message": {"content": GOOD_JSON}}]})

    _patch(monkeypatch, handler)
    res = await _aprocess(_client(), READABLE)
    assert res.status == "ok"
    assert res.data["semiMajorAxisKm"] == pytest.approx(6778.136, abs=1e-3)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_timeout_twice_unreadable_raises_unavailable(monkeypatch, caplog):
    import httpx
    calls = []

    async def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("cold model")

    _patch(monkeypatch, handler)
    with caplog.at_level(logging.WARNING, logger="orbitlab.extractor"):
        with pytest.raises(ExtractorUnavailable) as exc:
            await _aprocess(_client(), UNREADABLE)
    assert len(calls) == 2
    assert exc.value.code == "extractor_unavailable"
    assert exc.value.stage == "extract"
    assert "starting up or unreachable" in exc.value.message
    assert exc.value.details["explanation"] == exc.value.message
    assert "after retry" in caplog.text
    assert "Bearer" not in caplog.text


@pytest.mark.asyncio
async def test_timeout_twice_readable_falls_back_to_success(monkeypatch, caplog):
    import httpx
    calls = []

    async def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("cold model")

    _patch(monkeypatch, handler)
    with caplog.at_level(logging.WARNING, logger="orbitlab.extractor"):
        res = await _aprocess(_client(), READABLE)
    assert res.status == "ok"
    assert res.data["semiMajorAxisKm"] == pytest.approx(6778.136, abs=1e-3)
    assert len(calls) == 2
    assert "after retry" in caplog.text


@pytest.mark.asyncio
async def test_503_then_success(monkeypatch):
    from httpx import Response
    calls = []

    async def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return Response(503, json={"error": "warming up"})
        return Response(200, json={"choices": [{"message": {"content": GOOD_JSON}}]})

    _patch(monkeypatch, handler)
    res = await _aprocess(_client(), READABLE)
    assert res.status == "ok"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_401_single_attempt_then_unavailable(monkeypatch, caplog):
    from httpx import Response
    calls = []

    async def handler(request):
        calls.append(1)
        return Response(401, json={"error": "bad key"})

    _patch(monkeypatch, handler)
    with caplog.at_level(logging.WARNING, logger="orbitlab.extractor"):
        with pytest.raises(ExtractorUnavailable):
            await _aprocess(_client(), UNREADABLE)
    assert len(calls) == 1
    assert "after retry" not in caplog.text


@pytest.mark.asyncio
async def test_no_extractor_configured_unchanged():
    res = await FrontStepExtractor().process(UNREADABLE)
    assert res.status == "needs_clarification"
    res2 = await FrontStepExtractor().process(READABLE)
    assert res2.status == "ok"


@pytest.mark.asyncio
async def test_pipeline_emits_failed_extract_with_code(monkeypatch):
    import httpx
    calls = []

    async def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("cold model")

    _patch(monkeypatch, handler)
    pipeline = Pipeline(extractor=FrontStepExtractor(extractor_client=_client()),
                        interpreter=MockInterpreterClient(), explainer=MockExplainer(),
                        gmat_runner=None)
    events = []
    with pytest.raises(ExtractorUnavailable):
        await pipeline.run(UNREADABLE, event_cb=events.append)
    failed = [e for e in events if e.type == "stage_failed" and e.stage == "extract"]
    assert len(failed) == 1
    assert "extractor_unavailable" in failed[0].message
    assert len(calls) == 2


def test_api_carries_code_and_explanation(monkeypatch):
    import httpx
    from fastapi.testclient import TestClient
    from orbitlab_backend import config as cfg
    from orbitlab_backend.api.app import create_app

    async def handler(request):
        raise httpx.ReadTimeout("cold model")

    _patch(monkeypatch, handler)
    monkeypatch.setenv("EXTRACTOR_BASE_URL", "http://fake/extractor")
    monkeypatch.setenv("EXTRACTOR_API_KEY", "k")
    monkeypatch.setenv("EXTRACTOR_MODEL", "m")
    cfg.reset_settings()
    try:
        client = TestClient(create_app())
        jid = client.post("/api/experiments", json={"text": UNREADABLE}).json()["id"]
        job = None
        for _ in range(40):
            job = client.get(f"/api/experiments/{jid}").json()
            if job["status"] in ("success", "failed"):
                break
            time.sleep(0.5)
        assert job["status"] == "failed", job
        err = job["error"]
        assert err["code"] == "extractor_unavailable"
        assert err["stage"] == "extract"
        assert "starting up or unreachable" in err["message"]
        assert "starting up or unreachable" in (err.get("explanation") or "")
    finally:
        cfg.reset_settings()
