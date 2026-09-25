"""Unit tests for the GmatScriptCompiler."""

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
    TargetObjectives,
)
from orbitlab_core.compiler.generator import GmatScriptCompiler


class TestGmatScriptCompiler(unittest.TestCase):
    """Test deterministic GMAT script generation."""

    def setUp(self):
        self.compiler = GmatScriptCompiler()

    def test_keplerian_script_structure(self):
        exp = OrbitLabExperiment(
            experimentName="LEO_Propagate_Test",
            description="Simple LEO propagation test",
            spacecraft=SpacecraftConfig(name="Sat1", dryMassKg=350.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=7000.0,
                    eccentricity=0.005,
                    inclinationDeg=45.0,
                    raanDeg=30.0,
                    argumentOfPeriapsisDeg=60.0,
                    trueAnomalyDeg=15.0,
                ),
            ),
            forceModel=ForceModelConfig(
                gravityDegree=8,
                gravityOrder=8,
                pointMasses=["Sun", "Luna"],
                atmosphericDrag=AtmosphericDragConfig(enabled=True, model="MSISE90"),
                solarRadiationPressure=True,
            ),
            propagation=PropagationConfig(
                integrator="PrinceDormand78",
                stopCondition=StopCondition(type="ElapsedHours", value=12.0),
                stepSizeSecs=30.0,
            ),
        )

        script = self.compiler.compile_to_string(exp, telemetry_filepath="C:\\runs\\sim1\\telemetry.txt")

        # Verify key sections
        self.assertIn("Create Spacecraft Sat1;", script)
        self.assertIn("Sat1.SMA = 7000.000000;", script)
        self.assertIn("Sat1.ECC = 0.005000;", script)
        self.assertIn("Sat1.INC = 45.000000;", script)
        self.assertIn("Sat1.DryMass = 350.00;", script)

        # ForceModel
        self.assertIn("Create ForceModel OrbitLabForceModel;", script)
        self.assertIn("OrbitLabForceModel.GravityField.Earth.Degree = 8;", script)
        self.assertIn("OrbitLabForceModel.GravityField.Earth.Order = 8;", script)
        self.assertIn("OrbitLabForceModel.PointMasses = {Sun, Luna};", script)
        self.assertIn("OrbitLabForceModel.Drag.AtmosphereModel = MSISE90;", script)
        self.assertIn("OrbitLabForceModel.SRP = On;", script)

        # Propagator
        self.assertIn("Create Propagator OrbitLabPropagator;", script)
        self.assertIn("OrbitLabPropagator.Type = PrinceDormand78;", script)
        self.assertIn("OrbitLabPropagator.InitialStepSize = 30.00;", script)

        # Telemetry subscriber and path normalization
        self.assertIn("Create ReportFile OrbitLabReport;", script)
        self.assertIn("OrbitLabReport.Filename = 'C:/runs/sim1/telemetry.txt';", script)
        self.assertNotIn("\\", script.split("OrbitLabReport.Filename")[1].split(";")[0])

        # Mission sequence
        self.assertIn("BeginMissionSequence;", script)
        # 12 hours = 43200 seconds
        self.assertIn("Propagate 'Mission Propagation' OrbitLabPropagator(Sat1) {Sat1.ElapsedSecs = 43200.00};", script)

    def test_cartesian_script_structure(self):
        exp = OrbitLabExperiment(
            experimentName="Cartesian_Mission",
            spacecraft=SpacecraftConfig(name="GeoSat", dryMassKg=1200.0),
            initialOrbit=InitialOrbitConfig(
                type="Cartesian",
                elements=CartesianElements(
                    xKm=42164.0,
                    yKm=0.0,
                    zKm=0.0,
                    vxKmS=0.0,
                    vyKmS=3.0746,
                    vzKmS=0.0,
                ),
            ),
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="ElapsedDays", value=2.0)
            ),
        )

        script = self.compiler.compile_to_string(exp)
        self.assertIn("GeoSat.DisplayStateType = Cartesian;", script)
        self.assertIn("GeoSat.X = 42164.000000;", script)
        self.assertIn("GeoSat.VY = 3.07460000;", script)
        self.assertIn("Propagate 'Mission Propagation' OrbitLabPropagator(GeoSat) {GeoSat.ElapsedDays = 2.0000};", script)

    def test_impulsive_maneuver_script_structure(self):
        exp = OrbitLabExperiment(
            experimentName="Orbit_Raising_Burn",
            spacecraft=SpacecraftConfig(name="SatManeuver", dryMassKg=600.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=6800.0,
                    eccentricity=0.001,
                    inclinationDeg=28.5,
                ),
            ),
            maneuvers=[
                ManeuverConfig(
                    id="ApogeeRaise",
                    type="ImpulsiveBurn",
                    trigger=ManeuverTrigger(condition="AtPeriapsis"),
                    burnVector=BurnVector(deltaVVectorKmS=[0.125, 0.0, 0.0]),
                )
            ],
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="OrbitPeriods", value=3.0)
            ),
        )

        script = self.compiler.compile_to_string(exp)
        self.assertIn("Create ImpulsiveBurn Burn_ApogeeRaise;", script)
        self.assertIn("Burn_ApogeeRaise.Element1 = 0.125000;", script)
        self.assertIn("Burn_ApogeeRaise.Axes = VNB;", script)
        self.assertIn("Propagate 'Prop to Periapsis' OrbitLabPropagator(SatManeuver) {SatManeuver.Earth.Periapsis};", script)
        self.assertIn("Maneuver 'Apply ApogeeRaise' Burn_ApogeeRaise(SatManeuver);", script)

    def test_targeted_hohmann_transfer_script_structure(self):
        exp = OrbitLabExperiment(
            experimentName="LEO_to_MEO_Hohmann",
            spacecraft=SpacecraftConfig(name="TransferSat", dryMassKg=800.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=6700.0,
                    eccentricity=0.001,
                    inclinationDeg=28.5,
                ),
            ),
            maneuvers=[
                ManeuverConfig(
                    id="HohmannMEO",
                    type="TargetedHohmannTransfer",
                    trigger=ManeuverTrigger(condition="AtPeriapsis"),
                    targetObjectives=TargetObjectives(targetOrbitRadiusKm=10000.0),
                )
            ],
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="ElapsedHours", value=6.0)
            ),
        )

        script = self.compiler.compile_to_string(exp)
        self.assertIn("Create ImpulsiveBurn Burn_HohmannMEO_Insertion;", script)
        self.assertIn("Create ImpulsiveBurn Burn_HohmannMEO_Circularize;", script)
        self.assertIn("Maneuver 'Hohmann Insertion Burn' Burn_HohmannMEO_Insertion(TransferSat);", script)
        self.assertIn("Maneuver 'Hohmann Circularize Burn' Burn_HohmannMEO_Circularize(TransferSat);", script)

    def test_orbit_periods_stop_condition(self):
        exp = OrbitLabExperiment(
            experimentName="Period_Test",
            spacecraft=SpacecraftConfig(name="SatPeriod", dryMassKg=400.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=7000.0,
                    eccentricity=0.001,
                    inclinationDeg=51.6,
                ),
            ),
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="OrbitPeriods", value=5.0)
            ),
        )

        script = self.compiler.compile_to_string(exp)
        # Period for 7000 km is ~5828.516s * 5 = 29142.58s
        self.assertIn("Propagate 'Mission Propagation' OrbitLabPropagator(SatPeriod) {SatPeriod.ElapsedSecs = 29142.58};", script)

    def test_compile_to_file(self):
        import tempfile
        from pathlib import Path

        exp = OrbitLabExperiment(
            experimentName="File_Output_Test",
            spacecraft=SpacecraftConfig(name="FileSat", dryMassKg=300.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=6800.0,
                    eccentricity=0.002,
                    inclinationDeg=98.2,  # Sun-synchronous
                ),
            ),
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="ElapsedDays", value=1.0)
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "output.script"
            report_path = Path(tmpdir) / "output_telemetry.txt"
            res_path = self.compiler.compile_to_file(
                exp,
                output_script_path=str(script_path),
                telemetry_filepath=str(report_path)
            )

            self.assertTrue(res_path.exists())
            content = res_path.read_text(encoding="utf-8")
            self.assertIn("Sat.INC = 98.200000;" if "Sat." in content else "FileSat.INC = 98.200000;", content)
            self.assertIn(str(report_path).replace("\\", "/"), content)


if __name__ == "__main__":
    unittest.main()
