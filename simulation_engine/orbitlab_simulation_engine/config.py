"""GMAT executable discovery and runner configuration validation."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Mapping, Optional

from .errors import GmatConfigurationError
from .models import GmatRunnerConfig


def discover_gmat_executable(
    config: GmatRunnerConfig,
    *,
    environment: Optional[Mapping[str, str]] = None,
) -> Path:
    """Resolve GmatConsole from explicit config, environment, or PATH."""

    env = os.environ if environment is None else environment
    candidates: list[Path] = []

    if config.executable_path is not None:
        candidates.append(Path(config.executable_path).expanduser())
    else:
        configured = env.get(config.executable_environment_variable)
        if configured:
            candidates.append(Path(configured).expanduser())

        for home_variable in ("GMAT_HOME", "GMAT_ROOT"):
            home = env.get(home_variable)
            if home:
                candidates.append(Path(home).expanduser() / "bin" / "GmatConsole.exe")

        on_path = shutil.which("GmatConsole.exe") or shutil.which("GmatConsole")
        if on_path:
            candidates.append(Path(on_path))

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved

    if config.executable_path is not None:
        detail = f"Configured GMAT executable does not exist: {config.executable_path}"
    else:
        detail = (
            "GMAT executable was not found. Configure executable_path, set "
            f"{config.executable_environment_variable}, GMAT_HOME, or GMAT_ROOT, "
            "or add GmatConsole to PATH."
        )
    raise GmatConfigurationError(detail)


def validate_runner_config(config: GmatRunnerConfig) -> None:
    if config.default_timeout_seconds <= 0:
        raise GmatConfigurationError("default_timeout_seconds must be greater than zero")
    if not 2 <= config.max_visualization_points <= 2000:
        raise GmatConfigurationError(
            "max_visualization_points must be between 2 and the Phase 2 limit of 2000"
        )
    if config.sandbox_parent is not None:
        parent = Path(config.sandbox_parent)
        if not parent.is_dir():
            raise GmatConfigurationError(f"Sandbox parent is not a directory: {parent}")


def resolve_gmat_startup_file(config: GmatRunnerConfig, executable: Path) -> Path:
    """Resolve the startup template used to create a run-local GMAT configuration."""

    startup_file = (
        Path(config.startup_file_path).expanduser()
        if config.startup_file_path is not None
        else executable.parent / "gmat_startup_file.txt"
    ).resolve()
    if not startup_file.is_file():
        raise GmatConfigurationError(f"GMAT startup file does not exist: {startup_file}")
    return startup_file
