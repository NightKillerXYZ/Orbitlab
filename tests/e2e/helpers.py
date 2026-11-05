"""Shared helpers for the phase-6 end-to-end suite (real routes only)."""
import json
import time

from fastapi.testclient import TestClient

import orbitlab_backend.api.app as app_module
from orbitlab_backend.api.store import JobStore
from orbitlab_backend.frontstep.extractor import FrontStepExtractor
from orbitlab_backend.clients.interpreter_client import MockInterpreterClient
from orbitlab_backend.clients.explainer_client import MockExplainer
from orbitlab_backend.orchestrator.pipeline import Pipeline


def gmat_available():
    import os
    from pathlib import Path
    p = os.environ.get("GMAT_PATH")
    return bool(p) and Path(p).is_file()


NEEDS_GMAT = __import__("pytest").mark.skipif(
    not gmat_available(), reason="GMAT not installed (set GMAT_PATH to GmatConsole.exe)")


class RoutingInterpreter:
    """Fake interpreter returning a canned experiment per prompt marker."""

    def __init__(self, routes):
        self.routes = routes

    async def interpret_prompt(self, prompt, warming_callback=None):
        for marker, response in self.routes:
            if marker in (prompt or ""):
                if isinstance(response, Exception):
                    raise response
                if callable(response):
                    return response(prompt)
                return json.loads(json.dumps(response))
        raise AssertionError("no canned response for prompt: %s" % (prompt or "")[:120])


def sent_kepler(name, body, sma, ecc, inc, mass, dur_val, dur_unit, stop_type,
                maneuvers=None, raan=0, aop=0, ta=0):
    return {
        "experimentName": name, "spacecraftName": name,
        "centralBody": body, "dryMassKg": mass,
        "semiMajorAxisKm": sma, "eccentricity": ecc,
        "inclinationDeg": inc, "raanDeg": raan,
        "argumentOfPeriapsisDeg": aop, "trueAnomalyDeg": ta,
        "integrator": "RungeKutta89",
        "durationValue": dur_val, "durationUnit": dur_unit,
        "stopConditionType": stop_type,
        "forces": None, "maneuvers": maneuvers or [], "cartesian": None,
    }


def extracted_for(sent):
    """Front-step extractor input mirroring a normalized sent dict."""
    e = {
        "experimentName": sent["experimentName"],
        "spacecraftName": sent["spacecraftName"],
        "centralBody": sent["centralBody"], "dryMassKg": sent["dryMassKg"],
        "orbit": {"kind": "semiMajorAxisKm", "value": sent["semiMajorAxisKm"], "unit": "km"},
        "eccentricity": sent["eccentricity"],
        "inclinationDeg": sent["inclinationDeg"], "raanDeg": 0,
        "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0,
        "duration": {"value": sent["durationValue"], "unit": sent["durationUnit"]},
        "integrator": "RungeKutta89", "forces": None,
        "maneuvers": sent.get("maneuvers", []), "cartesian": None,
    }
    return e


def sent_cartesian(name, body, r, v, dur_val, dur_unit, stop_type, mass=500):
    return {
        "experimentName": name, "spacecraftName": name,
        "centralBody": body, "dryMassKg": mass,
        "semiMajorAxisKm": None, "eccentricity": None,
        "inclinationDeg": 0, "raanDeg": 0,
        "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0,
        "integrator": "RungeKutta89",
        "durationValue": dur_val, "durationUnit": dur_unit,
        "stopConditionType": stop_type,
        "forces": None, "maneuvers": [], "cartesian": {"x": r[0], "y": r[1], "z": r[2], "vx": v[0], "vy": v[1], "vz": v[2]},
    }


def extracted_cartesian_for(sent):
    e = extracted_for({**sent, "semiMajorAxisKm": 0, "eccentricity": 0})
    e["orbit"] = None
    e["cartesian"] = dict(sent["cartesian"])
    return e


def hohmann_out(sent_m):
    m = dict(sent_m)
    return {
        "id": m.get("id", "M1"),
        "type": "TargetedHohmannTransfer",
        "trigger": {"condition": "AtPeriapsis" if m.get("apsis", "periapsis") == "periapsis" else "AtApoapsis"},
        "targetObjectives": {k: m[k] for k in ("targetOrbitRadiusKm", "targetEccentricity") if k in m},
    }


def burn_out(sent_m):
    trig = sent_m.get("trigger")
    if trig == "ElapsedTimeSecs":
        trigger = {"condition": "ElapsedTimeSecs", "elapsedSecs": sent_m["elapsedSecs"]}
    else:
        trigger = {"condition": trig}
    return {
        "id": sent_m.get("id", "M1"),
        "type": "ImpulsiveBurn",
        "trigger": trigger,
        "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": list(sent_m["deltaV"])},
    }


def maneuver_out(sent_m):
    if sent_m.get("type") == "Hohmann":
        return hohmann_out(sent_m)
    return burn_out(sent_m)


def canned_for(sent, coord, forces=None, step=60, mass_override=None):
    els = {"semiMajorAxisKm": sent["semiMajorAxisKm"], "eccentricity": sent["eccentricity"],
           "inclinationDeg": sent["inclinationDeg"], "raanDeg": sent["raanDeg"],
           "argumentOfPeriapsisDeg": sent["argumentOfPeriapsisDeg"], "trueAnomalyDeg": sent["trueAnomalyDeg"]}
    if sent.get("cartesian"):
        c = sent["cartesian"]
        orbit = {"type": "Cartesian", "coordinateSystem": coord,
                 "elements": {"xKm": c["x"], "yKm": c["y"], "zKm": c["z"],
                              "vxKmS": c["vx"], "vyKmS": c["vy"], "vzKmS": c["vz"]}}
    else:
        orbit = {"type": "Keplerian", "coordinateSystem": coord, "elements": els}
    fm = forces or {"gravityDegree": 4, "gravityOrder": 4, "pointMasses": ["Luna", "Sun"],
                    "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
                    "solarRadiationPressure": True}
    return {
        "version": "1.0", "experimentName": sent["experimentName"],
        "spacecraft": {"name": "SC_" + sent["spacecraftName"], "dryMassKg": sent["dryMassKg"]},
        "centralBody": sent["centralBody"], "initialOrbit": orbit, "forceModel": fm,
        "propagation": {"integrator": "RungeKutta89",
                        "stopCondition": {"type": sent["stopConditionType"], "value": sent["durationValue"]},
                        "stepSizeSecs": step},
        "maneuvers": [maneuver_out(m) for m in sent.get("maneuvers", [])],
    }


def client_for(routes, extracted_by_text=None):
    """Fresh app + store whose pipeline serves canned (marker, response) pairs.

    extracted_by_text maps the POSTed text to front-step extractor input.
    If None, the real regex fallback runs on the posted text.
    """
    app_module.store = JobStore()

    def factory(*a, **k):
        ext = FrontStepExtractor()
        if extracted_by_text is not None:
            ext._fallback_extract = lambda t: dict(extracted_by_text[t])
        return Pipeline(extractor=ext, interpreter=RoutingInterpreter(routes),
                        explainer=MockExplainer(), gmat_runner=None)

    app_module.Pipeline = factory
    return TestClient(app_module.create_app())


def wait_for_job(client, jid, timeout_s=120):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        time.sleep(0.5)
        last = client.get("/api/experiments/%s" % jid).json()
        if last.get("status") in ("success", "failed"):
            return last
    raise AssertionError("job %s did not finish: %s" % (jid, last))


def run_text(client, text, timeout_s=120):
    jid = client.post("/api/experiments", json={"text": text}).json()["id"]
    return wait_for_job(client, jid, timeout_s)


def assert_explained(error, stage=None, code=None):
    assert isinstance(error, dict), error
    if stage is not None:
        assert error.get("stage") == stage, error
    if code is not None:
        assert error.get("code") == code, error
    assert isinstance(error.get("message"), str) and error["message"], error
    assert isinstance(error.get("explanation"), str) and error["explanation"], error
    details = error.get("details") or {}
    assert isinstance(details.get("explanation"), str) and details["explanation"], error
    return error
