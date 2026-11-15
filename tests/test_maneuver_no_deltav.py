"""Regression test for the extract-stage crash on apoapsis burns without an
explicit delta-V vector ("cannot unpack non-iterable NoneType object").

The triggering extractor output was recorded from the real endpoint for:
"500 kg satellite around Earth, 500 km altitude, burn at apoapsis to 800 km,
1 day". The model legitimately omits deltaVKmS for a target-radius burn;
normalize_extracted records deltaV=None (verify.py treats that as
"do not check the vector"), and the crash was prompt_builder.py unpacking it.
No network, no GMAT: the recorded shape is replayed through a stub client.
"""
from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.frontstep.prompt_builder import build_canonical_prompt
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.clients.explainer_client import MockExplainer
from orbitlab_backend.orchestrator.pipeline import Pipeline
import asyncio
import json


# Exact model-output shape that triggered the crash (only the maneuver entry
# is load-bearing; the surrounding keys mirror the recorded payload).
RECORDED_MANEUVER = {
    "type": "impulsive_burn",
    "trigger": "apoapsis",
    "targetRadiusKm": 800,
    "elapsedSecs": None,
    "deltaVKmS": None,
}


class _StubClient:
    def __init__(self, payload):
        self.payload = payload

    def extract_sync(self, user_text):
        return self.payload

    async def extract(self, user_text):
        return self.payload


def _base_exp(**over):
    exp = {"experimentName": "X", "spacecraftName": "Y", "dryMassKg": 500,
           "centralBody": "Earth", "semiMajorAxisKm": 6778.136, "eccentricity": 0,
           "inclinationDeg": 0, "raanDeg": 0, "argumentOfPeriapsisDeg": 0,
           "trueAnomalyDeg": 0, "durationValue": 1, "durationUnit": "days",
           "integrator": "RungeKutta89", "forces": None, "maneuvers": [],
           "cartesian": None}
    exp.update(over)
    return exp


def test_apsis_burn_without_deltav_renders():
    p = build_canonical_prompt(_base_exp(maneuvers=[
        {"type": "ImpulsiveBurn", "id": "M1", "trigger": "AtApoapsis",
         "apsis": "apoapsis", "deltaV": None}]))
    assert "At the next apoapsis, apply the LocalVNB burn." in p
    assert "None" not in p


def test_elapsed_burn_without_deltav_renders():
    p = build_canonical_prompt(_base_exp(maneuvers=[
        {"type": "ImpulsiveBurn", "id": "M1", "trigger": "ElapsedTimeSecs",
         "elapsedSecs": 120, "deltaV": None}]))
    assert "once 120 sec have elapsed." in p
    assert "None" not in p


def test_malformed_deltav_renders_without_vector():
    for bad in ([1.0, 2.0], "1,2,3", {"x": 1}, None):
        p = build_canonical_prompt(_base_exp(maneuvers=[
            {"type": "ImpulsiveBurn", "id": "M1", "trigger": "AtApoapsis",
             "apsis": "apoapsis", "deltaV": bad}]))
        assert "At the next apoapsis, apply the LocalVNB burn." in p
        assert "None" not in p


def test_recorded_model_output_asks_for_burn_size():
    recorded = {
        "centralBody": "Earth", "dryMassKg": 500,
        "orbit": {"kind": "circularAltitudeKm", "value": 500, "unit": "km"},
        "duration": {"value": 1, "unit": "days"},
        "maneuvers": [dict(RECORDED_MANEUVER)],
    }
    ext = FrontStepExtractor(extractor_client=_StubClient(recorded))
    res = ext.process_sync(
        "500 kg satellite around Earth, 500 km altitude, burn at apoapsis to 800 km, 1 day")
    assert res.status == "needs_clarification", res
    assert res.missing == ["deltaV"], res.missing
    assert res.prompt is None


def test_venus_sma_prompt_still_converts():
    recorded = {
        "centralBody": "Venus", "dryMassKg": 500,
        "orbit": {"kind": "semiMajorAxisKm", "value": 9000, "unit": "km"},
        "duration": {"value": 1, "unit": "days"},
        "maneuvers": [],
    }
    ext = FrontStepExtractor(extractor_client=_StubClient(recorded))
    res = ext.process_sync("500 kg satellite around Venus, semi-major axis 9000 km, 1 day")
    assert res.status == "ok", res
