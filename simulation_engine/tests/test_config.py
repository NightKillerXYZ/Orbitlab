import tempfile
import unittest
from pathlib import Path

from orbitlab_simulation_engine import (
    GmatConfigurationError,
    GmatRunnerConfig,
    discover_gmat_executable,
)
from orbitlab_simulation_engine.config import resolve_gmat_startup_file


class TestGmatExecutableDiscovery(unittest.TestCase):
    def test_explicit_path_takes_precedence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / "GmatConsole.exe"
            executable.touch()
            config = GmatRunnerConfig(executable_path=executable)

            self.assertEqual(discover_gmat_executable(config, environment={}), executable.resolve())

    def test_discovers_environment_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / "GmatConsole.exe"
            executable.touch()
            config = GmatRunnerConfig()

            resolved = discover_gmat_executable(
                config,
                environment={"GMAT_CONSOLE_PATH": str(executable)},
            )

            self.assertEqual(resolved, executable.resolve())

    def test_reports_clear_configuration_error(self):
        config = GmatRunnerConfig(executable_path=Path("definitely-missing-GmatConsole.exe"))
        with self.assertRaisesRegex(GmatConfigurationError, "does not exist"):
            discover_gmat_executable(config, environment={})

    def test_resolves_explicit_startup_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            executable = root / "GmatConsole.exe"
            startup = root / "custom_startup.txt"
            executable.touch()
            startup.touch()
            config = GmatRunnerConfig(
                executable_path=executable,
                startup_file_path=startup,
            )

            self.assertEqual(resolve_gmat_startup_file(config, executable), startup.resolve())
