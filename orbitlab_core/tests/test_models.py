"""Unit tests for OrbitLab AST and Pydantic models."""

import json
from pathlib import Path
import unittest
import jsonschema

from orbitlab_core.ast.models import (
    AtmosphericDragConfig,
    BurnVector,
    CartesianElements,
    EpochConfig,
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


class TestExperimentModels(unittest.TestCase):
    """Test AST model validation and schema conformance."""

    def setUp(self):
        # Load JSON schema to test conformance
        schema_path = Path(__file__).resolve().parent.parent.parent / "schemas" / "experiment.schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            self.json_schema = json.load(f)

    def test_valid_keplerian_experiment(self):
        exp = OrbitLabExperiment(
            experimentName="ISS_LEO_Baseline",
            description="International Space Station baseline orbit test",
            spacecraft=SpacecraftConfig(
                name="ISS_Sat",
                dryMassKg=420000.0,
                coefficientOfDrag=2.2,
                dragAreaM2=100.0,
                coefficientOfReflectivity=1.8,
                srpAreaM2=100.0,
            ),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=6778.0,
                    eccentricity=0.0005,
                    inclinationDeg=51.64,
                    raanDeg=120.0,
                    argumentOfPeriapsisDeg=45.0,
                    trueAnomalyDeg=0.0,
                ),
            ),
            forceModel=ForceModelConfig(
                gravityDegree=4,
                gravityOrder=4,
                pointMasses=["Luna", "Sun"],
                atmosphericDrag=AtmosphericDragConfig(enabled=True, model="JacchiaRoberts"),
                solarRadiationPressure=True,
            ),
            propagation=PropagationConfig(
                integrator="RungeKutta89",
                stopCondition=StopCondition(type="ElapsedHours", value=2.0),
                stepSizeSecs=60.0,
            ),
        )

        data = exp.model_dump(mode="json")
        # Validate against official JSON schema
        jsonschema.validate(instance=data, schema=self.json_schema)
        self.assertEqual(exp.spacecraft.name, "ISS_Sat")
        self.assertEqual(exp.initialOrbit.elements.semiMajorAxisKm, 6778.0)

    def test_valid_cartesian_experiment(self):
        exp = OrbitLabExperiment(
            experimentName="Cartesian_LEO_Test",
            spacecraft=SpacecraftConfig(
                name="CartSat",
                dryMassKg=500.0,
            ),
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
                stopCondition=StopCondition(type="ElapsedDays", value=1.0),
            ),
        )

        data = exp.model_dump(mode="json", exclude_none=True)
        jsonschema.validate(instance=data, schema=self.json_schema)
        self.assertEqual(exp.initialOrbit.type, "Cartesian")
        self.assertEqual(exp.initialOrbit.elements.xKm, 7000.0)

    def test_invalid_spacecraft_name(self):
        with self.assertRaises(ValueError):
            SpacecraftConfig(
                name="Invalid Name With Spaces!",
                dryMassKg=500.0,
            )

    def test_invalid_semi_major_axis_bounds(self):
        with self.assertRaises(ValueError):
            KeplerianElements(
                semiMajorAxisKm=5000.0,  # Below Earth surface + 100km (6478.137)
                eccentricity=0.01,
                inclinationDeg=28.5,
            )

    def test_invalid_eccentricity_bounds(self):
        with self.assertRaises(ValueError):
            KeplerianElements(
                semiMajorAxisKm=7000.0,
                eccentricity=1.05,  # Hyperbolic, max is 0.99
                inclinationDeg=28.5,
            )

    def test_impulsive_burn_validation(self):
        # Valid burn
        maneuver = ManeuverConfig(
            id="ApoapsisKick",
            type="ImpulsiveBurn",
            trigger=ManeuverTrigger(condition="AtApoapsis"),
            burnVector=BurnVector(
                coordinateSystem="LocalVNB",
                deltaVVectorKmS=[0.150, 0.0, 0.0],
            ),
        )
        self.assertEqual(maneuver.id, "ApoapsisKick")

        # Missing burnVector for ImpulsiveBurn
        with self.assertRaises(ValueError):
            ManeuverConfig(
                id="BadBurn",
                type="ImpulsiveBurn",
                trigger=ManeuverTrigger(condition="AtApoapsis"),
            )

    def test_elapsed_secs_required_for_elapsed_trigger(self):
        with self.assertRaises(ValueError):
            ManeuverTrigger(condition="ElapsedTimeSecs")


if __name__ == "__main__":
    unittest.main()
