from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATASET_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = DATASET_DIR.parents[2]

V3_TRAIN = DATASET_DIR / "correction_v3_train.jsonl"

SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "schemas"
    / "experiment.schema.json"
)

sys.path.insert(0, str(REPOSITORY_ROOT))

from orbitlab_core.ast.models import OrbitLabExperiment  # noqa: E402
from orbitlab_core.ast.validation import AstrodynamicValidator  # noqa: E402
import inspect
import orbitlab_core.ast.validation as validation_module

print("VALIDATION MODULE:", validation_module.__file__)
print(
    "VALIDATOR SOURCE:",
    inspect.getsourcefile(AstrodynamicValidator)
)


# ---------------------------------------------------------------------------
# Expected V3 dataset
# ---------------------------------------------------------------------------

EXPECTED_EXAMPLES = 40

EXPECTED_PREFIXES = {
    "VersionFix": 5,
    "CoordFix": 6,
    "DefForce": 5,
    "MinTest": 6,
    "ManId": 4,
    "ExactMan": 5,
    "Combo": 9,
}


# ---------------------------------------------------------------------------
# Raw GMAT detection
# ---------------------------------------------------------------------------

RAW_GMAT_MARKERS = [
    "Create Spacecraft",
    "Create Propagator",
    "Create ForceModel",
    "Create ReportFile",
    "Create ImpulsiveBurn",
    "Create DifferentialCorrector",
    "BeginMissionSequence",
    "Propagate ",
    "Report ",
    "GMAT ",
    "Spacecraft.",
    "ForceModel.",
    "Propagator.",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise AssertionError(
                    f"{path.name}: invalid JSON on line {line_number}: {exc}"
                )

    return records


def extract_model_json(record: dict[str, Any]) -> dict[str, Any]:
    contents = record["contents"]

    model_messages = [
        message
        for message in contents
        if message.get("role") == "model"
    ]

    if len(model_messages) != 1:
        raise AssertionError(
            "Expected exactly one model message."
        )

    parts = model_messages[0].get("parts", [])

    if len(parts) != 1 or "text" not in parts[0]:
        raise AssertionError(
            "Model message must contain exactly one text part."
        )

    raw = parts[0]["text"]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Model response is not valid JSON: {exc}"
        )

    if not isinstance(parsed, dict):
        raise AssertionError(
            "Model response must be a JSON object."
        )

    return parsed


def extract_user_text(record: dict[str, Any]) -> str:
    contents = record["contents"]

    user_messages = [
        message
        for message in contents
        if message.get("role") == "user"
    ]

    if len(user_messages) != 1:
        raise AssertionError(
            "Expected exactly one user message."
        )

    parts = user_messages[0].get("parts", [])

    if len(parts) != 1 or "text" not in parts[0]:
        raise AssertionError(
            "User message must contain exactly one text part."
        )

    return parts[0]["text"]


def has_raw_gmat(text: str) -> bool:
    return any(marker in text for marker in RAW_GMAT_MARKERS)


def jaccard_similarity(a: str, b: str) -> float:
    a_tokens = set(re.findall(r"\w+", a.lower()))
    b_tokens = set(re.findall(r"\w+", b.lower()))

    if not a_tokens and not b_tokens:
        return 1.0

    union = a_tokens | b_tokens

    if not union:
        return 0.0

    return len(a_tokens & b_tokens) / len(union)


def correction_prefix(name: str) -> str | None:
    match = re.match(
        r"^(VersionFix|CoordFix|DefForce|MinTest|ManId|ExactMan|Combo)\d+$",
        name,
    )

    if match:
        return match.group(1)

    return None


# ---------------------------------------------------------------------------
# Gemini JSONL structure validation
# ---------------------------------------------------------------------------

def validate_outer_structure(record: dict[str, Any]) -> list[str]:
    failures = []

    expected_keys = {"systemInstruction", "contents"}

    if set(record.keys()) != expected_keys:
        failures.append(
            f"outer keys are {sorted(record.keys())}, "
            f"expected {sorted(expected_keys)}"
        )

    if not isinstance(record.get("systemInstruction"), dict):
        failures.append("systemInstruction must be an object")

    else:
        if "parts" not in record["systemInstruction"]:
            failures.append(
                "systemInstruction missing parts"
            )

    contents = record.get("contents")

    if not isinstance(contents, list):
        failures.append("contents must be a list")
        return failures

    if len(contents) != 2:
        failures.append(
            f"contents must contain exactly 2 messages, got {len(contents)}"
        )
        return failures

    roles = [message.get("role") for message in contents]

    if roles != ["user", "model"]:
        failures.append(
            f"expected roles ['user', 'model'], got {roles}"
        )

    return failures


# ---------------------------------------------------------------------------
# OrbitLab JSON validation
# ---------------------------------------------------------------------------

def validate_experiment(
    experiment: dict[str, Any],
    schema_validator: Draft202012Validator,
) -> list[str]:

    failures = []

    # JSON Schema
    schema_errors = sorted(
        schema_validator.iter_errors(experiment),
        key=lambda error: list(error.path),
    )

    for error in schema_errors:
        location = ".".join(str(x) for x in error.path)

        if location:
            failures.append(
                f"JSON Schema: {location}: {error.message}"
            )
        else:
            failures.append(
                f"JSON Schema: {error.message}"
            )

    # Pydantic
    if not schema_errors:
        try:
            OrbitLabExperiment.model_validate(experiment)
        except Exception as exc:
            failures.append(
                f"Pydantic validation failed: {exc}"
            )

    # Physical validation
    if not schema_errors:
        try:
            parsed = OrbitLabExperiment.model_validate(experiment)

            validator = AstrodynamicValidator()
            result = validator.validate(parsed)

            # AstrodynamicValidator implementations may return either
            # a result object or raise on invalid input.
            if hasattr(result, "is_valid"):
                if not result.is_valid:
                    failures.append(
                        f"Physical validation failed: {result}"
                    )

        except Exception as exc:
            failures.append(
                f"Physical validation failed: {exc}"
            )

    return failures


# ---------------------------------------------------------------------------
# V3-specific checks
# ---------------------------------------------------------------------------

def validate_v3_rules(
    user_text: str,
    experiment: dict[str, Any],
) -> list[str]:

    failures = []

    # -----------------------------------------------------------------------
    # Required version
    # -----------------------------------------------------------------------

    if "version" not in experiment:
        failures.append(
            "V3: required version field is missing"
        )
    elif experiment["version"] != "1.0":
        failures.append(
            f"V3: version must be '1.0', got {experiment['version']!r}"
        )

    # -----------------------------------------------------------------------
    # Initial orbit
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
# Initial orbit
# -----------------------------------------------------------------------

    initial_orbit = experiment.get("initialOrbit")

    if initial_orbit is not None:

        # The experiment has already passed Pydantic validation, so
        # initialOrbit may be a Pydantic model rather than a dict.
        if hasattr(initial_orbit, "model_dump"):
            orbit_data = initial_orbit.model_dump(
                exclude_none=False
            )
        elif isinstance(initial_orbit, dict):
            orbit_data = initial_orbit
        else:
            orbit_data = {}

        coordinate_system = orbit_data.get("coordinateSystem")

        if coordinate_system != "EarthMJ2000Eq":
            failures.append(
                "V3: initialOrbit.coordinateSystem must be "
                "'EarthMJ2000Eq'"
            )

        orbit_type = orbit_data.get("type")

        elements = orbit_data.get("elements", {})

        if hasattr(elements, "model_dump"):
            elements = elements.model_dump(
                exclude_none=False
            )
        elif not isinstance(elements, dict):
            elements = {}

        if orbit_type == "Keplerian":

            required = {
                "semiMajorAxisKm",
                "eccentricity",
                "inclinationDeg",
            }

            missing = required - set(elements.keys())

            if missing:
                failures.append(
                    "V3: Keplerian elements missing: "
                    + ", ".join(sorted(missing))
                )

        elif orbit_type == "Cartesian":

            required = {
                "xKm",
                "yKm",
                "zKm",
                "vxKmS",
                "vyKmS",
                "vzKmS",
            }

            missing = required - set(elements.keys())

            if missing:
                failures.append(
                    "V3: Cartesian elements missing: "
                    + ", ".join(sorted(missing))
                )

    # -----------------------------------------------------------------------
    # Default force model
    # -----------------------------------------------------------------------

    lower_user = user_text.lower()

    requested_default_force_model = (
        "default force model" in lower_user
        or "leave force settings default" in lower_user
        or "unspecified force model" in lower_user
        or "force settings and epoch default" in lower_user
    )

    explicit_force_change = any(
        phrase in lower_user
        for phrase in [
            "include sun",
            "include luna",
            "include jupiter",
            "point masses",
            "gravity",
            "atmospheric drag",
            "srp",
            "solar radiation pressure",
        ]
    )

    if requested_default_force_model and not explicit_force_change:
        if "forceModel" in experiment:
            failures.append(
                "V3: default force model should be represented "
                "by omission"
            )

    # -----------------------------------------------------------------------
    # Minutes must be converted to supported seconds
    # -----------------------------------------------------------------------

    minute_patterns = [
        r"(\d+(?:\.\d+)?)\s*minutes?",
        r"(\d+(?:\.\d+)?)\s*mins?",
    ]

    requested_minutes = []

    for pattern in minute_patterns:
        requested_minutes.extend(
            float(value)
            for value in re.findall(pattern, lower_user)
        )

    if requested_minutes:
        propagation = experiment.get("propagation", {})
        stop = propagation.get("stopCondition", {})

        if stop.get("type") != "ElapsedSeconds":
            failures.append(
                "V3: minute-based duration must use "
                "ElapsedSeconds"
            )
        else:
            expected_seconds = requested_minutes[0] * 60

            actual_seconds = stop.get("value")

            if actual_seconds != expected_seconds:
                failures.append(
                    "V3: minute-to-second conversion is incorrect: "
                    f"expected {expected_seconds}, got {actual_seconds}"
                )

    # -----------------------------------------------------------------------
    # Maneuver IDs
    # -----------------------------------------------------------------------

    maneuvers = experiment.get("maneuvers", [])

    if isinstance(maneuvers, list):

        for index, maneuver in enumerate(maneuvers):

            if not isinstance(maneuver, dict):
                continue

            if "name" in maneuver:
                failures.append(
                    f"V3: maneuver {index} uses 'name'; "
                    "schema requires 'id'"
                )

            if "id" not in maneuver:
                failures.append(
                    f"V3: maneuver {index} is missing required 'id'"
                )

            trigger = maneuver.get("trigger")

            if isinstance(trigger, dict):

                condition = trigger.get("condition")

                if condition == "ElapsedTimeSecs":
                    if "elapsedSecs" not in trigger:
                        failures.append(
                            f"V3: maneuver {index} with "
                            "ElapsedTimeSecs trigger must contain "
                            "'elapsedSecs'"
                        )

            burn = maneuver.get("burnVector")

            if isinstance(burn, dict):

                if burn.get("coordinateSystem") != "LocalVNB":
                    failures.append(
                        f"V3: maneuver {index} burnVector must use "
                        "LocalVNB"
                    )

                if "deltaVVectorKmS" not in burn:
                    failures.append(
                        f"V3: maneuver {index} missing "
                        "deltaVVectorKmS"
                    )

    # -----------------------------------------------------------------------
    # Unsupported top-level fields
    # -----------------------------------------------------------------------

    allowed_top_level = {
        "version",
        "experimentName",
        "spacecraft",
        "epoch",
        "centralBody",
        "initialOrbit",
        "forceModel",
        "maneuvers",
        "propagation",
    }

    unexpected = set(experiment.keys()) - allowed_top_level

    for field in sorted(unexpected):
        failures.append(
            f"V3: unsupported top-level field: {field}"
        )

    # -----------------------------------------------------------------------
    # Known hallucinated field
    # -----------------------------------------------------------------------

    def recursively_contains_key(value: Any, key: str) -> bool:
        if isinstance(value, dict):
            if key in value:
                return True

            return any(
                recursively_contains_key(v, key)
                for v in value.values()
            )

        if isinstance(value, list):
            return any(
                recursively_contains_key(v, key)
                for v in value
            )

        return False

    if recursively_contains_key(experiment, "altitudeKm"):
        failures.append(
            "V3: unsupported/hallucinated altitudeKm field"
        )

    return failures


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:

    failures: list[str] = []

    if not V3_TRAIN.exists():
        print(
            f"ERROR: dataset not found:\n{V3_TRAIN}"
        )
        return 1

    if not SCHEMA_PATH.exists():
        print(
            f"ERROR: schema not found:\n{SCHEMA_PATH}"
        )
        return 1

    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    schema_validator = Draft202012Validator(schema)

    try:
        records = load_jsonl(V3_TRAIN)
    except AssertionError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"V3 correction examples: {len(records)}")

    # -----------------------------------------------------------------------
    # Count
    # -----------------------------------------------------------------------

    if len(records) != EXPECTED_EXAMPLES:
        failures.append(
            f"expected {EXPECTED_EXAMPLES} examples, "
            f"got {len(records)}"
        )

    # -----------------------------------------------------------------------
    # Track correction IDs
    # -----------------------------------------------------------------------

    correction_ids: list[str] = []
    prefix_counts = Counter()

    user_requests: list[str] = []
    model_responses: list[str] = []

    for index, record in enumerate(records, start=1):

        record_failures = validate_outer_structure(record)

        if record_failures:
            for failure in record_failures:
                failures.append(
                    f"Record {index}: {failure}"
                )

            continue

        try:
            user_text = extract_user_text(record)
            experiment = extract_model_json(record)

        except AssertionError as exc:
            failures.append(
                f"Record {index}: {exc}"
            )
            continue

        user_requests.append(user_text)
        model_responses.append(
            json.dumps(
                experiment,
                sort_keys=True,
                separators=(",", ":"),
            )
        )

        # -------------------------------------------------------------------
        # Detect correction ID from user prompt
        # -------------------------------------------------------------------

        match = re.search(
            r"\b(VersionFix|CoordFix|DefForce|MinTest|ManId|ExactMan|Combo)(\d+)\b",
            user_text,
        )

        if not match:
            failures.append(
                f"Record {index}: missing V3 correction ID"
            )

        else:
            correction_id = (
                f"{match.group(1)}{match.group(2)}"
            )

            correction_ids.append(correction_id)
            prefix_counts[match.group(1)] += 1

        # -------------------------------------------------------------------
        # Raw GMAT leakage
        # -------------------------------------------------------------------

        raw_model_text = json.dumps(
            experiment,
            ensure_ascii=False,
        )

        if has_raw_gmat(raw_model_text):
            failures.append(
                f"Record {index}: raw GMAT leakage detected"
            )

        # -------------------------------------------------------------------
        # Schema/Pydantic/physical validation
        # -------------------------------------------------------------------

        experiment_failures = validate_experiment(
            experiment,
            schema_validator,
        )

        for failure in experiment_failures:
            failures.append(
                f"Record {index}: {failure}"
            )

        # -------------------------------------------------------------------
        # V3-specific validation
        # -------------------------------------------------------------------

        v3_failures = validate_v3_rules(
            user_text,
            experiment,
        )

        for failure in v3_failures:
            failures.append(
                f"Record {index}: {failure}"
            )

    # -----------------------------------------------------------------------
    # Correction ID uniqueness
    # -----------------------------------------------------------------------

    duplicate_ids = [
        correction_id
        for correction_id, count in Counter(correction_ids).items()
        if count > 1
    ]

    if duplicate_ids:
        failures.append(
            "duplicate correction IDs: "
            + ", ".join(sorted(duplicate_ids))
        )

    # -----------------------------------------------------------------------
    # Expected category counts
    # -----------------------------------------------------------------------

    for prefix, expected_count in EXPECTED_PREFIXES.items():

        actual_count = prefix_counts[prefix]

        if actual_count != expected_count:
            failures.append(
                f"{prefix}: expected {expected_count}, "
                f"got {actual_count}"
            )

    # -----------------------------------------------------------------------
    # Exact duplicate checks
    # -----------------------------------------------------------------------

    duplicate_users = [
        text_value
        for text_value, count in Counter(user_requests).items()
        if count > 1
    ]

    duplicate_responses = [
        text_value
        for text_value, count in Counter(model_responses).items()
        if count > 1
    ]

    if duplicate_users:
        failures.append(
            f"duplicate user requests: {len(duplicate_users)}"
        )

    if duplicate_responses:
        failures.append(
            f"duplicate model responses: {len(duplicate_responses)}"
        )

    # -----------------------------------------------------------------------
    # Near duplicate requests
    #
    # V3 correction examples are intentionally systematic, so do NOT reject
    # high-similarity pairs automatically. Report them only.
    # -----------------------------------------------------------------------

    near_duplicate_count = 0

    for i in range(len(user_requests)):
        for j in range(i + 1, len(user_requests)):

            similarity = jaccard_similarity(
                user_requests[i],
                user_requests[j],
            )

            if similarity >= 0.90:
                near_duplicate_count += 1

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------

    print()
    print("V3 category counts:")

    for prefix in EXPECTED_PREFIXES:
        print(
            f"  {prefix}: "
            f"{prefix_counts[prefix]}"
        )

    print()
    print(
        f"Duplicate user requests: "
        f"{len(duplicate_users)}"
    )

    print(
        f"Duplicate model responses: "
        f"{len(duplicate_responses)}"
    )

    print(
        f"Near-duplicate request pairs: "
        f"{near_duplicate_count}"
    )

    print(
        f"Failures: "
        f"{len(failures)}"
    )

    # -----------------------------------------------------------------------
    # Failure output
    # -----------------------------------------------------------------------

    if failures:

        print()
        print("FAILURES:")

        for failure in failures:
            print(f"- {failure}")

        return 1

    print()
    print("V3 correction dataset validation PASSED.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())