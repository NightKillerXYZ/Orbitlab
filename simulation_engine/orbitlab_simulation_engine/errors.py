"""Typed failures exposed by the OrbitLab simulation engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class ErrorCode(str, Enum):
    CONFIGURATION = "configuration_error"
    INVALID_REQUEST = "invalid_request"
    TIMEOUT = "timeout"
    PROCESS_FAILURE = "process_failure"
    GMAT_FAILURE = "gmat_execution_failure"
    TELEMETRY_MISSING = "telemetry_missing"
    TELEMETRY_PARSE = "telemetry_parse_failure"
    TELEMETRY_INVALID = "invalid_telemetry"


@dataclass(frozen=True)
class ExecutionDiagnostics:
    """Diagnostics retained when an execution cannot produce a valid result."""

    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    duration_seconds: float = 0.0
    telemetry_path: Optional[Path] = None


class GmatExecutionError(Exception):
    """Base class for typed simulation failures."""

    code: ErrorCode

    def __init__(
        self,
        message: str,
        *,
        diagnostics: Optional[ExecutionDiagnostics] = None,
    ) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or ExecutionDiagnostics()


class GmatConfigurationError(GmatExecutionError):
    code = ErrorCode.CONFIGURATION


class InvalidExecutionRequestError(GmatExecutionError):
    code = ErrorCode.INVALID_REQUEST


class GmatTimeoutError(GmatExecutionError):
    code = ErrorCode.TIMEOUT


class GmatProcessError(GmatExecutionError):
    code = ErrorCode.PROCESS_FAILURE


class GmatExecutionFailure(GmatExecutionError):
    code = ErrorCode.GMAT_FAILURE


class TelemetryMissingError(GmatExecutionError):
    code = ErrorCode.TELEMETRY_MISSING


class TelemetryParseError(GmatExecutionError):
    code = ErrorCode.TELEMETRY_PARSE


class TelemetryValidationError(GmatExecutionError):
    code = ErrorCode.TELEMETRY_INVALID
