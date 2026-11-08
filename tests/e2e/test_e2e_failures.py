"""E2E: every failure stage through the real API, each with an explanation."""
import pytest

from orbitlab_backend.orchestrator.errors import InterpreterUnavailable
from tests.e2e.helpers import (
    assert_explained, canned_for, client_for, extracted_for,
    run_text, sent_kepler,
)


def _fail_case(sent_kwargs, canned_kwargs=None, text="CASE-FAIL", timeout_s=120,
               routes=None, extracted_map=None):
    sent = sent_kepler("E2EFail", **sent_kwargs)
    if canned_kwargs is None:
        canned_kwargs = {}
    canned = canned_for(sent, **canned_kwargs)
    routes = routes if routes is not None else [("CASE", canned)]
    extracted = extracted_map if extracted_map is not None else {text: extracted_for(sent)}
    client = client_for(routes, extracted)
    job = run_text(client, text, timeout_s=timeout_s)
    assert job["status"] == "failed", job
    return job["error"]


def test_validate_periapsis_below_surface():
    err = _fail_case(
        {"body": "Earth", "sma": 6448.136, "ecc": 0.0, "inc": 28.5, "mass": 500,
         "dur_val": 1, "dur_unit": "hours", "stop_type": "ElapsedHours"},
        {"coord": "EarthMJ2000Eq"})
    assert_explained(err, stage="validate", code="validation_failed")
    assert "70" in err["message"]


def test_validate_outside_soi():
    err = _fail_case(
        {"body": "Earth", "sma": 1000000.0, "ecc": 0.0, "inc": 28.5, "mass": 500,
         "dur_val": 1, "dur_unit": "hours", "stop_type": "ElapsedHours"},
        {"coord": "EarthMJ2000Eq"})
    assert_explained(err, stage="validate", code="validation_failed")


def test_validate_drag_on_non_earth():
    import copy
    sent = sent_kepler("E2EFail", "Mars", 3889.5, 0.0, 0.0, 500, 2, "hours", "ElapsedHours")
    canned = canned_for(sent, "MarsMJ2000Eq", forces={
        "gravityDegree": 4, "gravityOrder": 4, "pointMasses": ["Luna", "Sun"],
        "atmosphericDrag": {"enabled": True, "model": "JacchiaRoberts"},
        "solarRadiationPressure": True})
    routes = [("CASE", canned)]
    client = client_for(routes, {"CASE-FAIL": extracted_for(sent)})
    job = run_text(client, "CASE-FAIL")
    assert job["status"] == "failed", job
    assert_explained(job["error"], stage="validate", code="validation_failed")


def test_validate_eccentricity_over_one():
    err = _fail_case(
        {"body": "Earth", "sma": 7000.0, "ecc": 1.2, "inc": 0.0, "mass": 500,
         "dur_val": 2, "dur_unit": "hours", "stop_type": "ElapsedHours"},
        {"coord": "EarthMJ2000Eq"})
    assert_explained(err, stage="validate", code="schema_error")


def test_validate_inclination_over_180():
    err = _fail_case(
        {"body": "Earth", "sma": 6778.136, "ecc": 0.0, "inc": 200.0, "mass": 500,
         "dur_val": 2, "dur_unit": "hours", "stop_type": "ElapsedHours"},
        {"coord": "EarthMJ2000Eq"})
    assert_explained(err, stage="validate", code="schema_error")


def test_validate_duration_over_limit():
    err = _fail_case(
        {"body": "Earth", "sma": 6778.136, "ecc": 0.0, "inc": 0.0, "mass": 500,
         "dur_val": 400, "dur_unit": "days", "stop_type": "ElapsedDays"},
        {"coord": "EarthMJ2000Eq"})
    assert_explained(err, stage="validate", code="schema_error")


def test_interpret_invalid_json():
    from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
    import orbitlab_backend.api.app as app_module
    from orbitlab_backend.api.store import JobStore
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.clients.explainer_client import MockExplainer
    from orbitlab_backend.orchestrator.pipeline import Pipeline
    from fastapi.testclient import TestClient
    import json

    app_module.store = JobStore()
    extracted = extracted_for(sent_kepler("E2EFail", "Earth", 6778.136, 0.0, 0.0, 500, 2, "hours", "ElapsedHours"))

    def factory(*a, **k):
        ext = FrontStepExtractor()
        ext._fallback_extract = lambda t: dict(extracted)
        return Pipeline(extractor=ext,
                        interpreter=MockInterpreterClient(canned_json="not json {{{"),
                        explainer=MockExplainer(), gmat_runner=None)

    app_module.Pipeline = factory
    client = TestClient(app_module.create_app())
    try:
        job = run_text(client, "CASE-FAIL")
        assert job["status"] == "failed", job
        assert_explained(job["error"], stage="interpret", code="interpreter_unavailable")
    finally:
        import importlib
        importlib.reload(app_module)


def test_interpret_unknown_field():
    from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
    import orbitlab_backend.api.app as app_module
    from orbitlab_backend.api.store import JobStore
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.clients.explainer_client import MockExplainer
    from orbitlab_backend.orchestrator.pipeline import Pipeline
    from fastapi.testclient import TestClient

    class UnknownFieldInterpreter:
        async def interpret_prompt(self, prompt, warming_callback=None):
            raise ValueError("interpreter returned unsupported field 'warpDrive'")

    app_module.store = JobStore()
    extracted = extracted_for(sent_kepler("E2EFail", "Earth", 6778.136, 0.0, 0.0, 500, 2, "hours", "ElapsedHours"))

    def factory(*a, **k):
        ext = FrontStepExtractor()
        ext._fallback_extract = lambda t: dict(extracted)
        return Pipeline(extractor=ext, interpreter=UnknownFieldInterpreter(),
                        explainer=MockExplainer(), gmat_runner=None)

    app_module.Pipeline = factory
    client = TestClient(app_module.create_app())
    try:
        job = run_text(client, "CASE-FAIL")
        assert job["status"] == "failed", job
        assert_explained(job["error"], stage="interpret", code="interpreter_unavailable")
        assert "warpDrive" in job["error"]["message"]
    finally:
        import importlib
        importlib.reload(app_module)


def test_interpret_timeout_retries_once_then_typed_error():
    # Slow timeouts (>10 s warming window) become InterpreterUnavailableError
    # and are retried exactly once; the typed error surfaces after 2 attempts.
    import asyncio as _asyncio
    from httpx import AsyncClient, MockTransport, Response, Request, TimeoutException
    import orbitlab_backend.clients.interpreter_client as ic
    from orbitlab_backend.clients.interpreter_client import (
        HttpInterpreterClient, InterpreterUnavailableError)

    calls = [0]

    async def handler(request: Request):
        calls[0] += 1
        await _asyncio.sleep(15)
        return Response(200, json={"unreachable": True})

    real = ic.httpx.AsyncClient

    class PatchedClient(AsyncClient):
        def __init__(self, *a, **kw):
            super().__init__(transport=MockTransport(handler), timeout=kw.get("timeout"))

    ic.httpx.AsyncClient = PatchedClient
    try:
        client = HttpInterpreterClient(model_url="http://fake/interpreter", model_key="k", timeout_s=12)
        with pytest.raises(InterpreterUnavailableError) as exc:
            _asyncio.run(client.interpret_prompt("hello"))
        assert "timeout" in str(exc.value).lower()
        assert calls[0] == 2
    finally:
        ic.httpx.AsyncClient = real


def test_extract_timeout():
    import orbitlab_backend.api.app as app_module
    from orbitlab_backend.api.store import JobStore
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
    from orbitlab_backend.clients.explainer_client import MockExplainer
    from orbitlab_backend.orchestrator.pipeline import Pipeline
    from fastapi.testclient import TestClient

    class TimeoutExtractor(FrontStepExtractor):
        async def process(self, user_text):
            raise TimeoutError("extractor timed out after 5s")

    app_module.store = JobStore()

    def factory(*a, **k):
        return Pipeline(extractor=TimeoutExtractor(),
                        interpreter=MockInterpreterClient(canned_json="{}"),
                        explainer=MockExplainer(), gmat_runner=None)

    app_module.Pipeline = factory
    client = TestClient(app_module.create_app())
    try:
        job = run_text(client, "CASE-FAIL")
        assert job["status"] == "failed", job
        assert_explained(job["error"], stage="extract", code="extraction_error")
    finally:
        import importlib
        importlib.reload(app_module)


def test_extract_empty_fields():
    import orbitlab_backend.api.app as app_module
    from orbitlab_backend.api.store import JobStore
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
    from orbitlab_backend.clients.explainer_client import MockExplainer
    from orbitlab_backend.orchestrator.pipeline import Pipeline
    from fastapi.testclient import TestClient
    import json

    app_module.store = JobStore()
    empty = {"centralBody": None, "dryMassKg": None, "orbit": None, "eccentricity": None,
             "duration": None, "integrator": None, "forces": None, "maneuvers": [],
             "cartesian": None, "raw_text": "zzz"}

    def factory(*a, **k):
        ext = FrontStepExtractor()
        ext._fallback_extract = lambda t: dict(empty)
        return Pipeline(extractor=ext,
                        interpreter=MockInterpreterClient(canned_json=json.dumps(canned_for(
                            sent_kepler("E2EFail", "Earth", 6778.136, 0.0, 0.0, 500, 2, "hours", "ElapsedHours"),
                            "EarthMJ2000Eq"))),
                        explainer=MockExplainer(), gmat_runner=None)

    app_module.Pipeline = factory
    client = TestClient(app_module.create_app())
    try:
        job = run_text(client, "CASE-FAIL")
        assert job["status"] == "failed", job
        assert_explained(job["error"], stage="extract", code="needs_clarification")
        assert job["error"]["details"]["missing"]
    finally:
        import importlib
        importlib.reload(app_module)
