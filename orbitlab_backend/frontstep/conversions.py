"""Deterministic conversions for OrbitLab front step."""
from __future__ import annotations
import math
from typing import Tuple
import math as _math

BODY_RADII_KM: dict[str, float] = {
    "Earth": 6378.1363,
    "Moon": 1737.4,
    "Mars": 3389.5,
    "Mercury": 2440.53,
    "Venus": 6051.8,
    "Jupiter": 71492,
    "Sun": 695700,
}

AU_KM = 149597870.691
MILES_TO_KM = 1.609344
M_TO_KM = 0.001

def sma_from_circular_altitude(body_radius_km: float, altitude_km: float) -> float:
    return body_radius_km + altitude_km

def sma_from_periapsis_altitude(body_radius_km: float, alt_periapsis_km: float, eccentricity: float) -> float:
    # Faithfully compute even if e>=1 or negative; do not block
    try:
        return (body_radius_km + alt_periapsis_km) / (1.0 - eccentricity)
    except ZeroDivisionError:
        return float('inf')

def sma_and_ecc_from_apses_altitudes(body_radius_km: float, apoapsis_alt_km: float, periapsis_alt_km: float) -> Tuple[float,float]:
    rp = body_radius_km + periapsis_alt_km
    ra = body_radius_km + apoapsis_alt_km
    a = (ra + rp) / 2.0
    # e = (ra - rp)/(ra+rp)
    if (ra+rp)==0:
        e=0
    else:
        e=(ra - rp)/(ra+rp)
    return a,e

def sma_from_apo_peri_radii(r_apo_km: float, r_peri_km: float) -> Tuple[float,float]:
    a=(r_apo_km+r_peri_km)/2.0
    e=(r_apo_km - r_peri_km)/(r_apo_km + r_peri_km) if (r_apo_km+r_peri_km)!=0 else 0
    return a,e

def convert_miles_to_km(miles: float) -> float:
    return miles * MILES_TO_KM
def convert_m_to_km(meters: float) -> float:
    return meters * M_TO_KM
def convert_au_to_km(au: float) -> float:
    return au * AU_KM
def radians_to_degrees(rad: float) -> float:
    return rad * 180.0 / math.pi

def convert_duration_to_hours_or_days(value: float, unit: str):
    """Pass the user stop-condition unit through unchanged. Seconds stay ElapsedSeconds, minutes become seconds (*60), hours stay ElapsedHours, days stay ElapsedDays, orbit counts stay OrbitPeriods. Canonical units: seconds|hours|days|orbital periods. Historic name kept for compatibility."""
    u = unit.strip().lower()
    u_norm = u.replace("_", " ").replace("-", " ").strip()
    u_compact = u_norm.replace(" ", "")
    if u_norm in ("s", "sec", "secs", "second", "seconds", "elapsedseconds", "elapsed seconds"):
        return (round(float(value), 6), "seconds", "ElapsedSeconds")
    elif u_norm in ("min", "mins", "minute", "minutes"):
        return (round(float(value) * 60.0, 6), "seconds", "ElapsedSeconds")
    elif u_norm in ("h", "hr", "hrs", "hour", "hours", "elapsedhours", "elapsed hours"):
        return (round(float(value), 6), "hours", "ElapsedHours")
    elif u_norm in ("d", "day", "days", "elapseddays", "elapsed days"):
        return (round(float(value), 6), "days", "ElapsedDays")
    elif u_compact in ("orbit", "orbits", "orbitperiod", "orbitperiods", "orbitalperiod", "orbitalperiods", "period", "periods", "orbitcount", "orbitcounts") or u_norm in ("orbital period", "orbital periods", "orbit period", "orbit periods"):
        return (round(float(value), 6), "orbital periods", "OrbitPeriods")
    else:
        raise ValueError(f"Unsupported duration unit: {unit}")

def fmt_sma(a_km: float) -> str:
    # Round SMA to 3 decimals when formatting
    return f"{round(a_km,3):.3f}".rstrip('0').rstrip('.') if False else f"{round(a_km,3):.3f}"

def format_sma(a_km: float) -> str:
    return f"{round(a_km,3):.3f}"

def _mu_for_body(body: str) -> float:
    """Reuse repo mu constants from orbitlab_core.constants.BODIES (single source of truth)."""
    try:
        from orbitlab_core.constants import BODIES as _BODIES
        return float(_BODIES[body]["muKm3S2"])
    except Exception as e:
        raise ValueError(f"Unknown central body for orbit conversion: {body}") from e

def orbits_to_hours(semi_major_axis_km: float, central_body: str, n_orbits: float):
    """Convert N orbits to hours via T = 2*pi*sqrt(a^3/mu). Returns (hours, 'hours', 'ElapsedHours')."""
    import math as _m
    a = float(semi_major_axis_km); n = float(n_orbits)
    if not (a > 0) or not (n > 0):
        raise ValueError("a and N must be positive for orbit conversion")
    mu = _mu_for_body(central_body)
    t_sec = 2.0 * _m.pi * _m.sqrt(a ** 3 / mu)
    return (round(n * t_sec / 3600.0, 6), "hours", "ElapsedHours")
