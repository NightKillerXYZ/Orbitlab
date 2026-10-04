"""Typed requests and results for GMAT execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple


class ExecutionStatus(str, Enum):
    SUCCESS = "success"


@dataclass(frozen=True)
class TrajectoryPoint:
    elapsed_secs: float
    x_km: float
    y_km: float
    z_km: float
    vx_km_s: float
    vy_km_s: float
    vz_km_s: float
    semi_major_axis_km: float
    eccentricity: float
    inclination_deg: float
    altitude_km: float


@dataclass(frozen=True)
class TrajectoryEvent:
    """A telemetry landmark that visualization downsampling must preserve."""

    point_index: int
    name: str


@dataclass(frozen=True)
class TrajectoryData:
    full: Tuple[TrajectoryPoint, ...]
    visualization: Tuple[TrajectoryPoint, ...]
    events: Tuple[TrajectoryEvent, ...] = ()


@dataclass(frozen=True)
class GmatExecutionRequest:
    """An unmodified, Phase 1-compiled GMAT script ready for execution."""

    compiled_script: str
    timeout_seconds: Optional[float] = None
    telemetry_filename: str = "telemetry.txt"
    events: Tuple[TrajectoryEvent, ...] = ()


@dataclass(frozen=True)
class GmatExecutionResult:
    status: ExecutionStatus
    exit_code: int
    trajectory: TrajectoryData
    duration_seconds: float
    stdout: str
    stderr: str
    run_id: str


@dataclass(frozen=True)
class GmatRunnerConfig:
    executable_path: Optional[Path] = None
    startup_file_path: Optional[Path] = None
    executable_environment_variable: str = "GMAT_CONSOLE_PATH"
    default_timeout_seconds: float = 30.0
    max_visualization_points: int = 2000
    sandbox_parent: Optional[Path] = field(default=None, repr=False)
