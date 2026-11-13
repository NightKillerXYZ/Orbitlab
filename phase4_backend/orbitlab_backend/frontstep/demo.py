"""Demo mode: deterministic local extractor + interpreter (no network).

DemoExtractor emits the SAME strict schema the real extractor returns, so the
real `normalize_extracted` and `deterministic_convert` run unchanged.
DemoInterpreter parses the canonical prompt our own `prompt_builder` emits and
builds the full experiment JSON from schema defaults, so verify, the
validator, the compiler and real GMAT run unchanged.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from orbitlab_backend.config import get_settings


def demo_enabled() -> bool:
    try:
        return bool(get_settings().ORBITLAB_DEMO_MODE)
    except Exception:
        return False


_BODY_WORDS = [
    ("Moon", [r"moon", r"luna\b", r"lunar"]),
    ("Mars", [r"mars", r"martian"]),
    ("Mercury", [r"mercury"]),
    ("Venus", [r"venus"]),
    ("Jupiter", [r"jupiter"]),
    ("Sun", [r"sun\b", r"solar"]),
    ("Earth", [r"earth"]),
]

_NUM = r"(\d+\.?\d*)"
_DURATION_UNITS = (
    r"seconds|second|secs|sec|hours|hour|hrs|hr|days|day|orbits|orbit|"
    r"orbital periods|orbit periods|orbital period|orbit period"
)
_DURATION_TO_UNIT = {
    "seconds": "seconds", "second": "seconds", "secs": "seconds", "sec": "seconds",
    "hours": "hours", "hour": "hours", "hrs": "hours", "hr": "hours",
    "days": "days", "day": "days",
    "orbits": "orbits", "orbit": "orbits",
    "orbital periods": "orbits", "orbit periods": "orbits",
    "orbital period": "orbits", "orbit period": "orbits",
}


def _find_body(text: str) -> Optional[str]:
    for body, words in _BODY_WORDS:
        for w in words:
            if re.search(r"\b" + w, text):
                return body
    return None


def _find_num(pattern: str, text: str) -> Optional[float]:
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except (TypeError, ValueError, IndexError):
        return None


def demo_parse_strict_schema(user_text: str) -> Dict[str, Any]:
    """Parse free text into the strict extractor schema. Unknowns stay null."""
    t = (user_text or "").lower()
    body = _find_body(t)
    mass = _find_num(_NUM + r"\s*kg", t)

    orbit: Optional[Dict[str, Any]] = None
    ecc = _find_num(r"eccentricity\s*(?:of\s*|is\s*|=\s*)?" + _NUM, t)
    m = re.search(r"periapsis altitude\s*(?:of\s*)?" + _NUM + r"\s*km", t)
    if m:
        orbit = {"quantity": "periapsis_altitude", "valueKm": float(m.group(1)), "eccentricity": ecc}
    else:
        m = re.search(r"(?:semi-major axis|semi major axis|\bsma\b)\s*(?:of\s*)?" + _NUM + r"\s*km", t)
        if m:
            orbit = {"quantity": "semi_major_axis", "valueKm": float(m.group(1)), "eccentricity": ecc}
        else:
            m = re.search(_NUM + r"\s*km\s*circular orbit", t)
            if m:
                orbit = {"quantity": "radius", "valueKm": float(m.group(1)), "eccentricity": 0.0}
            else:
                m = (re.search(r"circular orbit at\s*" + _NUM + r"\s*km\s*altitude", t)
                     or re.search(_NUM + r"\s*km\s*altitude", t)
                     or re.search(r"altitude of\s*" + _NUM + r"\s*km", t))
                if m:
                    orbit = {"quantity": "altitude", "valueKm": float(m.group(1)),
                             "eccentricity": 0.0 if "circular" in t else None}

    inc = _find_num(r"inclination\s*(?:of\s*|is\s*|=\s*)?" + _NUM, t)
    raan = _find_num(r"\braan\b\s*(?:of\s*|is\s*|=\s*)?" + _NUM, t)
    aop = _find_num(r"argument of periapsis\s*(?:of\s*|is\s*|=\s*)?" + _NUM, t)
    ta = _find_num(r"true anomaly\s*(?:of\s*|is\s*|=\s*)?" + _NUM, t)

    duration = None
    m = re.search(_NUM + r"\s*(" + _DURATION_UNITS + r")\b", t)
    if m:
        try:
            duration = {"value": float(m.group(1)), "unit": _DURATION_TO_UNIT[m.group(2).strip().lower()]}
        except (TypeError, ValueError, KeyError):
            duration = None

    maneuvers: List[Dict[str, Any]] = []
    is_hohmann = "hohmann" in t
    tgt = _find_num(r"\bto\s*" + _NUM + r"\s*km", t)
    has_burn = "burn" in t
    if (is_hohmann or has_burn) and tgt is not None:
        if re.search(r"apoapsis|\bapo\b", t):
            trig = "apoapsis"
        elif re.search(r"periapsis|\bperi\b", t):
            trig = "periapsis"
        else:
            trig = "periapsis"
        maneuvers.append({"type": "hohmann_transfer", "trigger": trig,
                          "targetRadiusKm": tgt, "elapsedSecs": None, "deltaVKmS": None})

    return {"centralBody": body, "dryMassKg": mass, "orbit": orbit,
            "inclinationDeg": inc, "raanDeg": raan,
            "argumentOfPeriapsisDeg": aop, "trueAnomalyDeg": ta,
            "duration": duration, "maneuvers": maneuvers}


class DemoExtractor:
    """IFieldExtractor-compatible local parser (no network)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def extract(self, user_text: str) -> Dict[str, Any]:
        return demo_parse_strict_schema(user_text)

    def extract_sync(self, user_text: str) -> Dict[str, Any]:
        return demo_parse_strict_schema(user_text)


_STOP_TO_TYPE = {"seconds": "ElapsedSeconds", "hours": "ElapsedHours",
                "days": "ElapsedDays", "orbital periods": "OrbitPeriods"}


def _coord_system(body: str) -> str:
    try:
        from orbitlab_core.ast.models import CENTRAL_BODY_PROPERTIES
        info = CENTRAL_BODY_PROPERTIES.get(body)
        if info is not None:
            return info[3]
    except Exception:
        pass
    if body == "Moon":
        return "LunaMJ2000Eq"
    return "%sMJ2000Eq" % body


def demo_build_experiment(prompt: str) -> Dict[str, Any]:
    """Build the full experiment JSON by parsing our own canonical prompt."""
    t = prompt or ""

    def grab(pattern: str, default: Any = None) -> Any:
        m = re.search(pattern, t)
        return m.group(1) if m else default

    exp_name = grab(r"Configure experiment (\w+)", "DefaultExp") or "DefaultExp"
    sc_full = grab(r"for (SC_\w+)", "SC_" + exp_name) or ("SC_" + exp_name)
    try:
        dry_mass = float(grab(r"dry mass ([\d.eE+-]+) kg", "500"))
    except (TypeError, ValueError):
        dry_mass = 500.0
    body = grab(r"in a (\w+) orbit", "Earth") or "Earth"
    try:
        sma = float(grab(r"semi-major axis ([\d.eE+-]+) km", "6778.136"))
    except (TypeError, ValueError):
        sma = 6778.136

    def num(pattern: str, default: float = 0.0) -> float:
        try:
            return float(grab(pattern, str(default)))
        except (TypeError, ValueError):
            return default

    ecc = num(r"eccentricity ([\d.eE+-]+)")
    inc = num(r"inclination ([\d.eE+-]+) degrees")
    raan = num(r"RAAN ([\d.eE+-]+) degrees")
    aop = num(r"argument of periapsis ([\d.eE+-]+) degrees")
    ta = num(r"true anomaly ([\d.eE+-]+) degrees")
    try:
        dur_val = float(grab(r"propagate for ([\d.eE+-]+)", "2"))
    except (TypeError, ValueError):
        dur_val = 2.0
    dur_unit = grab(r"propagate for [\d.eE+-]+ (\w+(?: \w+)?) using integrator", "hours") or "hours"
    stop_type = _STOP_TO_TYPE.get(dur_unit.strip(), "ElapsedHours")
    integrator = grab(r"using integrator (\w+)", "RungeKutta89") or "RungeKutta89"
    if integrator not in ("RungeKutta89", "PrinceDormand78"):
        integrator = "RungeKutta89"

    maneuvers: List[Dict[str, Any]] = []
    for m in re.finditer(
            r"add maneuver (\w+): a Hohmann transfer at (\w+) to a target orbit radius of ([\d.eE+-]+) km", t):
        mid, apsis, target = m.group(1), m.group(2), float(m.group(3))
        cond = "AtPeriapsis" if apsis == "periapsis" else "AtApoapsis"
        maneuvers.append({"id": mid, "type": "TargetedHohmannTransfer",
                          "trigger": {"condition": cond},
                          "targetObjectives": {"targetOrbitRadiusKm": target}})
    for m in re.finditer(
            r"impulse once ([\d.eE+-]+) sec have elapsed: LocalVNB components \[([^\]]+)\] km/s", t):
        sec = float(m.group(1))
        vec = [float(x) for x in m.group(2).split(",")]
        maneuvers.append({"id": "M%d" % (len(maneuvers) + 1), "type": "ImpulsiveBurn",
                          "trigger": {"condition": "ElapsedTimeSecs", "elapsedSecs": sec},
                          "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": vec}})
    for m in re.finditer(
            r"At the next (\w+), apply the LocalVNB burn with V-N-B delta-v \[([^\]]+)\] km/s", t):
        apsis = m.group(1)
        vec = [float(x) for x in m.group(2).split(",")]
        cond = "AtPeriapsis" if apsis == "periapsis" else "AtApoapsis"
        maneuvers.append({"id": "M%d" % (len(maneuvers) + 1), "type": "ImpulsiveBurn",
                          "trigger": {"condition": cond},
                          "burnVector": {"coordinateSystem": "LocalVNB", "deltaVVectorKmS": vec}})

    return {"version": "1.0", "experimentName": exp_name,
            "spacecraft": {"name": sc_full, "dryMassKg": dry_mass,
                           "coefficientOfDrag": 2.2, "dragAreaM2": 1.0,
                           "coefficientOfReflectivity": 1.8, "srpAreaM2": 1.0},
            "centralBody": body,
            "initialOrbit": {"type": "Keplerian", "coordinateSystem": _coord_system(body),
                             "elements": {"semiMajorAxisKm": sma, "eccentricity": ecc,
                                          "inclinationDeg": inc, "raanDeg": raan,
                                          "argumentOfPeriapsisDeg": aop, "trueAnomalyDeg": ta}},
            "forceModel": {"gravityDegree": 4, "gravityOrder": 4, "pointMasses": ["Luna", "Sun"],
                           "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
                           "solarRadiationPressure": True},
            "propagation": {"integrator": integrator,
                             "stopCondition": {"type": stop_type, "value": dur_val},
                             "stepSizeSecs": 60},
            "maneuvers": maneuvers}


class DemoInterpreter:
    """Local deterministic experiment builder (no network)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def interpret_prompt(self, prompt: str, warming_callback: Any = None) -> Dict[str, Any]:
        return demo_build_experiment(prompt)

    def interpret(self, raw_text: str) -> Dict[str, Any]:
        return demo_build_experiment(raw_text)
