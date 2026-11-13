"""Demo mode unit tests: parser, builder, verify pass-through, no network."""
import json

import pytest

from orbitlab_backend.frontstep.demo import (
    DemoExtractor,
    DemoInterpreter,
    demo_build_experiment,
    demo_enabled,
    demo_parse_strict_schema,
)
from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.frontstep.verify import apply_frontstep_names, verify_experiment
from orbitlab_backend.orchestrator.pipeline import Pipeline
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.clients.explainer_client import MockExplainer
from orbitlab_backend.orchestrator.errors import NeedsClarification, ValidationFailed


def _convert(text):
    from orbitlab_backend.clients.extractor_client import normalize_extracted
    raw = demo_parse_strict_schema(text)
    return FrontStepExtractor().deterministic_convert(normalize_extracted(raw), text)


def test_parser_strict_schema_shapes():
    p = demo_parse_strict_schema(
        "Put a 500 kg satellite in a circular orbit at 400 km altitude around Earth for 1 day.")
    assert p == {"centralBody": "Earth", "dryMassKg": 500.0,
                 "orbit": {"quantity": "altitude", "valueKm": 400.0, "eccentricity": 0.0},
                 "inclinationDeg": None, "raanDeg": None,
                 "argumentOfPeriapsisDeg": None, "trueAnomalyDeg": None,
                 "duration": {"value": 1.0, "unit": "days"}, "maneuvers": []}
    p = demo_parse_strict_schema("Moon orbit, 100 km altitude, 500 kg, 6 hours")
    assert p["centralBody"] == "Moon" and p["dryMassKg"] == 500.0
    assert p["orbit"] == {"quantity": "altitude", "valueKm": 100.0, "eccentricity": None}
    assert p["duration"] == {"value": 6.0, "unit": "hours"}
    p = demo_parse_strict_schema(
        "Create a 1200 kg spacecraft around Mars with periapsis altitude 300 km "
        "and eccentricity 0.2 for 2 days.")
    assert p["orbit"] == {"quantity": "periapsis_altitude", "valueKm": 300.0, "eccentricity": 0.2}
    p = demo_parse_strict_schema(
        "800 kg spacecraft around Venus with semi-major axis 9000 km, "
        "eccentricity 0.05 and inclination 30 degrees for 5 orbits.")
    assert p["orbit"] == {"quantity": "semi_major_axis", "valueKm": 9000.0, "eccentricity": 0.05}
    assert p["inclinationDeg"] == 30.0
    assert p["duration"] == {"value": 5.0, "unit": "orbits"}
    p = demo_parse_strict_schema(
        "500 kg satellite around Earth in a 7000 km circular orbit, "
        "Hohmann transfer to 9000 km at periapsis, 2 days")
    assert p["orbit"] == {"quantity": "radius", "valueKm": 7000.0, "eccentricity": 0.0}
    assert p["maneuvers"] == [{"type": "hohmann_transfer", "trigger": "periapsis",
                               "targetRadiusKm": 9000.0, "elapsedSecs": None,
                               "deltaVKmS": None}]
    p = demo_parse_strict_schema("450 kg lunar orbiter, circular orbit at 150 km altitude, for 12 hours.")
    assert p["centralBody"] == "Moon"
    p = demo_parse_strict_schema("450 kg spacecraft around the martian planet for 12 hours.")
    assert p["centralBody"] == "Mars"
    p = demo_parse_strict_schema(
        "600 kg craft around Earth, inclination 10, raan 20, argument of periapsis 30, "
        "true anomaly 40, circular orbit at 400 km altitude, for 90 seconds.")
    assert (p["inclinationDeg"], p["raanDeg"], p["argumentOfPeriapsisDeg"],
            p["trueAnomalyDeg"]) == (10.0, 20.0, 30.0, 40.0)
    assert p["duration"] == {"value": 90.0, "unit": "seconds"}
    p = demo_parse_strict_schema("blorple wibble zorp")
    assert p["centralBody"] is None and p["orbit"] is None and p["duration"] is None


def test_demo_convert_verify_roundtrip():
    texts = [
        "Put a 500 kg satellite in a circular orbit at 400 km altitude around Earth for 1 day.",
        "500 kg satellite around Earth in a 7000 km circular orbit, "
        "Hohmann transfer to 9000 km at periapsis, 2 days",
        "Create a 1200 kg spacecraft around Mars with periapsis altitude 300 km "
        "and eccentricity 0.2 for 2 days.",
    ]
    for text in texts:
        conv = _convert(text)
        assert conv.status == "ok", conv.missing
        interp = DemoInterpreter()
        import asyncio
        returned = asyncio.run(interp.interpret_prompt(conv.prompt))
        assert returned["centralBody"] == conv.data["centralBody"]
        updated, _ = apply_frontstep_names(conv.data, returned)
        assert verify_experiment(conv.data, updated) == []
        assert updated["initialOrbit"]["coordinateSystem"].endswith("MJ2000Eq")


@pytest.mark.asyncio
async def test_demo_no_network_sockets_blocked(monkeypatch):
    import socket

    def _blocked(*a, **k):
        raise RuntimeError("network disabled in demo test")

    # Block real connection paths only (patching socket.socket itself breaks
    # isinstance checks inside asyncio).
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    pipeline = Pipeline(extractor=FrontStepExtractor(extractor_client=DemoExtractor()),
                        interpreter=DemoInterpreter(), explainer=MockExplainer(),
                        gmat_runner=None)
    res = await pipeline.run(
        "Put a 500 kg satellite in a circular orbit at 400 km altitude around Earth for 1 day.")
    assert res["status"] == "success"
    assert res["explanationSource"] == "fallback"
    assert res["experiment"]["initialOrbit"]["elements"]["semiMajorAxisKm"] == pytest.approx(6778.136)


def test_incomplete_prompts_name_missing_fields():
    cases = [
        ("satellite around Earth", {"dryMassKg", "orbit", "duration"}),
        ("500 kg satellite for 2 days", {"centralBody", "orbit"}),
        ("500 kg satellite around Earth in a 7000 km circular orbit", {"duration"}),
        ("500 kg satellite around Earth for 2 days", {"orbit"}),
    ]
    for text, missing in cases:
        conv = _convert(text)
        assert conv.status == "needs_clarification", text
        assert set(conv.missing) == missing, (text, conv.missing)


def test_validator_violation_has_explanation():
    import asyncio
    pipeline = Pipeline(extractor=FrontStepExtractor(extractor_client=DemoExtractor()),
                        interpreter=DemoInterpreter(), explainer=MockExplainer(),
                        gmat_runner=None)
    with pytest.raises(ValidationFailed) as exc:
        asyncio.run(pipeline.run(
            "500 kg satellite around Earth, 50 km circular orbit, for 2 days"))
    assert exc.value.code == "validation_failed"
    details = exc.value.details or {}
    assert isinstance(details.get("explanation"), str) and details["explanation"]


def test_health_demo_mode():
    from fastapi.testclient import TestClient
    from orbitlab_backend import config as cfg
    from orbitlab_backend.api.app import create_app
    import os
    os.environ["ORBITLAB_DEMO_MODE"] = "true"
    cfg.reset_settings()
    try:
        assert demo_enabled() is True
        r = TestClient(create_app()).get("/api/health")
        assert r.json() == {"status": "ok", "mode": "demo"}
    finally:
        del os.environ["ORBITLAB_DEMO_MODE"]
        cfg.reset_settings()
    r = TestClient(create_app()).get("/api/health")
    assert r.json() == {"status": "ok"}


def test_factories_return_demo_parts():
    import os
    from orbitlab_backend import config as cfg
    from orbitlab_backend.clients.extractor_client import get_extractor
    from orbitlab_backend.clients.interpreter_client import get_interpreter_client
    from orbitlab_backend.frontstep.demo import DemoExtractor, DemoInterpreter
    os.environ["ORBITLAB_DEMO_MODE"] = "true"
    cfg.reset_settings()
    try:
        assert isinstance(get_extractor(), DemoExtractor)
        assert isinstance(get_interpreter_client(), DemoInterpreter)
    finally:
        del os.environ["ORBITLAB_DEMO_MODE"]
        cfg.reset_settings()
