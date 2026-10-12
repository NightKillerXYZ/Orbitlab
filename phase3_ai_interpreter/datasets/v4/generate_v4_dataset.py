"""Build the hand-authored 100-record V4 batch files from explicit scenarios."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from orbitlab_core.ast.models import OrbitLabExperiment  # noqa: E402
from orbitlab_core.ast.validation import AstrodynamicValidator  # noqa: E402
from orbitlab_core.constants import CENTRAL_BODY_PROPERTIES  # noqa: E402


OUT = Path(__file__).resolve().parent
V3_TRAIN = OUT.parent / "v3" / "orbitlab_interpreter_train_v3.jsonl"
PREFIXES = {
    "body": "V4Body", "force": "V4Force", "cartesian": "V4Cartesian",
    "hohmann": "V4Hohmann", "multi": "V4Multi", "cross": "V4Cross",
    "propagation": "V4Propagation", "language": "V4Language",
    "robustness": "V4Robustness",
}
TEMPLATES = [
    "Please build {name} for {sat} {body_phrase}: {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
    "Could you model {sat} in {name}? {body_phrase}; initial state {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
    "I need {name}, spacecraft {sat}. Use {body_phrase} and set the orbit to {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
    "Configure {name} with {sat}; {body_phrase}. Start from {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
    "For {name}, put {sat} {body_phrase} using {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
    "Set up {name}: {sat} is {body_phrase}, with initial state {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
    "I'm comparing a new case, {name}. {sat} should use {body_phrase} and {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
    "Translate this request for {name}: {sat}, {body_phrase}, {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
    "Would you prepare {name} with {sat} {body_phrase}? Its state is {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
    "Run a study named {name} for {sat}. Choose {body_phrase}; the specified orbit is {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
    "For a technical comparison, create {name} using {sat}, {body_phrase}, and {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
    "{name}: {sat}; {body_phrase}; {orbit_text}. {maneuver_text}{force_text}{duration_text}{tail}",
]
TAILS = [
    "Leave every unmentioned optional field out; do not supply a date or force defaults.",
    "Keep unspecified settings implicit, and preserve the stated values exactly.",
    "Do not assume an epoch or add optional spacecraft properties.",
    "Return the experiment data only; do not add settings I did not request.",
    "Use only the values stated here; no generated epoch is wanted.",
    "Please keep all unspecified choices omitted.",
    "No extra parameters beyond those given, please.",
    "Do not expand defaults into optional output fields.",
    "Preserve every supplied number and omit absent options.",
    "I have not specified an epoch; leave it out.",
]
STOP_WORDS = {
    "ElapsedSeconds": "seconds", "ElapsedHours": "hours",
    "ElapsedDays": "days", "OrbitPeriods": "orbit periods",
}
CASE_ROWS: list[dict[str, Any]] = []


def case(category: str, body: str, orbit_type: str, elements: dict[str, float],
         stop_type: str, duration: float, mass: float, intent: str, **options: Any) -> None:
    CASE_ROWS.append({"category": category, "body": body, "orbit_type": orbit_type,
                      "elements": elements, "stop_type": stop_type, "duration": duration,
                      "mass": mass, "intent": intent, **options})


def add_cases() -> None:
    # V4Body 16: Moon/Mars Keplerian and Cartesian; body + duration/force/manoeuvre.
    case("body", "Moon", "Keplerian", {"semiMajorAxisKm": 2050, "eccentricity": 0.02, "inclinationDeg": 32, "raanDeg": 44}, "OrbitPeriods", 3, 240, "A lunar mapping arc", style=0)
    case("body", "Moon", "Keplerian", {"semiMajorAxisKm": 2300, "eccentricity": 0.05, "inclinationDeg": 68, "argumentOfPeriapsisDeg": 130, "trueAnomalyDeg": 28}, "ElapsedHours", 5, 310, "A high-inclination lunar survey", style=2)
    case("body", "Moon", "Keplerian", {"semiMajorAxisKm": 2600, "eccentricity": 0.08, "inclinationDeg": 12, "raanDeg": 205, "argumentOfPeriapsisDeg": 75}, "ElapsedSeconds", 840, 175, "Short lunar arc with an explicit degree/order", gravity={"gravityDegree": 6, "gravityOrder": 4}, style=5)
    case("body", "Moon", "Keplerian", {"semiMajorAxisKm": 3100, "eccentricity": 0.12, "inclinationDeg": 101}, "ElapsedDays", 0.4, 420, "A long lunar coast with solar perturbation", force={"solarRadiationPressure": False}, style=7)
    case("body", "Moon", "Keplerian", {"semiMajorAxisKm": 1900, "eccentricity": 0.04, "inclinationDeg": 87, "raanDeg": 18, "trueAnomalyDeg": 220}, "OrbitPeriods", 1.5, 205, "A lunar plane-change comparison", style=9)
    case("body", "Moon", "Keplerian", {"semiMajorAxisKm": 3400, "eccentricity": 0.2, "inclinationDeg": 42, "argumentOfPeriapsisDeg": 270}, "ElapsedHours", 12, 600, "A high-apolune transfer study", style=11)
    case("body", "Moon", "Cartesian", {"xKm": 2100, "yKm": 0, "zKm": 0, "vxKmS": 0, "vyKmS": 1.527, "vzKmS": 0}, "ElapsedSeconds", 600, 265, "A radial-axis lunar state", style=3)
    case("body", "Moon", "Cartesian", {"xKm": 0, "yKm": 0, "zKm": 2350, "vxKmS": 1.444, "vyKmS": 0, "vzKmS": 0}, "OrbitPeriods", 2, 350, "A polar lunar Cartesian propagation", style=8)
    case("body", "Mars", "Keplerian", {"semiMajorAxisKm": 3900, "eccentricity": 0.02, "inclinationDeg": 25, "raanDeg": 90}, "ElapsedHours", 7, 510, "A Mars-orbit relay case", style=1)
    case("body", "Mars", "Keplerian", {"semiMajorAxisKm": 4700, "eccentricity": 0.1, "inclinationDeg": 63, "argumentOfPeriapsisDeg": 160, "trueAnomalyDeg": 31}, "OrbitPeriods", 4, 475, "A Mars elliptic-orbit survey", style=4)
    case("body", "Mars", "Keplerian", {"semiMajorAxisKm": 5600, "eccentricity": 0.14, "inclinationDeg": 112}, "ElapsedDays", 1.2, 700, "A retrograde Mars coast", force={"pointMasses": ["Sun", "Jupiter"]}, style=6)
    case("body", "Mars", "Keplerian", {"semiMajorAxisKm": 3650, "eccentricity": 0.03, "inclinationDeg": 5, "raanDeg": 222, "trueAnomalyDeg": 310}, "ElapsedSeconds", 900, 280, "A short Mars navigation segment", integrator="PrinceDormand78", style=10)
    case("body", "Mars", "Keplerian", {"semiMajorAxisKm": 6400, "eccentricity": 0.22, "inclinationDeg": 82, "argumentOfPeriapsisDeg": 45}, "ElapsedHours", 18, 920, "A high-energy Mars elliptical arc", style=2)
    case("body", "Mars", "Keplerian", {"semiMajorAxisKm": 4200, "eccentricity": 0.07, "inclinationDeg": 146, "raanDeg": 305}, "OrbitPeriods", 2.5, 390, "A retrograde Martian track", style=7)
    case("body", "Mars", "Cartesian", {"xKm": 3800, "yKm": 0, "zKm": 0, "vxKmS": 0, "vyKmS": 3.355, "vzKmS": 0}, "ElapsedHours", 2, 330, "A direct Mars Cartesian state", style=0)
    case("body", "Mars", "Cartesian", {"xKm": 0, "yKm": 0, "zKm": 4400, "vxKmS": 3.121, "vyKmS": 0, "vzKmS": 0}, "ElapsedSeconds", 720, 455, "A polar Mars Cartesian state", style=5)

    # V4Force 12: explicit partial force requests and omitted default force models.
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 7800, "eccentricity": 0.03, "inclinationDeg": 51.6}, "ElapsedHours", 5, 390, "Only the gravity harmonic degree 8 and order 6 are specified", force={"gravityDegree": 8, "gravityOrder": 6}, style=0)
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 8400, "eccentricity": 0.04, "inclinationDeg": 28.5, "raanDeg": 33}, "OrbitPeriods", 3, 420, "Use Luna and Jupiter as point-mass perturbers only", force={"pointMasses": ["Luna", "Jupiter"]}, style=2)
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 7100, "eccentricity": 0.01, "inclinationDeg": 97.8}, "ElapsedSeconds", 2400, 250, "Enable atmospheric drag and explicitly choose MSISE90", force={"atmosphericDrag": {"enabled": True, "model": "MSISE90"}}, style=4)
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 9200, "eccentricity": 0.06, "inclinationDeg": 44}, "ElapsedDays", 0.8, 610, "Switch solar radiation pressure off", force={"solarRadiationPressure": False}, style=6)
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 7600, "eccentricity": 0.02, "inclinationDeg": 72}, "ElapsedHours", 4, 330, "Combine degree 12/order 8, Sun point mass, and enabled JacchiaRoberts drag", force={"gravityDegree": 12, "gravityOrder": 8, "pointMasses": ["Sun"], "atmosphericDrag": {"enabled": True, "model": "JacchiaRoberts"}}, style=8)
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 10500, "eccentricity": 0.09, "inclinationDeg": 36, "trueAnomalyDeg": 245}, "OrbitPeriods", 5, 505, "Explicitly use SRP and Luna only", force={"solarRadiationPressure": True, "pointMasses": ["Luna"]}, style=10)
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 6800, "eccentricity": 0.005, "inclinationDeg": 52}, "ElapsedHours", 1.5, 265, "Disable drag without specifying a drag model", force={"atmosphericDrag": {"enabled": False}}, style=1)
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 12400, "eccentricity": 0.13, "inclinationDeg": 84}, "ElapsedDays", 1.1, 730, "Use gravity degree 10/order 3 and SRP off", force={"gravityDegree": 10, "gravityOrder": 3, "solarRadiationPressure": False}, style=3)
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 7400, "eccentricity": 0.015, "inclinationDeg": 20}, "ElapsedSeconds", 3600, 280, "Use the default force model", force=None, style=5)
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 8900, "eccentricity": 0.05, "inclinationDeg": 66}, "ElapsedHours", 3, 460, "All force settings are at their normal defaults", force=None, style=7)
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 13200, "eccentricity": 0.18, "inclinationDeg": 39}, "OrbitPeriods", 2, 850, "Do not add extra forces; leave the force model implicit", force=None, style=9)
    case("force", "Earth", "Keplerian", {"semiMajorAxisKm": 6900, "eccentricity": 0.008, "inclinationDeg": 98.2}, "ElapsedDays", 0.25, 305, "Use OrbitLab's defaults and do not expand the default force configuration", force=None, style=11)

    # V4Cartesian 12: varied nonzero axes, force and maneuver pairings.
    cart_vectors = [
        {"xKm": 0, "yKm": 7100, "zKm": 0, "vxKmS": -7.493, "vyKmS": 0, "vzKmS": 0},
        {"xKm": 0, "yKm": 0, "zKm": 7200, "vxKmS": 7.441, "vyKmS": 0, "vzKmS": 0},
        {"xKm": 7350, "yKm": 0, "zKm": 0, "vxKmS": 0, "vyKmS": 0, "vzKmS": 7.367},
        {"xKm": 0, "yKm": -7600, "zKm": 0, "vxKmS": 7.243, "vyKmS": 0, "vzKmS": 0},
        {"xKm": 0, "yKm": 0, "zKm": -6900, "vxKmS": 0, "vyKmS": -7.601, "vzKmS": 0},
        {"xKm": -8000, "yKm": 0, "zKm": 0, "vxKmS": 0, "vyKmS": -7.061, "vzKmS": 0},
        {"xKm": 6600, "yKm": 0, "zKm": 0, "vxKmS": 0, "vyKmS": 0, "vzKmS": 7.778},
        {"xKm": 0, "yKm": 0, "zKm": 8500, "vxKmS": -6.849, "vyKmS": 0, "vzKmS": 0},
        {"xKm": 9300, "yKm": 0, "zKm": 0, "vxKmS": 0, "vyKmS": 6.546, "vzKmS": 0},
        {"xKm": 0, "yKm": -10000, "zKm": 0, "vxKmS": 0, "vyKmS": 0, "vzKmS": 6.313},
        {"xKm": 0, "yKm": 0, "zKm": 11000, "vxKmS": 0, "vyKmS": -6.021, "vzKmS": 0},
        {"xKm": -12500, "yKm": 0, "zKm": 0, "vxKmS": 0, "vyKmS": 5.647, "vzKmS": 0},
    ]
    for index, vector in enumerate(cart_vectors):
        force = {"solarRadiationPressure": False} if index in (3, 8) else None
        maneuver = None
        if index in (2, 6, 10):
            maneuver = [{"id": f"VectorKick{index+1:02d}", "type": "ImpulsiveBurn", "trigger": {"condition": "AtPeriapsis" if index != 6 else "AtApoapsis"}, "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": [0.01 * (index + 1), -0.002, 0.001]}}]
        case("cartesian", "Earth", "Cartesian", vector, "ElapsedSeconds" if index % 2 == 0 else "ElapsedHours", 900 if index % 2 == 0 else 2, 300 + index * 17, ["Axis-aligned state vector", "Three-dimensional position state", "Cartesian orbit with z-axis velocity", "Negative-y position", "Retrograde-oriented state", "Negative-x initial position", "Out-of-plane circular velocity", "Polar Cartesian trajectory", "Longer Cartesian arc", "Cartesian state plus SRP setting", "Spatial state with local burn", "Cartesian position and velocity"][index], force=force, maneuvers=maneuver, style=index)

    # V4Hohmann 14: outward/inward, circular/eccentric sources and target e.
    hohmann_specs = [
        (7600, .02, "AtPeriapsis", 11000, .0), (8200, .04, "AtApoapsis", 15000, .12),
        (9000, .08, "AtPeriapsis", 12500, .1), (10000, 0, "AtApoapsis", 16000, .2),
        (7200, .01, "AtApoapsis", 14000, .0), (8800, .06, "AtPeriapsis", 13000, .15),
        (10500, .12, "AtApoapsis", 18000, .08), (10000, 0, "AtPeriapsis", 7200, .0),
        (11200, .03, "AtApoapsis", 8000, .1), (9500, .07, "AtPeriapsis", 7000, .15),
        (12500, .1, "AtApoapsis", 8200, .0), (8400, .02, "AtPeriapsis", 6800, .08),
        (14000, .15, "AtApoapsis", 9000, .12), (10000, .0, "AtApoapsis", 7500, .2),
    ]
    for i, (sma, ecc, trigger, target, target_e) in enumerate(hohmann_specs):
        source_r = sma * (1 - ecc if trigger == "AtPeriapsis" else 1 + ecc)
        direction = "raise" if target > source_r else "lower"
        target_desc = f"target apsis radius {target} km and target eccentricity {target_e:g}" if target_e else f"circular target apsis radius {target} km"
        objectives = {"targetOrbitRadiusKm": target}
        if target_e > 0:
            objectives["targetEccentricity"] = target_e
        maneuver = {"id": f"Transfer{i+1:02d}", "type": "TargetedHohmannTransfer", "trigger": {"condition": trigger}, "targetObjectives": objectives}
        case("hohmann", "Earth", "Keplerian", {"semiMajorAxisKm": sma, "eccentricity": ecc, "inclinationDeg": 28 + i * 5}, "ElapsedHours", 6 + i, 350 + 15 * i, f"{direction} transfer from {trigger}; {target_desc}", maneuvers=[maneuver], style=i)

    # V4Multi 10: coherent consecutive apsis burns with distinct IDs.
    for i in range(10):
        first_trigger, second_trigger = (("AtPeriapsis", "AtApoapsis") if i % 2 == 0 else ("AtApoapsis", "AtPeriapsis"))
        first = {"id": f"ImpulseA{i+1:02d}", "type": "ImpulsiveBurn", "trigger": {"condition": first_trigger}, "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": [round(.012 + i * .002, 3), round(-.002 - i * .001, 3), .001]}}
        second = {"id": f"ImpulseB{i+1:02d}", "type": "ImpulsiveBurn", "trigger": {"condition": {"AtPeriapsis": "AtApoapsis", "AtApoapsis": "AtPeriapsis"}[first_trigger]}, "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": [round(-.008 - i * .001, 3), .001, round(.002 + i * .001, 3)]}}
        case("multi", "Earth", "Keplerian", {"semiMajorAxisKm": 7300 + i * 310, "eccentricity": round(.01 + i * .012, 3), "inclinationDeg": 25 + i * 7}, "OrbitPeriods", 2 + i % 4, 310 + i * 20, f"two sequential burns at {first_trigger} then {second['trigger']['condition']}; local VNB components are explicitly provided", maneuvers=[first, second], style=i)

    # V4Cross 12: explicitly paired features rather than isolated parameter edits.
    case("cross", "Moon", "Cartesian", {"xKm": 2000, "yKm": 0, "zKm": 0, "vxKmS": 0, "vyKmS": 1.561, "vzKmS": 0}, "OrbitPeriods", 2, 295, "Moon-centered Cartesian state with Prince-Dormand propagation", integrator="PrinceDormand78", style=0)
    case("cross", "Mars", "Keplerian", {"semiMajorAxisKm": 4600, "eccentricity": .04, "inclinationDeg": 58}, "ElapsedHours", 8, 460, "Mars orbit with an explicit Sun point-mass setting", force={"pointMasses": ["Sun"]}, style=1)
    case("cross", "Earth", "Keplerian", {"semiMajorAxisKm": 8200, "eccentricity": .09, "inclinationDeg": 67}, "ElapsedSeconds", 1800, 385, "eccentric orbit, periapsis impulse and nondefault integrator", integrator="PrinceDormand78", maneuvers=[{"id": "CrossKick1", "type": "ImpulsiveBurn", "trigger": {"condition": "AtPeriapsis"}, "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": [.025, -.004, .002]}}], style=2)
    case("cross", "Earth", "Keplerian", {"semiMajorAxisKm": 9800, "eccentricity": .06, "inclinationDeg": 42}, "ElapsedDays", .3, 520, "target-eccentricity Hohmann with explicit gravity and long-duration propagation", force={"gravityDegree": 8, "gravityOrder": 5}, maneuvers=[{"id": "CrossRaise1", "type": "TargetedHohmannTransfer", "trigger": {"condition": "AtApoapsis"}, "targetObjectives": {"targetOrbitRadiusKm": 16000, "targetEccentricity": .08}}], style=3)
    case("cross", "Moon", "Keplerian", {"semiMajorAxisKm": 2250, "eccentricity": .03, "inclinationDeg": 84}, "ElapsedSeconds", 1200, 275, "Moon orbit with enabled SRP and an apsis maneuver", force={"solarRadiationPressure": True}, maneuvers=[{"id": "LunaKick1", "type": "ImpulsiveBurn", "trigger": {"condition": "AtApoapsis"}, "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": [.008, 0, -.001]}}], style=4)
    case("cross", "Earth", "Cartesian", {"xKm": 0, "yKm": 7200, "zKm": 0, "vxKmS": -7.441, "vyKmS": 0, "vzKmS": 0}, "ElapsedHours", 3, 405, "Cartesian initial state and requested MSISE90 drag", force={"atmosphericDrag": {"enabled": True, "model": "MSISE90"}}, style=5)
    case("cross", "Mars", "Keplerian", {"semiMajorAxisKm": 5100, "eccentricity": .12, "inclinationDeg": 33, "raanDeg": 118}, "OrbitPeriods", 3, 615, "eccentric Mars orbit, Sun and Jupiter point masses, and explicit step size", force={"pointMasses": ["Sun", "Jupiter"]}, step=45, style=6)
    case("cross", "Earth", "Keplerian", {"semiMajorAxisKm": 7600, "eccentricity": .025, "inclinationDeg": 97.5}, "ElapsedSeconds", 2400, 340, "polar orbit with two consecutive VNB maneuvers", maneuvers=[{"id": "PolarA", "type": "ImpulsiveBurn", "trigger": {"condition": "AtPeriapsis"}, "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": [.01, .002, 0]}}, {"id": "PolarB", "type": "ImpulsiveBurn", "trigger": {"condition": "AtApoapsis"}, "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": [-.006, 0, .001]}}], style=7)
    case("cross", "Moon", "Cartesian", {"xKm": 0, "yKm": 0, "zKm": 2450, "vxKmS": 1.415, "vyKmS": 0, "vzKmS": 0}, "ElapsedHours", 5, 370, "polar lunar Cartesian state with gravity harmonics and Prince-Dormand", force={"gravityDegree": 6, "gravityOrder": 6}, integrator="PrinceDormand78", style=8)
    case("cross", "Earth", "Keplerian", {"semiMajorAxisKm": 9000, "eccentricity": .05, "inclinationDeg": 55}, "ElapsedDays", .5, 490, "inward eccentric Hohmann transfer with requested point masses", force={"pointMasses": ["Luna", "Sun"]}, maneuvers=[{"id": "CrossLower1", "type": "TargetedHohmannTransfer", "trigger": {"condition": "AtApoapsis"}, "targetObjectives": {"targetOrbitRadiusKm": 7000, "targetEccentricity": .1}}], style=9)
    case("cross", "Mars", "Cartesian", {"xKm": 3900, "yKm": 0, "zKm": 0, "vxKmS": 0, "vyKmS": 3.284, "vzKmS": 0}, "OrbitPeriods", 1.5, 525, "Mars Cartesian state, elapsed-time impulse at exactly 1800 seconds and SRP off", force={"solarRadiationPressure": False}, maneuvers=[{"id": "MarsEpochKick", "type": "ImpulsiveBurn", "trigger": {"condition": "ElapsedTimeSecs", "elapsedSecs": 1800}, "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": [.004, -.001, .002]}}], style=10)
    case("cross", "Earth", "Keplerian", {"semiMajorAxisKm": 11800, "eccentricity": .16, "inclinationDeg": 71, "argumentOfPeriapsisDeg": 210}, "ElapsedHours", 10, 680, "outward target-elliptic Hohmann plus a second periapsis burn", maneuvers=[{"id": "RaiseEcc1", "type": "TargetedHohmannTransfer", "trigger": {"condition": "AtPeriapsis"}, "targetObjectives": {"targetOrbitRadiusKm": 20000, "targetEccentricity": .1}}, {"id": "LaterKick1", "type": "ImpulsiveBurn", "trigger": {"condition": "AtApoapsis"}, "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": [.003, 0, -.002]}}], style=11)

    # V4Propagation 8: unit conversion, integrator and explicitly chosen steps.
    case("propagation", "Earth", "Keplerian", {"semiMajorAxisKm": 7050, "eccentricity": .003, "inclinationDeg": 48}, "ElapsedSeconds", 900, 250, "duration written as 15 minutes, converted to elapsed seconds", style=0)
    case("propagation", "Earth", "Keplerian", {"semiMajorAxisKm": 8300, "eccentricity": .02, "inclinationDeg": 61}, "ElapsedSeconds", 2700, 380, "run for 45 min and set the step to 30 seconds", step=30, style=2)
    case("propagation", "Earth", "Keplerian", {"semiMajorAxisKm": 9600, "eccentricity": .07, "inclinationDeg": 23}, "ElapsedHours", 2.25, 430, "Prince-Dormand for two and a quarter hours", integrator="PrinceDormand78", style=4)
    case("propagation", "Earth", "Keplerian", {"semiMajorAxisKm": 11200, "eccentricity": .11, "inclinationDeg": 80}, "ElapsedDays", .75, 570, "three-quarter-day propagation using RungeKutta89", integrator="RungeKutta89", style=6)
    case("propagation", "Earth", "Keplerian", {"semiMajorAxisKm": 7800, "eccentricity": .01, "inclinationDeg": 45}, "OrbitPeriods", 6, 310, "six complete orbital revolutions with a 120-second step", step=120, style=8)
    case("propagation", "Earth", "Keplerian", {"semiMajorAxisKm": 14500, "eccentricity": .19, "inclinationDeg": 104}, "ElapsedSeconds", 3600, 660, "one hour in seconds with Prince-Dormand and an 80-second step", integrator="PrinceDormand78", step=80, style=10)
    case("propagation", "Earth", "Keplerian", {"semiMajorAxisKm": 9100, "eccentricity": .035, "inclinationDeg": 37}, "ElapsedHours", 7, 490, "seven hours using the integrator default", style=1)
    case("propagation", "Earth", "Keplerian", {"semiMajorAxisKm": 6800, "eccentricity": .002, "inclinationDeg": 98}, "ElapsedDays", .125, 335, "a three-hour equivalent requested as one eighth of a day", style=3)

    # V4Language 10: request voice/syntax variety with supported semantics.
    language_cases = [
        ("Earth", {"semiMajorAxisKm": 8100, "eccentricity": .035, "inclinationDeg": 44}, "OrbitPeriods", 2.5, "Short direct request; no optional additions"),
        ("Moon", {"semiMajorAxisKm": 2200, "eccentricity": .02, "inclinationDeg": 77}, "ElapsedHours", 3, "Conversational lunar navigation comparison"),
        ("Mars", {"semiMajorAxisKm": 4300, "eccentricity": .07, "inclinationDeg": 31}, "ElapsedDays", .2, "Technical shorthand with SMA/e/i labels"),
        ("Earth", {"semiMajorAxisKm": 10300, "eccentricity": .12, "inclinationDeg": 69}, "ElapsedSeconds", 4200, "Question-style request preserving exact elements"),
        ("Earth", {"semiMajorAxisKm": 7200, "eccentricity": .006, "inclinationDeg": 98.2}, "ElapsedHours", 1.75, "Concise polar orbit prompt with a stated purpose but no description request"),
        ("Moon", {"semiMajorAxisKm": 2800, "eccentricity": .11, "inclinationDeg": 54, "trueAnomalyDeg": 88}, "OrbitPeriods", 4, "Multi-sentence lunar request"),
        ("Mars", {"semiMajorAxisKm": 5900, "eccentricity": .17, "inclinationDeg": 119}, "ElapsedSeconds", 1200, "Casual request using a 20-minute duration"),
        ("Earth", {"semiMajorAxisKm": 8700, "eccentricity": .045, "inclinationDeg": 17, "raanDeg": 271}, "ElapsedDays", .6, "Preserve a supplied ascending node"),
        ("Earth", {"semiMajorAxisKm": 15500, "eccentricity": .21, "inclinationDeg": 132}, "OrbitPeriods", 1.25, "Retrograde orbit comparison with fractional revolutions"),
        ("Mars", {"semiMajorAxisKm": 3800, "eccentricity": .025, "inclinationDeg": 88, "argumentOfPeriapsisDeg": 155}, "ElapsedHours", 9, "Request using apoapsis/periapsis terminology for the source geometry"),
    ]
    for i, (body, elements, stop_type, duration, intent) in enumerate(language_cases):
        epoch = {"format": "UTCGregorian", "value": "08 Feb 2028 10:30:00.000"} if i == 4 else None
        if i == 4:
            intent += "; explicit epoch 08 Feb 2028 10:30:00.000"
        case("language", body, "Keplerian", elements, stop_type, duration, 410 + i * 23, intent, style=i, epoch=epoch)

    # V4Robustness 6: exact structure, omission, and explicit-value discipline.
    case("robustness", "Earth", "Keplerian", {"semiMajorAxisKm": 7400, "eccentricity": .01, "inclinationDeg": 53}, "ElapsedHours", 2, 320, "Required version and frame even though not requested; omit unspecified epoch and force model", style=0)
    case("robustness", "Earth", "Keplerian", {"semiMajorAxisKm": 8600, "eccentricity": .035, "inclinationDeg": 63}, "ElapsedSeconds", 1800, 445, "Default force request with a request not to emit an empty forceModel", force=None, style=2)
    case("robustness", "Earth", "Keplerian", {"semiMajorAxisKm": 9900, "eccentricity": .08, "inclinationDeg": 38}, "ElapsedHours", 4, 515, "The maneuver is called BurnR3 and its schema identifier must remain id", maneuvers=[{"id": "BurnR3", "type": "ImpulsiveBurn", "trigger": {"condition": "AtPeriapsis"}, "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": [.007, -.003, .002]}}], style=4)
    case("robustness", "Moon", "Keplerian", {"semiMajorAxisKm": 2400, "eccentricity": .04, "inclinationDeg": 36}, "OrbitPeriods", 2, 360, "Specify LunaMJ2000Eq explicitly and do not invent a date", style=6)
    case("robustness", "Earth", "Keplerian", {"semiMajorAxisKm": 10800, "eccentricity": .14, "inclinationDeg": 74}, "ElapsedDays", .3, 585, "User gives only one optional spacecraft property: Cd 2.4; do not add drag area", spacecraft={"coefficientOfDrag": 2.4}, style=8)
    case("robustness", "Mars", "Cartesian", {"xKm": 4100, "yKm": 0, "zKm": 0, "vxKmS": 0, "vyKmS": 3.229, "vzKmS": 0}, "ElapsedSeconds", 1500, 395, "Output one Experiment JSON only; never return mission script syntax", style=10)


def body_phrase(body: str) -> str:
    return {"Earth": "in Earth-centered space", "Moon": "around the Moon", "Mars": "around Mars"}[body]


def orbit_phrase(kind: str, elements: dict[str, float]) -> str:
    if kind == "Keplerian":
        labels = {"semiMajorAxisKm": "SMA", "eccentricity": "eccentricity", "inclinationDeg": "inclination", "raanDeg": "RAAN", "argumentOfPeriapsisDeg": "argument of periapsis", "trueAnomalyDeg": "true anomaly"}
        return ", ".join(f"{labels[key]} {value:g}" + (" km" if key == "semiMajorAxisKm" else " degrees" if key != "eccentricity" else "") for key, value in elements.items())
    return "Cartesian state [" + ", ".join(f"{elements[k]:g}" for k in ("xKm", "yKm", "zKm")) + "] km and velocity [" + ", ".join(f"{elements[k]:g}" for k in ("vxKmS", "vyKmS", "vzKmS")) + "] km/s"


def force_phrase(force: dict[str, Any] | None) -> str:
    if force is None:
        return " Use the default force model; leave it omitted." if force is not False else ""
    pieces = []
    if "gravityDegree" in force:
        pieces.append(f"gravity degree {force['gravityDegree']} and order {force['gravityOrder']}")
    if "pointMasses" in force:
        pieces.append("point masses " + " and ".join(force["pointMasses"]))
    if "atmosphericDrag" in force:
        drag = force["atmosphericDrag"]
        pieces.append(("enable" if drag["enabled"] else "disable") + " atmospheric drag" + (f" using {drag['model']}" if "model" in drag else ""))
    if "solarRadiationPressure" in force:
        pieces.append("SRP " + ("on" if force["solarRadiationPressure"] else "off"))
    return " Force request: " + "; ".join(pieces) + "."


def maneuver_phrase(maneuvers: list[dict[str, Any]] | None) -> str:
    if not maneuvers:
        return ""
    texts = []
    for item in maneuvers:
        trigger = item["trigger"]["condition"]
        if item["type"] == "ImpulsiveBurn":
            burn = item["burnVector"]["deltaVVectorKmS"]
            texts.append(f"Impulsive burn id {item['id']} at {trigger}, VNB vector [{', '.join(f'{v:g}' for v in burn)}] km/s")
        else:
            target = item["targetObjectives"]
            ecctext = f" and target eccentricity {target['targetEccentricity']:g}" if "targetEccentricity" in target else ""
            texts.append(f"Targeted Hohmann transfer id {item['id']} triggered at {trigger}, target radius {target['targetOrbitRadiusKm']:g} km{ecctext}")
    return " Maneuver request: " + "; then ".join(texts) + "."


def make_prompt(name: str, sat: str, row: dict[str, Any], index: int) -> str:
    stop_type, duration = row["stop_type"], row["duration"]
    if stop_type == "ElapsedSeconds" and row["category"] == "propagation" and index in (0, 1, 5):
        duration_text = {0: " Run for 15 minutes (900 seconds).", 1: " Run for 45 min (2700 seconds).", 5: " The requested one hour is 3600 seconds."}[index]
    elif row["category"] == "language" and index == 6:
        duration_text = " Propagate for 20 minutes, represented as 1200 elapsed seconds."
    else:
        duration_text = f" Propagate for {duration:g} {STOP_WORDS[stop_type]}."
    integrator = f" Integrator: {row['integrator']}." if row.get("integrator") else ""
    step = f" Set the initial step size to {row['step']:g} seconds." if row.get("step") is not None else ""
    epoch = f" Start at UTCGregorian epoch {row['epoch']['value']}." if row.get("epoch") else ""
    body = row["body"]
    orbit = orbit_phrase(row["orbit_type"], row["elements"])
    maneuver = maneuver_phrase(row.get("maneuvers"))
    for item in row.get("maneuvers") or []:
        if item["type"] == "TargetedHohmannTransfer":
            target = item["targetObjectives"]
            maneuver += f" Preserve target radius {target['targetOrbitRadiusKm']:g} km."
            if "targetEccentricity" in target:
                maneuver += f" Target eccentricity is {target['targetEccentricity']:g}."
        elif item["trigger"]["condition"] == "ElapsedTimeSecs":
            maneuver += f" Trigger time is exactly {item['trigger']['elapsedSecs']:g} seconds."
        elif item["type"] == "ImpulsiveBurn":
            maneuver += " Preserve the exact VNB vector components above."
    force = force_phrase(row.get("force"))
    tail = TAILS[(index + len(name)) % len(TAILS)]
    mass_text = f" Spacecraft dry mass is {row['mass']:g} kg."
    prompt = TEMPLATES[row.get("style", index) % len(TEMPLATES)].format(
        name=name, sat=sat, body_phrase=body_phrase(body), orbit_text=orbit,
        maneuver_text=maneuver, force_text=force, duration_text=duration_text,
        tail=integrator + step + epoch + " " + tail,
    )
    return prompt + mass_text + " Purpose: " + row["intent"] + "."


def build() -> list[dict[str, Any]]:
    CASE_ROWS.clear()
    add_cases()
    counts = Counter(row["category"] for row in CASE_ROWS)
    expected = {"body": 16, "force": 12, "cartesian": 12, "hohmann": 14, "multi": 10, "cross": 12, "propagation": 8, "language": 10, "robustness": 6}
    if dict(counts) != expected or len(CASE_ROWS) != 100:
        raise ValueError(f"Scenario distribution mismatch: {counts}")
    system = json.loads(V3_TRAIN.read_text(encoding="utf-8-sig").splitlines()[0])["systemInstruction"]
    counters: Counter[str] = Counter()
    records = []
    for index, row in enumerate(CASE_ROWS):
        category = row["category"]
        counters[category] += 1
        name = f"{PREFIXES[category]}{counters[category]:03d}"
        sat = f"V4Sat{index+1:03d}"
        prompt = make_prompt(name, sat, row, index)
        experiment: dict[str, Any] = {
            "version": "1.0", "experimentName": name,
            "description": row["intent"],
            "spacecraft": {"name": sat, "dryMassKg": row["mass"]},
            "centralBody": row["body"],
            "initialOrbit": {"type": row["orbit_type"], "coordinateSystem": {"Earth": "EarthMJ2000Eq", "Moon": "LunaMJ2000Eq", "Mars": "MarsMJ2000Eq"}[row["body"]], "elements": row["elements"]},
            "maneuvers": row.get("maneuvers") or [],
            "propagation": {"stopCondition": {"type": row["stop_type"], "value": row["duration"]}},
        }
        if row.get("force"):
            experiment["forceModel"] = row["force"]
        if row.get("integrator"):
            experiment["propagation"]["integrator"] = row["integrator"]
        if row.get("step") is not None:
            experiment["propagation"]["stepSizeSecs"] = row["step"]
        if row.get("epoch"):
            experiment["epoch"] = row["epoch"]
        if row.get("spacecraft"):
            experiment["spacecraft"].update(row["spacecraft"])
        parsed = OrbitLabExperiment.model_validate(experiment)
        physical = AstrodynamicValidator.validate(parsed)
        if not physical.is_valid:
            raise ValueError(f"{name}: physical validation failed: {physical.errors}")
        response = json.dumps(experiment, separators=(",", ":"), ensure_ascii=False)
        records.append({"systemInstruction": system, "contents": [{"role": "user", "parts": [{"text": prompt}]}, {"role": "model", "parts": [{"text": response}]}]})
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, choices=range(1, 11), required=True)
    args = parser.parse_args()
    records = build()
    start = (args.batch - 1) * 10
    path = ROOT / ".devswarm-temp" / f"orbitlab_v4_batch_{args.batch:02d}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    newline = bytes((10,))
    payload = newline.join(json.dumps(row, separators=(",", ":"), ensure_ascii=False).encode("utf-8") for row in records[start:start + 10]) + newline
    path.write_bytes(payload)
    print(f"Generated batch {args.batch}: 10 candidates at {path}")


if __name__ == "__main__":
    main()
