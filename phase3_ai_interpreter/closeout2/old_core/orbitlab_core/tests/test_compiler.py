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
        self.assertIn("Sat1.Earth.ECC, Sat1.INC, Sat1.Earth.Altitude", script)
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
        self.assertIn("Create ImpulsiveBurn Burn_HohmannMEO_TargetInsertion;", script)
        self.assertIn("Maneuver 'Hohmann Insertion Burn' Burn_HohmannMEO_Insertion(TransferSat);", script)
        self.assertIn("Maneuver 'Hohmann Target Insertion Burn' Burn_HohmannMEO_TargetInsertion(TransferSat);", script)

    def test_non_earth_script_uses_body_frame_mu_and_body_parameters(self):
        exp = OrbitLabExperiment(
            experimentName="Moon_Transfer",
            centralBody="Moon",
            spacecraft=SpacecraftConfig(name="MoonSat", dryMassKg=300.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                coordinateSystem="LunaMJ2000Eq",
                elements=KeplerianElements(
                    semiMajorAxisKm=2000.0,
                    eccentricity=0.0,
                    inclinationDeg=0.0,
                ),
            ),
            maneuvers=[ManeuverConfig(
                id="Raise",
                type="TargetedHohmannTransfer",
                trigger=ManeuverTrigger(condition="AtPeriapsis"),
                targetObjectives=TargetObjectives(
                    targetOrbitRadiusKm=3000.0,
                    targetEccentricity=0.2,
                ),
            )],
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="OrbitPeriods", value=2.0)
            ),
        )

        script = self.compiler.compile_to_string(exp)
        self.assertIn("Create CoordinateSystem LunaMJ2000Eq;", script)
        self.assertIn("LunaMJ2000Eq.Origin = Luna;", script)
        self.assertIn("OrbitLabForceModel.CentralBody = Luna;", script)
        self.assertIn("OrbitLabForceModel.GravityField.Luna.Degree = 4;", script)
        self.assertIn("MoonSat.LunaMJ2000Eq.X", script)
        self.assertIn("MoonSat.Luna.SMA", script)
        self.assertIn("MoonSat.Luna.Periapsis", script)
        self.assertIn("MoonSat.Luna.Apoapsis", script)
        self.assertIn("Propagate 'Mission Propagation' OrbitLabPropagator(MoonSat) {MoonSat.ElapsedSecs = 16052.13};", script)
        self.assertIn("Burn_Raise_Insertion.Element1 = 0.149438;", script)
        self.assertIn("Burn_Raise_TargetInsertion.Element1 = 0.000000;", script)
        self.assertNotIn("EarthMJ2000Eq", script)
        self.assertNotIn("GravityField.Earth", script)

    def test_nonzero_eccentric_hohmann_target_is_compiled(self):
        exp = OrbitLabExperiment(
            experimentName="Apoapsis_Elliptic_Target",
            spacecraft=SpacecraftConfig(name="TargetSat", dryMassKg=300.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=8200.0,
                    eccentricity=0.01,
                    inclinationDeg=56.0,
                ),
            ),
            maneuvers=[ManeuverConfig(
                id="EllipticTarget",
                type="TargetedHohmannTransfer",
                trigger=ManeuverTrigger(condition="AtApoapsis"),
                targetObjectives=TargetObjectives(
                    targetOrbitRadiusKm=18000.0,
                    targetEccentricity=0.12,
                ),
            )],
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="ElapsedSeconds", value=100.0)
            ),
        )

        script = self.compiler.compile_to_string(exp)
        self.assertIn("Burn_EllipticTarget_TargetInsertion.Element1 =", script)
        self.assertIn("Propagate 'Prop to Hohmann Apoapsis'", script)
        self.assertIn("Burn_EllipticTarget_Insertion.Element1 = 1.216690;", script)
        self.assertIn("Burn_EllipticTarget_TargetInsertion.Element1 = 0.678602;", script)

    def test_nonzero_eccentric_inward_hohmann_target_is_compiled(self):
        experiment = OrbitLabExperiment(
            experimentName="Circular_to_Elliptic_Inward",
            spacecraft=SpacecraftConfig(name="InwardSat", dryMassKg=300.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=10000.0,
                    eccentricity=0.0,
                    inclinationDeg=0.0,
                ),
            ),
            maneuvers=[ManeuverConfig(
                id="LowerAtApoapsis",
                type="TargetedHohmannTransfer",
                trigger=ManeuverTrigger(condition="AtApoapsis"),
                targetObjectives=TargetObjectives(
                    targetOrbitRadiusKm=7000.0,
                    targetEccentricity=0.1,
                ),
            )],
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="ElapsedSeconds", value=100.0)
            ),
        )

        script = self.compiler.compile_to_string(experiment)
        self.assertIn("Burn_LowerAtApoapsis_Insertion.Element1 = -0.584090;", script)
        self.assertIn("Burn_LowerAtApoapsis_TargetInsertion.Element1 = -0.270477;", script)
        self.assertIn("Propagate 'Prop to Hohmann Periapsis'", script)

    def test_hohmann_target_equal_to_burn_radius_is_rejected(self):
        experiment = OrbitLabExperiment(
            experimentName="ZeroTransfer",
            spacecraft=SpacecraftConfig(name="ZeroSat", dryMassKg=100.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=8000.0,
                    eccentricity=0.1,
                    inclinationDeg=10.0,
                ),
            ),
            maneuvers=[ManeuverConfig(
                id="NoOpTransfer",
                type="TargetedHohmannTransfer",
                trigger=ManeuverTrigger(condition="AtPeriapsis"),
                targetObjectives=TargetObjectives(targetOrbitRadiusKm=7200.0),
            )],
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="ElapsedSeconds", value=10.0)
            ),
        )

        with self.assertRaisesRegex(ValueError, "target radius must differ from the burn radius"):
            self.compiler.compile_to_string(experiment)

    def test_mars_gravity_model_uses_available_potential(self):
        exp = OrbitLabExperiment(
            experimentName="MarsOrbit",
            centralBody="Mars",
            spacecraft=SpacecraftConfig(name="MarsSat", dryMassKg=300.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                coordinateSystem="MarsMJ2000Eq",
                elements=KeplerianElements(
                    semiMajorAxisKm=4000.0,
                    eccentricity=0.0,
                    inclinationDeg=0.0,
                ),
            ),
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="ElapsedSeconds", value=120.0)
            ),
        )

        script = self.compiler.compile_to_string(exp)
        self.assertIn("MarsMJ2000Eq.Origin = Mars;", script)
        self.assertIn("OrbitLabForceModel.GravityField.Mars.PotentialFile = Mars50c.cof;", script)
        self.assertIn("OrbitLabForceModel.GravityField.Mars.Degree = 4;", script)

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

    def test_cartesian_orbit_periods_use_specific_central_body_mu(self):
        import math

        experiment = OrbitLabExperiment(
            experimentName="MoonCartesianPeriods",
            centralBody="Moon",
            spacecraft=SpacecraftConfig(name="MoonCart", dryMassKg=250.0),
            initialOrbit=InitialOrbitConfig(
                type="Cartesian",
                coordinateSystem="LunaMJ2000Eq",
                elements=CartesianElements(
                    xKm=2000.0, yKm=0.0, zKm=0.0,
                    vxKmS=0.0, vyKmS=math.sqrt(4902.800066 / 2000.0), vzKmS=0.0,
                ),
            ),
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="OrbitPeriods", value=1.0)
            ),
        )

        script = self.compiler.compile_to_string(experiment)
        self.assertIn("{MoonCart.ElapsedSecs = 8026.07};", script)

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
