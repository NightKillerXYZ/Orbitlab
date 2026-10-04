"""OrbitLab Phase 2 simulation engine public API."""

from .config import discover_gmat_executable
from .downsampling import RamerDouglasPeuckerDownsampler, TrajectoryDownsampler
from .errors import (
    ErrorCode,
    ExecutionDiagnostics,
    GmatConfigurationError,
    GmatExecutionError,
    GmatExecutionFailure,
    GmatProcessError,
    GmatTimeoutError,
    InvalidExecutionRequestError,
    TelemetryMissingError,
    TelemetryParseError,
    TelemetryValidationError,
)
from .models import (
    ExecutionStatus,
    GmatExecutionRequest,
    GmatExecutionResult,
    GmatRunnerConfig,
    TrajectoryData,
    TrajectoryEvent,
    TrajectoryPoint,
)
from .runner import GmatRunner
from .telemetry import GmatReportParser

__all__ = [
    "ErrorCode",
    "ExecutionDiagnostics",
    "ExecutionStatus",
    "GmatConfigurationError",
    "GmatExecutionError",
    "GmatExecutionFailure",
    "GmatExecutionRequest",
    "GmatExecutionResult",
    "GmatProcessError",
    "GmatReportParser",
    "GmatRunner",
    "GmatRunnerConfig",
    "GmatTimeoutError",
    "InvalidExecutionRequestError",
    "RamerDouglasPeuckerDownsampler",
    "TelemetryMissingError",
    "TelemetryParseError",
    "TelemetryValidationError",
    "TrajectoryData",
    "TrajectoryDownsampler",
    "TrajectoryEvent",
    "TrajectoryPoint",
    "discover_gmat_executable",
]
