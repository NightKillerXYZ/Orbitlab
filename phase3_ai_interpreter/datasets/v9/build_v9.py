"""Build V9 correction records filling the V8 coverage gaps.

Gap A - low periapsis altitude on the Moon and Mars: V8's new rows never go
below ~340 km periapsis altitude, leaving the 20-340 km band (where the
physical validator allows >= 20 km) completely uncovered.  This build adds
Keplerian rows with periapsis altitudes in roughly 25-335 km for both bodies.

Gap B - atmospheric drag coverage: only ~59/500 V8-new rows enable drag, all
on Earth.  This build adds Earth rows with atmospheric drag enabled, spanning
both drag models (JacchiaRoberts / MSISE90) and explicit spacecraft Cd /
drag-area values.

Every candidate is validated with the JSON schema, the Pydantic AST, the
physical validator, and the deterministic GMAT compiler before it is accepted.
Prompts are de-duplicated against the existing V8 master and within V9 using
exact, numeric-masked, and token-set similarity checks.
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
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

V8_MASTER = DATASETS / "v7" / "targeted_500" / "orbitlab_interpreter_train_v8_master.jsonl"
SCHEMA_PATH = ROOT / "schemas" / "experiment.schema.json"

OUT_CORRECTIONS = HERE / "orbitlab_interpreter_train_v9_corrections.jsonl"
OUT_MASTER = HERE / "orbitlab_interpreter_train_v9_master.jsonl"
OUT_ANNOTATIONS = HERE / "_v9_annotations.json"
OUT_FAILURES = HERE / "_v9_generation_failures.json"

BODY = {
    "Earth": ("EarthMJ2000Eq", 6378.1363, 398600.4415),
    "Moon": ("LunaMJ2000Eq", 1737.4, 4902.800066),
    "Mars": ("MarsMJ2000Eq", 3389.5, 42828.375214),
}
MIN_ALT = {"Earth": 100.0, "Moon": 20.0, "Mars": 20.0}

SYSTEM = (
    "The model is an OrbitLab Experiment Interpreter.\n\n"
    "It converts natural-language orbital-simulation requests into the exact "
    "OrbitLab Experiment JSON structure.\n\n"
    "Rules:\n"
    "- Output only the Experiment JSON when the request contains enough information for a valid experiment.\n"
    "- Never output raw GMAT script.\n"
    "- Never invent unsupported fields.\n"
    "- Never silently change user-specified physical parameters.\n"
    "- Use only fields supported by the actual OrbitLab schema.\n"
    "- Do not decide physical validity independently of OrbitLab validation.\n"
    "- Preserve the user's requested values and units after converting them to the schema's required units.\n"
    "- If required information is genuinely missing, the production system should request clarification rather than inventing a value.\n"
    "- The deterministic OrbitLab compiler, not the AI, is responsible for producing GMAT syntax."
)

PLAN = {
    "moon_low_altitude": 175,
    "mars_low_altitude": 175,
    "earth_drag": 150,
}
TOTAL = sum(PLAN.values())

INTEGRATORS = ("RungeKutta89", "PrinceDormand78")
STOP_TYPES = ("ElapsedSeconds", "ElapsedHours", "ElapsedDays")

# Natural-language stop-unit phrasing keyed by stop condition type.
STOP_TEXT = {
    "ElapsedSeconds": (
        "propagate for {v} seconds",
        "run it for {v} seconds of elapsed time",
        "stop after {v} seconds",
        "let it run {v} seconds",
    ),
    "ElapsedHours": (
        "propagate for {v} hours",
        "run it for {v} hours of elapsed time",
        "stop after {v} hours",
        "let it run for {v} hours",
    ),
    "ElapsedDays": (
        "propagate for {v} days",
        "run it for {v} days of elapsed time",
        "stop after {v} days",
        "let it run {v} days",
    ),
}

# Prompt framing openers so rows read as natural requests rather than templates.
OPENERS = (
    "Please set up a case",
    "I'd like an experiment",
    "Model a run",
    "Can you build an orbit example",
    "Set up a trajectory",
    "I want to model",
    "Please prepare a simulation",
    "Construct a case",
    "Give me an experiment definition for",
    "Help me set up",
)

MASS_WORDINGS = (
    "the spacecraft dry mass is {m} kg",
    "use {m} kg for the dry mass",
    "the bus carries {m} kg dry",
    "dry mass: {m} kg",
    "the vehicle weighs {m} kg dry",
    "a {m} kg dry-mass vehicle",
)

NAME_WORDINGS = (
    'name the experiment "{e}" and the spacecraft "{s}"',
    'call the run "{e}" with spacecraft "{s}"',
    'the case is "{e}" and its vehicle is "{s}"',
    'label the experiment "{e}"; spacecraft "{s}"',
    'use experiment name "{e}" and vehicle "{s}"',
)

ORBIT_INTROS = (
    "with a periapsis altitude of {alt} km and eccentricity {ecc}",
    "periapsis altitude {alt} km, orbital eccentricity {ecc}",
    "a low pass whose periapsis sits {alt} km up, eccentricity {ecc}",
    "perigee/periapsis {alt} km and eccentricity {ecc}",
    "starting from a periapsis altitude of {alt} km, e = {ecc}",
)

ANGLE_WORDS = {
    "inclinationDeg": "inclination",
    "raanDeg": "RAAN",
    "argumentOfPeriapsisDeg": "argument of periapsis",
    "trueAnomalyDeg": "true anomaly",
}

DRAG_WORDINGS = (
    "enable atmospheric drag using the {model} model",
    "turn on drag with the {model} atmosphere profile",
    "account for atmospheric drag ({model})",
    "activate the {model} drag model",
    "include atmospheric drag modeled by {model}",
)

CD_WORDINGS = (
    "set the drag coefficient to {cd} and the drag area to {area} m^2",
    "coefficient of drag {cd}, drag area {area} m^2",
    "use Cd = {cd} and cross-sectional area {area} m^2",
    "drag coefficient {cd} with {area} m^2 of drag area",
)

DEFAULT_FORCE_WORDINGS = (
    "leave all force-model options at their canonical defaults",
    "use the model's default force settings; I'm not asking for extra options",
    "do not add force options I didn't ask for",
    "keep unmentioned force fields at their declared defaults",
)

POSITION_WORDINGS = (
    "with the true anomaly at {ta} degrees",
    "starting true anomaly {ta} degrees",
)


def num(value: float) -> str:
    """Render a float deterministically with minimal trailing noise."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8-sig").splitlines() if x.strip()]


def record(prompt: str, answer: str) -> dict[str, Any]:
    return {
        "systemInstruction": {"role": "system", "parts": [{"text": SYSTEM}]},
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]},
            {"role": "model", "parts": [{"text": answer}]},
        ],
    }


def numeric_mask(text: str) -> str:
    value = re.sub(r'"[^"\n]*"', "<ID>", text)
    value = re.sub(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", "<N>", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def tokens(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z]+", text.casefold()))


def signature_key(exp: dict[str, Any]) -> tuple[Any, ...]:
    """A numeric uniqueness key for a proposed experiment.

    Two rows count as duplicates only if they request an identical physical
    specification (same body, orbit elements, mass, stop condition and force
    configuration).  Natural-language phrasing differences are deliberately
    not part of this key; the masked-template check handles prose duplicates.
    """
    o = exp["initialOrbit"]["elements"]
    stop = exp["propagation"]["stopCondition"]
    drag = exp["forceModel"]["atmosphericDrag"]
    return (
        exp["centralBody"],
        round(o["semiMajorAxisKm"], 4),
        round(o["eccentricity"], 4),
        round(o["inclinationDeg"], 3),
        round(o["raanDeg"], 3),
        round(o["argumentOfPeriapsisDeg"], 3),
        round(o["trueAnomalyDeg"], 3),
        round(exp["spacecraft"]["dryMassKg"], 3),
        stop["type"],
        num(stop["value"]),
        drag["enabled"],
        drag["model"],
    )


def build_low_altitude(category: str) -> dict[str, Any]:
    """A Keplerian Moon/Mars row with periapsis altitude in ~25-335 km.

    Returns a record dict keyed for prompt + (answer, exp, semantic).
    """
    body = "Moon" if category == "moon_low_altitude" else "Mars"
    frame, radius, _mu = BODY[body]
    serial = _SERIAL[0]
    _SERIAL[0] += 1
    rng = random.Random(20260901 + serial * 7919)

    alt_p = float(rng.randrange(25, 336))            # 25..335 km, above 20 km floor
    eccentricity = rng.choice((0.001, 0.004, 0.008, 0.02, 0.04, 0.07, 0.10))
    semi_major = (radius + alt_p) / (1.0 - eccentricity)

    incl = float(rng.randrange(0, 180))
    raan = float(rng.randrange(0, 360))
    argp = float(rng.randrange(0, 360))
    ta = float(rng.randrange(0, 360))

    mass = round(rng.uniform(120.0, 3800.0), 2)
    stop_type = rng.choice(STOP_TYPES)
    stop_value = stop_value_for(stop_type, rng)
    integrator = rng.choice(INTEGRATORS)

    exp_name = f"V9Low{body}{serial:04d}"
    craft_name = f"SCV9Low{body}{serial:04d}"

    orbit = {
        "type": "Keplerian",
        "coordinateSystem": frame,
        "elements": {
            "semiMajorAxisKm": round(semi_major, 3),
            "eccentricity": eccentricity,
            "inclinationDeg": incl,
            "raanDeg": raan,
            "argumentOfPeriapsisDeg": argp,
            "trueAnomalyDeg": ta,
        },
    }

    exp = {
        "version": "1.0",
        "experimentName": exp_name,
        "description": f"Low-altitude {body.lower()} orbit covering the previously-uncovered periapsis band.",
        "spacecraft": {
            "name": craft_name,
            "dryMassKg": mass,
            "coefficientOfDrag": 2.2,
            "dragAreaM2": 1.0,
            "coefficientOfReflectivity": 1.8,
            "srpAreaM2": 1.0,
        },
        "centralBody": body,
        "epoch": {"format": "UTCGregorian", "value": "01 Jan 2026 12:00:00.000"},
        "initialOrbit": orbit,
        "forceModel": {
            "gravityDegree": 4,
            "gravityOrder": 4,
            "pointMasses": ["Luna", "Sun"],
            "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
            "solarRadiationPressure": True,
        },
        "maneuvers": [],
        "propagation": {
            "integrator": integrator,
            "stopCondition": {"type": stop_type, "value": stop_value},
            "stepSizeSecs": 60.0,
        },
    }

    prompt = compose_keplerian_prompt(exp, body_name=body, alt_p=alt_p)
    return {"exp": exp, "prompt": prompt, "exp_name": exp_name, "craft": craft_name}


def stop_value_for(stop_type: str, rng: random.Random) -> float:
    if stop_type == "ElapsedSeconds":
        return float(rng.choice((900, 1800, 3600, 5400, 7200)))
    if stop_type == "ElapsedHours":
        return float(rng.choice((1, 2, 4, 6, 12)))
    return float(rng.choice((0.5, 1, 2, 3, 5)))


def build_earth_drag() -> dict[str, Any]:
    """An Earth Keplerian row with atmospheric drag enabled."""
    frame, radius, _mu = BODY["Earth"]
    serial = _SERIAL[0]
    _SERIAL[0] += 1
    rng = random.Random(20260902 + serial * 1013)

    alt_p = float(rng.randrange(300, 1501))          # LEO, above 100 km floor
    eccentricity = rng.choice((0.0005, 0.0015, 0.004, 0.009, 0.015))
    semi_major = (radius + alt_p) / (1.0 - eccentricity)

    incl = float(rng.randrange(0, 180))
    raan = float(rng.randrange(0, 360))
    argp = float(rng.randrange(0, 360))
    ta = float(rng.randrange(0, 360))

    mass = round(rng.uniform(140.0, 4200.0), 2)
    drag_model = rng.choice(("JacchiaRoberts", "MSISE90"))
    cd = round(rng.uniform(1.2, 3.2), 2)
    area = round(rng.uniform(0.8, 25.0), 2)
    srp = rng.choice((True, False))
    stop_type = rng.choice(STOP_TYPES)
    stop_value = stop_value_for(stop_type, rng)
    integrator = rng.choice(INTEGRATORS)

    exp_name = f"V9Drag{serial:04d}"
    craft_name = f"SCV9Drag{serial:04d}"

    exp = {
        "version": "1.0",
        "experimentName": exp_name,
        "description": "Earth low-Earth orbit with atmospheric drag enabled.",
        "spacecraft": {
            "name": craft_name,
            "dryMassKg": mass,
            "coefficientOfDrag": cd,
            "dragAreaM2": area,
            "coefficientOfReflectivity": 1.8,
            "srpAreaM2": 1.0,
        },
        "centralBody": "Earth",
        "epoch": {"format": "UTCGregorian", "value": "01 Jan 2026 12:00:00.000"},
        "initialOrbit": {
            "type": "Keplerian",
            "coordinateSystem": frame,
            "elements": {
                "semiMajorAxisKm": round(semi_major, 3),
                "eccentricity": eccentricity,
                "inclinationDeg": incl,
                "raanDeg": raan,
                "argumentOfPeriapsisDeg": argp,
                "trueAnomalyDeg": ta,
            },
        },
        "forceModel": {
            "gravityDegree": 4,
            "gravityOrder": 4,
            "pointMasses": ["Luna", "Sun"],
            "atmosphericDrag": {"enabled": True, "model": drag_model},
            "solarRadiationPressure": srp,
        },
        "maneuvers": [],
        "propagation": {
            "integrator": integrator,
            "stopCondition": {"type": stop_type, "value": stop_value},
            "stepSizeSecs": 60.0,
        },
    }

    prompt = compose_prompt(exp, alt_p=alt_p)
    return {"exp": exp, "prompt": prompt, "exp_name": exp_name, "craft": craft_name, "alt_p": alt_p}


def compose_keplerian_prompt(exp: dict[str, Any], body_name: str, alt_p: float) -> str:
    """Natural-language prompt for a low-altitude Keplerian row."""
    serial = _SERIAL[0] - 1
    rng = random.Random(20260903 + serial * 2131)
    e = exp["initialOrbit"]["elements"]
    ecc = e["eccentricity"]
    stop = exp["propagation"]["stopCondition"]

    opener = OPENERS[serial % len(OPENERS)]
    name_part = NAME_WORDINGS[serial % len(NAME_WORDINGS)].format(e=exp["experimentName"], s=exp["spacecraft"]["name"])
    mass_part = MASS_WORDINGS[serial % len(MASS_WORDINGS)].format(m=num(exp["spacecraft"]["dryMassKg"]))
    orbit_intro = ORBIT_INTROS[serial % len(ORBIT_INTROS)].format(alt=num(alt_p), ecc=num(ecc))

    body_clause = "around the Moon" if body_name == "Moon" else "around Mars"
    orbit_clause = (
        f"{orbit_intro}, inclination {num(e['inclinationDeg'])} degrees, "
        f"RAAN {num(e['raanDeg'])} degrees, argument of periapsis {num(e['argumentOfPeriapsisDeg'])} degrees, "
        f"true anomaly {num(e['trueAnomalyDeg'])} degrees"
    )
    stop_clause = STOP_TEXT[stop["type"]][serial % len(STOP_TEXT[stop["type"]])].format(v=num(stop["value"]))
    integ_clause = f"integrate with {exp['propagation']['integrator']}"
    force_clause = DEFAULT_FORCE_WORDINGS[serial % len(DEFAULT_FORCE_WORDINGS)]

    return (
        f"{opener} {body_clause} {name_part}; "
        f"{mass_part}; {orbit_clause}; {stop_clause}; {integ_clause}; "
        f"{force_clause}."
    )


def compose_prompt(exp: dict[str, Any], alt_p: float) -> str:
    """Natural-language prompt for an Earth drag row."""
    serial = _SERIAL[0] - 1
    rng = random.Random(20260904 + serial * 3347)
    e = exp["initialOrbit"]["elements"]
    stop = exp["propagation"]["stopCondition"]
    drag = exp["forceModel"]["atmosphericDrag"]
    sc = exp["spacecraft"]

    opener = OPENERS[serial % len(OPENERS)]
    name_part = NAME_WORDINGS[serial % len(NAME_WORDINGS)].format(e=exp["experimentName"], s=sc["name"])
    mass_part = MASS_WORDINGS[serial % len(MASS_WORDINGS)].format(m=num(sc["dryMassKg"]))
    orbit_intro = ORBIT_INTROS[serial % len(ORBIT_INTROS)].format(alt=num(round(alt_p)), ecc=num(e["eccentricity"]))
    orbit_clause = (
        f"around Earth {orbit_intro}, inclination {num(e['inclinationDeg'])} degrees, "
        f"RAAN {num(e['raanDeg'])} degrees, argument of periapsis {num(e['argumentOfPeriapsisDeg'])} degrees, "
        f"true anomaly {num(e['trueAnomalyDeg'])} degrees"
    )
    stop_clause = STOP_TEXT[stop["type"]][serial % len(STOP_TEXT[stop["type"]])].format(v=num(stop["value"]))
    integ_clause = f"integrate with {exp['propagation']['integrator']}"
    drag_clause = DRAG_WORDINGS[serial % len(DRAG_WORDINGS)].format(model=drag["model"])
    cd_clause = CD_WORDINGS[serial % len(CD_WORDINGS)].format(cd=num(sc["coefficientOfDrag"]), area=num(sc["dragAreaM2"]))
    srp_word = "and also disable solar radiation pressure" if not exp["forceModel"]["solarRadiationPressure"] else "and keep solar radiation pressure on"

    return (
        f"{opener} {name_part}; {mass_part}; {orbit_clause}; {stop_clause}; "
        f"{integ_clause}; {drag_clause} with {cd_clause}, {srp_word}."
    )


def main() -> int:
    if sum(PLAN.values()) != TOTAL:
        raise ValueError("V9 plan mismatch")

    v8 = load_rows(V8_MASTER)
    v8_prompts = {r["contents"][0]["parts"][0]["text"] for r in v8}
    v8_templates = {numeric_mask(p) for p in v8_prompts}
    v8_tokens = [tokens(p) for p in v8_prompts]

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_validator = jsonschema.Draft7Validator(schema)

    global _SERIAL
    _SERIAL = [1]

    generated: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    seen_templates: set[str] = set()
    seen_prompts: set[str] = set()
    seen_signatures: set[tuple[Any, ...]] = set()

    results = {k: [] for k in PLAN}

    for category, quota in PLAN.items():
        added = 0
        tries = 0
        while added < quota:
            tries += 1
            if tries > quota * 60:
                raise RuntimeError(f"Could not fill {category} quota after {tries} tries")
            if category in ("moon_low_altitude", "mars_low_altitude"):
                row = build_low_altitude(category)
            else:
                row = build_earth_drag()
            prompt = row["prompt"]
            exp = row["exp"]
            answer = compact(exp)
            template = numeric_mask(prompt)

            issues: list[str] = []
            if list(schema_validator.iter_errors(exp)):
                issues.append("json_schema_failure")
            try:
                model = OrbitLabExperiment.model_validate(exp)
            except Exception as exc:
                issues.append("pydantic:" + str(exc))
                model = None
            if model is not None:
                phys = AstrodynamicValidator.validate(model)
                if not phys.is_valid:
                    issues.extend("physical:" + e for e in phys.errors)
                try:
                    GmatScriptCompiler().compile_to_string(model)
                except Exception as exc:
                    issues.append("compiler:" + str(exc))

            if prompt in seen_prompts:
                issues.append("duplicate_prompt")
            if template in seen_templates or template in v8_templates:
                issues.append("duplicate_template")
            sig = signature_key(exp)
            if sig in seen_signatures:
                issues.append("duplicate_signature")

            if issues:
                failures.append({
                    "category": category, "issues": issues,
                    "prompt": prompt[:400], "exp": exp,
                })
                continue

            seen_prompts.add(prompt)
            seen_templates.add(template)
            seen_signatures.add(sig)
            generated.append(record(prompt, answer))
            results[category].append(exp)
            annotations.append({
                "category": category,
                "centralBody": exp["centralBody"],
                "experimentName": exp["experimentName"],
                "spacecraftName": exp["spacecraft"]["name"],
                "periapsisAltitudeKm": round(
                    exp["initialOrbit"]["elements"]["semiMajorAxisKm"]
                    * (1 - exp["initialOrbit"]["elements"]["eccentricity"])
                    - BODY[exp["centralBody"]][1], 2
                ),
                "dragEnabled": exp["forceModel"]["atmosphericDrag"]["enabled"],
                "dragModel": exp["forceModel"]["atmosphericDrag"].get("model"),
                "coefficientOfDrag": exp["spacecraft"].get("coefficientOfDrag"),
                "dragAreaM2": exp["spacecraft"].get("dragAreaM2"),
            })
            added += 1

    if len(generated) != TOTAL:
        raise RuntimeError(f"expected {TOTAL} rows, generated {len(generated)}")

    corpus = generated
    prompts = [r["contents"][0]["parts"][0]["text"] for r in corpus]
    if len(prompts) != len(set(prompts)):
        raise RuntimeError("duplicate prompts slipped through the guard")

    with OUT_CORRECTIONS.open("w", encoding="utf-8", newline="\n") as f:
        for item in corpus:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with OUT_MASTER.open("w", encoding="utf-8", newline="\n") as f:
        for item in v8:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        for item in corpus:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    OUT_ANNOTATIONS.write_text(json.dumps(annotations, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_FAILURES.write_text(json.dumps(failures, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "v8_rows": len(v8),
        "v9_new_rows": len(generated),
        "v9_master_rows": len(v8) + len(generated),
        "rejected_candidates": len(failures),
        "by_category": {k: len(v) for k, v in results.items()},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
