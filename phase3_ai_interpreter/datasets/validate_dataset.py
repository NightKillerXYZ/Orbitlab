"""Validate OrbitLab's Gemini supervised-tuning seed dataset."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import ValidationError


DATASET_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = DATASET_DIR.parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from orbitlab_core.ast.models import OrbitLabExperiment  # noqa: E402
from orbitlab_core.ast.validation import AstrodynamicValidator  # noqa: E402


FILES = {
    "train": DATASET_DIR / "v3" / "orbitlab_interpreter_train_v3.jsonl",
    "validation": DATASET_DIR / "orbitlab_interpreter_validation.jsonl",
}
EXPECTED_COUNTS = {"train": 302, "validation": 56}
EXPECTED_CATEGORIES = {
    "train": {
        "Basic": 35,
        "Paraphrase": 35,
        "Multi": 35,
        "Cartesian": 24,
        "Maneuver": 41,
        "Force": 17,
        "Propagation": 15,
        "Cross": 20,
        "CorrectionV2": 40,
        "VersionFix": 5,
        "CoordFix": 6,
        "DefForce": 5,
        "MinTest": 6,
        "ManId": 4,
        "ExactMan": 5,
        "Combo": 9,
    },
    "validation": {
        "Basic": 8,
        "Paraphrase": 8,
        "Multi": 9,
        "Cartesian": 6,
        "Maneuver": 10,
        "Force": 5,
        "Propagation": 4,
        "Cross": 6,
    },
}
STANDARD_CATEGORY_PATTERN = re.compile(
    r"^(Basic|Paraphrase|Multi|Cartesian|Maneuver|Force|Propagation|Cross)(?:Train|Val)\d{3}$"
)
CORRECTION_V2_PATTERN = re.compile(r"^CorrectionV2_\d{3}$")
V3_CORRECTION_PATTERN = re.compile(
    r"^(VersionFix|CoordFix|DefForce|MinTest|ManId|ExactMan|Combo)\d{2}$"
)
WORD_PATTERN = re.compile(r"[a-z]+")
RAW_GMAT_MARKERS = (
    "Create Spacecraft",
    "Create Propagator",
    "BeginMissionSequence",
    "Create ForceModel",
)


def extract_text(
    record: dict[str, Any], split: str, line_number: int
) -> tuple[str, str, str]:
    label = f"{split}:{line_number}"
    if set(record) != {"systemInstruction", "contents"}:
        raise ValueError(
            f"{label}: outer object must contain only systemInstruction and contents"
        )
    system = record["systemInstruction"]
    contents = record["contents"]
    if system.get("role") != "system" or len(system.get("parts", [])) != 1:
        raise ValueError(f"{label}: invalid systemInstruction")
    if not isinstance(contents, list) or len(contents) != 2:
        raise ValueError(
            f"{label}: contents must contain exactly one user and one model message"
        )
    if contents[0].get("role") != "user" or contents[1].get("role") != "model":
        raise ValueError(f"{label}: contents roles must be user followed by model")
    for message in contents:
        if set(message) != {"role", "parts"} or len(message["parts"]) != 1:
            raise ValueError(f"{label}: each message must contain exactly one part")
        if set(message["parts"][0]) != {"text"} or not isinstance(
            message["parts"][0]["text"], str
        ):
            raise ValueError(f"{label}: each part must contain one text string")
    return (
        system["parts"][0]["text"],
        contents[0]["parts"][0]["text"],
        contents[1]["parts"][0]["text"],
    )


def token_set(text: str) -> set[str]:
    return {word for word in WORD_PATTERN.findall(text.lower()) if len(word) > 2}


def validate() -> int:
    schema = json.loads(
        (REPOSITORY_ROOT / "schemas" / "experiment.schema.json").read_text(
            encoding="utf-8"
        )
    )
    schema_validator = jsonschema.Draft7Validator(schema)
    failures: list[str] = []
    systems: set[str] = set()
    users: list[tuple[str, int, str]] = []
    responses: list[tuple[str, int, str]] = []
    category_counts: dict[str, Counter[str]] = {split: Counter() for split in FILES}
    schema_valid = 0
    physically_valid = 0

    for split, path in FILES.items():
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError as exc:
            failures.append(f"{split}: cannot read {path}: {exc}")
            continue
        if len(lines) != EXPECTED_COUNTS[split]:
            failures.append(
                f"{split}: expected {EXPECTED_COUNTS[split]} records, found {len(lines)}"
            )
        for line_number, line in enumerate(lines, 1):
            label = f"{split}:{line_number}"
            try:
                outer = json.loads(line)
                system, user_text, model_text = extract_text(outer, split, line_number)
                systems.add(system)
                users.append((split, line_number, user_text))
                responses.append((split, line_number, model_text))
                if not user_text.strip():
                    raise ValueError(f"{label}: user request is empty")
                if any(marker in model_text for marker in RAW_GMAT_MARKERS):
                    raise ValueError(
                        f"{label}: model response contains raw GMAT syntax"
                    )
                experiment_data = json.loads(model_text)
                schema_errors = sorted(
                    schema_validator.iter_errors(experiment_data),
                    key=lambda error: list(error.path),
                )
                if schema_errors:
                    details = "; ".join(error.message for error in schema_errors)
                    raise ValueError(
                        f"{label}: JSON Schema validation failed: {details}"
                    )
                schema_valid += 1
                experiment = OrbitLabExperiment.model_validate(experiment_data)
                if experiment.centralBody != "Earth":
                    serialized = experiment.model_dump(mode="json", exclude_none=True)
                    schema_errors = list(schema_validator.iter_errors(serialized))
                    if schema_errors:
                        raise ValueError(
                            f"{label}: normalized JSON Schema validation failed: "
                            + "; ".join(error.message for error in schema_errors)
                        )
                result = AstrodynamicValidator.validate(experiment)
                if not result.is_valid:
                    raise ValueError(
                        f"{label}: astrodynamic validation failed: {'; '.join(result.errors)}"
                    )
                physically_valid += 1
                name = experiment.experimentName
                match = STANDARD_CATEGORY_PATTERN.fullmatch(name)
                if match:
                    category_counts[split][match.group(1)] += 1
                elif split == "train":
                    correction_v2 = CORRECTION_V2_PATTERN.fullmatch(name)
                    v3_correction = V3_CORRECTION_PATTERN.fullmatch(name)
                    if correction_v2:
                        category_counts[split]["CorrectionV2"] += 1
                    elif v3_correction:
                        category_counts[split][v3_correction.group(1)] += 1
                    else:
                        raise ValueError(
                            f"{label}: experimentName does not encode a recognized V3 training category"
                        )
                else:
                    raise ValueError(
                        f"{label}: experimentName does not encode a recognized validation category"
                    )
            except (
                json.JSONDecodeError,
                ValidationError,
                TypeError,
                ValueError,
            ) as exc:
                failures.append(f"{label}: {exc}")

    if len(systems) != 1:
        failures.append(
            f"system instruction variants: expected 1, found {len(systems)}"
        )
    for split, expected in EXPECTED_CATEGORIES.items():
        if dict(category_counts[split]) != expected:
            failures.append(
                f"{split}: category distribution {dict(category_counts[split])}, expected {expected}"
            )

    user_counter = Counter(text for _, _, text in users)
    response_counter = Counter(text for _, _, text in responses)
    duplicate_users = sum(count - 1 for count in user_counter.values() if count > 1)
    duplicate_responses = sum(
        count - 1 for count in response_counter.values() if count > 1
    )
    if duplicate_users:
        failures.append(f"duplicate user requests: {duplicate_users}")
    if duplicate_responses:
        failures.append(f"duplicate model responses: {duplicate_responses}")

    train_users = {text for split, _, text in users if split == "train"}
    val_users = {text for split, _, text in users if split == "validation"}
    train_responses = {text for split, _, text in responses if split == "train"}
    val_responses = {text for split, _, text in responses if split == "validation"}
    overlap = len(train_users & val_users) + len(train_responses & val_responses)
    if overlap:
        failures.append(f"train/validation exact overlap: {overlap}")

    near_duplicates: list[str] = []
    tokenized = [(split, line, text, token_set(text)) for split, line, text in users]
    for index, (left_split, left_line, _, left_tokens) in enumerate(tokenized):
        for right_split, right_line, _, right_tokens in tokenized[index + 1 :]:
            similarity = len(left_tokens & right_tokens) / len(
                left_tokens | right_tokens
            )
            if similarity >= 0.90:
                near_duplicates.append(
                    f"{left_split}:{left_line}/{right_split}:{right_line} ({similarity:.3f})"
                )
    if near_duplicates:
        failures.append("near-duplicate user requests: " + ", ".join(near_duplicates))

    total = len(users)
    print(f"Training examples: {sum(1 for split, _, _ in users if split == 'train')}")
    print(
        f"Validation examples: {sum(1 for split, _, _ in users if split == 'validation')}"
    )
    print(f"Total examples: {total}")
    print(f"JSON-Schema-valid examples: {schema_valid}")
    print(f"Pydantic and physically valid examples: {physically_valid}")
    print(f"Duplicate user requests: {duplicate_users}")
    print(f"Duplicate model responses: {duplicate_responses}")
    print(f"Near-duplicate request pairs: {len(near_duplicates)}")
    print(f"Train/validation exact overlap: {overlap}")
    print(f"Training categories: {dict(category_counts['train'])}")
    print(f"Validation categories: {dict(category_counts['validation'])}")
    print(f"Failures: {len(failures)}")
    for failure in failures:
        print(f"- {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(validate())
