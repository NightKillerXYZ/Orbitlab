"""Validation policy table: rule id -> block/warn, defaulting to current behaviour."""
from __future__ import annotations

# Current hard-stop rules (is_valid=False) in AstrodynamicValidator.validate:
# - periapsis_altitude_below_min
# - soi_escape
# - drag_unsupported
# - hohmann_target_periapsis_below_min
# - hohmann_requires_bound_orbit
# - unknown_orbit_type
# - cartesian_zero_magnitude
# Plus Pydantic schema hard-stops:
# - stop_condition_limit_365_days (and 8760 hours, 31536000 secs, 365 periods)
# - eccentricity 0-0.99
# - inclination 0-180
# - sma >0
# - coordinateSystem mismatch
# - gravityOrder <= gravityDegree

VALIDATION_POLICY = {
    "periapsis_altitude": "block",
    "soi_escape": "block",
    "drag_unsupported": "block",
    "hohmann_target_periapsis": "block",
    "hohmann_requires_bound": "block",
    "unknown_orbit_type": "block",
    "cartesian_zero": "block",
    "stop_condition_limit": "block",
    "eccentricity_range": "block",
    "inclination_range": "block",
    "sma_positive": "block",
    "coordinate_system_mismatch": "block",
    "gravity_order_exceeds_degree": "block",
    # warnings that never stop pipeline:
    "large_delta_v": "warn",
    "zero_delta_v": "warn",
    "unbound_orbit": "warn",
    "point_mass_gravity_degree_ignored": "warn",
    "step_size_greater_than_duration": "warn",
    "other_warning": "warn",
}

def get_hard_stop_rules():
    return [k for k,v in VALIDATION_POLICY.items() if v=="block"]

def is_block(rule_id: str) -> bool:
    return VALIDATION_POLICY.get(rule_id, "block") == "block"
