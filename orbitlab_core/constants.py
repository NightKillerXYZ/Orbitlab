"""Physical and Astrodynamical Constants for OrbitLab."""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Central Body Data Table
#
# THE SINGLE SOURCE OF TRUTH for central-body physical constants, GMAT body
# mapping, per-body minimum periapsis altitude, drag allowance, and whether a
# body is modelled purely as a point mass (no gravity harmonic file).
#
# File: orbitlab_core/bodies.json (relative to this module)
# ---------------------------------------------------------------------------

_BODIES_JSON = Path(__file__).resolve().parent / "bodies.json"
_BODY_DATA: dict = json.loads(_BODIES_JSON.read_text(encoding="utf-8"))["bodies"]


def _load_body_config() -> dict:
    """Return the full per-body configuration table loaded from bodies.json."""
    config = {}
    for body, props in _BODY_DATA.items():
        config[body] = {
            "radiusKm": float(props["radiusKm"]),
            "muKm3S2": float(props["muKm3S2"]),
            "gmatName": props["gmatName"],
            "coordinateSystem": props["coordinateSystem"],
            "minPeriapsisAltKm": float(props["minPeriapsisAltKm"]),
            "pointMassOnly": bool(props["pointMassOnly"]),
            "potentialFile": props.get("potentialFile"),
            "allowsDrag": bool(props["allowsDrag"]),
            "soiRadiusKm": props.get("soiRadiusKm"),
        }
    return config


BODIES: dict = _load_body_config()

# Backwards-compatible individual constants (legacy values preserved).
# Earth equatorial radius in kilometers (WGS-84 / GMAT standard)
EARTH_RADIUS_KM: float = BODIES["Earth"]["radiusKm"]

# Earth gravitational parameter mu (G * M_Earth) in km^3 / s^2
EARTH_MU_KM3_S2: float = BODIES["Earth"]["muKm3S2"]

# Moon gravitational parameter in km^3 / s^2
MOON_MU_KM3_S2: float = BODIES["Moon"]["muKm3S2"]

# Mars gravitational parameter in km^3 / s^2
MARS_MU_KM3_S2: float = BODIES["Mars"]["muKm3S2"]

# Central Body Properties: {body -> (radius_km, mu_km3_s2, gmat_name, coord_system)}
CENTRAL_BODY_PROPERTIES = {
    body: (
        cfg["radiusKm"],
        cfg["muKm3S2"],
        cfg["gmatName"],
        cfg["coordinateSystem"],
    )
    for body, cfg in BODIES.items()
}

# Per-body minimum allowable periapsis altitude above the body surface (km).
MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY = {
    body: cfg["minPeriapsisAltKm"] for body, cfg in BODIES.items()
}

# Whether atmospheric drag may be modelled for the central body.
BODY_ALLOWS_DRAG = {body: cfg["allowsDrag"] for body, cfg in BODIES.items()}

# Point-mass-only bodies (no spherical-harmonic gravity field file in GMAT).
POINT_MASS_ONLY_BODIES = {
    body for body, cfg in BODIES.items() if cfg["pointMassOnly"]
}

# Default third-body point-mass perturbers applied when the user did NOT
# specify perturbers (front-step `forces` is None). The schema-level default
# (ForceModelConfig.pointMasses ["Luna", "Sun"]) is body-agnostic and is the
# source of Moon runs listing Luna and Mars runs missing Earth; these
# per-body defaults replace it at normalize time. Bodies not listed here keep
# whatever list they carry.
DEFAULT_POINT_MASSES_BY_BODY = {
    "Earth": ["Luna", "Sun"],
    "Moon": ["Earth", "Sun"],
    "Mars": ["Sun"],
}

# Optional GMAT gravity-field potential-file name per body.
BODY_POTENTIAL_FILES = {body: cfg["potentialFile"] for body, cfg in BODIES.items()}

# Sphere-of-influence radius (km) per body; None/0 means no enclosing parent
# (e.g. the Sun for heliocentric orbits) and imposes no SOI restriction.
BODY_SOI_RADIUS_KM = {
    body: cfg["soiRadiusKm"] for body, cfg in BODIES.items()
}

# ---------------------------------------------------------------------------
# Backwards-compatible default minima (legacy names preserved for frozen tools).
# ---------------------------------------------------------------------------

# Minimum allowable periapsis altitude above Earth surface in kilometers
# (Karman line / dense thermosphere entry limit)
MIN_PERIAPSIS_ALTITUDE_KM: float = MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY["Earth"]

# Minimum allowable periapsis altitude above the Moon or Mars surface.
MIN_OTHER_BODY_PERIAPSIS_ALTITUDE_KM: float = MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY["Moon"]

# Maximum eccentricity for bound closed orbits
MAX_BOUND_ECCENTRICITY: float = 0.999

# Speed of light in km/s (for reference)
SPEED_OF_LIGHT_KM_S: float = 299792.458

# Astronomical unit in kilometers (DE405: 1.495978706910000E+08)
AU_KM: float = 149597870.691
