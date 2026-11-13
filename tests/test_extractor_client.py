import pytest
from httpx import AsyncClient, MockTransport, Response, Request, TimeoutException
import orbitlab_backend.clients.extractor_client as ec
from orbitlab_backend.clients.extractor_client import OpenAIExtractor, extract_json_object


def _client(monkeypatch, handler, **kw):
    real = ec.httpx.AsyncClient

    class PatchedClient(AsyncClient):
        def __init__(self, *a, **k):
            super().__init__(transport=MockTransport(handler), timeout=k.get("timeout"))

    monkeypatch.setattr(ec.httpx, "AsyncClient", PatchedClient)
    client = OpenAIExtractor(base_url="http://fake/extractor", api_key="k",
                             model="m", **kw)
    return client, real


def _good():
    return {"centralBody": "Earth", "dryMassKg": 500,
            "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"},
            "duration": {"value": 1, "unit": "days"}}


@pytest.mark.asyncio
async def test_success(monkeypatch):
    import json as _j

    async def handler(request: Request):
        return Response(200, json={"choices": [{"message": {"content": _j.dumps(_good())}}]})

    client, real = _client(monkeypatch, handler)
    try:
        out = await client.extract("anything")
        assert out["centralBody"] == "Earth"
        assert out["dryMassKg"] == 500
    finally:
        ec.httpx.AsyncClient = real


@pytest.mark.asyncio
async def test_http_400_raises(monkeypatch):
    calls = [0]

    async def handler(request: Request):
        calls[0] += 1
        return Response(400, json={"error": "bad request"})

    client, real = _client(monkeypatch, handler)
    try:
        with pytest.raises(Exception):
            await client.extract("anything")
        assert calls[0] == 1
    finally:
        ec.httpx.AsyncClient = real


@pytest.mark.asyncio
async def test_http_401_raises(monkeypatch):
    calls = [0]

    async def handler(request: Request):
        calls[0] += 1
        return Response(401, json={"error": "unauthorized"})

    client, real = _client(monkeypatch, handler)
    try:
        with pytest.raises(Exception):
            await client.extract("anything")
        assert calls[0] == 1
    finally:
        ec.httpx.AsyncClient = real


@pytest.mark.asyncio
async def test_timeout_raises(monkeypatch):
    calls = [0]

    async def handler(request: Request):
        calls[0] += 1
        raise TimeoutException("simulated timeout")

    client, real = _client(monkeypatch, handler)
    try:
        with pytest.raises(Exception):
            await client.extract("anything")
        assert calls[0] == 2
    finally:
        ec.httpx.AsyncClient = real


@pytest.mark.asyncio
async def test_fenced_reply_parsed(monkeypatch):
    import json as _j

    async def handler(request: Request):
        return Response(200, json={"choices": [{"message": {"content": "```json\n" + _j.dumps(_good()) + "\n```"}}]})

    client, real = _client(monkeypatch, handler)
    try:
        assert (await client.extract("anything"))["dryMassKg"] == 500
    finally:
        ec.httpx.AsyncClient = real


@pytest.mark.asyncio
async def test_text_around_json_parsed(monkeypatch):
    import json as _j
    body = "Here is the result: " + _j.dumps(_good()) + " Let me know if you need more."

    async def handler(request: Request):
        return Response(200, json={"choices": [{"message": {"content": body}}]})

    client, real = _client(monkeypatch, handler)
    try:
        assert (await client.extract("anything"))["centralBody"] == "Earth"
    finally:
        ec.httpx.AsyncClient = real


def test_null_fields_survive_parsing():
    out = extract_json_object('{"centralBody": null, "dryMassKg": null, "orbit": null, "duration": null}')
    assert out == {"centralBody": None, "dryMassKg": None, "orbit": None, "duration": None}


def test_null_duration_needs_clarification():
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    ext = FrontStepExtractor()
    res = ext.deterministic_convert({"centralBody": "Earth", "dryMassKg": 500,
                                     "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"},
                                     "duration": {"value": None, "unit": "days"}},
                                    "test")
    assert res.status == "needs_clarification"
    assert "duration" in res.missing


def test_null_orbit_value_needs_clarification():
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    ext = FrontStepExtractor()
    res = ext.deterministic_convert({"centralBody": "Earth", "dryMassKg": 500,
                                     "orbit": {"kind": "circularAltitudeKm", "value": None, "unit": "km"},
                                     "duration": {"value": 1, "unit": "days"}},
                                    "test")
    assert res.status == "needs_clarification"
    assert "orbit" in res.missing


def test_string_numbers_accepted():
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    ext = FrontStepExtractor()
    res = ext.deterministic_convert({"centralBody": "Earth", "dryMassKg": "500",
                                     "orbit": {"kind": "circularAltitudeKm", "value": "400", "unit": "km"},
                                     "duration": {"value": "2", "unit": "hours"}},
                                    "test")
    assert res.status == "ok"
    assert res.data["semiMajorAxisKm"] == 6778.1363


def test_json_mode_default_is_prompt(monkeypatch):
    import asyncio
    import json as _j
    seen = {}

    async def handler(request: Request):
        seen["body"] = _j.loads(request.content.decode())
        return Response(200, json={"choices": [{"message": {"content": _j.dumps(_good())}}]})

    client, real = _client(monkeypatch, handler)
    try:
        asyncio.run(_consume(client))
        assert "response_format" not in seen["body"]
    finally:
        ec.httpx.AsyncClient = real


def test_json_object_mode_sends_response_format(monkeypatch):
    import json as _j
    seen = {}

    async def handler(request: Request):
        seen["body"] = _j.loads(request.content.decode())
        return Response(200, json={"choices": [{"message": {"content": _j.dumps(_good())}}]})

    client, real = _client(monkeypatch, handler, json_mode="json_object")
    import asyncio
    try:
        asyncio.run(_consume(client))
        assert seen["body"].get("response_format") == {"type": "json_object"}
    finally:
        ec.httpx.AsyncClient = real


async def _consume(client):
    await client.extract("anything")
