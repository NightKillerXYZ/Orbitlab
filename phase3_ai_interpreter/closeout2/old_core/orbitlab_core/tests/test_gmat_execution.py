"""Integration tests executing compiler-generated scripts with NASA GMAT Console."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from orbitlab_core.ast.models import (
    AtmosphericDragConfig,
    BurnVector,
    CartesianElements,
    ForceModelConfig,
    InitialOrbitConfig,
    KeplerianElements,
    ManeuverConfig,
    ManeuverTrigger,
    OrbitLabExperiment,
    PropagationConfig,
    SpacecraftConfig,
    StopCondition,
)
from orbitlab_core.compiler.generator import GmatScriptCompiler

GMAT_CONSOLE_PATH = Path(r"C:\Users\canit\XY\Downloads\gmat-win-R2026a\bin\GmatConsole.exe")


@unittest.skipUnless(GMAT_CONSOLE_PATH.exists(), "GMAT Console executable not found on host")
class TestGmatExecutionIntegration(unittest.TestCase):
    """Smoke test ensuring generated scripts execute cleanly in NASA GMAT R2026a."""

    def setUp(self):
        self.compiler = GmatScriptCompiler()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workdir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run_gmat(self, script_path: Path) -> subprocess.CompletedProcess:
        cmd = [
            str(GMAT_CONSOLE_PATH),
            "--run",
            str(script_path),
            "--exit",
        ]
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def test_gmat_run_circular_leo(self):
        exp = OrbitLabExperiment(
            experimentName="GMAT_Smoke_CircularLEO",
            spacecraft=SpacecraftConfig(name="SatSmoke", dryMassKg=450.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=6900.0,
                    eccentricity=0.001,
                    inclinationDeg=51.6,
                    raanDeg=45.0,
                    argumentOfPeriapsisDeg=0.0,
                    trueAnomalyDeg=0.0,
                ),
            ),
            forceModel=ForceModelConfig(
                gravityDegree=4,
                gravityOrder=4,
                pointMasses=["Sun", "Luna"],
                atmosphericDrag=AtmosphericDragConfig(enabled=True, model="JacchiaRoberts"),
                solarRadiationPressure=True,
            ),
            propagation=PropagationConfig(
                integrator="RungeKutta89",
                stopCondition=StopCondition(type="ElapsedMinutes", value=30.0) if False else StopCondition(type="ElapsedHours", value=0.5),
                stepSizeSecs=60.0,
            ),
        )

        script_file = self.workdir / "smoke_leo.script"
        telemetry_file = self.workdir / "telemetry_leo.txt"

        self.compiler.compile_to_file(
            exp,
            output_script_path=str(script_file),
            telemetry_filepath=str(telemetry_file)
        )

        result = self._run_gmat(script_file)
        self.assertEqual(result.returncode, 0, f"GMAT execution failed:\n{result.stdout}\n{result.stderr}")
        self.assertTrue(telemetry_file.exists(), "Telemetry output file was not produced")

        lines = telemetry_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertGreater(len(lines), 2, "Telemetry output should contain header and multiple data rows")
        # Verify columns in header
        header = lines[0]
        required_columns = (
            "SatSmoke.ElapsedSecs",
            "SatSmoke.EarthMJ2000Eq.X",
            "SatSmoke.EarthMJ2000Eq.Y",
            "SatSmoke.EarthMJ2000Eq.Z",
            "SatSmoke.EarthMJ2000Eq.VX",
            "SatSmoke.EarthMJ2000Eq.VY",
            "SatSmoke.EarthMJ2000Eq.VZ",
            "SatSmoke.Earth.SMA",
            "SatSmoke.Earth.ECC",
            "SatSmoke.INC",
            "SatSmoke.Earth.Altitude",
        )
        for column in required_columns:
            self.assertIn(column, header)

    def test_gmat_run_cartesian_propagation(self):
        exp = OrbitLabExperiment(
            experimentName="GMAT_Smoke_Cartesian",
            spacecraft=SpacecraftConfig(name="CartSatSmoke", dryMassKg=500.0),
            initialOrbit=InitialOrbitConfig(
                type="Cartesian",
                elements=CartesianElements(
                    xKm=7000.0,
                    yKm=0.0,
                    zKm=0.0,
                    vxKmS=0.0,
                    vyKmS=7.546,
                    vzKmS=0.0,
                ),
            ),
            propagation=PropagationConfig(
                integrator="PrinceDormand78",
                stopCondition=StopCondition(type="ElapsedSeconds", value=300.0),
                stepSizeSecs=60.0,
            ),
        )

        script_file = self.workdir / "smoke_cart.script"
        telemetry_file = self.workdir / "telemetry_cart.txt"

        self.compiler.compile_to_file(
            exp,
            output_script_path=str(script_file),
            telemetry_filepath=str(telemetry_file)
        )

        result = self._run_gmat(script_file)
        self.assertEqual(result.returncode, 0, f"GMAT execution failed:\n{result.stdout}\n{result.stderr}")
        self.assertTrue(telemetry_file.exists(), "Telemetry output was not produced")

    def test_gmat_run_impulsive_burn(self):
        exp = OrbitLabExperiment(
            experimentName="GMAT_Smoke_Burn",
            spacecraft=SpacecraftConfig(name="BurnSatSmoke", dryMassKg=600.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=6900.0,
                    eccentricity=0.01,
                    inclinationDeg=28.5,
                ),
            ),
            maneuvers=[
                ManeuverConfig(
                    id="DeltaV1",
                    type="ImpulsiveBurn",
                    trigger=ManeuverTrigger(condition="AtPeriapsis"),
                    burnVector=BurnVector(deltaVVectorKmS=[0.050, 0.0, 0.0]),
                )
            ],
            propagation=PropagationConfig(
                integrator="RungeKutta89",
                stopCondition=StopCondition(type="ElapsedHours", value=1.0),
            ),
        )

        script_file = self.workdir / "smoke_burn.script"
        telemetry_file = self.workdir / "telemetry_burn.txt"

        self.compiler.compile_to_file(
            exp,
            output_script_path=str(script_file),
            telemetry_filepath=str(telemetry_file)
        )

        result = self._run_gmat(script_file)
        self.assertEqual(result.returncode, 0, f"GMAT execution failed:\n{result.stdout}\n{result.stderr}")
        self.assertTrue(telemetry_file.exists())


if __name__ == "__main__":
    unittest.main()
