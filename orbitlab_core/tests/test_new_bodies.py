"""Permanent tests for the new central bodies (Mercury, Venus, Jupiter, Sun).

Covers all 7 bodies (Earth, Moon, Mars, Mercury, Venus, Jupiter, Sun):
  a) Validator periapsis-altitude minimum boundary (just below invalid, just
     above valid).
  b) Validator point-mass gravity warning for the point-mass-only bodies
     (Sun, Mercury, Jupiter) and its absence for the harmonic bodies.
  c) Compiler emission: point-mass-only bodies emit "PrimaryBodies = {};",
     the central body exactly once in PointMasses, no GravityField line and no
     potential file; harmonic bodies emit a GravityField block and a potential
     file (Venus must use the name from bodies.json, never hardcoded);
     ReportFile.Add is emitted on one single line.
  d) SOI containment: Jupiter apoapsis inside its limit is valid, outside is
     invalid with the SOI reason text; the Sun is never limited.

All physical values are read from orbitlab_core/bodies.json via constants
(MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY, CENTRAL_BODY_PROPERTIES,
BODY_SOI_RADIUS_KM, BODY_POTENTIAL_FILES) so the tests never hardcode numbers.
"""

import unittest

from orbitlab_core.ast.models import (
    ForceModelConfig,
    InitialOrbitConfig,
    KeplerianElements,
    OrbitLabExperiment,
    PropagationConfig,
    SpacecraftConfig,
    StopCondition,
)
from orbitlab_core.ast.validation import AstrodynamicValidator
from orbitlab_core.compiler.generator import GmatScriptCompiler
from orbitlab_core.constants import (
    BODY_POTENTIAL_FILES,
    BODY_SOI_RADIUS_KM,
    CENTRAL_BODY_PROPERTIES,
    MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY,
    POINT_MASS_ONLY_BODIES,
)

ALL_BODIES = ["Earth", "Moon", "Mars", "Mercury", "Venus", "Jupiter", "Sun"]
HARMONIC_BODIES = ["Earth", "Moon", "Mars", "Venus"]
POINT_MASS_BODIES = ["Sun", "Mercury", "Jupiter"]


def build_experiment(
    central_body: str,
    sma_km: float,
    gravity_degree: int = 0,
    gravity_order: int = 0,
    point_masses=None,
) -> OrbitLabExperiment:
    """Build a minimal valid circular-orbit experiment around a given body."""
    return OrbitLabExperiment(
        centralBody=central_body,
        experimentName="new_bodies_test",
        spacecraft=SpacecraftConfig(name="S", dryMassKg=500.0),
        initialOrbit=InitialOrbitConfig(
            type="Keplerian",
            elements=KeplerianElements(
                semiMajorAxisKm=sma_km,
                eccentricity=0.0,
                inclinationDeg=0.0,
            ),
        ),
        forceModel=ForceModelConfig(
            gravityDegree=gravity_degree,
            gravityOrder=gravity_order,
            pointMasses=point_masses if point_masses is not None else [],
        ),
        propagation=PropagationConfig(
            stopCondition=StopCondition(type="ElapsedDays", value=1.0),
        ),
    )


class TestNewBodiesPeriapsisAltitude(unittest.TestCase):
    """(a) Backwards/forwards tolerance of the periapsis-altitude minimum."""

    def test_min_altitude_boundary_every_body(self):
        for body in ALL_BODIES:
            radius = CENTRAL_BODY_PROPERTIES[body][0]
            min_alt = MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY[body]
            with self.subTest(body=body):
                # Just below the minimum -> invalid with the safe-altitude reason.
                below = build_experiment(body, radius + min_alt - 0.5)
                res_below = AstrodynamicValidator.validate(below)
                self.assertFalse(res_below.is_valid, f"{body} at min-0.5 should be invalid")
                self.assertTrue(
                    any("safe periapsis" in e.lower() for e in res_below.errors),
                    f"{body} invalid must cite the safe-periapsis reason",
                )
                # Just above the minimum -> valid.
                above = build_experiment(body, radius + min_alt + 0.5)
                res_above = AstrodynamicValidator.validate(above)
                self.assertTrue(res_above.is_valid, f"{body} at min+0.5 should be valid")
                self.assertEqual(res_above.errors, [])


class TestNewBodiesPointMassWarning(unittest.TestCase):
    """(b) Point-mass-only gravity warning presence / absence."""

    def test_point_mass_warning_present(self):
        for body in POINT_MASS_BODIES:
            radius = CENTRAL_BODY_PROPERTIES[body][0]
            min_alt = MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY[body]
            exp = build_experiment(body, radius + min_alt + 1000.0, gravity_degree=4, gravity_order=4)
            res = AstrodynamicValidator.validate(exp)
            with self.subTest(body=body):
                self.assertTrue(res.is_valid)
                joined = " ".join(res.warnings).lower()
                self.assertIn("point mass", joined, f"{body} should warn about a point mass")
                self.assertIn("ignored", joined, f"{body} warning should say the field is ignored")

    def test_no_point_mass_warning_harmonic_bodies(self):
        for body in HARMONIC_BODIES:
            radius = CENTRAL_BODY_PROPERTIES[body][0]
            min_alt = MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY[body]
            exp = build_experiment(body, radius + min_alt + 1000.0, gravity_degree=4, gravity_order=4)
            res = AstrodynamicValidator.validate(exp)
            with self.subTest(body=body):
                self.assertTrue(res.is_valid)
                self.assertFalse(
                    any("point mass" in w.lower() for w in res.warnings),
                    f"{body} should have no point-mass warning",
                )

    def test_no_point_mass_warning_sun_degree_zero(self):
        radius = CENTRAL_BODY_PROPERTIES["Sun"][0]
        min_alt = MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY["Sun"]
        exp = build_experiment("Sun", radius + min_alt + 1000.0, gravity_degree=0, gravity_order=0)
        res = AstrodynamicValidator.validate(exp)
        self.assertTrue(res.is_valid)
        self.assertFalse(
            any("point mass" in w.lower() for w in res.warnings),
            "Sun with gravity degree 0 should have no point-mass warning",
        )


class TestNewBodiesCompilerEmission(unittest.TestCase):
    """(c) Compiler emission for point-mass-only vs. harmonic bodies."""

    def setUp(self):
        self.compiler = GmatScriptCompiler()

    def _compile(self, body):
        radius = CENTRAL_BODY_PROPERTIES[body][0]
        min_alt = MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY[body]
        exp = build_experiment(body, radius + min_alt + 1000.0, gravity_degree=4, gravity_order=4)
        return self.compiler.compile_to_string(exp)

    def test_point_mass_bodies_emit_point_mass_block(self):
        for body in POINT_MASS_BODIES:
            script = self._compile(body)
            gmat = CENTRAL_BODY_PROPERTIES[body][2]
            with self.subTest(body=body):
                self.assertIn("PrimaryBodies = {};", script)
                # Central body appears exactly once in PointMasses.
                pm_line = next(
                    line for line in script.splitlines()
                    if line.startswith("OrbitLabForceModel.PointMasses")
                )
                self.assertEqual(pm_line.count(gmat), 1, f"{gmat} must appear exactly once in PointMasses")
                # No gravity-field block and no potential file for point-mass-only bodies.
                self.assertNotIn("GravityField", script)
                self.assertNotIn("PotentialFile", script)

    def test_harmonic_bodies_emit_gravity_field(self):
        for body in HARMONIC_BODIES:
            script = self._compile(body)
            gmat = CENTRAL_BODY_PROPERTIES[body][2]
            with self.subTest(body=body):
                self.assertIn(f"PrimaryBodies = {{{gmat}}};", script)
                self.assertIn("GravityField", script)

    def test_harmonic_bodies_emit_potential_file_from_bodies_json(self):
        # Every harmonic body that declares a potentialFile in bodies.json must
        # emit exactly that PotentialFile line. (Earth declares null, so it is
        # correctly absent.)
        for body in HARMONIC_BODIES:
            script = self._compile(body)
            gmat = CENTRAL_BODY_PROPERTIES[body][2]
            expected = BODY_POTENTIAL_FILES[body]
            with self.subTest(body=body):
                if expected is None:
                    self.assertNotIn("PotentialFile", script, f"{body} declares no potentialFile")
                else:
                    self.assertIn(
                        f"GravityField.{gmat}.PotentialFile = {expected};",
                        script,
                        f"{body} must emit the potential file from bodies.json",
                    )

    def test_venus_potential_file_from_bodies_json(self):
        script = self._compile("Venus")
        expected = BODY_POTENTIAL_FILES["Venus"]
        self.assertIsNotNone(expected, "Venus must declare a potential file in bodies.json")
        with self.subTest(expected=expected):
            self.assertIn(f"GravityField.Venus.PotentialFile = {expected};", script)

    def test_report_file_add_on_single_line(self):
        script = self._compile("Earth")
        add_lines = [ln for ln in script.splitlines() if ln.startswith("OrbitLabReport.Add")]
        self.assertEqual(len(add_lines), 1, "ReportFile.Add must appear exactly once")
        self.assertTrue(add_lines[0].endswith("};"), "ReportFile.Add must close on the same line")
        # The Add statement spans exactly one physical line in the script.
        self.assertNotIn("\n", add_lines[0])


class TestNewBodiesSoiContainment(unittest.TestCase):
    """(d) Sphere-of-influence containment for Jupiter; Sun never limited."""

    def test_jupiter_inside_soi_valid(self):
        soi = BODY_SOI_RADIUS_KM["Jupiter"]
        self.assertIsNotNone(soi)
        exp = build_experiment("Jupiter", soi * 0.5, gravity_degree=0, gravity_order=0)
        res = AstrodynamicValidator.validate(exp)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.errors, [])

    def test_jupiter_outside_soi_invalid_with_reason(self):
        soi = BODY_SOI_RADIUS_KM["Jupiter"]
        self.assertIsNotNone(soi)
        exp = build_experiment("Jupiter", soi + 1000.0, gravity_degree=0, gravity_order=0)
        res = AstrodynamicValidator.validate(exp)
        self.assertFalse(res.is_valid)
        self.assertTrue(
            any("sphere of influence" in e.lower() for e in res.errors),
            "outside-SOI Jupiter orbit must cite the sphere-of-influence reason",
        )

    def test_sun_never_soi_limited(self):
        # Sun has no SOI limit (null), so even a very large heliocentric orbit
        # must stay valid (no SOI containment error) as long as periapsis is
        # above the Sun's minimum altitude.
        self.assertIsNone(BODY_SOI_RADIUS_KM["Sun"])
        radius = CENTRAL_BODY_PROPERTIES["Sun"][0]
        large_sma = 2.0 * (149597870.691)  # 2 AU, far beyond any planet's SOI
        exp = build_experiment("Sun", large_sma, gravity_degree=0, gravity_order=0)
        res = AstrodynamicValidator.validate(exp)
        self.assertTrue(res.is_valid, f"Sun orbit errored: {res.errors}")
        self.assertFalse(
            any("sphere of influence" in e.lower() for e in res.errors),
            "the Sun must never impose an SOI containment error",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
