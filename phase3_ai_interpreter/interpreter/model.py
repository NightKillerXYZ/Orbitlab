"""Interpreter contracts: the interpretation interface and result object."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from orbitlab_core.ast.models import OrbitLabExperiment


@dataclass
class InterpretationResult:
    """Outcome of interpreting a model-produced experiment payload.

    Attributes
    ----------
    success:
        True only when the raw text parsed, loaded into the AST and passed both
        the astrodynamic physical validator and the deterministic GMAT compiler.
    experiment:
        The validated experiment model, or ``None`` on failure.
    errors:
        Human-readable failures encountered along the pipeline.
    warnings:
        Physical-validation warnings that did not block interpretation.
    compiled:
        The deterministic GMAT script when compilation succeeded, else ``None``.
    """

    success: bool
    experiment: Optional[OrbitLabExperiment] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    compiled: Optional[str] = None

    @property
    def is_valid_physical(self) -> bool:
        return not any(e.startswith("physical:") for e in self.errors)

    @property
    def is_compileable(self) -> bool:
        return self.compiled is not None


class IExperimentInterpreter(ABC):
    """Minimal callable interface for any experiment interpreter.

    Implementations translate raw natural-language-derived payloads (here: the
    compact JSON produced by the model) into a validated :class:`InterpretationResult`.
    """

    @abstractmethod
    def interpret(self, raw_text: str) -> InterpretationResult:
        """Parse ``raw_text`` and return an :class:`InterpretationResult`."""
        raise NotImplementedError


def can_interpret(interpreter: IExperimentInterpreter, raw_text: str) -> bool:
    """Convenience predicate: True when the interpreter produced a success result."""
    return interpreter.interpret(raw_text).success
