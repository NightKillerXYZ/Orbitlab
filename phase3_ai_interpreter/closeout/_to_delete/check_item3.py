"""STEP 1 check for item 3 subpart A: point-mass-only gravity warning."""
from orbitlab_core.ast.models import (
    OrbitLabExperiment, InitialOrbitConfig, KeplerianElements,
    SpacecraftConfig, PropagationConfig, ForceModelConfig, StopCondition,
)
from orbitlab_core.ast.validation import AstrodynamicValidator


def build(centralBody, gravityDegree, gravityOrder, sma):
    exp = OrbitLabExperiment(
        centralBody=centralBody,
        experimentName="chk",
        spacecraft=SpacecraftConfig(name="S", dryMassKg=500.0),
        initialOrbit=InitialOrbitConfig(
            type="Keplerian",
            elements=KeplerianElements(
                semiMajorAxisKm=sma,
                eccentricity=0.0,
                inclinationDeg=28.5,
            ),
        ),
        forceModel=ForceModelConfig(
            gravityDegree=gravityDegree,
            gravityOrder=gravityOrder,
        ),
        propagation=PropagationConfig(
            stopCondition=StopCondition(type="ElapsedHours", value=1.0)
        ),
    )
    return exp


# sun-like SMA ~1 AU; planets just inside their SOI
smas = {
    "Earth": 7000.0,
    "Mars": 4000.0,
    "Sun": 150000000.0,
    "Mercury": 2500.0,
    "Jupiter": 73000.0,
}

def pwarn(res):
    return any("point" in w.lower() and "ignored" in w.lower() for w in res.warnings)

for body in ("Earth", "Mars", "Sun", "Mercury", "Jupiter"):
    res = AstrodynamicValidator.validate(build(body, 4, 4, smas[body]))
    print(f"{body:8s} deg=4/ord=4 -> warnings={len(res.warnings)} pwarn={pwarn(res)} is_valid={res.is_valid}")

res = AstrodynamicValidator.validate(build("Sun", 0, 0, smas["Sun"]))
print(f"Sun     deg=0/ord=0 -> warnings={len(res.warnings)} pwarn={pwarn(res)}")

res = AstrodynamicValidator.validate(build("Earth", 4, 4, smas["Earth"]))
print(f"Earth   deg=4/ord=4 -> warnings={len(res.warnings)} pwarn={pwarn(res)}")
