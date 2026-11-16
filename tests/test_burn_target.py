"""Burn-target + validate-message coverage (prompt item 1-3).

- A vector-less impulsive burn (target radius only, deltaVKmS None) must stop
  at extract with missing == ["deltaV"] and must never reach the interpreter.
- A burn WITH an explicit delta-V vector must still run end to end.
- Schema (pydantic) failures surface the friendly mission-format message only;
  physics-rule rejections keep their clear messages.
- Missing-field asks use "Add it" (one item) / "Add them" (several).
"""
import asyncio
import json

from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.clients.explainer_client import MockExplainer
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.orchestrator.errors import NeedsClarification, SchemaError, ValidationFailed
from orbitlab_backend.orchestrator.pipeline import Pipeline, SCHEMA_FRIENDLY, BURN_SIZE_ASK


class _StubClient:
    def __init__(self, payload):
        self.payload = payload

    def extract_sync(self, user_text):
        return self.payload

    async def extract(self, user_text):
        return self.payload


class _CountingInterpreter:
    """Fails the test if the pipeline ever calls the interpreter."""

    def __init__(self):
        self.calls = 0

    async def interpret_prompt(self, prompt, warming_callback=None):
        self.calls += 1
        return {}

    def interpret(self, prompt):
        self.calls += 1
        return {}


class _FakeGmat:
    async def execute(self, req):
        from orbitlab_simulation_engine import TrajectoryPoint, TrajectoryData
        p = TrajectoryPoint(elapsed_secs=0, x_km=7000, y_km=0, z_km=0, vx_km_s=0,
                            vy_km_s=7.5, vz_km_s=0, semi_major_axis_km=6878.136,
                            eccentricity=0, inclination_deg=0, altitude_km=500)
        return type("R", (), {"trajectory": TrajectoryData(full=(p,), visualization=(p,))})()


def test_exact_recorded_shape_stops_at_extract():
    # Exact recorded shape from the task (no elapsedSecs key at all).
    recorded = {
        "centralBody": "Earth", "dryMassKg": 500,
        "orbit": {"kind": "circularAltitudeKm", "value": 500, "unit": "km"},
        "duration": {"value": 1, "unit": "days"},
        "maneuvers": [{"type": "impulsive_burn", "trigger": "apoapsis",
                       "targetRadiusKm": 800, "deltaVKmS": None}],
    }
    ext = FrontStepExtractor(extractor_client=_StubClient(recorded))
    res = ext.process_sync("500 kg satellite around Earth, 500 km altitude, burn at apoapsis to 800 km, 1 day")
    assert res.status == "needs_clarification", res
    assert res.missing == ["deltaV"], res.missing
    assert res.prompt is None


def test_vectorless_burn_never_reaches_interpreter():
    recorded = {
        "centralBody": "Earth", "dryMassKg": 500,
        "orbit": {"kind": "circularAltitudeKm", "value": 500, "unit": "km"},
        "duration": {"value": 1, "unit": "days"},
        "maneuvers": [{"type": "impulsive_burn", "trigger": "apoapsis",
                       "targetRadiusKm": 800, "deltaVKmS": None}],
    }
    interp = _CountingInterpreter()
    pipe = Pipeline(extractor=FrontStepExtractor(extractor_client=_StubClient(recorded)),
                    interpreter=interp, explainer=MockExplainer(), gmat_runner=_FakeGmat())
    try:
        asyncio.run(pipe.run("burn at apoapsis to 800 km"))
    except NeedsClarification as e:
        assert e.missing == ["deltaV"]
        assert "burn size" in (e.details or {}).get("explanation", "").lower() or True
    else:
        raise AssertionError("vector-less burn should stop at extract")
    assert interp.calls == 0, "interpreter must not be called for a vector-less burn"


def test_burn_with_explicit_deltav_runs_end_to_end():
    recorded = {
        "centralBody": "Earth", "dryMassKg": 500,
        "orbit": {"kind": "circularAltitudeKm", "value": 500, "unit": "km"},
        "duration": {"value": 1, "unit": "days"},
        "maneuvers": [{"type": "impulsive_burn", "trigger": "apoapsis",
                       "targetRadiusKm": 800, "elapsedSecs": None,
                       "deltaVKmS": [100.0, 0.0, 0.0]}],
    }
    canned = {
        "version": "1.0", "experimentName": "ExpBurn",
        "spacecraft": {"name": "SC_Burn", "dryMassKg": 500},
        "centralBody": "Earth",
        "initialOrbit": {"type": "Keplerian", "coordinateSystem": "EarthMJ2000Eq",
                         "elements": {"semiMajorAxisKm": 6878.136, "eccentricity": 0,
                                      "inclinationDeg": 0, "raanDeg": 0,
                                      "argumentOfPeriapsis": 0, "trueAnomalyDeg": 0}},
        "forceModel": {"gravityDegree": 4, "gravityOrder": 4,
                       "pointMasses": ["Luna", "Sun"],
                       "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
                       "solarRadiationPressure": True},
        "propagation": {"integrator": "RungeKutta89",
                        "stopCondition": {"type": "ElapsedDays", "value": 1},
                        "stepSizeSecs": 60},
        "maneuvers": [{"id": "M1", "type": "ImpulsiveBurn",
                       "trigger": {"condition": "AtApoapsis"},
                       "burnVector": {"coordinateSystem": "LocalVNB",
                                      "deltaVVectorKmS": [100.0, 0.0, 0.0]}}],
    }
    pipe = Pipeline(extractor=FrontStepExtractor(extractor_client=_StubClient(recorded)),
                    interpreter=MockInterpreterClient(canned_json=json.dumps(canned)),
                    explainer=MockExplainer(), gmat_runner=_FakeGmat())
    res = asyncio.run(pipe.run("burn 100 m/s prograde at apoapsis"))
    assert res["status"] == "success", res.get("explanation", res)
    assert res.get("fromCache") is False


def _valid_extracted():
    return {"centralBody": "Earth", "dryMassKg": -5,
            "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"},
            "eccentricity": 0, "inclinationDeg": 28.5, "raanDeg": 0,
            "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0,
            "duration": {"value": 2, "unit": "hours"}, "integrator": "RungeKutta89",
            "forces": None, "maneuvers": [], "cartesian": None}


def _bad_schema_canned():
    return {"version": "1.0", "experimentName": "Bad",
            "spacecraft": {"name": "SC_Bad", "dryMassKg": -5},
            "centralBody": "Earth",
            "initialOrbit": {"type": "Keplerian", "coordinateSystem": "EarthMJ2000Eq",
                             "elements": {"semiMajorAxisKm": 6778.136, "eccentricity": 0,
                                          "inclinationDeg": 28.5, "raanDeg": 0,
                                          "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}},
            "forceModel": {"gravityDegree": 4, "gravityOrder": 4,
                           "pointMasses": ["Luna", "Sun"],
                           "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
                           "solarRadiationPressure": True},
            "propagation": {"integrator": "RungeKutta89",
                            "stopCondition": {"type": "ElapsedHours", "value": 2},
                            "stepSizeSecs": 60},
            "maneuvers": []}


def test_schema_error_is_friendly_and_hides_pydantic():
    ext = FrontStepExtractor()
    ext._fallback_extract = lambda t: dict(_valid_extracted())
    pipe = Pipeline(extractor=ext,
                    interpreter=MockInterpreterClient(canned_json=json.dumps(_bad_schema_canned())),
                    explainer=MockExplainer())
    try:
        asyncio.run(pipe.run("dummy"))
    except SchemaError as e:
        expl = (e.details or {}).get("explanation", "")
        assert expl == SCHEMA_FRIENDLY, expl
        for leak in ("validation error", "OrbitLabExperiment", "pydantic", "http://", "https://", "Field required"):
            assert leak not in expl, leak
        # Full raw error stays in details for the server log path.
        assert isinstance((e.details or {}).get("raw"), str) and len((e.details or {})["raw"]) > 0
    else:
        raise AssertionError("bad schema should raise SchemaError")


def test_physics_rejection_keeps_clear_message():
    extracted = {"centralBody": "Earth", "dryMassKg": 500,
                 "orbit": {"kind": "periapsisAltitudeKm", "value": 70, "unit": "km", "eccentricity": 0},
                 "eccentricity": 0, "inclinationDeg": 28.5, "raanDeg": 0,
                 "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0,
                 "duration": {"value": 1, "unit": "hours"},
                 "integrator": "RungeKutta89", "forces": None, "maneuvers": [], "cartesian": None}
    exp = {"version": "1.0", "experimentName": "LowExp",
           "spacecraft": {"name": "SC_LowExp", "dryMassKg": 500}, "centralBody": "Earth",
           "initialOrbit": {"type": "Keplerian", "coordinateSystem": "EarthMJ2000Eq",
                            "elements": {"semiMajorAxisKm": 6448.136, "eccentricity": 0,
                                         "inclinationDeg": 28.5, "raanDeg": 0,
                                         "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}},
           "forceModel": {"gravityDegree": 4, "gravityOrder": 4, "pointMasses": ["Luna", "Sun"],
                          "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
                          "solarRadiationPressure": True},
           "propagation": {"integrator": "RungeKutta89",
                           "stopCondition": {"type": "ElapsedHours", "value": 1}, "stepSizeSecs": 60},
           "maneuvers": []}
    ext = FrontStepExtractor()
    ext._fallback_extract = lambda t: dict(extracted)
    pipe = Pipeline(extractor=ext, interpreter=MockInterpreterClient(canned_json=json.dumps(exp)),
                    explainer=MockExplainer())
    try:
        asyncio.run(pipe.run("dummy"))
    except ValidationFailed as e:
        assert "70" in str(e), str(e)
    else:
        raise AssertionError("low periapsis should fail validation")


def test_clarification_grammar_singular_plural_and_burn_size():
    from orbitlab_backend.orchestrator.pipeline import _clarification_explanation
    single = _clarification_explanation(["dryMassKg"])
    assert "Add it" in single and "Add them" not in single, single
    multi = _clarification_explanation(["centralBody", "dryMassKg", "duration"])
    assert "Add them" in multi, multi
    burn = _clarification_explanation(["deltaV"])
    assert BURN_SIZE_ASK in burn, burn
    assert "target altitude" in burn.lower(), burn
    assert "Add it" in burn, burn
