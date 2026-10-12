"""Validate V4 candidate examples against schema, physics, and frozen splits."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import ValidationError


DATASET_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = DATASET_DIR.parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from orbitlab_core.ast.models import OrbitLabExperiment  # noqa: E402
from orbitlab_core.ast.validation import AstrodynamicValidator  # noqa: E402


TRAIN_V3 = DATASET_DIR.parent / "v3" / "orbitlab_interpreter_train_v3.jsonl"
VALIDATION = DATASET_DIR.parent / "orbitlab_interpreter_validation.jsonl"
TRAIN_V4 = DATASET_DIR / "orbitlab_interpreter_train_v4.jsonl"
SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "experiment.schema.json"

V4_COUNTS = {
    "V4Body": 16,
    "V4Force": 12,
    "V4Cartesian": 12,
    "V4Hohmann": 14,
    "V4Multi": 10,
    "V4Cross": 12,
    "V4Propagation": 8,
    "V4Language": 10,
    "V4Robustness": 6,
}
V4_NAME = re.compile(r"^(V4Body|V4Force|V4Cartesian|V4Hohmann|V4Multi|V4Cross|V4Propagation|V4Language|V4Robustness)(\d{3})$")
WORDS = re.compile(r"[a-z]+")
RAW_GMAT_MARKERS = (
    "Create Spacecraft", "Create Propagator", "Create ForceModel",
    "Create ReportFile", "Create ImpulsiveBurn", "BeginMissionSequence",
    "Propagate ", "GMAT ",
)
DEFAULT_FORCE_RE = re.compile(r"default force model|force model defaults|force settings default|no extra forces", re.I)
EPOCH_RE = re.compile(r"\bepoch\b|utcg?regorian|\b(start|begin)(?:ing)? date\b|\bon \d{1,2} [a-z]{3} \d{4}\b", re.I)
ROOT_FIELDS = {"version", "experimentName", "description", "spacecraft", "centralBody", "epoch", "initialOrbit", "forceModel", "maneuvers", "propagation"}
SPACECRAFT_FIELDS = {"name", "dryMassKg", "coefficientOfDrag", "dragAreaM2", "coefficientOfReflectivity", "srpAreaM2"}
ORBIT_FIELDS = {"type", "coordinateSystem", "elements"}
KEPLERIAN_FIELDS = {"semiMajorAxisKm", "eccentricity", "inclinationDeg", "raanDeg", "argumentOfPeriapsisDeg", "trueAnomalyDeg"}
CARTESIAN_FIELDS = {"xKm", "yKm", "zKm", "vxKmS", "vyKmS", "vzKmS"}
FORCE_FIELDS = {"gravityDegree", "gravityOrder", "pointMasses", "atmosphericDrag", "solarRadiationPressure"}
MANEUVER_FIELDS = {"id", "type", "trigger", "burnVector", "targetObjectives"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path.name}:{line_number}: record must be an object")
            records.append(record)
    return records


def record_text(record: dict[str, Any], label: str) -> tuple[str, str, str]:
    if set(record) != {"systemInstruction", "contents"}:
        raise ValueError(f"{label}: outer keys must be systemInstruction and contents")
    system = record["systemInstruction"]
    contents = record["contents"]
    if not isinstance(system, dict) or system.get("role") != "system" or len(system.get("parts", [])) != 1:
        raise ValueError(f"{label}: invalid system instruction")
    if not isinstance(contents, list) or len(contents) != 2 or [x.get("role") for x in contents] != ["user", "model"]:
        raise ValueError(f"{label}: contents must be one user and one model message")
    for message in contents:
        if set(message) != {"role", "parts"} or len(message["parts"]) != 1 or set(message["parts"][0]) != {"text"} or not isinstance(message["parts"][0]["text"], str):
            raise ValueError(f"{label}: message must contain exactly one text part")
    return system["parts"][0]["text"], contents[0]["parts"][0]["text"], contents[1]["parts"][0]["text"]


def unknown_paths(value: Any, allowed: set[str], path: str) -> list[str]:
    if not isinstance(value, dict):
        return [path + " must be an object"]
    return [f"{path}.{key}" for key in value if key not in allowed]


def unsupported_fields(exp: dict[str, Any]) -> list[str]:
    findings = unknown_paths(exp, ROOT_FIELDS, "$experiment")
    spacecraft = exp.get("spacecraft", {})
    findings += unknown_paths(spacecraft, SPACECRAFT_FIELDS, "$.spacecraft")
    if "epoch" in exp:
        findings += unknown_paths(exp["epoch"], {"format", "value"}, "$.epoch")
    orbit = exp.get("initialOrbit", {})
    findings += unknown_paths(orbit, ORBIT_FIELDS, "$.initialOrbit")
    if isinstance(orbit, dict):
        elements = orbit.get("elements", {})
        keys = KEPLERIAN_FIELDS if orbit.get("type") == "Keplerian" else CARTESIAN_FIELDS
        findings += unknown_paths(elements, keys, "$.initialOrbit.elements")
    if "forceModel" in exp:
        force = exp["forceModel"]
        findings += unknown_paths(force, FORCE_FIELDS, "$.forceModel")
        if isinstance(force, dict) and "atmosphericDrag" in force:
            findings += unknown_paths(force["atmosphericDrag"], {"enabled", "model"}, "$.forceModel.atmosphericDrag")
    if "maneuvers" in exp:
        if not isinstance(exp["maneuvers"], list):
            findings.append("$.maneuvers must be an array")
        else:
            for i, maneuver in enumerate(exp["maneuvers"]):
                base = f"$.maneuvers[{i}]"
                findings += unknown_paths(maneuver, MANEUVER_FIELDS, base)
                if not isinstance(maneuver, dict):
                    continue
                findings += unknown_paths(maneuver.get("trigger", {}), {"condition", "elapsedSecs"}, base + ".trigger")
                if "burnVector" in maneuver:
                    findings += unknown_paths(maneuver["burnVector"], {"coordinateSystem", "deltaVVectorKmS"}, base + ".burnVector")
                if "targetObjectives" in maneuver:
                    findings += unknown_paths(maneuver["targetObjectives"], {"targetOrbitRadiusKm", "targetEccentricity"}, base + ".targetObjectives")
    propagation = exp.get("propagation", {})
    findings += unknown_paths(propagation, {"integrator", "stopCondition", "stepSizeSecs"}, "$.propagation")
    if isinstance(propagation, dict):
        findings += unknown_paths(propagation.get("stopCondition", {}), {"type", "value"}, "$.propagation.stopCondition")
    return findings


def validate_requested_optionals(exp: dict[str, Any], user: str, label: str) -> None:
    if "centralBody" in exp and not re.search(r"\b" + re.escape(exp["centralBody"]) + r"\b", user, re.I):
        raise ValueError(f"{label}: centralBody was not requested")
    if "description" in exp and not re.search(r"description|purpose|goal|objective", user, re.I):
        raise ValueError(f"{label}: description was not requested")
    if "epoch" in exp and not EPOCH_RE.search(user):
        raise ValueError(f"{label}: epoch output lacks an explicit epoch request")
    force = exp.get("forceModel")
    if force is not None:
        if not isinstance(force, dict) or not force:
            raise ValueError(f"{label}: empty forceModel objects are not allowed")
        if any(k in force for k in ("gravityDegree", "gravityOrder")) and not re.search(r"gravity|harmonic", user, re.I):
            raise ValueError(f"{label}: gravity fields were not requested")
        if "pointMasses" in force:
            requested = [body for body in ("Luna", "Sun", "Jupiter") if re.search(r"\b" + body + r"\b", user, re.I)]
            if not re.search(r"point mass|third bod|perturb", user, re.I) or any(body not in requested for body in force["pointMasses"]):
                raise ValueError(f"{label}: point masses were not explicitly requested")
        if "atmosphericDrag" in force:
            drag = force["atmosphericDrag"]
            if not re.search(r"drag", user, re.I):
                raise ValueError(f"{label}: atmospheric drag was not requested")
            if "model" in drag and drag["model"].casefold() not in user.casefold():
                raise ValueError(f"{label}: drag model was not explicitly requested")
        if "solarRadiationPressure" in force and not re.search(r"solar radiation|\bSRP\b|radiation pressure", user, re.I):
            raise ValueError(f"{label}: SRP setting was not requested")
    spacecraft = exp.get("spacecraft", {})
    for field, terms in {
        "coefficientOfDrag": r"coefficient of drag|\bCd\b",
        "dragAreaM2": r"drag area",
        "coefficientOfReflectivity": r"coefficient of reflectivity|\bCr\b",
        "srpAreaM2": r"SRP area|solar radiation pressure area",
    }.items():
        if field in spacecraft and not re.search(terms, user, re.I):
            raise ValueError(f"{label}: optional spacecraft field {field} was not requested")
    if exp.get("maneuvers") and not re.search(r"maneuver|burn|transfer", user, re.I):
        raise ValueError(f"{label}: maneuvers were not requested")


def tokens(text: str) -> set[str]:
    return {word for word in WORDS.findall(text.lower()) if len(word) > 2}


def jaccard(a: str, b: str) -> float:
    left, right = tokens(a), tokens(b)
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def number_values(value: Any) -> list[float]:
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [number for item in value.values() for number in number_values(item)]
    if isinstance(value, list):
        return [number for item in value for number in number_values(item)]
    return []


def validate(path: Path, final: bool) -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    schema_validator = jsonschema.Draft7Validator(schema)
    baseline = load_jsonl(TRAIN_V3)
    frozen = load_jsonl(VALIDATION)
    candidates = load_jsonl(path)
    baseline_users = [record_text(r, "V3")[1] for r in baseline]
    frozen_users = [record_text(r, "validation")[1] for r in frozen]
    candidate_users: list[str] = []
    candidate_responses: list[str] = []
    systems: set[str] = set()
    counts: Counter[str] = Counter()
    failures: list[str] = []
    schema_ok = pydantic_ok = physical_ok = unsupported = raw_gmat = 0

    if final and len(candidates) != 100:
        failures.append(f"expected 100 V4 records, got {len(candidates)}")

    for index, record in enumerate(candidates, 1):
        label = f"{path.name}:{index}"
        try:
            system, user, response = record_text(record, label)
            systems.add(system)
            if not user.strip():
                raise ValueError(f"{label}: empty user request")
            if any(marker.casefold() in response.casefold() for marker in RAW_GMAT_MARKERS):
                raw_gmat += 1
                raise ValueError(f"{label}: raw GMAT leakage")
            exp = json.loads(response)
            if not isinstance(exp, dict):
                raise ValueError(f"{label}: response must be one Experiment object")
            if response != json.dumps(exp, separators=(",", ":"), ensure_ascii=False):
                raise ValueError(f"{label}: model response is not compact canonical JSON")
            findings = unsupported_fields(exp)
            unsupported += len(findings)
            if findings:
                raise ValueError(f"{label}: unsupported fields: {', '.join(findings)}")
            if exp.get("version") != "1.0":
                raise ValueError(f"{label}: required version must be '1.0'")
            expected_frame = {"Earth": "EarthMJ2000Eq", "Moon": "LunaMJ2000Eq", "Mars": "MarsMJ2000Eq"}.get(exp.get("centralBody", "Earth"))
            if exp.get("initialOrbit", {}).get("coordinateSystem") != expected_frame:
                raise ValueError(f"{label}: coordinateSystem must be explicitly {expected_frame}")
            validate_requested_optionals(exp, user, label)
            if "epoch" not in exp and re.search(r"\bUTCGregorian\b|\b(?:start|begin)(?:ing)? date\b|\bon \d{1,2} [a-z]{3} \d{4}\b", user, re.I):
                raise ValueError(f"{label}: explicit epoch request missing from output")
            if DEFAULT_FORCE_RE.search(user) and "forceModel" in exp and not re.search(r"(?:gravity|point.?mass|drag|srp|solar radiation)", user, re.I):
                raise ValueError(f"{label}: default force model must be represented by omission")
            stop = exp["propagation"]["stopCondition"]
            number_cues = re.findall(r"-?\d+(?:\.\d+)?", user)
            mentioned_numbers = [float(number) for number in number_cues]
            time_values = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", user)]
            for value in time_values:
                if re.search(r"\b(?:min|mins|minute|minutes)\b", user, re.I):
                    mentioned_numbers.append(value * 60.0)
            for numeric in number_values({k: v for k, v in exp.items() if k != "version"}):
                mentioned = any(math.isclose(numeric, value, rel_tol=0, abs_tol=1e-9) for value in mentioned_numbers)
                if not mentioned:
                    raise ValueError(f"{label}: numeric output {numeric:g} is not stated or a permitted time conversion")
            if "maneuvers" in exp:
                for m in exp["maneuvers"]:
                    if "id" not in m or "name" in m:
                        raise ValueError(f"{label}: maneuvers must use id, not name")
                    if m["id"] not in user:
                        raise ValueError(f"{label}: maneuver id {m['id']!r} not present in prompt")
            schema_errors = list(schema_validator.iter_errors(exp))
            if schema_errors:
                raise ValueError(f"{label}: schema: {'; '.join(e.message for e in schema_errors)}")
            schema_ok += 1
            parsed = OrbitLabExperiment.model_validate(exp)
            pydantic_ok += 1
            physical = AstrodynamicValidator.validate(parsed)
            if not physical.is_valid:
                raise ValueError(f"{label}: physical: {'; '.join(physical.errors)}")
            physical_ok += 1
            match = V4_NAME.fullmatch(exp.get("experimentName", ""))
            if not match:
                raise ValueError(f"{label}: experimentName must use a V4 category prefix")
            counts[match.group(1)] += 1
            candidate_users.append(user)
            candidate_responses.append(response)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError, KeyError) as exc:
            failures.append(str(exc))

    if len(systems) != 1 or (systems and systems != {record_text(baseline[0], "V3")[0]}):
        failures.append(f"expected one system instruction in V4 batch, found {len(systems)}")
    if final and dict(counts) != V4_COUNTS:
        failures.append(f"V4 category counts {dict(counts)} do not match {V4_COUNTS}")
    if len(set(candidate_users)) != len(candidate_users):
        failures.append("duplicate user prompts within V4")
    if len(set(candidate_responses)) != len(candidate_responses):
        failures.append("duplicate responses within V4")
    if set(candidate_users) & set(baseline_users):
        failures.append("exact prompt overlap with V3 training")
    if set(candidate_responses) & {record_text(r, "V3")[2] for r in baseline}:
        failures.append("exact response overlap with V3 training")
    if set(candidate_users) & set(frozen_users):
        failures.append("exact prompt overlap with frozen validation")
    if set(candidate_responses) & {record_text(r, "validation")[2] for r in frozen}:
        failures.append("exact response overlap with frozen validation")

    train_all = baseline_users + candidate_users
    for i, left in enumerate(train_all):
        for j in range(i + 1, len(train_all)):
            score = jaccard(left, train_all[j])
            if score >= 0.90:
                left_candidate = i >= len(baseline_users)
                right_candidate = j >= len(baseline_users)
                if not (left_candidate and right_candidate):
                    failures.append(f"unacceptable training near-duplicate {i + 1}/{j + 1}: {score:.3f}")
    validation_semantic_pairs = []
    for i, user in enumerate(candidate_users):
        for j, validation_user in enumerate(frozen_users, 1):
            score = jaccard(user, validation_user)
            if score >= 0.70:
                validation_semantic_pairs.append((i + 1, j, score))
    if validation_semantic_pairs:
        failures.append(f"semantic overlap with validation >= 0.70: {validation_semantic_pairs}")

    print(f"V4 candidates: {len(candidates)}")
    print(f"Schema valid: {schema_ok}; Pydantic valid: {pydantic_ok}; physically valid: {physical_ok}")
    print(f"Unsupported fields: {unsupported}; raw GMAT leaks: {raw_gmat}")
    print(f"V4 categories: {dict(counts)}")
    print(f"Frozen validation records consulted for overlap only: {len(frozen)}")
    print(f"Failures: {len(failures)}")
    for failure in failures:
        print("- " + failure)
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=TRAIN_V4)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    raise SystemExit(validate(args.candidate, args.final))
