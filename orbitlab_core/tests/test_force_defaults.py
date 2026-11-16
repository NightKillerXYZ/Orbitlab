"""Permanent tests for per-body point-mass defaults and central-body stripping.

Covers orbitlab_core.ast.validation.normalize_point_masses and the compiler
emission that consumes it:
  a) Moon unspecified -> [Earth, Sun]; Earth unspecified -> [Luna, Sun];
     Mars unspecified -> [Sun]; other bodies keep their list.
  b) Explicit lists are kept, except the central body (GMAT name) is removed
     with a note; duplicates collapse.
  c) The compiler never emits the central body as its own perturber and logs
     a note when it strips one.
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
from orbitlab_core.ast.validation import normalize_point_masses
from orbitlab_core.compiler.generator import GmatScriptCompiler
from orbitlab_core.constants import CENTRAL_BODY_PROPERTIES


def build_experiment(central_body, point_masses, sma_km=7000.0):
    return OrbitLabExperiment(
        centralBody=central_body,
        experimentName="force_defaults_test",
        spacecraft=SpacecraftConfig(name="S", dryMassKg=500.0),
        initialOrbit=InitialOrbitConfig(
            type="Keplerian",
            elements=KeplerianElements(
                semiMajorAxisKm=sma_km, eccentricity=0.0, inclinationDeg=0.0
            ),
        ),
        forceModel=ForceModelConfig(
            gravityDegree=4, gravityOrder=4, pointMasses=point_masses
        ),
        propagation=PropagationConfig(
            stopCondition=StopCondition(type="ElapsedDays", value=1.0)
        ),
    )


def point_mass_line(script):
    return next(
        line for line in script.splitlines()
        if line.startswith("OrbitLabForceModel.PointMasses")
    )


class TestNormalizePointMasses(unittest.TestCase):
    def test_moon_unspecified_gets_earth_sun(self):
        cleaned, notes = normalize_point_masses("Moon", ["Luna", "Sun"], False)
        self.assertEqual(cleaned, ["Earth", "Sun"])
        self.assertTrue(any("Moon" in n for n in notes))

    def test_earth_unspecified_keeps_luna_sun(self):
        cleaned, notes = normalize_point_masses("Earth", ["Luna", "Sun"], False)
        self.assertEqual(cleaned, ["Luna", "Sun"])
        self.assertEqual(notes, [])

    def test_mars_unspecified_gets_sun_only(self):
        cleaned, notes = normalize_point_masses("Mars", ["Luna", "Sun"], False)
        self.assertEqual(cleaned, ["Sun"])
        self.assertTrue(any("Mars" in n for n in notes))

    def test_other_body_unspecified_keeps_list(self):
        cleaned, notes = normalize_point_masses("Venus", ["Luna", "Sun"], False)
        self.assertEqual(cleaned, ["Luna", "Sun"])
        self.assertEqual(notes, [])

    def test_explicit_list_kept_minus_central_body(self):
        cleaned, notes = normalize_point_masses(
            "Moon", ["Earth", "Luna", "Sun"], True
        )
        self.assertEqual(cleaned, ["Earth", "Sun"])
        self.assertTrue(any("Luna" in n for n in notes))

    def test_explicit_list_without_central_body_untouched(self):
        cleaned, notes = normalize_point_masses("Mars", ["Earth", "Sun"], True)
        self.assertEqual(cleaned, ["Earth", "Sun"])
        self.assertEqual(notes, [])

    def test_duplicates_collapse(self):
        cleaned, _ = normalize_point_masses("Moon", ["Sun", "Sun", "Earth"], True)
        self.assertEqual(cleaned, ["Sun", "Earth"])

    def test_none_list_unspecified_still_defaults(self):
        cleaned, notes = normalize_point_masses("Moon", None, False)
        self.assertEqual(cleaned, ["Earth", "Sun"])
        self.assertTrue(notes)


class TestCompilerPointMassEmission(unittest.TestCase):
    def setUp(self):
        self.compiler = GmatScriptCompiler()

    def test_moon_strips_luna_and_logs(self):
        exp = build_experiment("Moon", ["Luna", "Sun"], sma_km=2237.4)
        with self.assertLogs("orbitlab.compiler", level="INFO") as logs:
            script = self.compiler.compile_to_string(exp)
        self.assertEqual(point_mass_line(script), "OrbitLabForceModel.PointMasses = {Sun};")
        self.assertTrue(any("Luna" in m for m in logs.output))

    def test_moon_earth_sun_emitted(self):
        exp = build_experiment("Moon", ["Earth", "Sun"], sma_km=2237.4)
        script = self.compiler.compile_to_string(exp)
        self.assertEqual(
            point_mass_line(script), "OrbitLabForceModel.PointMasses = {Earth, Sun};"
        )

    def test_earth_keeps_luna_sun(self):
        exp = build_experiment("Earth", ["Luna", "Sun"], sma_km=6878.136)
        script = self.compiler.compile_to_string(exp)
        self.assertEqual(
            point_mass_line(script), "OrbitLabForceModel.PointMasses = {Luna, Sun};"
        )

    def test_mars_sun_only_emitted(self):
        exp = build_experiment("Mars", ["Sun"], sma_km=3890.0)
        script = self.compiler.compile_to_string(exp)
        self.assertEqual(point_mass_line(script), "OrbitLabForceModel.PointMasses = {Sun};")

    def test_central_body_never_its_own_perturber(self):
        for body in ("Earth", "Moon", "Mars", "Venus"):
            gmat = CENTRAL_BODY_PROPERTIES[body][2]
            exp = build_experiment(body, [gmat, "Sun"], sma_km=7000.0)
            script = self.compiler.compile_to_string(exp)
            line = point_mass_line(script)
            self.assertNotIn(gmat, line.replace("PointMasses", ""),
                             f"{body} must not perturb itself")


if __name__ == "__main__":
    unittest.main(verbosity=2)
