"""End-to-end: an impulsive burn WITH an explicit delta-V runs the full pipeline.

Uses a recorded-style extractor payload with deltaVKmS present, a matching
canned interpreter experiment, and a stubbed GMAT runner. No network, no GMAT.
"""
import asyncio
import json

from orbitlab_backend.clients.explainer_client import MockExplainer
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.orchestrator.pipeline import Pipeline


class _StubClient:
    def __init__(self, payload):
        self.payload = payload

    def extract_sync(self, user_text):
        return self.payload

    async def extract(self, user_text):
        return self.payload


class _FakeGmat:
    async def execute(self, req):
        from orbitlab_simulation_engine import TrajectoryPoint, TrajectoryData
        p = TrajectoryPoint(elapsed_secs=0, x_km=7000, y_km=0, z_km=0, vx_km_s=0,
                            vy_km_s=7.5, vz_km_s=0, semi_major_axis_km=6878.136,
                            eccentricity=0, inclination_deg=0, altitude_km=500)
        return type("R", (), {"trajectory": TrajectoryData(full=(p,), visualization=(p,))})()


def test_burn_with_explicit_delta_v_runs_end_to_end():
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
    ext = FrontStepExtractor(extractor_client=_StubClient(recorded))
    interp = MockInterpreterClient(canned_json=json.dumps(canned))
    pipe = Pipeline(extractor=ext, interpreter=interp,
                    explainer=MockExplainer(), gmat_runner=_FakeGmat())
    res = asyncio.run(pipe.run("burn 100 m/s prograde at apoapsis"))
    assert res["status"] == "success", res.get("explanation", res)
    assert res.get("fromCache") is False
    assert isinstance(res.get("elapsedSeconds"), float)
