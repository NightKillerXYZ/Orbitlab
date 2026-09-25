"""OrbitLab Physics Core: AST, Schema Validation, and Deterministic GMAT Compiler."""

from orbitlab_core.ast.models import (
    AtmosphericDragConfig,
    BurnVector,
    CartesianElements,
    EpochConfig,
    ForceModelConfig,
    InitialOrbitConfig,
    KeplerianElements,
    ManeuverConfig,
    ManeuverTrigger,
    OrbitLabExperiment,
    PropagationConfig,
    SpacecraftConfig,
    StopCondition,
    TargetObjectives,
)
from orbitlab_core.ast.validation import (
    AstrodynamicProperties,
    AstrodynamicValidator,
    ValidationResult,
)
from orbitlab_core.compiler.generator import GmatScriptCompiler

__version__ = "1.0.0"

__all__ = [
    "OrbitLabExperiment",
    "SpacecraftConfig",
    "EpochConfig",
    "KeplerianElements",
    "CartesianElements",
    "InitialOrbitConfig",
    "ForceModelConfig",
    "AtmosphericDragConfig",
    "ManeuverConfig",
    "ManeuverTrigger",
    "BurnVector",
    "TargetObjectives",
    "PropagationConfig",
    "StopCondition",
    "AstrodynamicValidator",
    "AstrodynamicProperties",
    "ValidationResult",
    "GmatScriptCompiler",
    "__version__",
]
