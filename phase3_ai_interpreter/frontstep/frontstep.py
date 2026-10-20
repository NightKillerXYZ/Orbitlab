"""Deterministic Front-Step Normalizer and Prompt Builder for OrbitLab.

Takes the raw extraction JSON from the Front-Step Extractor LLM, performs all
unit conversions and astrodynamic formulas deterministically using the Python
standard library, applies the explicit default policy, and renders the
standardized prompt using verbatim templates from the training corpus.
"""

from __future__ import annotations

import ast
import math
import re
from typing import Any

# ============================================================================
# 1. EXACT BODY RADII (km)
# Verified against user specification and training/eval datasets:
# - Earth: BasicTrain004 (alt 538 -> SMA 6916.1363 => R = 6378.1363)
# - Moon:  v9c-blind-101 (alt 80  -> SMA 1817.4    => R = 1737.4)
# - Mars:  v9c-blind-111 (alt 100 -> SMA 3489.5    => R = 3389.5)
# - Mercury/Venus/Jupiter/Sun: SPICE 2015 IAU nominal radii, single source of
#   truth is orbitlab_core/bodies.json (kept in lock-step with the compiler).
# ============================================================================
BODY_RADII_KM: dict[str, float] = {
    "Earth": 6378.1363,
    "Moon": 1737.4,
    "Mars": 3389.5,
    "Mercury": 2440.53,
    "Venus": 6051.8,
    "Jupiter": 71492.0,
    "Sun": 695700.0,
}

BODY_COORD_SYSTEM: dict[str, str] = {
    "Earth": "EarthMJ2000Eq",
    "Moon": "LunaMJ2000Eq",
    "Mars": "MarsMJ2000Eq",
    "Mercury": "MercuryMJ2000Eq",
    "Venus": "VenusMJ2000Eq",
    "Jupiter": "JupiterMJ2000Eq",
    "Sun": "SunMJ2000Eq",
}

# Point-mass-only central bodies (no spherical-harmonic gravity field in GMAT):
# kept in lock-step with POINT_MASS_ONLY_BODIES in orbitlab_core/constants.py.
POINT_MASS_ONLY_BODIES: frozenset[str] = frozenset(
    {"Sun", "Mercury", "Jupiter"}
)

# Astronomical unit in kilometres (DE405) — used for "x AU from the centre"
# heliocentric orbit inputs for the Sun.
AU_KM: float = 149597870.691

# ============================================================================
# 2. SCHEMA DEFAULTS (from experiment.schema.json)
# ============================================================================
SCHEMA_DEFAULTS: dict[str, Any] = {
    "coefficientOfDrag": 2.2,
    "dragAreaM2": 1.0,
    "coefficientOfReflectivity": 1.8,
    "srpAreaM2": 1.0,
    "gravityDegree": 4,
    "gravityOrder": 4,
    "pointMasses": ["Luna", "Sun"],
    "atmosphericDragEnabled": False,
    "atmosphericDragModel": "JacchiaRoberts",
    "solarRadiationPressure": True,
    "integrator": "RungeKutta89",
    "stepSizeSecs": 60.0,
    "burnCoordinateSystem": "LocalVNB",
}

# ============================================================================
# 3. PROPOSED DEFAULTS (where experiment.schema.json has no default)
# Every use of a PROPOSED default is logged in "assumptions".
# ============================================================================
PROPOSED_DEFAULTS: dict[str, Any] = {
    "experimentName": "DefaultRun001",       # PROPOSED, needs approval
    "spacecraftName": "DefaultSat001",       # PROPOSED, needs approval
    "dryMassKg": 1000.0,                     # PROPOSED, needs approval
    "eccentricity": 0.0,                     # PROPOSED (for circular/single-alt inputs)
    "inclinationDeg": 0.0,                   # PROPOSED, needs approval
    "raanDeg": 0.0,                          # PROPOSED, needs approval
    "argumentOfPeriapsisDeg": 0.0,           # PROPOSED, needs approval
    "trueAnomalyDeg": 0.0,                   # PROPOSED, needs approval
    "maneuverIdImpulsive": "Burn01",         # PROPOSED, needs approval
    "maneuverIdHohmann": "Transfer01",       # PROPOSED, needs approval
    "purpose": "Inspect inertial position drift while preparing a lab notebook.",  # from BasicTrain001
}


# ============================================================================
# 4. FORMULA & CONVERSION FUNCTIONS
# ============================================================================
def radius_and_altitude_from_gravity_fraction(
    body_radius_km: float, f: float
) -> tuple[float, float]:
    """r = R / sqrt(f); altitude = r - R."""
    r = body_radius_km / math.sqrt(f)
    alt = r - body_radius_km
    return r, alt


def sma_from_circular_altitude(body_radius_km: float, altitude_km: float) -> float:
    """a = R + altitude."""
    return body_radius_km + altitude_km


def sma_from_periapsis_altitude(
    body_radius_km: float, periapsis_alt_km: float, eccentricity: float
) -> float:
    """a = (R + altitude) / (1 - e)."""
    return (body_radius_km + periapsis_alt_km) / (1.0 - eccentricity)


def sma_and_ecc_from_apses_altitudes(
    body_radius_km: float, apoapsis_alt_km: float, periapsis_alt_km: float
) -> tuple[float, float]:
    """a = R + (alt_a + alt_p)/2, e = (alt_a - alt_p)/(2R + alt_a + alt_p)."""
    a = body_radius_km + (apoapsis_alt_km + periapsis_alt_km) / 2.0
    e = (apoapsis_alt_km - periapsis_alt_km) / (
        2.0 * body_radius_km + apoapsis_alt_km + periapsis_alt_km
    )
    return a, e


def _safe_eval(node: ast.AST) -> float:
    """Evaluates a tiny arithmetic AST: numbers, + - * / and unary minus only."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _safe_eval(node.operand)
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        a, b = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        return a / b
    raise ValueError("unsupported expression")


def parse_pi_or_float(val: float | int | str) -> float:
    """Evaluates numbers or constant pi expressions such as 'pi/8', '12pi/8',
    '3*pi/2' or '1.5pi'. A number written directly before 'pi' means multiplication.
    Anything with letters other than pi (for example 'y**2+8') raises ValueError."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().lower().replace(" ", "").replace("\u03c0", "pi")
    s = re.sub(r"(?<=[0-9.)])pi", "*pi", s)    # 12pi -> 12*pi
    s = re.sub(r"pi(?=[0-9.(])", "pi*", s)     # pi2 -> pi*2
    s = s.replace("pi", repr(math.pi))
    if not re.fullmatch(r"[0-9.+\-*/()eE]+", s):
        raise ValueError(f"not a constant expression: {val!r}")
    return _safe_eval(ast.parse(s, mode="eval"))


def rad_to_deg(rad_val: float | int | str) -> float:
    """deg = rad * (180 / pi)."""
    return parse_pi_or_float(rad_val) * (180.0 / math.pi)


def tons_to_kg(tons: float) -> float:
    """1 t = 1000 kg."""
    return tons * 1000.0


def lb_to_kg(lb: float) -> float:
    """1 lb = 0.45359237 kg."""
    return lb * 0.45359237


def minutes_to_seconds(minutes: float) -> float:
    """1 minute = 60 seconds."""
    return minutes * 60.0


def fmt_num(val: float, decimals: int = 3) -> str:
    """Formats a float up to `decimals` places, stripping trailing zeros."""
    rounded = round(float(val), decimals)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")


# ============================================================================
# 5. VALIDATION & DEFAULT POLICY APPLICATION
# ============================================================================
def validate_and_apply_defaults(
    extraction_payload: dict[str, Any],
) -> dict[str, Any]:
    """Validates scope/schema rules, computes derived values, and applies defaults."""
    ext = extraction_payload.get("extracted") or {}
    unsupported: list[dict[str, str]] = list(
        extraction_payload.get("unsupported") or []
    )
    missing: list[str] = []
    derived: list[dict[str, Any]] = []
    assumptions: list[str] = []

    body = ext.get("centralBody")
    orbit_size = ext.get("orbitSize")
    run_time = ext.get("runTime")

    # Check supported centralBody
    if body is not None and body not in BODY_RADII_KM:
        unsupported.append({
            "what": f"centralBody={body}",
            "why": "supported central bodies are Earth, Moon, Mars, Mercury, Venus, Jupiter, Sun (the Sun has no spherical-harmonic field; it is a point mass).",
        })

    # A planet/body as the *orbiting object* is still rejected: the orbiting
    # object must be a spacecraft, not one of the central bodies (upstream
    # extractor also flags this; we enforce it here defensively).
    orbiting = ext.get("orbitingObject")
    if orbiting is not None and str(orbiting) in BODY_RADII_KM:
        unsupported.append({
            "what": f"orbitingObject={orbiting}",
            "why": "A planet as the orbiting object is unsupported; the orbiting object must be a spacecraft.",
        })

    # Check periodHours orbitSize (unsupported without mu)
    if isinstance(orbit_size, dict) and orbit_size.get("kind") == "periodHours":
        unsupported.append({
            "what": f"orbitSize.kind=periodHours ({orbit_size.get('value')} h)",
            "why": "Gravitational parameter (mu) is not defined in the schema; period cannot be converted to SMA.",
        })

    # Check forceModel rules
    fm = ext.get("forceModel") or {}
    drag_spec = fm.get("atmosphericDrag") or {}
    if drag_spec.get("enabled") is True and body in ("Moon", "Mars"):
        unsupported.append({
            "what": f"atmosphericDrag.enabled=true on {body}",
            "why": "Atmospheric drag is supported only for Earth.",
        })
    if drag_spec.get("model") not in (None, "JacchiaRoberts", "MSISE90"):
        unsupported.append({
            "what": f"atmosphericDrag.model={drag_spec.get('model')}",
            "why": "experiment.schema.json atmosphericDrag.model enum allows only JacchiaRoberts, MSISE90.",
        })
    for pm in fm.get("pointMasses") or []:
        if pm not in ("Luna", "Sun", "Jupiter"):
            unsupported.append({
                "what": f"pointMass={pm}",
                "why": "experiment.schema.json pointMasses enum allows only Luna, Sun, Jupiter.",
            })

    # Check integrator
    integrator_in = ext.get("integrator")
    if integrator_in not in (None, "RungeKutta89", "PrinceDormand78"):
        unsupported.append({
            "what": f"integrator={integrator_in}",
            "why": "experiment.schema.json integrator enum allows only RungeKutta89, PrinceDormand78.",
        })

    # Check maneuver rules
    man = ext.get("maneuver")
    if isinstance(man, dict):
        m_type = man.get("type")
        m_trig = man.get("triggerCondition")
        if m_type not in ("ImpulsiveBurn", "TargetedHohmannTransfer"):
            unsupported.append({
                "what": f"maneuver.type={m_type}",
                "why": "experiment.schema.json maneuvers.type enum allows only ImpulsiveBurn, TargetedHohmannTransfer.",
            })
        if m_trig not in ("AtPeriapsis", "AtApoapsis", "ElapsedTimeSecs"):
            unsupported.append({
                "what": f"maneuver.triggerCondition={m_trig}",
                "why": "experiment.schema.json trigger.condition enum allows only AtPeriapsis, AtApoapsis, ElapsedTimeSecs.",
            })
        if m_type == "TargetedHohmannTransfer" and m_trig == "ElapsedTimeSecs":
            unsupported.append({
                "what": "TargetedHohmannTransfer with trigger ElapsedTimeSecs",
                "why": "experiment.schema.json allOf requires TargetedHohmannTransfer trigger to be AtPeriapsis or AtApoapsis.",
            })
        if m_type == "ImpulsiveBurn" and man.get("deltaV") is None:
            missing.append("maneuver.deltaV")

    # Check required fields
    if body is None:
        missing.append("centralBody")
    if orbit_size is None:
        missing.append("orbitSize")
    if run_time is None:
        missing.append("runTime")

    # Even if missing or unsupported, compute any derivable quantities from what WAS given
    R = BODY_RADII_KM.get(body) if body in BODY_RADII_KM else None

    # 1. Dry mass conversion
    dry_mass_obj = ext.get("dryMass")
    if isinstance(dry_mass_obj, dict) and dry_mass_obj.get("value") is not None:
        m_val = float(dry_mass_obj["value"])
        m_unit = dry_mass_obj.get("unit", "kg")
        if m_unit == "t":
            dry_mass_kg = round(tons_to_kg(m_val), 3)
            derived.append({
                "quantity": "dry_mass_kg",
                "formula": "kg = tons * 1000",
                "inputs": {"tons": m_val},
                "result": dry_mass_kg,
            })
        elif m_unit == "lb":
            dry_mass_kg = round(lb_to_kg(m_val), 3)
            derived.append({
                "quantity": "dry_mass_kg",
                "formula": "kg = lb * 0.45359237",
                "inputs": {"lb": m_val},
                "result": dry_mass_kg,
            })
        else:
            dry_mass_kg = m_val
    else:
        dry_mass_kg = PROPOSED_DEFAULTS["dryMassKg"]
        assumptions.append(
            f"PROPOSED DEFAULT: Used dryMassKg = {dry_mass_kg} kg (not stated by user)."
        )

    # 2. Angles conversion & defaults
    resolved_angles: dict[str, float] = {}
    for field_key, default_key, label in [
        ("inclination", "inclinationDeg", "inclination_deg"),
        ("raan", "raanDeg", "raan_deg"),
        ("argumentOfPeriapsis", "argumentOfPeriapsisDeg", "argument_of_periapsis_deg"),
        ("trueAnomaly", "trueAnomalyDeg", "true_anomaly_deg"),
    ]:
        ang_obj = ext.get(field_key)
        if isinstance(ang_obj, dict) and ang_obj.get("value") is not None:
            raw_v = ang_obj["value"]
            unit = ang_obj.get("unit", "deg")
            try:
                if unit == "rad":
                    deg_v = round(rad_to_deg(raw_v), 3)
                    derived.append({
                        "quantity": label,
                        "formula": "deg = rad * (180 / pi)",
                        "inputs": {"rad": raw_v},
                        "result": deg_v,
                    })
                    resolved_angles[field_key] = deg_v
                else:
                    resolved_angles[field_key] = float(raw_v)
            except Exception:
                unsupported.append({
                    "what": f"{field_key}={raw_v}",
                    "why": "Non-numeric or symbolic expression cannot be evaluated as a constant angle.",
                })
                resolved_angles[field_key] = PROPOSED_DEFAULTS[default_key]
        else:
            resolved_angles[field_key] = PROPOSED_DEFAULTS[default_key]
            assumptions.append(
                f"PROPOSED DEFAULT: Used {default_key} = {PROPOSED_DEFAULTS[default_key]} deg (not stated by user)."
            )

    # 3. Orbit Size & Eccentricity derivation
    ecc_in = ext.get("eccentricity")
    sma_km: float | None = None
    ecc_val: float | None = float(ecc_in) if ecc_in is not None else None
    peri_alt_km: float | None = None
    circ_alt_km: float | None = None
    is_circular: bool = False

    if isinstance(orbit_size, dict) and R is not None:
        kind = orbit_size.get("kind")
        if kind == "circularAltitudeKm":
            alt = float(orbit_size["value"])
            circ_alt_km = alt
            if ecc_val is None:
                ecc_val = 0.0
            is_circular = (ecc_val == 0.0)
            sma_raw = sma_from_circular_altitude(R, alt)
            sma_km = round(sma_raw, 3)
            derived.append({
                "quantity": "semi_major_axis_km",
                "formula": "a = R + altitude",
                "inputs": {"R": R, "altitude": alt},
                "result": sma_km,
            })

        elif kind == "periapsisAltitudeKm":
            alt = float(orbit_size["value"])
            peri_alt_km = alt
            if ecc_val is None:
                ecc_val = PROPOSED_DEFAULTS["eccentricity"]
                assumptions.append(
                    "PROPOSED DEFAULT: Assumed circular orbit (eccentricity = 0.0) because eccentricity was not stated."
                )
            is_circular = (ecc_val == 0.0)
            if is_circular:
                circ_alt_km = alt
                sma_raw = sma_from_circular_altitude(R, alt)
                sma_km = round(sma_raw, 3)
                derived.append({
                    "quantity": "semi_major_axis_km",
                    "formula": "a = R + altitude",
                    "inputs": {"R": R, "altitude": alt},
                    "result": sma_km,
                })
            else:
                sma_raw = sma_from_periapsis_altitude(R, alt, ecc_val)
                sma_km = round(sma_raw, 3)
                derived.append({
                    "quantity": "semi_major_axis_km",
                    "formula": "a = (R + altitude) / (1 - e)",
                    "inputs": {"R": R, "altitude": alt, "e": ecc_val},
                    "result": sma_km,
                })

        elif kind == "gravityFraction":
            f_val = float(orbit_size["value"])
            if f_val <= 0:
                unsupported.append({
                    "what": f"gravityFraction={f_val}",
                    "why": "Gravity fraction f must be > 0 to evaluate r = R / sqrt(f).",
                })
            else:
                r_raw, alt_raw = radius_and_altitude_from_gravity_fraction(R, f_val)
                r_round = round(r_raw, 3)
                alt_round = round(alt_raw, 3)
                derived.append({
                    "quantity": "radius_km",
                    "formula": "r = R / sqrt(f)",
                    "inputs": {"R": R, "f": f_val},
                    "result": r_round,
                })
                derived.append({
                    "quantity": "circular_altitude_km",
                    "formula": "altitude = r - R",
                    "inputs": {"r": r_round, "R": R},
                    "result": alt_round,
                })
                if ecc_val is None:
                    ecc_val = 0.0
                    assumptions.append(
                        "PROPOSED DEFAULT: Assumed circular orbit (eccentricity = 0.0) for surface gravity fraction."
                    )
                is_circular = (ecc_val == 0.0)
                circ_alt_km = alt_round
                peri_alt_km = alt_round
                sma_raw = sma_from_circular_altitude(R, alt_raw)
                sma_km = round(sma_raw, 3)
                derived.append({
                    "quantity": "semi_major_axis_km",
                    "formula": "a = R + altitude",
                    "inputs": {"R": R, "altitude": alt_round},
                    "result": sma_km,
                })

        elif kind == "apoapsisAndPeriapsisAltitudeKm":
            alt_a = float(orbit_size["apoapsis"])
            alt_p = float(orbit_size["periapsis"])
            peri_alt_km = alt_p
            a_raw, e_raw = sma_and_ecc_from_apses_altitudes(R, alt_a, alt_p)
            sma_km = round(a_raw, 3)
            ecc_round_3 = round(e_raw, 3)
            ecc_round_6 = round(e_raw, 6)
            derived.append({
                "quantity": "semi_major_axis_km",
                "formula": "a = R + (alt_a + alt_p) / 2",
                "inputs": {"R": R, "alt_a": alt_a, "alt_p": alt_p},
                "result": sma_km,
            })
            derived.append({
                "quantity": "eccentricity",
                "formula": "e = (alt_a - alt_p) / (2*R + alt_a + alt_p)",
                "inputs": {"R": R, "alt_a": alt_a, "alt_p": alt_p},
                "result": ecc_round_3,
                "result_6dec": ecc_round_6,
            })
            ecc_val = ecc_round_6
            is_circular = (ecc_val == 0.0)

        elif kind == "radiusFromCenterKm":
            r_val = float(orbit_size["value"])
            if ecc_val is None:
                ecc_val = 0.0
                assumptions.append(
                    "PROPOSED DEFAULT: Assumed circular orbit (eccentricity = 0.0) for radiusFromCenterKm."
                )
            is_circular = (ecc_val == 0.0)
            sma_km = round(r_val if is_circular else r_val / (1.0 - ecc_val), 3)
            alt_val = round(r_val - R, 3)
            circ_alt_km = alt_val
            peri_alt_km = alt_val
            derived.append({
                "quantity": "semi_major_axis_km",
                "formula": "a = r" if is_circular else "a = r / (1 - e)",
                "inputs": {"r": r_val} if is_circular else {"r": r_val, "e": ecc_val},
                "result": sma_km,
            })

        elif kind == "radiusFromCenterAu":
            # Heliocentric (Sun-centred): "x AU from the centre".
            au_val = float(orbit_size["value"])
            if ecc_val is None:
                ecc_val = 0.0
                assumptions.append(
                    "PROPOSED DEFAULT: Assumed circular orbit (eccentricity = 0.0) for radiusFromCenterAu."
                )
            is_circular = (ecc_val == 0.0)
            r_au_km = au_val * AU_KM
            sma_km = round(r_au_km if is_circular else r_au_km / (1.0 - ecc_val), 3)
            alt_val = round(r_au_km - R, 3)
            circ_alt_km = alt_val
            peri_alt_km = alt_val
            derived.append({
                "quantity": "semi_major_axis_km",
                "formula": "a = AU_value * AU_KM" if is_circular else "a = (AU_value * AU_KM) / (1 - e)",
                "inputs": {
                    "AU": au_val,
                    "AU_KM": AU_KM,
                } if is_circular else {
                    "AU": au_val,
                    "AU_KM": AU_KM,
                    "e": ecc_val,
                },
                "result": sma_km,
            })
            derived.append({
                "quantity": "semi_major_axis_au",
                "formula": "a_AU = a_km / AU_KM",
                "inputs": {"a_km": sma_km, "AU_KM": AU_KM},
                "result": round(sma_km / AU_KM, 6),
            })

        elif kind == "semiMajorAxisKm":
            sma_km = float(orbit_size["value"])
            if ecc_val is None:
                ecc_val = 0.0
                assumptions.append(
                    "PROPOSED DEFAULT: Assumed circular orbit (eccentricity = 0.0) for semiMajorAxisKm."
                )
            is_circular = (ecc_val == 0.0)
            peri_alt_km = round(sma_km * (1.0 - ecc_val) - R, 3)
            circ_alt_km = round(sma_km - R, 3)

    # 4. Run time conversion
    rt_val_out: float | None = None
    rt_unit_out: str | None = None
    if isinstance(run_time, dict) and run_time.get("value") is not None:
        raw_rt = float(run_time["value"])
        raw_unit = run_time.get("unit")
        if raw_unit == "minutes":
            rt_val_out = round(minutes_to_seconds(raw_rt), 3)
            rt_unit_out = "seconds"
            derived.append({
                "quantity": "run_time_seconds",
                "formula": "seconds = minutes * 60",
                "inputs": {"minutes": raw_rt},
                "result": rt_val_out,
            })
        elif raw_unit == "orbitPeriods":
            rt_val_out = raw_rt
            rt_unit_out = "orbit periods"
        elif raw_unit in ("seconds", "hours", "days"):
            rt_val_out = raw_rt
            rt_unit_out = raw_unit
        else:
            unsupported.append({
                "what": f"runTime.unit={raw_unit}",
                "why": "experiment.schema.json stopCondition allows only ElapsedSeconds, ElapsedHours, ElapsedDays, OrbitPeriods.",
            })

    # 5. Names and schema defaults
    exp_name = ext.get("experimentName")
    if not exp_name:
        exp_name = PROPOSED_DEFAULTS["experimentName"]
        assumptions.append(
            f"PROPOSED DEFAULT: Used experimentName = '{exp_name}' (not stated by user)."
        )

    sc_name = ext.get("spacecraftName")
    if not sc_name:
        sc_name = PROPOSED_DEFAULTS["spacecraftName"]
        assumptions.append(
            f"PROPOSED DEFAULT: Used spacecraftName = '{sc_name}' (not stated by user)."
        )

    integrator = integrator_in or SCHEMA_DEFAULTS["integrator"]
    if not integrator_in:
        assumptions.append(
            f"SCHEMA DEFAULT: Used integrator = '{integrator}'."
        )

    step_size = ext.get("stepSizeSecs")
    if step_size is None:
        step_size = SCHEMA_DEFAULTS["stepSizeSecs"]
        assumptions.append(
            f"SCHEMA DEFAULT: Used stepSizeSecs = {step_size} s."
        )

    # Determine final status
    if unsupported:
        status = "unsupported"
    elif missing:
        status = "missing"
    else:
        status = "ok"

    return {
        "status": status,
        "missing": missing,
        "unsupported": unsupported,
        "derived": derived,
        "assumptions": assumptions,
        "resolved": {
            "centralBody": body,
            "experimentName": exp_name,
            "spacecraftName": sc_name,
            "dryMassKg": dry_mass_kg,
            "semiMajorAxisKm": sma_km,
            "periapsisAltitudeKm": peri_alt_km,
            "circularAltitudeKm": circ_alt_km,
            "isCircular": is_circular,
            "eccentricity": ecc_val,
            "inclinationDeg": resolved_angles["inclination"],
            "raanDeg": resolved_angles["raan"],
            "argumentOfPeriapsisDeg": resolved_angles["argumentOfPeriapsis"],
            "trueAnomalyDeg": resolved_angles["trueAnomaly"],
            "runTimeValue": rt_val_out,
            "runTimeUnit": rt_unit_out,
            "integrator": integrator,
            "stepSizeSecs": step_size,
            "forceModel": fm,
            "maneuver": man,
            "orbitSize": orbit_size,
            "hasCustomForceOrStep": bool(fm) or (ext.get("integrator") is not None) or (ext.get("stepSizeSecs") is not None),
        },
    }


# ============================================================================
# 6. PROMPT BUILDER (Verbatim Training Templates)
# ============================================================================
def build_prompt(
    extraction_payload: dict[str, Any],
    template_style: str = "template_a",
) -> dict[str, Any]:
    """Builds the standardized interpreter prompt from the extracted payload.

    Args:
        extraction_payload: Output dict from the Front-Step Extractor LLM.
        template_style:
            - "template_a": Verbatim "I'd like an experiment call the run..."
              form (from V9/V9C rows).
            - "train_v9b": Verbatim BasicTrain002 / MultiTrain003 /
              CartesianTrain006 / ManeuverTrain004 forms from
              orbitlab_v9b_tinker.jsonl.

    Returns:
        {"status", "prompt", "derived", "assumptions", "missing", "unsupported"}
    """
    checked = validate_and_apply_defaults(extraction_payload)
    status = checked["status"]
    if status != "ok":
        return {
            "status": status,
            "prompt": None,
            "derived": checked["derived"],
            "assumptions": checked["assumptions"],
            "missing": checked["missing"],
            "unsupported": checked["unsupported"],
        }

    res = checked["resolved"]
    body = res["centralBody"]
    exp_name = res["experimentName"]
    sc_name = res["spacecraftName"]
    dry_mass = fmt_num(res["dryMassKg"])
    sma = fmt_num(res["semiMajorAxisKm"]) if res["semiMajorAxisKm"] is not None else ""
    ecc = fmt_num(res["eccentricity"], 6) if res["eccentricity"] is not None else "0"
    inc = fmt_num(res["inclinationDeg"])
    raan = fmt_num(res["raanDeg"])
    aop = fmt_num(res["argumentOfPeriapsisDeg"])
    ta = fmt_num(res["trueAnomalyDeg"])
    rt_val = fmt_num(res["runTimeValue"])
    rt_unit = res["runTimeUnit"]
    integrator = res["integrator"]
    step = fmt_num(res["stepSizeSecs"])
    purpose = PROPOSED_DEFAULTS["purpose"]
    orbit_size = res["orbitSize"]
    fm = res["forceModel"]
    man = res["maneuver"]

    # ------------------------------------------------------------------------
    # Cartesian case (copied word-for-word from CartesianTrain006)
    # ------------------------------------------------------------------------
    if isinstance(orbit_size, dict) and orbit_size.get("kind") == "cartesian":
        coord_sys = BODY_COORD_SYSTEM[body]
        x = fmt_num(orbit_size["xKm"], 8)
        y = fmt_num(orbit_size["yKm"], 8)
        z = fmt_num(orbit_size["zKm"], 8)
        vx = fmt_num(orbit_size["vxKmS"], 8)
        vy = fmt_num(orbit_size["vyKmS"], 8)
        vz = fmt_num(orbit_size["vzKmS"], 8)
        prompt = (
            f"Make an OrbitLab experiment for Cartesian case {exp_name} for {sc_name}, "
            f"dry mass {dry_mass} kg. In {coord_sys} use position [{x}, {y}, {z}] km "
            f"and velocity [{vx}, {vy}, {vz}] km/s. Propagate {rt_val} {rt_unit} "
            f"with {integrator} and a {step} second step. Use {body} as the central body. "
            f"Record the purpose as: {purpose}"
        )
        return {
            "status": "ok",
            "prompt": prompt,
            "derived": checked["derived"],
            "assumptions": checked["assumptions"],
            "missing": checked["missing"],
            "unsupported": checked["unsupported"],
        }

    # ------------------------------------------------------------------------
    # STYLE 1: Template A ("I'd like an experiment call the run ...")
    # ------------------------------------------------------------------------
    if template_style == "template_a":
        body_phrase = "the Moon" if body == "Moon" else body
        if body == "Sun" and isinstance(orbit_size, dict) and orbit_size.get("kind") == "radiusFromCenterAu":
            # Heliocentric "x AU from the centre" for the Sun (not an altitude).
            orbit_clause = (
                f"with SMA {fmt_num(orbit_size['value'])} AU from the centre "
                f"(= {sma} km), eccentricity {ecc}"
            )
        elif res["isCircular"] and res["circularAltitudeKm"] is not None:
            alt_str = fmt_num(res["circularAltitudeKm"])
            orbit_clause = f"a circular orbit at an altitude of {alt_str} km"
        elif res["periapsisAltitudeKm"] is not None:
            alt_str = fmt_num(res["periapsisAltitudeKm"])
            ecc_4 = f"{float(res['eccentricity']):.4f}"
            orbit_clause = f"a periapsis altitude of {alt_str} km, eccentricity {ecc_4}"
        else:
            orbit_clause = f"with SMA {sma} km, eccentricity {ecc}"

        # Tail clause selection (maneuver vs drag vs custom force vs default)
        if isinstance(man, dict):
            if man["type"] == "ImpulsiveBurn":
                dv = man["deltaV"]
                dv_unit = man.get("deltaVUnit") or "km/s"
                if dv_unit == "m/s":
                    dv_kms = [round(v / 1000.0, 6) for v in dv]
                    checked["derived"].append({
                        "quantity": "delta_v_km_s",
                        "formula": "km/s = (m/s) / 1000",
                        "inputs": {"m/s": dv},
                        "result": dv_kms,
                    })
                else:
                    dv_kms = dv
                dv_str = f"[{dv_kms[0]:.4f}, {dv_kms[1]:.4f}, {dv_kms[2]:.4f}]"
                trig = man["triggerCondition"]
                if trig == "AtPeriapsis":
                    trig_phrase = "when the spacecraft reaches periapsis"
                elif trig == "AtApoapsis":
                    trig_phrase = "when the spacecraft reaches apoapsis"
                else:
                    el_s = fmt_num(man["elapsedSecs"])
                    trig_phrase = f"{el_s} seconds into the run"
                tail_clause = (
                    f"apply a single impulsive burn {trig_phrase} in the local VNB frame "
                    f"with delta-v {dv_str} km/s; otherwise use default force settings."
                )
            else:
                # TargetedHohmannTransfer falls back to ManeuverTrain021 phrasing
                return build_prompt(extraction_payload, template_style="train_v9b")
        elif fm.get("atmosphericDrag", {}).get("enabled") is True:
            model = fm["atmosphericDrag"].get("model", SCHEMA_DEFAULTS["atmosphericDragModel"])
            cd = fmt_num(fm.get("coefficientOfDrag", SCHEMA_DEFAULTS["coefficientOfDrag"]))
            area = fmt_num(fm.get("dragAreaM2", SCHEMA_DEFAULTS["dragAreaM2"]))
            tail_clause = (
                f"turn on drag with the {model} atmosphere profile with drag coefficient "
                f"{cd} and {area} m^2 of drag area; also disable solar radiation pressure."
            )
        elif fm:
            deg = fm.get("gravityDegree", SCHEMA_DEFAULTS["gravityDegree"])
            order = fm.get("gravityOrder", SCHEMA_DEFAULTS["gravityOrder"])
            pms = ", ".join(fm.get("pointMasses", SCHEMA_DEFAULTS["pointMasses"]))
            srp_verb = (
                "enable"
                if fm.get("solarRadiationPressure", SCHEMA_DEFAULTS["solarRadiationPressure"])
                else "disable"
            )
            tail_clause = (
                f"use a degree-{deg} and order-{order} gravity field with point masses "
                f"{pms} and {srp_verb} solar radiation pressure."
            )
        else:
            tail_clause = "use the model's default force settings; I'm not asking for extra options."

        prompt = (
            f'I\'d like an experiment call the run "{exp_name}" with spacecraft "{sc_name}"; '
            f"use {dry_mass} kg for the dry mass; around {body_phrase} {orbit_clause}, "
            f"inclination {inc} degrees, RAAN {raan} degrees, argument of periapsis {aop} degrees, "
            f"true anomaly {ta} degrees; propagate for {rt_val} {rt_unit}; "
            f"integrate with {integrator}; {tail_clause}"
        )
        return {
            "status": "ok",
            "prompt": prompt,
            "derived": checked["derived"],
            "assumptions": checked["assumptions"],
            "missing": checked["missing"],
            "unsupported": checked["unsupported"],
        }

    # ------------------------------------------------------------------------
    # STYLE 2: Verbatim orbitlab_v9b_tinker.jsonl Templates
    # ------------------------------------------------------------------------
    if isinstance(man, dict):
        m_id = man.get("id")
        if not m_id:
            m_id = (
                PROPOSED_DEFAULTS["maneuverIdImpulsive"]
                if man["type"] == "ImpulsiveBurn"
                else PROPOSED_DEFAULTS["maneuverIdHohmann"]
            )
            checked["assumptions"].append(
                f"PROPOSED DEFAULT: Used maneuver.id = '{m_id}' (not stated by user)."
            )
        trig = man["triggerCondition"]
        if man["type"] == "ImpulsiveBurn":
            dv = man["deltaV"]
            dv_unit = man.get("deltaVUnit") or "m/s"
            if dv_unit == "km/s":
                dv_ms = [round(v * 1000.0, 3) for v in dv]
            else:
                dv_ms = dv
            dv_str = f"[{fmt_num(dv_ms[0])}, {fmt_num(dv_ms[1])}, {fmt_num(dv_ms[2])}]"
            if trig == "AtPeriapsis":
                man_clause = f"apply burn {m_id} at periapsis with LocalVNB delta-v {dv_str} m/s"
            elif trig == "AtApoapsis":
                man_clause = f"apply burn {m_id} at apoapsis with LocalVNB delta-v {dv_str} m/s"
            else:
                el_s = fmt_num(man["elapsedSecs"])
                man_clause = f"apply burn {m_id} at {el_s} elapsed seconds with LocalVNB delta-v {dv_str} m/s"
        else:
            loc = "periapsis" if trig == "AtPeriapsis" else "apoapsis"
            t_rad = fmt_num(man["targetOrbitRadiusKm"])
            man_clause = f"execute targeted Hohmann maneuver {m_id} at {loc} toward a circular radius of {t_rad} km"

        # Verbatim from ManeuverTrain004 / ManeuverTrain021
        prompt = (
            f"Configure a run for maneuver experiment {exp_name} for {sc_name}, "
            f"dry mass {dry_mass} kg, initially at SMA {sma} km, eccentricity {ecc}, "
            f"inclination {inc} degrees, RAAN {raan} degrees, argument of periapsis {aop} degrees, "
            f"and true anomaly {ta} degrees; {man_clause}; then propagate for {rt_val} {rt_unit}. "
            f"My goal is to compare this case with later lab runs. Use {body} as the central body. "
            f"Record the purpose as: {purpose}"
        )
    elif res["hasCustomForceOrStep"]:
        cd = fmt_num(fm.get("coefficientOfDrag", SCHEMA_DEFAULTS["coefficientOfDrag"]))
        drag_area = fmt_num(fm.get("dragAreaM2", SCHEMA_DEFAULTS["dragAreaM2"]))
        cr = fmt_num(fm.get("coefficientOfReflectivity", SCHEMA_DEFAULTS["coefficientOfReflectivity"]))
        srp_area = fmt_num(fm.get("srpAreaM2", SCHEMA_DEFAULTS["srpAreaM2"]))
        deg = fm.get("gravityDegree", SCHEMA_DEFAULTS["gravityDegree"])
        order = fm.get("gravityOrder", SCHEMA_DEFAULTS["gravityOrder"])
        pms = ", ".join(fm.get("pointMasses", SCHEMA_DEFAULTS["pointMasses"]))
        drag_model = fm.get("atmosphericDrag", {}).get("model", SCHEMA_DEFAULTS["atmosphericDragModel"])
        srp_on = "on" if fm.get("solarRadiationPressure", SCHEMA_DEFAULTS["solarRadiationPressure"]) else "off"

        # Verbatim from MultiTrain003
        prompt = (
            f"Put together multi-parameter case {exp_name} for {sc_name}: "
            f"dry mass {dry_mass} kg, Cd {cd}, drag area {drag_area} m², Cr {cr}, SRP area {srp_area} m²; "
            f"initial SMA {sma} km, eccentricity {ecc}, inclination {inc} degrees, RAAN {raan} degrees, "
            f"argument of periapsis {aop} degrees, and true anomaly {ta} degrees. "
            f"Use {deg}x{order} gravity, {pms} point masses, {drag_model} drag, SRP {srp_on}, "
            f"{integrator}, a {step} second step, and propagate for {rt_val} {rt_unit}. "
            f"My goal is to compare this case with later lab runs. Use {body} as the central body. "
            f"Record the purpose as: {purpose}"
        )
    else:
        # Verbatim from BasicTrain002
        prompt = (
            f"For my orbital mechanics lab, create experiment {exp_name} using {sc_name}, "
            f"dry mass {dry_mass} kg"
        )
        if body == "Sun" and isinstance(orbit_size, dict) and orbit_size.get("kind") == "radiusFromCenterAu":
            # "x AU from the centre" (heliocentric) for the Sun.
            prompt += (
                f", with SMA {fmt_num(orbit_size['value'] * AU_KM)} km "
                f"(= {fmt_num(orbit_size['value'])} AU from the centre), eccentricity {ecc}"
            )
        else:
            prompt += f", with SMA {sma} km, eccentricity {ecc}"
        prompt += (
            f", inclination {inc} degrees, RAAN {raan} degrees, argument of periapsis {aop} degrees, "
            f"and true anomaly {ta} degrees; propagate for {rt_val} {rt_unit}. "
            f"My goal is to compare this case with later lab runs. Use {body} as the central body. "
            f"Record the purpose as: {purpose}"
        )

    return {
        "status": "ok",
        "prompt": prompt,
        "derived": checked["derived"],
        "assumptions": checked["assumptions"],
        "missing": checked["missing"],
        "unsupported": checked["unsupported"],
    }