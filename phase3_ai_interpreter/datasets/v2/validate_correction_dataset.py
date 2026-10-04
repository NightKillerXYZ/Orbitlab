"""Validate the isolated OrbitLab V2 correction-training dataset."""

from __future__ import annotations

import copy
import json
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


DATASET = DATASET_DIR / "correction_train.jsonl"
RAW_GMAT_MARKERS = ("Create Spacecraft", "Create Propagator", "BeginMissionSequence", "Create ForceModel")
ALLOWED_ROOT = {"version", "experimentName", "description", "spacecraft", "centralBody", "epoch",
                "initialOrbit", "forceModel", "maneuvers", "propagation"}
ALLOWED_SPACECRAFT = {"name", "dryMassKg", "coefficientOfDrag", "dragAreaM2",
                      "coefficientOfReflectivity", "srpAreaM2"}
ALLOWED_EPOCH = {"format", "value"}
ALLOWED_ORBIT = {"type", "coordinateSystem", "elements"}
ALLOWED_KEPLERIAN = {"semiMajorAxisKm", "eccentricity", "inclinationDeg", "raanDeg",
                     "argumentOfPeriapsisDeg", "trueAnomalyDeg"}
ALLOWED_CARTESIAN = {"xKm", "yKm", "zKm", "vxKmS", "vyKmS", "vzKmS"}
ALLOWED_FORCE = {"gravityDegree", "gravityOrder", "pointMasses", "atmosphericDrag",
                 "solarRadiationPressure"}
ALLOWED_DRAG = {"enabled", "model"}
ALLOWED_MANEUVER = {"id", "type", "trigger", "burnVector", "targetObjectives"}
ALLOWED_TRIGGER = {"condition", "elapsedSecs"}
ALLOWED_BURN = {"coordinateSystem", "deltaVVectorKmS"}
ALLOWED_TARGET = {"targetOrbitRadiusKm", "targetEccentricity"}
ALLOWED_PROPAGATION = {"integrator", "stopCondition", "stepSizeSecs"}
ALLOWED_STOP = {"type", "value"}


def unknown_keys(value: dict[str, Any], allowed: set[str], path: str) -> list[str]:
    return [f"{path}.{key}" for key in value if key not in allowed]


def unsupported_fields(data: dict[str, Any]) -> list[str]:
    findings = unknown_keys(data, ALLOWED_ROOT, "$" )
    spacecraft = data.get("spacecraft", {})
    findings += unknown_keys(spacecraft, ALLOWED_SPACECRAFT, "$.spacecraft")
    if "epoch" in data:
        findings += unknown_keys(data["epoch"], ALLOWED_EPOCH, "$.epoch")
    orbit = data.get("initialOrbit", {})
    findings += unknown_keys(orbit, ALLOWED_ORBIT, "$.initialOrbit")
    elements = orbit.get("elements", {})
    element_keys = ALLOWED_KEPLERIAN if orbit.get("type") == "Keplerian" else ALLOWED_CARTESIAN
    findings += unknown_keys(elements, element_keys, "$.initialOrbit.elements")
    if "forceModel" in data:
        force = data["forceModel"]
        findings += unknown_keys(force, ALLOWED_FORCE, "$.forceModel")
        if "atmosphericDrag" in force:
            findings += unknown_keys(force["atmosphericDrag"], ALLOWED_DRAG, "$.forceModel.atmosphericDrag")
    for index, maneuver in enumerate(data.get("maneuvers", [])):
        base = f"$.maneuvers[{index}]"
        findings += unknown_keys(maneuver, ALLOWED_MANEUVER, base)
        findings += unknown_keys(maneuver.get("trigger", {}), ALLOWED_TRIGGER, f"{base}.trigger")
        if "burnVector" in maneuver:
            findings += unknown_keys(maneuver["burnVector"], ALLOWED_BURN, f"{base}.burnVector")
        if "targetObjectives" in maneuver:
            findings += unknown_keys(maneuver["targetObjectives"], ALLOWED_TARGET, f"{base}.targetObjectives")
    propagation = data.get("propagation", {})
    findings += unknown_keys(propagation, ALLOWED_PROPAGATION, "$.propagation")
    findings += unknown_keys(propagation.get("stopCondition", {}), ALLOWED_STOP, "$.propagation.stopCondition")
    return findings


def message_text(record: dict[str, Any], line_number: int) -> tuple[str, str, str]:
    if set(record) != {"systemInstruction", "contents"}:
        raise ValueError("outer record must contain only systemInstruction and contents")
    system = record["systemInstruction"]
    contents = record["contents"]
    if system.get("role") != "system" or len(system.get("parts", [])) != 1:
        raise ValueError("invalid systemInstruction")
    if len(contents) != 2 or [item.get("role") for item in contents] != ["user", "model"]:
        raise ValueError("contents must contain one user and one model message")
    for item in contents:
        if set(item) != {"role", "parts"} or len(item["parts"]) != 1:
            raise ValueError("each message must contain exactly one part")
        if set(item["parts"][0]) != {"text"} or not isinstance(item["parts"][0]["text"], str):
            raise ValueError("each part must contain exactly one text string")
    return system["parts"][0]["text"], contents[0]["parts"][0]["text"], contents[1]["parts"][0]["text"]


def validate() -> int:
    schema = json.loads((REPOSITORY_ROOT / "schemas" / "experiment.schema.json").read_text(encoding="utf-8"))
    schema_validator = jsonschema.Draft7Validator(schema)
    records = DATASET.read_text(encoding="utf-8").splitlines()
    failures: list[str] = []
    systems: set[str] = set()
    users: list[str] = []
    responses: list[str] = []
    schema_pass = pydantic_pass = physical_pass = 0
    raw_gmat_leaks = unsupported_count = 0

    for line_number, line in enumerate(records, 1):
        try:
            outer = json.loads(line)
            system, user, response = message_text(outer, line_number)
            systems.add(system)
            users.append(user)
            responses.append(response)
            if any(marker in response for marker in RAW_GMAT_MARKERS):
                raw_gmat_leaks += 1
                failures.append(f"line {line_number}: raw GMAT syntax in model response")
            target = json.loads(response)
            if response != json.dumps(target, separators=(",", ":"), ensure_ascii=False):
                failures.append(f"line {line_number}: model response is not canonically serialized")
            findings = unsupported_fields(target)
            unsupported_count += len(findings)
            if findings:
                failures.append(f"line {line_number}: unsupported fields: {', '.join(findings)}")
            schema_errors = list(schema_validator.iter_errors(target))
            if schema_errors:
                failures.append(f"line {line_number}: schema: {'; '.join(error.message for error in schema_errors)}")
                continue
            schema_pass += 1
            parsed = OrbitLabExperiment.model_validate(copy.deepcopy(target))
            pydantic_pass += 1
            physical = AstrodynamicValidator.validate(parsed)
            if not physical.is_valid:
                failures.append(f"line {line_number}: physical: {'; '.join(physical.errors)}")
                continue
            physical_pass += 1

            lower_user = user.lower()
            if "epoch" in target and "epoch" not in lower_user:
                failures.append(f"line {line_number}: epoch appears without an epoch request")
            if "use the default force model" in lower_user and "forceModel" in target:
                failures.append(f"line {line_number}: default force model was unnecessarily expanded")
            if "altitude" in lower_user and "altitudeKm" in target.get("initialOrbit", {}).get("elements", {}):
                failures.append(f"line {line_number}: altitudeKm must not be emitted")
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError, KeyError) as exc:
            failures.append(f"line {line_number}: {exc}")

    duplicate_users = sum(count - 1 for count in Counter(users).values() if count > 1)
    duplicate_responses = sum(count - 1 for count in Counter(responses).values() if count > 1)
    duplicate_count = duplicate_users + duplicate_responses
    if duplicate_count:
        failures.append(f"duplicates: users={duplicate_users}, responses={duplicate_responses}")
    if len(records) != 40:
        failures.append(f"expected 40 examples, found {len(records)}")
    if len(systems) != 1:
        failures.append(f"expected one system instruction, found {len(systems)}")

    original_users: set[str] = set()
    original_responses: set[str] = set()
    for filename in ("orbitlab_interpreter_train.jsonl", "orbitlab_interpreter_validation.jsonl"):
        for line in (DATASET_DIR.parent / filename).read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            original_users.add(record["contents"][0]["parts"][0]["text"])
            original_responses.add(record["contents"][1]["parts"][0]["text"])
    overlap = len(set(users) & original_users) + len(set(responses) & original_responses)
    if overlap:
        failures.append(f"overlap with original dataset: {overlap}")

    print(f"Examples: {len(records)}")
    print(f"Schema pass count: {schema_pass}")
    print(f"Pydantic pass count: {pydantic_pass}")
    print(f"Physical validation pass count: {physical_pass}")
    print(f"Duplicate count: {duplicate_count}")
    print(f"Raw GMAT leakage count: {raw_gmat_leaks}")
    print(f"Unsupported-field count: {unsupported_count}")
    print(f"Original-dataset overlap count: {overlap}")
    print(f"Failures: {len(failures)}")
    for failure in failures:
        print(f"- {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(validate())
