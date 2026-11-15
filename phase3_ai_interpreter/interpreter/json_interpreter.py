"""A concrete interpreter that turns the model's compact JSON into a validated
experiment.

The JSON payload is the exact format produced as the assistant answer in the v9b
training rows: a single compact JSON object matching the OrbitLab experiment
schema.  The interpreter runs the same chain the validators use:

  1. strict JSON parse (no code / GMAT leakage tolerated by the dataset rules),
  2. Pydantic AST load,
  3. astrodynamic physical validation,
  4. deterministic GMAT compilation.

The result is an :class:`InterpretationResult` carrying the validated model and
the compiled script when every stage succeeds.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from orbitlab_core.ast.models import OrbitLabExperiment
from orbitlab_core.ast.validation import AstrodynamicValidator
from orbitlab_core.compiler.generator import GmatScriptCompiler

from .model import IExperimentInterpreter, InterpretationResult

ROOT_FIELDS = {"version", "experimentName", "description", "spacecraft", "centralBody", "epoch", "initialOrbit", "forceModel", "maneuvers", "propagation"}
ALLOWED_FIELDS = {
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


def _unsupported_fields(payload: dict[str, Any]) -> list[str]:
    """Return dotted paths of fields outside the experiment schema, matching the
    dataset validator's unsupported-field detection (Pydantic alone tolerates
    extra fields, so this is checked explicitly)."""
    out: list[str] = []
    if not isinstance(payload, dict):
        return ["$ not an object"]
    out.extend(f"$.{key}" for key in payload if key not in ROOT_FIELDS)
    for parent in ("spacecraft", "epoch", "initialOrbit", "forceModel", "propagation"):
        child = payload.get(parent)
        if isinstance(child, dict):
            out.extend(f"$.{parent}.{key}" for key in child if key not in ALLOWED_FIELDS[parent])
    orbit = payload.get("initialOrbit", {})
    if isinstance(orbit, dict) and isinstance(orbit.get("elements"), dict):
        out.extend(f"$.initialOrbit.elements.{key}" for key in orbit["elements"] if key not in ALLOWED_FIELDS.get(orbit.get("type"), set()))
    force = payload.get("forceModel", {})
    if isinstance(force, dict) and isinstance(force.get("atmosphericDrag"), dict):
        out.extend(f"$.forceModel.atmosphericDrag.{key}" for key in force["atmosphericDrag"] if key not in ALLOWED_FIELDS["atmosphericDrag"])
    for i, maneuver in enumerate(payload.get("maneuvers", [])):
        if not isinstance(maneuver, dict):
            out.append(f"$.maneuvers[{i}]")
            continue
        out.extend(f"$.maneuvers[{i}].{key}" for key in maneuver if key not in ALLOWED_FIELDS["maneuver"])
        for parent in ("trigger", "burnVector", "targetObjectives"):
            if isinstance(maneuver.get(parent), dict):
                out.extend(f"$.maneuvers[{i}].{parent}.{key}" for key in maneuver[parent] if key not in ALLOWED_FIELDS[parent])
    return out


class JsonExperimentInterpreter(IExperimentInterpreter):
    """Interprets compact-JSON experiment payloads into validated experiments."""

    def __init__(self) -> None:
        self._compiler = GmatScriptCompiler()

    def interpret(self, raw_text: str) -> InterpretationResult:
        errors: list[str] = []
        warnings: list[str] = []

        try:
            payload = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError) as exc:
            return InterpretationResult(success=False, errors=[f"json: {exc}"])

        if not isinstance(payload, dict):
            return InterpretationResult(success=False, errors=["json: payload is not an object"])

        unsupported = _unsupported_fields(payload)
        if unsupported:
            return InterpretationResult(success=False, errors=["unsupported:" + p for p in unsupported])

        try:
            experiment = OrbitLabExperiment.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - convert any Pydantic error to a message
            return InterpretationResult(success=False, errors=[f"pydantic: {exc}"])

        physical = AstrodynamicValidator.validate(experiment)
        if not physical.is_valid:
            errors = errors + ["physical:" + message for message in physical.errors]
        warnings = warnings + list(physical.warnings)

        compiled: Optional[str] = None
        if not errors:
            try:
                compiled = self._compiler.compile_to_string(experiment)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"compiler: {exc}")

        success = not errors and compiled is not None
        return InterpretationResult(
            success=success,
            experiment=experiment if success else None,
            errors=errors,
            warnings=warnings,
            compiled=compiled,
        )

    def interpret_pretty(self, raw_text: str) -> str:
        """Human-readable summary of an interpretation (used by the CLI)."""
        result = self.interpret(raw_text)
        if result.success:
            assert result.experiment is not None
            experiment = result.experiment
            body = experiment.centralBody
            orbit = experiment.initialOrbit
            elements = orbit.elements
            line = [
                f"SUCCESS experiment={experiment.experimentName}",
                f"  centralBody={body}",
                f"  orbit={orbit.type} sma={getattr(elements, 'semiMajorAxisKm', None)} km",
                f"  inspector=JsonExperimentInterpreter",
            ]
            return "\n".join(line)
        return "FAILED\n  " + "\n  ".join(result.errors)
