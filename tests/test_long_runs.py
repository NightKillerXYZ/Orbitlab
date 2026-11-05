import asyncio
import pytest


def _exp(body, coord, sma, ecc, stop_type, stop_val, step=60, mass=500):
    return {
        "version": "1.0",
        "experimentName": "T",
        "spacecraft": {"name": "SC_T", "dryMassKg": mass},
        "centralBody": body,
        "initialOrbit": {"type": "Keplerian", "coordinateSystem": coord, "elements": {
            "semiMajorAxisKm": sma, "eccentricity": ecc, "inclinationDeg": 0,
            "raanDeg": 0, "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}},
        "propagation": {"integrator": "RungeKutta89",
                        "stopCondition": {"type": stop_type, "value": stop_val},
                        "stepSizeSecs": step},
        "maneuvers": [],
    }


def test_estimate_hours_and_days():
    from orbitlab_backend.orchestrator.estimate import estimate_run_seconds
    e = _exp("Earth", "EarthMJ2000Eq", 6778.136, 0, "ElapsedHours", 2)
    assert estimate_run_seconds(e, 0.5) == pytest.approx(2 / 24 * 0.5)
    e = _exp("Earth", "EarthMJ2000Eq", 6778.136, 0, "ElapsedDays", 365)
    assert estimate_run_seconds(e, 0.5) == pytest.approx(365 * 0.5)


def test_estimate_seconds_and_step_scaling():
    from orbitlab_backend.orchestrator.estimate import estimate_run_seconds
    e = _exp("Earth", "EarthMJ2000Eq", 6778.136, 0, "ElapsedSeconds", 7200, step=60)
    assert estimate_run_seconds(e, 0.5) == pytest.approx(7200 / 86400 * 0.5)
    e300 = _exp("Earth", "EarthMJ2000Eq", 6778.136, 0, "ElapsedSeconds", 7200, step=300)
    assert estimate_run_seconds(e300, 0.5) == pytest.approx(7200 / 86400 * 0.5 * 60 / 300)


def test_estimate_orbit_periods_uses_period_only_for_estimate():
    import copy
    from orbitlab_backend.orchestrator.estimate import estimate_run_seconds
    e = _exp("Earth", "EarthMJ2000Eq", 6778.136, 0, "OrbitPeriods", 3)
    got = estimate_run_seconds(e, 0.5)
    import math
    period = 2 * math.pi * (6778.136 ** 3 / 398600.4415) ** 0.5
    assert got == pytest.approx(3 * period / 86400 * 0.5)
    # stop condition itself untouched
    assert e["propagation"]["stopCondition"] == {"type": "OrbitPeriods", "value": 3}


@pytest.mark.asyncio
async def test_too_long_run_fails_at_validate_with_explanation(monkeypatch):
    import json
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
    from orbitlab_backend.clients.explainer_client import MockExplainer
    from orbitlab_backend.orchestrator.pipeline import Pipeline
    from orbitlab_backend.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "ORBITLAB_GMAT_MAX_TIMEOUT_S", 0.001)
    canned = _exp("Earth", "EarthMJ2000Eq", 6778.136, 0, "ElapsedHours", 2)
    extracted = {"centralBody": "Earth", "dryMassKg": 500,
                 "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"},
                 "duration": {"value": 2, "unit": "hours"}, "integrator": "RungeKutta89",
                 "forces": None, "maneuvers": [], "cartesian": None,
                 "experimentName": "T", "spacecraftName": "T"}
    ext = FrontStepExtractor()
    ext._fallback_extract = lambda t: extracted
    pipe = Pipeline(extractor=ext, interpreter=MockInterpreterClient(canned_json=json.dumps(canned)),
                    explainer=MockExplainer(), gmat_runner=None)
    with pytest.raises(Exception) as exc:
        await pipe.run("dummy")
    assert exc.value.stage == "validate"
    assert "too long" in str(exc.value.message).lower()
    assert exc.value.details.get("explanation")


@pytest.mark.asyncio
async def test_normal_run_uses_floor_timeout():
    import json
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
    from orbitlab_backend.clients.explainer_client import MockExplainer
    from orbitlab_backend.orchestrator.pipeline import Pipeline

    canned = _exp("Earth", "EarthMJ2000Eq", 6778.136, 0, "ElapsedHours", 2)
    extracted = {"centralBody": "Earth", "dryMassKg": 500,
                 "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"},
                 "duration": {"value": 2, "unit": "hours"}, "integrator": "RungeKutta89",
                 "forces": None, "maneuvers": [], "cartesian": None,
                 "experimentName": "T", "spacecraftName": "T"}
    ext = FrontStepExtractor()
    ext._fallback_extract = lambda t: extracted
    seen = {}

    class FakeGmat:
        async def execute(self, req):
            seen["timeout"] = req.timeout_seconds
            from orbitlab_simulation_engine import TrajectoryPoint, TrajectoryData
            p = TrajectoryPoint(elapsed_secs=0, x_km=7000, y_km=0, z_km=0, vx_km_s=0,
                                vy_km_s=7.5, vz_km_s=0, semi_major_axis_km=6778.136,
                                eccentricity=0, inclination_deg=0, altitude_km=400)
            return type("R", (), {"trajectory": TrajectoryData(full=(p,), visualization=(p,))})()

    pipe = Pipeline(extractor=ext, interpreter=MockInterpreterClient(canned_json=json.dumps(canned)),
                    explainer=MockExplainer(), gmat_runner=FakeGmat())
    await pipe.run("dummy")
    from orbitlab_backend.config import get_settings
    assert seen["timeout"] == pytest.approx(float(get_settings().GMAT_TIMEOUT_S))


@pytest.mark.asyncio
async def test_progress_events_during_slow_simulation(monkeypatch):
    import json
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
    from orbitlab_backend.clients.explainer_client import MockExplainer
    from orbitlab_backend.orchestrator.pipeline import Pipeline
    from orbitlab_backend.config import get_settings

    monkeypatch.setattr(get_settings(), "ORBITLAB_PROGRESS_INTERVAL_S", 0.2)
    canned = _exp("Earth", "EarthMJ2000Eq", 6778.136, 0, "ElapsedHours", 2)
    extracted = {"centralBody": "Earth", "dryMassKg": 500,
                 "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"},
                 "duration": {"value": 2, "unit": "hours"}, "integrator": "RungeKutta89",
                 "forces": None, "maneuvers": [], "cartesian": None,
                 "experimentName": "T", "spacecraftName": "T"}
    ext = FrontStepExtractor()
    ext._fallback_extract = lambda t: extracted

    class SlowGmat:
        async def execute(self, req):
            await asyncio.sleep(1.0)
            from orbitlab_simulation_engine import TrajectoryPoint, TrajectoryData
            p = TrajectoryPoint(elapsed_secs=0, x_km=7000, y_km=0, z_km=0, vx_km_s=0,
                                vy_km_s=7.5, vz_km_s=0, semi_major_axis_km=6778.136,
                                eccentricity=0, inclination_deg=0, altitude_km=400)
            return type("R", (), {"trajectory": TrajectoryData(full=(p,), visualization=(p,))})()

    events = []

    async def cb(ev):
        events.append((ev.type, ev.stage, ev.details))

    pipe = Pipeline(extractor=ext, interpreter=MockInterpreterClient(canned_json=json.dumps(canned)),
                    explainer=MockExplainer(), gmat_runner=SlowGmat())
    await pipe.run("dummy", event_cb=cb)
    prog = [e for e in events if e[0] == "progress" and e[1] == "simulate"]
    assert len(prog) >= 1
    assert "elapsedSecs" in prog[0][2] and "estimateSecs" in prog[0][2]
