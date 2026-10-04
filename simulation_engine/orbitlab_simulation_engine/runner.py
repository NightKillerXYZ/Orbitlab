"""Asynchronous, sandboxed NASA GMAT execution."""

from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional

from .config import (
    discover_gmat_executable,
    resolve_gmat_startup_file,
    validate_runner_config,
)
from .downsampling import RamerDouglasPeuckerDownsampler, TrajectoryDownsampler
from .errors import (
    ExecutionDiagnostics,
    GmatConfigurationError,
    GmatExecutionError,
    GmatExecutionFailure,
    GmatProcessError,
    GmatTimeoutError,
    InvalidExecutionRequestError,
)
from .models import (
    ExecutionStatus,
    GmatExecutionRequest,
    GmatExecutionResult,
    GmatRunnerConfig,
    TrajectoryData,
)
from .telemetry import GmatReportParser


_OUTPUT_FILENAME_PATTERN = re.compile(
    r"^\s*[A-Za-z0-9_]+\.Filename\s*=\s*['\"]([^'\"]+)['\"]\s*;",
    re.IGNORECASE | re.MULTILINE,
)
_OUTPUT_PATH_PATTERN = re.compile(
    r"^\s*OUTPUT_PATH\s*=.*$",
    re.IGNORECASE | re.MULTILINE,
)


class GmatRunner:
    """Execute Phase 1-compiled scripts without altering their contents."""

    def __init__(
        self,
        config: Optional[GmatRunnerConfig] = None,
        *,
        parser: Optional[GmatReportParser] = None,
        downsampler: Optional[TrajectoryDownsampler] = None,
    ) -> None:
        self.config = config or GmatRunnerConfig()
        validate_runner_config(self.config)
        self.executable = discover_gmat_executable(self.config)
        self.startup_file = resolve_gmat_startup_file(self.config, self.executable)
        self.parser = parser or GmatReportParser()
        self.downsampler = downsampler or RamerDouglasPeuckerDownsampler()

    async def execute(self, request: GmatExecutionRequest) -> GmatExecutionResult:
        """Run GMAT and return only complete, strictly validated telemetry."""

        timeout = (
            request.timeout_seconds
            if request.timeout_seconds is not None
            else self.config.default_timeout_seconds
        )
        self._validate_request(request, timeout)
        run_id = uuid.uuid4().hex
        started = time.perf_counter()
        process: Optional[asyncio.subprocess.Process] = None
        communication_task: Optional[asyncio.Task[tuple[bytes, bytes]]] = None

        with tempfile.TemporaryDirectory(
            prefix=f"orbitlab-{run_id}-",
            dir=self.config.sandbox_parent,
        ) as sandbox_name:
            sandbox = Path(sandbox_name)
            script_path = sandbox / "experiment.script"
            telemetry_path = sandbox / Path(request.telemetry_filename)
            telemetry_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(request.compiled_script, encoding="utf-8")
            startup_path = self._create_sandbox_startup_file(sandbox)

            try:
                process = await self._start_process(script_path, startup_path, sandbox)
                communication_task = asyncio.create_task(process.communicate())
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        asyncio.shield(communication_task), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    await self._terminate_process_tree(process)
                    stdout_bytes, stderr_bytes = await self._finish_communication(communication_task)
                    duration = time.perf_counter() - started
                    raise GmatTimeoutError(
                        f"GMAT execution exceeded the {timeout:.3f}s timeout",
                        diagnostics=self._diagnostics(
                            stdout_bytes,
                            stderr_bytes,
                            process.returncode,
                            duration,
                            telemetry_path,
                        ),
                    )
                except asyncio.CancelledError:
                    await self._terminate_process_tree(process)
                    await self._finish_communication(communication_task)
                    raise
            except GmatExecutionError:
                raise
            except asyncio.CancelledError:
                raise
            except OSError as exc:
                duration = time.perf_counter() - started
                raise GmatProcessError(
                    f"Unable to start GMAT process: {exc}",
                    diagnostics=ExecutionDiagnostics(duration_seconds=duration),
                ) from exc

            duration = time.perf_counter() - started
            diagnostics = self._diagnostics(
                stdout_bytes,
                stderr_bytes,
                process.returncode,
                duration,
                telemetry_path,
            )
            if process.returncode != 0:
                raise GmatExecutionFailure(
                    f"GMAT exited with non-zero status {process.returncode}",
                    diagnostics=diagnostics,
                )

            try:
                full_trajectory = self.parser.parse(telemetry_path)
                landmark_indices = tuple(event.point_index for event in request.events)
                visualization = self.downsampler.downsample(
                    full_trajectory,
                    self.config.max_visualization_points,
                    landmark_indices,
                )
            except GmatExecutionError as exc:
                raise type(exc)(str(exc), diagnostics=diagnostics) from exc
            except ValueError as exc:
                raise InvalidExecutionRequestError(
                    f"Invalid trajectory event landmarks: {exc}",
                    diagnostics=diagnostics,
                ) from exc

            return GmatExecutionResult(
                status=ExecutionStatus.SUCCESS,
                exit_code=process.returncode,
                trajectory=TrajectoryData(
                    full=full_trajectory,
                    visualization=visualization,
                    events=request.events,
                ),
                duration_seconds=duration,
                stdout=diagnostics.stdout,
                stderr=diagnostics.stderr,
                run_id=run_id,
            )

    def _validate_request(self, request: GmatExecutionRequest, timeout: float) -> None:
        if not request.compiled_script.strip():
            raise InvalidExecutionRequestError("compiled_script must not be empty")
        if timeout <= 0:
            raise InvalidExecutionRequestError("timeout_seconds must be greater than zero")
        self._validate_relative_output_path(request.telemetry_filename, "telemetry filename")
        for output_path in _OUTPUT_FILENAME_PATTERN.findall(request.compiled_script):
            self._validate_relative_output_path(output_path, "GMAT output filename")

    @staticmethod
    def _validate_relative_output_path(value: str, label: str) -> None:
        windows_path = PureWindowsPath(value)
        posix_path = PurePosixPath(value.replace("\\", "/"))
        if (
            not value.strip()
            or windows_path.is_absolute()
            or posix_path.is_absolute()
            or ".." in windows_path.parts
            or ".." in posix_path.parts
        ):
            raise InvalidExecutionRequestError(
                f"{label} must remain within the run sandbox: {value!r}"
            )

    async def _start_process(
        self,
        script_path: Path,
        startup_path: Path,
        sandbox: Path,
    ) -> asyncio.subprocess.Process:
        kwargs: dict[str, object] = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        return await asyncio.create_subprocess_exec(
            str(self.executable),
            "--startup_file",
            str(startup_path),
            "--run",
            str(script_path),
            "--exit",
            cwd=str(sandbox),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **kwargs,
        )

    def _create_sandbox_startup_file(self, sandbox: Path) -> Path:
        try:
            template = self.startup_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise GmatConfigurationError(
                f"Unable to read GMAT startup file: {self.startup_file}"
            ) from exc
        output_path = sandbox.as_posix() + "/"
        replacement = f"OUTPUT_PATH            = {output_path}"
        configured, replacements = _OUTPUT_PATH_PATTERN.subn(replacement, template, count=1)
        if replacements != 1:
            raise GmatConfigurationError(
                f"GMAT startup file has no OUTPUT_PATH setting: {self.startup_file}"
            )
        startup_path = sandbox / "gmat_startup_file.txt"
        startup_path.write_text(configured, encoding="utf-8")
        return startup_path

    async def _terminate_process_tree(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        if os.name == "nt":
            try:
                terminator = await asyncio.create_subprocess_exec(
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await terminator.wait()
                if terminator.returncode != 0 and process.returncode is None:
                    process.kill()
            except OSError:
                process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except (ProcessLookupError, asyncio.TimeoutError):
                if process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            if process.returncode is None:
                process.kill()
                await process.wait()

    @staticmethod
    async def _finish_communication(
        communication_task: asyncio.Task[tuple[bytes, bytes]],
    ) -> tuple[bytes, bytes]:
        try:
            return await asyncio.wait_for(asyncio.shield(communication_task), timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            communication_task.cancel()
            return b"", b""

    @staticmethod
    def _diagnostics(
        stdout: bytes,
        stderr: bytes,
        exit_code: Optional[int],
        duration: float,
        telemetry_path: Path,
    ) -> ExecutionDiagnostics:
        return ExecutionDiagnostics(
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            exit_code=exit_code,
            duration_seconds=duration,
            telemetry_path=telemetry_path,
        )
