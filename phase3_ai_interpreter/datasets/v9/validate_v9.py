"""Validate the V9 corrections and combined V9 master.

The V9 corrections are 500 targeted records that close the two V8 coverage gaps:
  1. Low periapsis altitude (about 25-335 km) on the Moon and Mars.
  2. Earth atmospheric-drag coverage across both drag models with explicit
     spacecraft drag coefficients and drag areas.

This script verifies, for every record in both the corrections and the combined
master:
  - Gemini message structure and a single consistent system instruction,
  - compact canonical JSON model answer with no raw GMAT or code leakage,
  - unknown / unsupported field detection,
  - JSON-schema validity,
  - Pydantic AST load,
  - astrodynamic physical validity,
  - deterministic GMAT compilation,

and additionally enforces the V9 invariants:
  - the V9 master is the verbatim concatenation of the preserved V8 master
    rows followed by the V9 corrections rows,
  - the corrections contain Moon and Mars low-periapsis rows inside the safe
    band and Earth drag-enabled rows,
  - at least 100 Moon, 100 Mars and 100 Earth rows are added.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
DATASETS = HERE.parent
ROOT = DATASETS.parents[1]
sys.path.insert(0, str(ROOT))

from orbitlab_core.ast.models import OrbitLabExperiment  # noqa: E402
from orbitlab_core.ast.validation import AstrodynamicValidator  # noqa: E402
from orbitlab_core.compiler.generator import GmatScriptCompiler  # noqa: E402
from orbitlab_core.constants import (  # noqa: E402
    MIN_OTHER_BODY_PERIAPSIS_ALTITUDE_KM,
    MIN_PERIAPSIS_ALTITUDE_KM,
)

V8_MASTER = DATASETS / "v7" / "targeted_500" / "orbitlab_interpreter_train_v8_master.jsonl"
CORRECTIONS = HERE / "orbitlab_interpreter_train_v9_corrections.jsonl"
MASTER = HERE / "orbitlab_interpreter_train_v9_master.jsonl"
SCHEMA_PATH = ROOT / "schemas" / "experiment.schema.json"

FRAMES = {"Earth": "EarthMJ2000Eq", "Moon": "LunaMJ2000Eq", "Mars": "MarsMJ2000Eq"}
ROOT_KEYS = {"version", "experimentName", "description", "spacecraft", "centralBody", "epoch", "initialOrbit", "forceModel", "maneuvers", "propagation"}
VALID_ROOT_FIELDS = {
    "spacecraft": {"name", "dryMassKg", "coefficientOfDrag", "dragAreaM2", "coefficientOfReflectivity", "srpAreaM2"},
    "epoch": {"format", "value"}, "initialOrbit": {"type", "coordinateSystem", "elements"},
    "forceModel": {"gravityDegree", "gravityOrder", "pointMasses", "atmosphericDrag", "solarRadiationPressure"},
    "propagation": {"integrator", "stopCondition", "stepSizeSecs"},
}
VALID_NESTED = {
    "Keplerian": {"semiMajorAxisKm", "eccentricity", "inclinationDeg", "raanDeg", "argumentOfPeriapsisDeg", "trueAnomalyDeg"},
    "Cartesian": {"xKm", "yKm", "zKm", "vxKmS", "vyKmS", "vzKmS"},
    "atmosphericDrag": {"enabled", "model"},
    "maneuver": {"id", "type", "trigger", "burnVector", "targetObjectives"},
    "trigger": {"condition", "elapsedSecs"}, "burnVector": {"coordinateSystem", "deltaVVectorKmS"},
    "targetObjectives": {"targetOrbitRadiusKm", "targetEccentricity"}, "stopCondition": {"type", "value"},
}
RAW = ("Create Spacecraft", "Create Propagator", "Create ForceModel", "Create ReportFile", "Create ImpulsiveBurn", "BeginMissionSequence", "GMAT ", "Propagate ")
PYTHON = ("import json", "from pathlib", "def ", "class ", "print(", "__main__")

EXPECTED_NEW = {"moon_low_altitude": 175, "mars_low_altitude": 175, "earth_drag": 150}


def read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8-sig").splitlines() if x.strip()]


def msg(row: dict[str, Any]) -> tuple[str, str, str]:
    if set(row) != {"systemInstruction", "contents"}:
        raise ValueError("Gemini format keys invalid")
    cont = row["contents"]
    if len(cont) != 2 or [x.get("role") for x in cont] != ["user", "model"]:
        raise ValueError("Gemini roles invalid")
    return row["systemInstruction"]["parts"][0]["text"], cont[0]["parts"][0]["text"], cont[1]["parts"][0]["text"]


def fields(exp: dict[str, Any]) -> list[str]:
    out = [f"$.{k}" for k in exp if k not in ROOT_KEYS]
    for parent, allowed in VALID_ROOT_FIELDS.items():
        if isinstance(exp.get(parent), dict):
            out.extend(f"$.{parent}.{k}" for k in exp[parent] if k not in allowed)
    orbit = exp.get("initialOrbit", {})
    if isinstance(orbit, dict) and isinstance(orbit.get("elements"), dict):
        out.extend(f"$.initialOrbit.elements.{k}" for k in orbit["elements"] if k not in VALID_NESTED.get(orbit.get("type"), set()))
    force = exp.get("forceModel", {})
    if isinstance(force, dict) and isinstance(force.get("atmosphericDrag"), dict):
        out.extend(f"$.forceModel.atmosphericDrag.{k}" for k in force["atmosphericDrag"] if k not in VALID_NESTED["atmosphericDrag"])
    for i, maneuver in enumerate(exp.get("maneuvers", [])):
        if not isinstance(maneuver, dict):
            out.append(f"$.maneuvers[{i}] not an object")
            continue
        out.extend(f"$.maneuvers[{i}].{k}" for k in maneuver if k not in VALID_NESTED["maneuver"])
        for parent in ("trigger", "burnVector", "targetObjectives"):
            if isinstance(maneuver.get(parent), dict):
                out.extend(f"$.maneuvers[{i}].{parent}.{k}" for k in maneuver[parent] if k not in VALID_NESTED[parent])
    prop = exp.get("propagation", {})
    if isinstance(prop, dict) and isinstance(prop.get("stopCondition"), dict):
        out.extend(f"$.propagation.stopCondition.{k}" for k in prop["stopCondition"] if k not in VALID_NESTED["stopCondition"])
    return out


def verify(rows: list[dict[str, Any]], schema_validator: Any) -> dict[str, Any]:
    json_ok = schema_ok = pydantic_ok = physics_ok = compiler_ok = 0
    unknowns = raw = py = 0
    problems: list[dict[str, Any]] = []
    bodies: Counter[str] = Counter()
    orbit_types: Counter[str] = Counter()
    stops: Counter[str] = Counter()
    drag_enabled = 0
    low_band = 0
    for index, row in enumerate(rows):
        issues: list[str] = []
        try:
            _, prompt, response = msg(row)
            exp = json.loads(response)
            if not isinstance(exp, dict) or response != json.dumps(exp, ensure_ascii=False, separators=(",", ":")):
                raise ValueError("not a single compact JSON object")
            json_ok += 1
            unknown = fields(exp)
            if unknown:
                unknowns += len(unknown)
                issues.extend("unsupported " + x for x in unknown)
            schema_errors = list(schema_validator.iter_errors(exp))
            if schema_errors:
                issues.append("schema:" + schema_errors[0].message)
            else:
                schema_ok += 1
            model = OrbitLabExperiment.model_validate(exp)
            pydantic_ok += 1
            physical = AstrodynamicValidator.validate(model)
            if physical.is_valid:
                physics_ok += 1
            else:
                issues.extend("physical:" + x for x in physical.errors)
            GmatScriptCompiler().compile_to_string(model)
            compiler_ok += 1
            if any(x.casefold() in response.casefold() for x in RAW):
                raw += 1
                issues.append("raw GMAT leakage")
            if any(x in response for x in PYTHON):
                py += 1
                issues.append("Python/code leakage")
            if exp.get("initialOrbit", {}).get("coordinateSystem") != FRAMES[exp.get("centralBody")]:
                issues.append("body/frame mismatch")
            bodies[exp.get("centralBody", "<missing>")] += 1
            orbit_types[exp["initialOrbit"]["type"]] += 1
            stops[exp["propagation"]["stopCondition"]["type"]] += 1
            if exp["forceModel"]["atmosphericDrag"]["enabled"]:
                drag_enabled += 1
            radius = {"Earth": 6378.1363, "Moon": 1737.4, "Mars": 3389.5}[exp["centralBody"]]
            elems = exp["initialOrbit"]["elements"]
            if exp["initialOrbit"]["type"] == "Keplerian":
                alt_p = elems["semiMajorAxisKm"] * (1.0 - elems["eccentricity"]) - radius
                if alt_p < 340:
                    low_band += 1
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            issues.append("exception:" + str(exc))
        if issues:
            problems.append({"line": index + 1, "issues": issues})
    return {
        "counts": {"examples": len(rows), "json": json_ok, "schema": schema_ok, "pydantic": pydantic_ok, "physical": physics_ok, "compiler": compiler_ok},
        "unsupported_fields": unknowns, "raw_gmat": raw, "python_leakage": py, "problems": problems,
        "bodies": dict(bodies), "orbit_types": dict(orbit_types), "stops": dict(stops),
        "drag_enabled": drag_enabled, "low_band_rows": low_band,
    }


def main() -> int:
    v8 = read(V8_MASTER)
    corrections = read(CORRECTIONS)
    master = read(MASTER)

    if len(v8) != 3300:
        raise ValueError(f"V8 master must contain 3300 rows; got {len(v8)}")
    if len(corrections) != 500:
        raise ValueError(f"V9 corrections must contain 500 rows; got {len(corrections)}")
    if len(master) != len(v8) + len(corrections):
        raise ValueError("V9 master count must equal V8 master + V9 corrections")

    if master[: len(v8)] != v8:
        raise ValueError("V9 master does not preserve the V8 master rows (order or content changed)")
    if master[len(v8):] != corrections:
        raise ValueError("V9 master does not append the V9 corrections rows verbatim")

    schema_validator = jsonschema.Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

    new_check = verify(corrections, schema_validator)
    master_check = verify(master, schema_validator)

    if new_check["counts"]["schema"] != 500 or new_check["problems"]:
        raise ValueError("V9 corrections have validation problems")

    v8_rows = len(v8)
    v9_master_problems = [p for p in master_check["problems"] if p["line"] > v8_rows]
    inherited_v8_rows_without_force_model = sum(
        1 for r in v8 if "forceModel" not in json.loads(msg(r)[2])
    )
    if v9_master_problems:
        raise ValueError(f"V9 master contains {len(v9_master_problems)} problems in the V9 segment")

    ann_moon = new_check["bodies"].get("Moon", 0)
    ann_mars = new_check["bodies"].get("Mars", 0)
    ann_earth = new_check["bodies"].get("Earth", 0)
    if ann_moon < 100 or ann_mars < 100 or ann_earth < 100:
        raise ValueError(f"V9 must add at least 100 rows per body; got Moon {ann_moon}, Mars {ann_mars}, Earth {ann_earth}")

    if new_check["drag_enabled"] < 100:
        raise ValueError(f"V9 must add at least 100 Earth drag-enabled rows; got {new_check['drag_enabled']}")
    if new_check["low_band_rows"] < 200:
        raise ValueError(f"V9 must add at least 200 rows below 340 km periapsis; got {new_check['low_band_rows']}")

    drag_models: Counter[str] = Counter()
    for r in corrections:
        exp = json.loads(msg(r)[2])
        if exp["forceModel"]["atmosphericDrag"]["enabled"]:
            drag_models[exp["forceModel"]["atmosphericDrag"].get("model")] += 1
    if set(drag_models) != {"JacchiaRoberts", "MSISE90"} or min(drag_models.values()) < 10:
        raise ValueError(f"drag model variety insufficient: {dict(drag_models)}")

    stats = {
        "source_counts": {"v8_master": len(v8), "v9_new": len(corrections), "v9_master": len(master)},
        "v9_validation": {"new": new_check["counts"], "master": master_check["counts"], "new_problem_count": len(new_check["problems"]), "master_problem_count": len(master_check["problems"]), "v9_segment_problem_count": len(v9_master_problems), "inherited_v8_rows_without_force_model": inherited_v8_rows_without_force_model, "unsupported_fields": new_check["unsupported_fields"], "raw_gmat": new_check["raw_gmat"], "python_leakage": new_check["python_leakage"]},
        "coverage": {"bodies_new": new_check["bodies"], "bodies_master": master_check["bodies"], "drag_enabled_new": new_check["drag_enabled"], "low_band_new": new_check["low_band_rows"], "drag_models_new": dict(drag_models)},
    }
    (HERE / "v9_statistics.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
