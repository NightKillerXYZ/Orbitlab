"""Part A helper: build gold / faithful-model JSON for the 30 realistic cases.

For each of the 20 accept cases (R01-R20) it expands the minimal expect_json
with the canonical v11 defaults into a full, interpreter-valid experiment and
confirms Pydantic + AstrodynamicValidator + compiler accept it.

For each of the 10 reject cases (X01-X10) it builds the "faithful model
answer" (the full experiment a compliant model would produce from the request,
which the parser/validator must reject), runs the full chain, records the exact
rejection message, and picks a short stable case-insensitive substring for
expect_reason.

Writes the updated cases file (accepts: full gold expect_json; rejects:
faithful-model expect_json + expect_reason) back to the same path.

Run from: phase3_ai_interpreter/
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent          # .../v11_train/eval
V11 = HERE.parent                                # .../v11_train
PHASE = V11.parent.parent                        # .../phase3_ai_interpreter
ROOT = PHASE.parent                              # <repo root>
DATASETS = PHASE / "datasets"
CASES = DATASETS / "cases_realistic.jsonl"

sys.path.insert(0, str(PHASE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PHASE / "datasets" / "v11_train" / "eval"))

from interpreter.json_interpreter import JsonExperimentInterpreter  # noqa: E402

# ---------------------------------------------------------------------------
# Constants (mirror v11 defaults used by the generator)
# ---------------------------------------------------------------------------
with open(ROOT / "orbitlab_core" / "bodies.json", encoding="utf-8") as f:
    bodies_cfg = json.load(f)["bodies"]

COORD_SYSTEM = {
    "Earth": "EarthMJ2000Eq", "Sun": "SunMJ2000Eq", "Moon": "LunaMJ2000Eq",
    "Mars": "MarsMJ2000Eq", "Mercury": "MercuryMJ2000Eq",
    "Jupiter": "JupiterMJ2000Eq", "Venus": "VenusMJ2000Eq",
}
DEFAULT_GRAV_DEG = 4
DEFAULT_PM = ["Luna", "Sun"]
AU_KM = 149597870.691


def body_radius(body):
    return bodies_cfg[body]["radiusKm"]


def force_model(body, force_spec=None):
    if force_spec:
        deg = force_spec["deg"]
        pm = list(force_spec["pm"])
        srp = bool(force_spec["srp"])
    else:
        deg = 0 if body in ("Mercury", "Jupiter", "Sun") else DEFAULT_GRAV_DEG
        pm = [] if body == "Sun" else list(DEFAULT_PM)
        srp = True
    return {
        "gravityDegree": deg,
        "gravityOrder": deg,
        "pointMasses": pm,
        "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
        "solarRadiationPressure": srp,
    }


def parse_user(text: str) -> dict:
    """Extract request parameters from the realistic-case user text."""
    get = lambda pat, grp=1, cast=float: cast(re.search(pat, text).group(grp))  # noqa: E731
    body = re.search(r"around (\w+)", text).group(1)
    mass = get(r"use ([0-9.]+) kg for the dry mass")
    inc = get(r"inclination ([0-9.]+) degrees")
    raan = get(r"RAAN ([0-9.]+) degrees")
    aop = get(r"argument of periapsis ([0-9.]+) degrees")
    ta = get(r"true anomaly ([0-9.]+) degrees")
    dur, unit = get(r"propagate for ([0-9.]+) (days|hours)", 1), (re.search(r"propagate for ([0-9.]+) (days|hours)", text).group(2))
    integ = get(r"integrate with (\w+)", 1, str)
    if " circular orbit at an altitude of " in text:
        form, h = "circ", get(r"circular orbit at an altitude of ([0-9.]+) km")
        e = 0.0
    elif " periapsis altitude of " in text:
        form = "peri"
        h = get(r"periapsis altitude of ([0-9.]+) km")
        e = get(r"periapsis altitude of [0-9.]+ km,\s*eccentricity ([0-9.]+)")
    elif " AU " in text:
        # e.g. "with SMA 0.387 AU (57894375.957 km) from the centre, eccentricity ..."
        form = "au"
        x = get(r"with SMA ([0-9.]+) AU")
        e = get(r"from the centre,\s*eccentricity ([0-9.]+)")
        sma = round(x * AU_KM, 3)
        h = None
    elif " with SMA " in text:
        form = "sma"
        sma = get(r"with SMA ([0-9.]+) km")
        e = get(r"with SMA [0-9.]+ km,\s*eccentricity ([0-9.]+)")
        h = None
    else:
        raise ValueError("unknown orbit phrasing")
    return {"body": body, "mass": mass, "inc": inc, "raan": raan, "aop": aop,
            "ta": ta, "dur": dur, "unit": unit, "integ": integ,
            "form": form, "h": h, "e": e, "sma": locals().get("sma")}


def compute_sma(p):
    r = body_radius(p["body"])
    if p["form"] == "circ":
        return r + p["h"]
    if p["form"] == "peri":
        return round((r + p["h"]) / (1.0 - p["e"]), 3)
    if p["form"] == "sma":
        return p["sma"]
    raise ValueError(p["form"])


def faithful_model(case: dict) -> dict:
    p = parse_user(case["user_text"])
    body = p["body"]
    sma = compute_sma(p)
    stop = {"type": "ElapsedHours" if p["unit"] == "hours" else "ElapsedDays",
            "value": float(p["dur"])}
    return {
        "version": "1.0",
        "experimentName": case["id"],
        "spacecraft": {
            "name": "SC" + case["id"],
            "dryMassKg": float(p["mass"]),
            "coefficientOfDrag": 2.2,
            "dragAreaM2": 1.0,
            "coefficientOfReflectivity": 1.8,
            "srpAreaM2": 1.0,
        },
        "centralBody": body,
        "epoch": {"format": "UTCGregorian", "value": "01 Jan 2026 12:00:00.000"},
        "initialOrbit": {
            "type": "Keplerian",
            "coordinateSystem": COORD_SYSTEM[body],
            "elements": {
                "semiMajorAxisKm": float(sma),
                "eccentricity": float(p["e"]),
                "inclinationDeg": float(p["inc"]),
                "raanDeg": float(p["raan"]),
                "argumentOfPeriapsisDeg": float(p["aop"]),
                "trueAnomalyDeg": float(p["ta"]),
            },
        },
        "forceModel": force_model(body),
        "maneuvers": [],
        "propagation": {
            "integrator": p["integ"],
            "stopCondition": stop,
            "stepSizeSecs": 60.0,
        },
    }


def gold_from_expect(case: dict) -> dict:
    """Expand an accept case's minimal expect_json with v11 defaults."""
    exp = case["expect_json"]
    body = exp["centralBody"]
    elem = exp["initialOrbit"]["elements"]
    sc_name = "SC" + case["id"]
    return {
        "version": "1.0",
        "experimentName": case["id"],
        "spacecraft": {
            "name": sc_name,
            "dryMassKg": float(parse_user(case["user_text"])["mass"]),
            "coefficientOfDrag": 2.2,
            "dragAreaM2": 1.0,
            "coefficientOfReflectivity": 1.8,
            "srpAreaM2": 1.0,
        },
        "centralBody": body,
        "epoch": {"format": "UTCGregorian", "value": "01 Jan 2026 12:00:00.000"},
        "initialOrbit": {
            "type": "Keplerian",
            "coordinateSystem": COORD_SYSTEM[body],
            "elements": {
                "semiMajorAxisKm": elem["semiMajorAxisKm"],
                "eccentricity": elem["eccentricity"],
                "inclinationDeg": elem["inclinationDeg"],
                "raanDeg": elem["raanDeg"],
                "argumentOfPeriapsisDeg": elem["argumentOfPeriapsisDeg"],
                "trueAnomalyDeg": elem["trueAnomalyDeg"],
            },
        },
        "forceModel": force_model(body),
        "maneuvers": [],
        "propagation": {
            "integrator": exp["propagation"]["integrator"],
            "stopCondition": exp["propagation"]["stopCondition"],
            "stepSizeSecs": 60.0,
        },
    }


def main():
    cases = [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"loaded {len(cases)} cases from {CASES.name}")

    interp = JsonExperimentInterpreter()
    accepts = rejects = 0
    out_cases = []
    for c in cases:
        cid = c["id"]
        expect = c["expect"]
        if expect == "accept":
            gold = gold_from_expect(c)
            # Must be order-preserving canonical for the compiled output; validate
            res = interp.interpret(json.dumps(gold, ensure_ascii=False))
            if not res.success:
                raise SystemExit(f"{cid}: accept gold FAILED: {res.errors}")
            # sanity: elements must equal the target
            for k, v in c["expect_json"]["initialOrbit"]["elements"].items():
                if gold["initialOrbit"]["elements"][k] != v:
                    raise SystemExit(f"{cid}: gold element {k} mismatch")
            c["expect_json"] = gold
            accepts += 1
            print(f"  {cid}: accept gold OK (sma={gold['initialOrbit']['elements']['semiMajorAxisKm']})")
        else:  # reject
            model = faithful_model(c)
            raw = json.dumps(model, ensure_ascii=False)
            res = interp.interpret(raw)
            if res.success:
                raise SystemExit(f"{cid}: faithful model unexpectedly ACCEPTED")
            full = res.errors
            # keep both the faithful model JSON and the recorded reason
            c["expect_json"] = model
            c["expect_reason"] = pick_substring(cid, full)
            c["_reason_full"] = " | ".join(full)
            rejects += 1
            print(f"  {cid}: reject OK -> {c['expect_reason']!r}")
            print(f"      full: {c['_reason_full']}")

        out_cases.append(c)

    print(f"\naccepts={accepts} rejects={rejects} total={len(out_cases)}")

    # Write updated cases (drop private _reason_full? keep for report only)
    with CASES.open("w", encoding="utf-8", newline="") as f:
        for c in out_cases:
            c.pop("_reason_full", None)
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"wrote updated {CASES} (accepts=gold json, rejects=faithful json + expect_reason)")
    return 0


def min_alt_text(body: str) -> str:
    """The exact sub-string the validator emits for a below-min-altitude reject."""
    alt = bodies_cfg[body]["minPeriapsisAltKm"]
    return f"below the minimum safe altitude of {alt:.1f} km for central body '{body}'"


def soi_text(body: str) -> str:
    """The exact sub-string the validator emits for a beyond-SOI reject."""
    return f"escapes the sphere of influence of central body '{body}'"


def pick_substring(cid, full: list[str]) -> str:
    """Return a short stable case-insensitive substring unique to the reject."""
    text = "\n".join(full)
    for cand in _CANDIDATES(cid):
        if cand.lower() in text.lower():
            return cand
    raise SystemExit(f"{cid}: no candidate substring found in {text!r} body={cid.split('_')[0]}")


# Stable, wording-anchored substrings derived from bodies.json so they match the
# actual validator / pydantic messages exactly (values are not hardcoded).
def _CANDIDATES(cid: str) -> list[str]:
    if cid == "X01_Incl270":
        return ["less than or equal to 180"]                 # pydantic inclination cap
    if cid == "X02_EarthLow":
        return [min_alt_text("Earth")]
    if cid == "X03_MoonLow":
        return [min_alt_text("Moon")]
    if cid == "X04_MarsLow":
        return [min_alt_text("Mars")]
    if cid == "X05_VenusLow":
        return [min_alt_text("Venus")]
    if cid == "X06_JupiterLow":
        return [min_alt_text("Jupiter")]
    if cid == "X07_MoonSOI":
        return [soi_text("Moon")]
    if cid == "X08_MercurySOI":
        return [soi_text("Mercury")]
    if cid == "X09_SunClose":
        return [min_alt_text("Sun")]
    if cid == "X10_EarthSOI":
        return [soi_text("Earth")]
    raise SystemExit(f"{cid}: unknown reject id")


if __name__ == "__main__":
    raise SystemExit(main())
