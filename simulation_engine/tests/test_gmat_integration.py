import tempfile
import unittest
from pathlib import Path

from orbitlab_core import (
    GmatScriptCompiler,
    InitialOrbitConfig,
    KeplerianElements,
    OrbitLabExperiment,
    PropagationConfig,
    SpacecraftConfig,
    StopCondition,
)
from orbitlab_simulation_engine import (
    ExecutionStatus,
    GmatExecutionRequest,
    GmatRunner,
    GmatRunnerConfig,
    GmatTimeoutError,
)


GMAT_CONSOLE_PATH = Path(r"C:\Users\canit\XY\Downloads\gmat-win-R2026a\bin\GmatConsole.exe")


def compiled_phase1_scenario() -> str:
    experiment = OrbitLabExperiment(
        experimentName="Phase2_Integration_LEO",
        spacecraft=SpacecraftConfig(name="Phase2Sat", dryMassKg=450.0),
        initialOrbit=InitialOrbitConfig(
            type="Keplerian",
            elements=KeplerianElements(
                semiMajorAxisKm=6900.0,
                eccentricity=0.001,
                inclinationDeg=51.6,
            ),
        ),
        propagation=PropagationConfig(
            stopCondition=StopCondition(type="ElapsedSeconds", value=120.0),
            stepSizeSecs=60.0,
        ),
    )
    return GmatScriptCompiler().compile_to_string(experiment)


@unittest.skipUnless(GMAT_CONSOLE_PATH.exists(), "GMAT R2026a GmatConsole.exe not installed")
class TestGmatRunnerIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_phase1_script_executes_and_returns_typed_trajectory(self):
        with tempfile.TemporaryDirectory() as parent:
            runner = GmatRunner(
                GmatRunnerConfig(
                    executable_path=GMAT_CONSOLE_PATH,
                    sandbox_parent=Path(parent),
                )
            )

            result = await runner.execute(
                GmatExecutionRequest(compiled_script=compiled_phase1_scenario())
            )

            self.assertEqual(result.status, ExecutionStatus.SUCCESS)
            self.assertEqual(result.exit_code, 0)
            self.assertGreater(len(result.trajectory.full), 1)
            self.assertAlmostEqual(result.trajectory.full[0].inclination_deg, 51.6, delta=0.1)
            self.assertLessEqual(len(result.trajectory.visualization), 2000)
            self.assertEqual(list(Path(parent).iterdir()), [])

    async def test_real_gmat_timeout_cleans_run_directory(self):
        with tempfile.TemporaryDirectory() as parent:
            runner = GmatRunner(
                GmatRunnerConfig(
                    executable_path=GMAT_CONSOLE_PATH,
                    sandbox_parent=Path(parent),
                )
            )

            with self.assertRaises(GmatTimeoutError):
                await runner.execute(
                    GmatExecutionRequest(
                        compiled_script=compiled_phase1_scenario(),
                        timeout_seconds=0.001,
                    )
                )

            self.assertEqual(list(Path(parent).iterdir()), [])
