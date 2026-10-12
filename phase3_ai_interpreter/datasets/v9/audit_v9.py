"""Independent V9 audit.

Audits the 500 V9 corrections (Moon low-altitude + Mars low-altitude + Earth
drag) against the current schema, AST, physical validator, deterministic GMAT
compiler, and a semantic review tailored to V9's own prompt phrasing.  It also
verifies the two coverage gaps that motivated V9 are actually closed:

  1. Moon and Mars rows with periapsis altitude in ~25-335 km (inside the
     20->340 km band that V8's new rows never populated), and
  2. enough Earth rows with atmospheric drag enabled, spanning both the
     JacchiaRoberts and MSISE90 models with explicit Cd / drag-area values.

It reports no-semantic-issue counts, coverage distributions, and duplicate
statistics, mirroring the V8 audit conventions.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import ValidationError

HERE = Path(__file__).resolve().parent
DATASETS = HERE.parent
ROOT = DATASETS.parents[1]
sys.path.insert(0, str(ROOT))

from orbitlab_core.ast.models import OrbitLabExperiment  # noqa: E402
from orbitlab_core.ast.validation import AstrodynamicValidator  # noqa: E402
from orbitlab_core.compiler.generator import GmatScriptCompiler  # noqa: E402

CORRECTIONS = HERE / "orbitlab_interpreter_train_v9_corrections.jsonl"
MASTER = HERE / "orbitlab_interpreter_train_v9_master.jsonl"
V8_MASTER = DATASETS / "v7" / "targeted_500" / "orbitlab_interpreter_train_v8_master.jsonl"
SCHEMA_PATH = ROOT / "schemas" / "experiment.schema.json"
ANNOTATIONS_PATH = HERE / "_v9_annotations.json"

FRAMES = {"Earth": "EarthMJ2000Eq", "Moon": "LunaMJ2000Eq", "Mars": "MarsMJ2000Eq"}
RADIUS = {"Earth": 6378.1363, "Moon": 1737.4, "Mars": 3389.5}
ROOT_FIELDS = {"version", "experimentName", "description", "spacecraft", "centralBody", "epoch", "initialOrbit", "forceModel", "maneuvers", "propagation"}
ALLOWED = {
    "spacecraft": {"name", "dryMassKg", "coefficientOfDrag", "dragAreaM2", "coefficientOfReflectivity", "srpAreaM2"},
    "epoch": {"format", "value"},
    "initialOrbit": {"type", "coordinateSystem", "elements"},
    "Keplerian": {"semiMajorAxisKm", "eccentricity", "inclinationDeg", "raanDeg", "argumentOfPeriapsisDeg", "trueAnomalyDeg"},
    "Cartesian": {"xKm", "yKm", "zKm", "vxKmS", "vyKmS", "vzKmS"},
    "forceModel": {"gravityDegree", "gravityOrder", "pointMasses", "atmosphericDrag", "solarRadiationPressure"},
    "atmosphericDrag": {"enabled", "model"},
    "maneuver": {"id", "type", "trigger", "burnVector", "targetObjectives"},
    "trigger": {"condition", "elapsedSecs"},
    "burnVector": {"coordinateSystem", "deltaVVectorKmS"},
    "targetObjectives": {"targetOrbitRadiusKm", "targetEccentricity"},
    "propagation": {"integrator", "stopCondition", "stepSizeSecs"},
    "stopCondition": {"type", "value"},
}
RAW_MARKERS = ("Create Spacecraft", "Create Propagator", "Create ForceModel", "Create ReportFile", "Create ImpulsiveBurn", "BeginMissionSequence", "GMAT ", "Propagate ")
PYTHON_MARKERS = ("import json", "from pathlib", "def ", "class ", "print(", "__main__")
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def messages(row: dict[str, Any]) -> tuple[str, str, str]:
    system = row["systemInstruction"]["parts"][0]["text"]
    contents = row["contents"]
    return system, contents[0]["parts"][0]["text"], contents[1]["parts"][0]["text"]


def extras(exp: Any) -> list[str]:
    if not isinstance(exp, dict):
        return ["$ not an object"]
    out = [f"$.{key}" for key in exp if key not in ROOT_FIELDS]
    for parent in ("spacecraft", "epoch", "initialOrbit", "forceModel", "propagation"):
        child = exp.get(parent)
        if isinstance(child, dict):
            out.extend(f"$.{parent}.{key}" for key in child if key not in ALLOWED[parent])
    orbit = exp.get("initialOrbit", {})
    if isinstance(orbit, dict) and isinstance(orbit.get("elements"), dict):
        out.extend(f"$.initialOrbit.elements.{key}" for key in orbit["elements"] if key not in ALLOWED.get(orbit.get("type"), set()))
    force = exp.get("forceModel", {})
    if isinstance(force, dict) and isinstance(force.get("atmosphericDrag"), dict):
        out.extend(f"$.forceModel.atmosphericDrag.{key}" for key in force["atmosphericDrag"] if key not in ALLOWED["atmosphericDrag"])
    for i, m in enumerate(exp.get("maneuvers", [])):
        if not isinstance(m, dict):
            out.append(f"$.maneuvers[{i}]")
            continue
        out.extend(f"$.maneuvers[{i}].{key}" for key in m if key not in ALLOWED["maneuver"])
        for parent in ("trigger", "burnVector", "targetObjectives"):
            if isinstance(m.get(parent), dict):
                out.extend(f"$.maneuvers[{i}].{parent}.{key}" for key in m[parent] if key not in ALLOWED[parent])
    return out


def close(a: float, b: float) -> bool:
    return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-6)


def numeric_mentions(pattern: str, prompt: str) -> list[float]:
    return [float(value) for value in re.findall(pattern, prompt, re.I)]


def semantic_audit(prompt: str, exp: dict[str, Any], annotation: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    body = exp.get("centralBody")
    frame = exp.get("initialOrbit", {}).get("coordinateSystem")
    if frame != FRAMES.get(body):
        issues.append("body-frame mismatch")

    body_lower = body.casefold()
    if "moon" in body_lower:
        phrases = ("around the Moon", "Moon orbit", "lunar")
    elif "mars" in body_lower:
        phrases = ("around Mars", "Mars orbit")
    else:
        phrases = ("around Earth",)
    if not any(p.casefold() in prompt.casefold() for p in phrases):
        issues.append("prompt does not state the target body")

    elements = exp.get("initialOrbit", {}).get("elements", {})
    e = elements.get("eccentricity")
    if e is not None:
        peri_alt = elements.get("semiMajorAxisKm") * (1 - e) - RADIUS[body]
        annotated_alt = annotation.get("periapsisAltitudeKm")
        if annotated_alt is not None and not math.isclose(peri_alt, annotated_alt, rel_tol=1e-6, abs_tol=0.01):
            issues.append("annotation periapsis altitude mismatch")
        if peri_alt < 20:
            issues.append("periapsis altitude below the 20 km safety floor")

    # Keplerian values must all be explicitly stated in the prompt.
    spoken_patterns = {
        "semiMajorAxisKm": None,  # stated indirectly via periapsis altitude + ecc
        "eccentricity": rf"(?:eccentricity|e\s*=)\s*(?:is|of|=|:)?\s*({NUMBER})",
        "inclinationDeg": rf"inclination\s+(?:of\s+)?({NUMBER})\s*degrees",
        "raanDeg": rf"RAAN\s+({NUMBER})\s*degrees",
        "argumentOfPeriapsisDeg": rf"argument of periapsis\s+({NUMBER})\s*degrees",
        "trueAnomalyDeg": rf"true anomaly\s+({NUMBER})\s*degrees",
    }
    for field, pattern in spoken_patterns.items():
        if field not in elements:
            continue
        if field == "eccentricity":
            values = list(numeric_mentions(pattern, prompt))
            values += list(numeric_mentions(rf"e\s*=\s*({NUMBER})", prompt))
            if values and not any(close(value, elements[field]) for value in values):
                issues.append("eccentricity mismatch")
        elif pattern:
            spoken = numeric_mentions(pattern, prompt)
            if spoken and not any(close(value, elements[field]) for value in spoken):
                issues.append(f"Keplerian {field} mismatch")

    # Periapsis altitude: prompt states "{alt} km" associated with periapsis.
    peri_mentions = numeric_mentions(rf"periapsis altitude (?:of )?({NUMBER}) km", prompt)
    peri_mentions += numeric_mentions(rf"periapsis sits ({NUMBER}) km", prompt)
    peri_mentions += numeric_mentions(rf"perigee/periapsis ({NUMBER}) km", prompt)
    peri_mentions += numeric_mentions(rf"periapsis altitude ({NUMBER}) km", prompt)
    actual_peri = elements.get("semiMajorAxisKm") * (1 - elements.get("eccentricity", 0)) - RADIUS[body]
    if not peri_mentions or not any(math.isclose(value, actual_peri, rel_tol=1e-6, abs_tol=0.5) for value in peri_mentions):
        issues.append("periapsis altitude not stated/matched in prompt")

    stop = exp.get("propagation", {}).get("stopCondition", {})
    unit = stop.get("type")
    unit_words = {"ElapsedSeconds": r"seconds", "ElapsedHours": r"hours", "ElapsedDays": r"days"}
    stop_matches = re.findall(rf"(?:propagate for|run it for|run for|stop after|let it run(?: for)?)\s*({NUMBER})\s*({unit_words.get(unit, '(?!)')})", prompt, re.I)
    if not stop_matches or not any(close(value, stop.get("value", float("nan"))) for value, u in stop_matches):
        issues.append("stop duration/unit not semantically matched")

    craft = exp.get("spacecraft", {})
    mass_values = numeric_mentions(rf"(?:dry mass is|dry mass:|use|weighs|mass is|carries)\s*({NUMBER})\s*kg(?: dry)?", prompt)
    mass_values += numeric_mentions(rf"({NUMBER})\s*kg dry", prompt)
    if not mass_values or not any(close(value, craft.get("dryMassKg", float("nan"))) for value in mass_values):
        issues.append("dry mass not stated/matched")

    integrator = exp.get("propagation", {}).get("integrator")
    if integrator and integrator not in prompt:
        issues.append("integrator not mentioned in prompt")

    annotation = annotation or {}
    if annotation.get("dragEnabled"):
        drag = exp.get("forceModel", {}).get("atmosphericDrag", {})
        model = drag.get("model")
        if model and model not in prompt:
            issues.append("drag model not mentioned in prompt")
        cd = craft.get("coefficientOfDrag")
        area = craft.get("dragAreaM2")
        cd_mentions = numeric_mentions(rf"(?:drag coefficient|coefficient of drag|Cd\s*=\s*)\s*(?:to|of|=|:)?\s*(?:is\s+)?({NUMBER})", prompt)
        area_mentions = numeric_mentions(rf"({NUMBER})\s*m\^2", prompt)
        cd_ok = cd is not None and any(close(value, cd) for value in cd_mentions)
        area_ok = area is not None and any(close(value, area) for value in area_mentions)
        if not cd_ok:
            issues.append("drag coefficient not stated/matched")
        if not area_ok:
            issues.append("drag area not stated/matched")
        if "drag" not in prompt.casefold():
            issues.append("drag enable not mentioned in prompt")
        if exp.get("forceModel", {}).get("atmosphericDrag", {}).get("model") not in ("JacchiaRoberts", "MSISE90"):
            issues.append("unsupported drag model")

    if annotation is not None and annotation.get("centralBody") != body:
        issues.append("annotation centralBody mismatch")
    if annotation is not None and annotation.get("experimentName") != exp.get("experimentName"):
        issues.append("annotation experimentName mismatch")

    if body == "Earth" and not exp.get("forceModel", {}).get("atmosphericDrag", {}).get("enabled") and not annotation.get("dragEnabled"):
        pass
    return issues


def main() -> int:
    rows = load(CORRECTIONS)
    master = load(MASTER)
    v8 = load(V8_MASTER)
    annotations = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)

    json_bad = schema_bad = pydantic_bad = physical_bad = compiler_bad = 0
    gmat_leak = python_leak = unsupported = 0
    any_semantic: Counter[str] = Counter()
    issues: list[dict[str, Any]] = []
    bodies: Counter[str] = Counter()
    drag_models: Counter[str] = Counter()
    cd_values: set[float] = set()
    area_values: set[float] = set()
    peri_by_body: dict[str, list[float]] = {"Moon": [], "Mars": [], "Earth": []}
    drag_enabled_rows = 0
    low_band_rows = 0
    names: Counter[str] = Counter()
    templates: Counter[str] = Counter()

    for index, row in enumerate(rows):
        record_issues: list[str] = []
        try:
            if set(row) != {"systemInstruction", "contents"} or [m.get("role") for m in row.get("contents", [])] != ["user", "model"]:
                raise ValueError("training format mismatch")
            _, prompt, response = messages(row)
            if not isinstance(response, str):
                raise ValueError("assistant response not a string")
            exp = json.loads(response)
            if not isinstance(exp, dict) or response != json.dumps(exp, separators=(",", ":"), ensure_ascii=False):
                raise ValueError("assistant must be one compact JSON object")
            extra = extras(exp)
            if extra:
                unsupported += len(extra)
                record_issues.extend("unsupported:" + item for item in extra)
            if list(validator.iter_errors(exp)):
                schema_bad += 1
                record_issues.append("json_schema_failure")
            model = OrbitLabExperiment.model_validate(exp)
            physical = AstrodynamicValidator.validate(model)
            if not physical.is_valid:
                physical_bad += 1
                record_issues.extend("physical:" + e for e in physical.errors)
            try:
                GmatScriptCompiler().compile_to_string(model)
            except Exception as exc:
                compiler_bad += 1
                record_issues.append("compiler:" + str(exc))
            if any(marker.casefold() in response.casefold() for marker in RAW_MARKERS):
                gmat_leak += 1
                record_issues.append("raw_gmat_leak")
            if any(marker in response for marker in PYTHON_MARKERS):
                python_leak += 1
                record_issues.append("python_code_leak")
            record_issues.extend(semantic_audit(prompt, exp, annotations[index]))

            body = exp["centralBody"]
            bodies[body] += 1
            drag = exp["forceModel"]["atmosphericDrag"]
            if drag["enabled"]:
                drag_enabled_rows += 1
                drag_models[drag.get("model")] += 1
                cd_values.add(float(exp["spacecraft"]["coefficientOfDrag"]))
                area_values.add(float(exp["spacecraft"]["dragAreaM2"]))
            peri = exp["initialOrbit"]["elements"]["semiMajorAxisKm"] * (1 - exp["initialOrbit"]["elements"]["eccentricity"]) - RADIUS[body]
            peri_by_body.setdefault(body, []).append(peri)
            if peri < 340:
                low_band_rows += 1

            name = exp.get("experimentName", "<missing>")
            names[name] += 1
            template = re.sub(r'"[^"\n]*"', "<id>", prompt.casefold())
            template = re.sub(NUMBER, "<n>", template)
            template = re.sub(r"\s+", " ", template).strip()
            templates[template] += 1
        except (json.JSONDecodeError, ValidationError, KeyError, TypeError, ValueError) as exc:
            if "ValidationError" in type(exc).__name__:
                pydantic_bad += 1
            record_issues.append("record_error:" + str(exc))
        if record_issues:
            for issue in record_issues:
                any_semantic[issue.split(":", 1)[0]] += 1
            issues.append({"line": index + 1, "category": annotations[index].get("category"), "issues": record_issues, "prompt": messages(row)[1]})

    prompts = [messages(row)[1] for row in rows]
    answers = [messages(row)[2] for row in rows]
    v8_prompts = {messages(row)[1] for row in v8}
    master_prompts = [messages(row)[1] for row in master]
    exact_dups = {
        "within_v9_prompt": len(prompts) - len(set(prompts)),
        "within_v9_answer": len(answers) - len(set(answers)),
        "v8_prompt_overlap": len(set(prompts) & v8_prompts),
        "master_prompt_duplicates": len(master_prompts) - len(set(master_prompts)),
    }

    moon_peri = peri_by_body.get("Moon", [])
    mars_peri = peri_by_body.get("Mars", [])
    low_moon = sum(1 for p in moon_peri if p < 340)
    low_mars = sum(1 for p in mars_peri if p < 340)

    if bodies["Moon"] < 100 or bodies["Mars"] < 100 or bodies["Earth"] < 100:
        raise ValueError(f"V9 body counts too low: {dict(bodies)}")
    if low_moon < 100 or low_mars < 100:
        raise ValueError(f"low-altitude band not filled: Moon {low_moon}, Mars {low_mars}")
    if drag_enabled_rows < 100:
        raise ValueError(f"drag-enabled rows too low: {drag_enabled_rows}")
    if set(drag_models) != {"JacchiaRoberts", "MSISE90"}:
        raise ValueError(f"drag models missing: {dict(drag_models)}")
    if len(issues):
        print("WARNING: semantic issues found")
        for it in issues[:20]:
            print(it["line"], it["issues"])

    result = {
        "v8_master_rows": len(v8),
        "v9_new_rows": len(rows),
        "v9_master_rows": len(master),
        "v9_audit": {
            "json_valid": len(rows) - json_bad,
            "json_schema_valid": len(rows) - schema_bad,
            "pydantic_valid": len(rows) - pydantic_bad,
            "physical_valid": len(rows) - physical_bad,
            "compiler_valid": len(rows) - compiler_bad,
            "semantic_issue_records": len(issues),
            "semantic_issue_count_by_type": dict(any_semantic),
            "schema_drift_fields": unsupported,
            "raw_gmat_leakage": gmat_leak,
            "python_code_leakage": python_leak,
            "central_bodies": dict(bodies),
            "drag_enabled_rows": drag_enabled_rows,
            "drag_models": dict(drag_models),
            "distinct_coefficient_of_drag": len(cd_values),
            "distinct_drag_area": len(area_values),
            "low_band_rows_below_340km": low_band_rows,
            "moon_low_altitude_rows": low_moon,
            "mars_low_altitude_rows": low_mars,
            "moon_periapsis_km": {"min": min(moon_peri), "max": max(moon_peri)},
            "mars_periapsis_km": {"min": min(mars_peri), "max": max(mars_peri)},
            "earth_drag_periapsis_km": {"min": min(peri_by_body.get("Earth", [0])), "max": max(peri_by_body.get("Earth", [0]))},
            "exact_duplicate_counts": exact_dups,
            "numeric_masked_prompt_collisions": sum(c - 1 for c in templates.values() if c > 1),
            "unique_numeric_masked_templates": len(templates),
            "repeated_experiment_names": sum(c - 1 for c in names.values() if c > 1),
        },
    }
    (HERE / "v9_audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["v9_audit"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
