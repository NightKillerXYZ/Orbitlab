import asyncio
import tempfile
import unittest
from pathlib import Path

from orbitlab_simulation_engine import (
    ExecutionStatus,
    GmatExecutionFailure,
    GmatExecutionRequest,
    GmatRunner,
    GmatRunnerConfig,
    GmatTimeoutError,
    InvalidExecutionRequestError,
    TelemetryMissingError,
    TrajectoryEvent,
)

from .test_telemetry import HEADER


class FakeProcess:
    def __init__(self, *, returncode=0, wait_forever=False):
        self.returncode = None if wait_forever else returncode
        self._event = asyncio.Event()
        if not wait_forever:
            self._event.set()
        self._final_returncode = returncode
        self.pid = 999999
        self.killed = False

    async def communicate(self):
        await self._event.wait()
        self.returncode = self._final_returncode
        return b"captured stdout", b"captured stderr"

    async def wait(self):
        await self._event.wait()
        self.returncode = self._final_returncode
        return self.returncode

    def kill(self):
        self.killed = True
        self._final_returncode = -9
        self.returncode = -9
        self._event.set()


class StubRunner(GmatRunner):
    def __init__(self, config, process, *, write_telemetry=True):
        self._process = process
        self._write_telemetry = write_telemetry
        super().__init__(config)

    async def _start_process(self, script_path, startup_path, sandbox):
        if self._write_telemetry:
            (sandbox / "telemetry.txt").write_text(
                HEADER + "\n0 7000 0 0 0 7.5 0 7000 0.001 28.5 621.864\n",
                encoding="utf-8",
            )
        return self._process


class TestGmatRunner(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.executable = root / "GmatConsole.exe"
        self.executable.touch()
        (root / "gmat_startup_file.txt").write_text(
            "ROOT_PATH = ../\nOUTPUT_PATH = ../output/\nLOG_FILE = OUTPUT_PATH/GmatLog.txt\n",
            encoding="utf-8",
        )
        self.sandboxes = root / "sandboxes"
        self.sandboxes.mkdir()
        self.config = GmatRunnerConfig(
            executable_path=self.executable,
            sandbox_parent=self.sandboxes,
            max_visualization_points=2,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_returns_typed_result_and_cleans_sandbox(self):
        runner = StubRunner(self.config, FakeProcess())

        result = await runner.execute(GmatExecutionRequest(compiled_script="BeginMissionSequence;"))

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(result.stdout, "captured stdout")
        self.assertEqual(result.trajectory.full, result.trajectory.visualization)
        self.assertEqual(list(self.sandboxes.iterdir()), [])

    async def test_nonzero_exit_is_typed_failure_and_cleans_sandbox(self):
        runner = StubRunner(self.config, FakeProcess(returncode=7))

        with self.assertRaises(GmatExecutionFailure) as raised:
            await runner.execute(GmatExecutionRequest(compiled_script="BeginMissionSequence;"))

        self.assertEqual(raised.exception.diagnostics.exit_code, 7)
        self.assertEqual(raised.exception.diagnostics.stderr, "captured stderr")
        self.assertEqual(list(self.sandboxes.iterdir()), [])

    async def test_missing_telemetry_is_failure(self):
        runner = StubRunner(self.config, FakeProcess(), write_telemetry=False)

        with self.assertRaises(TelemetryMissingError):
            await runner.execute(GmatExecutionRequest(compiled_script="BeginMissionSequence;"))

    async def test_timeout_terminates_process_and_cleans_sandbox(self):
        process = FakeProcess(wait_forever=True)
        runner = StubRunner(self.config, process)

        with self.assertRaises(GmatTimeoutError):
            await runner.execute(
                GmatExecutionRequest(
                    compiled_script="BeginMissionSequence;",
                    timeout_seconds=0.01,
                )
            )

        self.assertTrue(process.killed)
        self.assertEqual(list(self.sandboxes.iterdir()), [])

    async def test_cancellation_terminates_process_and_cleans_sandbox(self):
        process = FakeProcess(wait_forever=True)
        runner = StubRunner(self.config, process)
        task = asyncio.create_task(
            runner.execute(GmatExecutionRequest(compiled_script="BeginMissionSequence;"))
        )
        await asyncio.sleep(0)

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertTrue(process.killed)
        self.assertEqual(list(self.sandboxes.iterdir()), [])

    async def test_rejects_outputs_outside_sandbox(self):
        runner = StubRunner(self.config, FakeProcess())
        request = GmatExecutionRequest(
            compiled_script="OrbitLabReport.Filename = 'C:/outside/telemetry.txt';"
        )

        with self.assertRaisesRegex(InvalidExecutionRequestError, "sandbox"):
            await runner.execute(request)

    async def test_rejects_non_positive_timeout(self):
        runner = StubRunner(self.config, FakeProcess())
        with self.assertRaisesRegex(InvalidExecutionRequestError, "greater than zero"):
            await runner.execute(
                GmatExecutionRequest(
                    compiled_script="BeginMissionSequence;",
                    timeout_seconds=0.0,
                )
            )

    async def test_event_landmark_is_preserved_in_result(self):
        runner = StubRunner(self.config, FakeProcess())
        event = TrajectoryEvent(point_index=0, name="burn")

        result = await runner.execute(
            GmatExecutionRequest(
                compiled_script="BeginMissionSequence;",
                events=(event,),
            )
        )

        self.assertEqual(result.trajectory.events, (event,))
