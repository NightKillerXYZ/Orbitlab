"""Unit tests for astrodynamic validation and physical boundary enforcement."""

import unittest
from orbitlab_core.ast.models import (
    BurnVector,
    CartesianElements,
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
from orbitlab_core.ast.validation import (
    AstrodynamicValidator,
    compute_orbital_properties_from_cartesian,
    compute_orbital_properties_from_keplerian,
)
from orbitlab_core.constants import EARTH_MU_KM3_S2, EARTH_RADIUS_KM


class TestAstrodynamicValidation(unittest.TestCase):
    """Test orbital mechanics physical boundary checks."""

    def test_safe_keplerian_orbit(self):
        # 400km circular LEO orbit: SMA = 6778.1363 km, e = 0.001
        elements = KeplerianElements(
            semiMajorAxisKm=6778.1363,
            eccentricity=0.001,
            inclinationDeg=51.6,
        )
        props = compute_orbital_properties_from_keplerian(elements, EARTH_RADIUS_KM, EARTH_MU_KM3_S2)
        self.assertTrue(props.is_bound)
        self.assertGreater(props.periapsis_altitude_km, 390.0)
        self.assertAlmostEqual(props.orbital_period_secs, 5553.0, delta=20.0)

    def test_unsafe_low_periapsis_rejected(self):
        # Highly elliptical orbit with periapsis inside dense atmosphere:
        # SMA = 7000 km, e = 0.10 => rp = 7000 * 0.9 = 6300 km < Earth Radius (6378 km) -> crash!
        exp = OrbitLabExperiment(
            experimentName="Crashing_Orbit",
            spacecraft=SpacecraftConfig(name="DoomedSat", dryMassKg=500.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=7000.0,
                    eccentricity=0.10,  # periapsis = 6300 km (sub-surface!)
                    inclinationDeg=28.5,
                ),
            ),
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="ElapsedHours", value=1.0)
            ),
        )

        res = AstrodynamicValidator.validate(exp)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("periapsis threshold" in err for err in res.errors))

    def test_safe_cartesian_orbit(self):
        # Circular orbit at r = 7000 km (altitude ~622 km), circular speed v = sqrt(mu/r) ~ 7.546 km/s
        exp = OrbitLabExperiment(
            experimentName="Circular_Cartesian_LEO",
            spacecraft=SpacecraftConfig(name="CartSat", dryMassKg=500.0),
            initialOrbit=InitialOrbitConfig(
                type="Cartesian",
                elements=CartesianElements(
                    xKm=7000.0,
                    yKm=0.0,
                    zKm=0.0,
                    vxKmS=0.0,
                    vyKmS=7.54605,
                    vzKmS=0.0,
                ),
            ),
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="ElapsedHours", value=1.0)
            ),
        )

        res = AstrodynamicValidator.validate(exp)
        self.assertTrue(res.is_valid)
        self.assertAlmostEqual(res.properties["periapsisAltitudeKm"], 621.86, delta=2.0)
        self.assertTrue(res.properties["isBound"])

    def test_cartesian_atmospheric_impact_rejected(self):
        # Position at 6400 km, moving downward into surface
        exp = OrbitLabExperiment(
            experimentName="Impact_Cartesian",
            spacecraft=SpacecraftConfig(name="FallingSat", dryMassKg=500.0),
            initialOrbit=InitialOrbitConfig(
                type="Cartesian",
                elements=CartesianElements(
                    xKm=6420.0,  # Only ~42 km altitude (well below 100km)
                    yKm=0.0,
                    zKm=0.0,
                    vxKmS=-2.0,
                    vyKmS=7.0,
                    vzKmS=0.0,
                ),
            ),
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="ElapsedHours", value=1.0)
            ),
        )

        res = AstrodynamicValidator.validate(exp)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("periapsis threshold" in err for err in res.errors))

    def test_large_delta_v_warning(self):
        exp = OrbitLabExperiment(
            experimentName="SuperBurn_Mission",
            spacecraft=SpacecraftConfig(name="InterstellarSat", dryMassKg=500.0),
            initialOrbit=InitialOrbitConfig(
                type="Keplerian",
                elements=KeplerianElements(
                    semiMajorAxisKm=7000.0,
                    eccentricity=0.001,
                    inclinationDeg=28.5,
                ),
            ),
            maneuvers=[
                ManeuverConfig(
                    id="ExtremeBurn",
                    type="ImpulsiveBurn",
                    trigger=ManeuverTrigger(condition="AtPeriapsis"),
                    burnVector=BurnVector(deltaVVectorKmS=[20.0, 0.0, 0.0]),  # 20 km/s!
                )
            ],
            propagation=PropagationConfig(
                stopCondition=StopCondition(type="ElapsedHours", value=1.0)
            ),
        )

        res = AstrodynamicValidator.validate(exp)
        self.assertTrue(res.is_valid)  # Valid physically, but flags a warning
        self.assertTrue(any("exceptionally large Delta-V" in warn for warn in res.warnings))

    def test_hohmann_target_below_earth_rejected(self):
        # Target radius below 6500 km violates schema and physical safety
        with self.assertRaises(ValueError):
            TargetObjectives(targetOrbitRadiusKm=6400.0)


if __name__ == "__main__":
    unittest.main()
