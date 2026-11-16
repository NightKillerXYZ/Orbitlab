"""Pipeline normalize-time force-model defaults.

- Unspecified perturbers (front-step forces None) are replaced per body:
  Earth -> [Luna, Sun], Moon -> [Earth, Sun], Mars -> [Sun], with a
  force_model_normalized warning.
- Explicit user lists are kept, except the central body is removed.
- No network, no GMAT (stubbed runner).
"""
import asyncio
import json

from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.clients.explainer_client import MockExplainer
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


def _extracted(body, alt_km, sma, forces=None):
    return {"centralBody": body, "dryMassKg": 500,
            "orbit": {"kind": "circularAltitudeKm", "value": alt_km, "unit": "km"},
            "duration": {"value": 6, "unit": "hours"}, "integrator": "RungeKutta89",
            "forces": forces, "maneuvers": [], "cartesian": None}


def _canned(body, coord, sma, point_masses):
    return {"version": "1.0", "experimentName": "ExpF",
            "spacecraft": {"name": "SC_ExpF", "dryMassKg": 500},
            "centralBody": body,
            "initialOrbit": {"type": "Keplerian", "coordinateSystem": coord,
                             "elements": {"semiMajorAxisKm": sma, "eccentricity": 0,
                                          "inclinationDeg": 0, "raanDeg": 0,
                                          "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}},
            "forceModel": {"gravityDegree": 4, "gravityOrder": 4,
                           "pointMasses": point_masses,
                           "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
                           "solarRadiationPressure": True},
            "propagation": {"integrator": "RungeKutta89",
                            "stopCondition": {"type": "ElapsedHours", "value": 6},
                            "stepSizeSecs": 60},
            "maneuvers": []}


def _run(body, alt_km, sma, coord, returned_pm, sent_forces=None):
    ext = FrontStepExtractor(extractor_client=_StubClient(
        _extracted(body, alt_km, sma, forces=sent_forces)))
    pipe = Pipeline(extractor=ext,
                    interpreter=MockInterpreterClient(
                        canned_json=json.dumps(_canned(body, coord, sma, returned_pm))),
                    explainer=MockExplainer(), gmat_runner=_FakeGmat())
    return asyncio.run(pipe.run("dummy %s" % body))


def test_moon_unspecified_defaults_to_earth_sun():
    res = _run("Moon", 500, 2237.4, "LunaMJ2000Eq", ["Luna", "Sun"])
    assert res["status"] == "success", res.get("explanation", res)
    assert res["experiment"]["forceModel"]["pointMasses"] == ["Earth", "Sun"]
    assert any("force_model_normalized" in w for w in res["warnings"]), res["warnings"]
    assert "{Earth, Sun}" in res["script"]


def test_mars_unspecified_defaults_to_sun_only():
    res = _run("Mars", 500, 3889.5, "MarsMJ2000Eq", ["Luna", "Sun"])
    assert res["status"] == "success", res.get("explanation", res)
    assert res["experiment"]["forceModel"]["pointMasses"] == ["Sun"]
    assert any("force_model_normalized" in w for w in res["warnings"]), res["warnings"]


def test_earth_unspecified_keeps_luna_sun_without_note():
    res = _run("Earth", 500, 6878.136, "EarthMJ2000Eq", ["Luna", "Sun"])
    assert res["status"] == "success", res.get("explanation", res)
    assert res["experiment"]["forceModel"]["pointMasses"] == ["Luna", "Sun"]
    assert not any("force_model_normalized" in w for w in res["warnings"]), res["warnings"]


def test_explicit_list_kept_minus_central_body():
    sent = {"gravityDegree": 4, "gravityOrder": 4,
            "pointMasses": ["Luna", "Sun"], "solarRadiationPressure": True}
    res = _run("Moon", 500, 2237.4, "LunaMJ2000Eq", ["Luna", "Sun"], sent_forces=sent)
    assert res["status"] == "success", res.get("explanation", res)
    assert res["experiment"]["forceModel"]["pointMasses"] == ["Sun"]
    assert any("force_model_normalized" in w for w in res["warnings"]), res["warnings"]
