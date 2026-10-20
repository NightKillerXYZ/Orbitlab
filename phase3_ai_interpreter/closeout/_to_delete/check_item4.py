"""STEP 1 check for item 4: point-mass-only compiler emission."""
from orbitlab_core.ast.models import (
    OrbitLabExperiment, InitialOrbitConfig, KeplerianElements,
    SpacecraftConfig, PropagationConfig, ForceModelConfig, StopCondition,
)
from orbitlab_core.compiler.generator import GmatScriptCompiler

comp = GmatScriptCompiler()

def build(centralBody, sma, drag=False):
    return OrbitLabExperiment(
        centralBody=centralBody,
        experimentName="chk",
        spacecraft=SpacecraftConfig(name="S", dryMassKg=500.0, coefficientOfDrag=2.2, dragAreaM2=1.0),
        initialOrbit=InitialOrbitConfig(
            type="Keplerian",
            elements=KeplerianElements(
                semiMajorAxisKm=sma,
                eccentricity=0.0,
                inclinationDeg=28.5,
            ),
        ),
        forceModel=ForceModelConfig(
            gravityDegree=4, gravityOrder=4,
            pointMasses=["Luna", "Sun"],
        ),
        propagation=PropagationConfig(
            stopCondition=StopCondition(type="ElapsedHours", value=1.0)
        ),
    )

def report(body, sma):
    script = comp.compile_to_string(build(body, sma))
    print(f"\n===== {body} =====")
    for line in script.splitlines():
        if any(k in line for k in (
            "CentralBody", "PrimaryBodies", "PointMasses",
            "GravityField", "PotentialFile", "Filename",
        )):
            print(line)

report("Sun", 150000000.0)
report("Mercury", 2500.0)
report("Jupiter", 73000.0)
report("Earth", 7000.0)
report("Mars", 4000.0)
report("Moon", 1800.0)
