"""OrbitLab Experiment Interpreter.

A small, dependency-light runtime (standard library + the existing
``orbitlab_core`` AST/validation/compiler modules) that interprets a model's
JSON experiment output into a validated :class:`OrbitLabExperiment`, running the
same schema/Pydantic/physical/compiler chain used to validate the training sets.

This satisfies the phase-3 gap where no callable interpreter implementation
existed in the repository.
"""

from .json_interpreter import JsonExperimentInterpreter
from .model import IExperimentInterpreter, InterpretationResult

__all__ = ["IExperimentInterpreter", "InterpretationResult", "JsonExperimentInterpreter"]
