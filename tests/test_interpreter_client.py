import pytest, json, asyncio
from fastapi.testclient import TestClient
from tests.fake_interpreter import app as fake_app, CORRECT_EXPERIMENT
from orbitlab_backend.clients.interpreter_client import HttpInterpreterClient
import httpx
from httpx import AsyncClient, Response, Request, MockTransport

# Test via direct HttpInterpreterClient with MockTransport


def _choices(content):
    return {"choices": [{"message": {"content": content}}]}


def _patched_client(monkeypatch, handler, timeout_s=2):
    import orbitlab_backend.clients.interpreter_client as ic
    real = ic.httpx.AsyncClient

    class PatchedClient(AsyncClient):
        def __init__(self, *a, **kw):
            super().__init__(transport=MockTransport(handler), timeout=kw.get("timeout"))

    monkeypatch.setattr(ic.httpx, "AsyncClient", PatchedClient)
    client = HttpInterpreterClient(model_url="http://fake/interpreter", model_key="test", timeout_s=timeout_s)
    return client, real


@pytest.mark.asyncio
async def test_correct_experiment(monkeypatch):
    async def handler(request: Request):
        return Response(200, json=_choices(CORRECT_EXPERIMENT))
    client, _ = _patched_client(monkeypatch, handler)
    out = await client.interpret_prompt("hello")
    assert out["experimentName"] == "FakeExp"


@pytest.mark.asyncio
async def test_handles_json_string_output(monkeypatch):
    async def handler(request: Request):
        return Response(200, json=_choices(json.dumps(CORRECT_EXPERIMENT)))
    client, _ = _patched_client(monkeypatch, handler)
    out = await client.interpret_prompt("hello")
    assert out["experimentName"] == "FakeExp"


@pytest.mark.asyncio
async def test_openai_request_shape(monkeypatch):
    seen = {}

    async def handler(request: Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content.decode())
        return Response(200, json=_choices(CORRECT_EXPERIMENT))

    client, _ = _patched_client(monkeypatch, handler)
    await client.interpret_prompt("hello")
    assert seen["url"] == "http://fake/interpreter/v1/chat/completions"
    assert seen["auth"] and seen["auth"].startswith("Bearer ")
    assert "test" in seen["auth"]
    body = seen["body"]
    assert isinstance(body.get("model"), str) and body["model"]
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user"]
    assert body["messages"][1]["content"] == "hello"
    assert body["messages"][0]["content"]


@pytest.mark.asyncio
async def test_system_prompt_is_training_text(monkeypatch):
    from orbitlab_backend.clients.interpreter_client import INTERPRETER_SYSTEM_PROMPT
    seen = {}

    async def handler(request: Request):
        import json as _j
        seen["body"] = _j.loads(request.content.decode())
        from tests.fake_interpreter import CORRECT_EXPERIMENT
        return Response(200, json={"choices": [{"message": {"content": _j.dumps(CORRECT_EXPERIMENT)}}]})

    client, _ = _patched_client(monkeypatch, handler)
    await client.interpret_prompt("hello")
    assert seen["body"]["messages"][0] == {"role": "system", "content": INTERPRETER_SYSTEM_PROMPT}
    assert INTERPRETER_SYSTEM_PROMPT.startswith("The model is an OrbitLab Experiment Interpreter.")


@pytest.mark.asyncio
async def test_fenced_json_output(monkeypatch):
    fenced = "```json\n" + json.dumps(CORRECT_EXPERIMENT) + "\n```"

    async def handler(request: Request):
        return Response(200, json=_choices(fenced))

    client, _ = _patched_client(monkeypatch, handler)
    out = await client.interpret_prompt("hello")
    assert out["experimentName"] == "FakeExp"


@pytest.mark.asyncio
async def test_missing_choices_no_retry(monkeypatch):
    calls = [0]

    async def handler(request: Request):
        calls[0] += 1
        return Response(200, json={"unexpected": "shape"})

    client, _ = _patched_client(monkeypatch, handler)
    with pytest.raises(Exception):
        await client.interpret_prompt("hello")
    assert calls[0] == 1


@pytest.mark.asyncio
async def test_retry_on_503_then_success(monkeypatch):
    call = [0]

    async def handler(request: Request):
        call[0] += 1
        if call[0] == 1:
            return Response(503, json={"error": "unavailable"})
        return Response(200, json=_choices(CORRECT_EXPERIMENT))

    client, _ = _patched_client(monkeypatch, handler)
    out = await client.interpret_prompt("test")
    assert call[0] == 2
    assert out["experimentName"] == "FakeExp"


@pytest.mark.asyncio
async def test_timeout_triggers_retry_and_fails(monkeypatch):
    import httpx as httpx_mod

    async def handler(request: Request):
        raise httpx_mod.TimeoutException("timeout")

    client, _ = _patched_client(monkeypatch, handler, timeout_s=0.2)
    with pytest.raises(Exception) as exc:
        await client.interpret_prompt("hello")
    assert "timeout" in str(exc.value).lower() or "unavailable" in str(exc.value).lower()


def test_warming_event():
    async def run():
        async def handler(request: Request):
            await asyncio.sleep(10.5)
            return Response(200, json=_choices(CORRECT_EXPERIMENT))

        import orbitlab_backend.clients.interpreter_client as ic
        real = ic.httpx.AsyncClient

        class PatchedClient(AsyncClient):
            def __init__(self, *a, **kw):
                super().__init__(transport=MockTransport(handler), timeout=kw.get("timeout"))

        ic.httpx.AsyncClient = PatchedClient
        client = HttpInterpreterClient(model_url="http://fake/interpreter", model_key="test", timeout_s=12)
        warmed = []

        async def warming():
            warmed.append(True)

        try:
            out = await client.interpret_prompt("hello", warming_callback=warming)
            assert len(warmed) == 1
        finally:
            ic.httpx.AsyncClient = real
    pass

@pytest.mark.asyncio
async def test_body_contains_max_tokens(monkeypatch):
    import json as _j
    seen = {}

    async def handler(request: Request):
        seen["body"] = _j.loads(request.content.decode())
        from tests.fake_interpreter import CORRECT_EXPERIMENT
        return Response(200, json={"choices": [{"message": {"content": _j.dumps(CORRECT_EXPERIMENT)}}]})

    client, _ = _patched_client(monkeypatch, handler)
    await client.interpret_prompt("hello")
    assert seen["body"]["max_tokens"] == 1500


@pytest.mark.asyncio
async def test_truncated_output_raises_without_retry(monkeypatch):
    import json as _j
    from orbitlab_backend.clients.interpreter_client import InterpreterOutputTruncatedError
    calls = [0]

    async def handler(request: Request):
        calls[0] += 1
        return Response(200, json={"choices": [{"message": {"content": "{\"a\""}, "finish_reason": "length"}]})

    client, _ = _patched_client(monkeypatch, handler)
    with pytest.raises(InterpreterOutputTruncatedError) as exc:
        await client.interpret_prompt("hello")
    assert "cut off" in str(exc.value)
    assert calls[0] == 1
