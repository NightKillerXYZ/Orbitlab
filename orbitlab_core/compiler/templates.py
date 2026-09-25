"""GMAT Script Templates and Procedural AST Helpers."""

from __future__ import annotations

import math
from typing import Tuple
from orbitlab_core.constants import EARTH_MU_KM3_S2, EARTH_RADIUS_KM


def normalize_gmat_path(path: str) -> str:
    """Normalize file paths for GMAT scripts by replacing Windows backslashes with forward slashes.

    GMAT script parser fails on raw Windows backslashes due to escape parsing.
    """
    return path.replace("\\", "/")


def compute_hohmann_delta_v(
    r1_km: float,
    r2_km: float,
    mu_km3_s2: float = EARTH_MU_KM3_S2
) -> Tuple[float, float]:
    """Compute impulsive Delta-V for a two-impulse Hohmann transfer between circular orbits.

    Returns:
        (dv1_km_s, dv2_km_s): Insertion burn at r1 and circularization burn at r2.
    """
    v1 = math.sqrt(mu_km3_s2 / r1_km)
    v_trans1 = math.sqrt(mu_km3_s2 * ((2.0 / r1_km) - (2.0 / (r1_km + r2_km))))
    dv1 = v_trans1 - v1

    v_trans2 = math.sqrt(mu_km3_s2 * ((2.0 / r2_km) - (2.0 / (r1_km + r2_km))))
    v2 = math.sqrt(mu_km3_s2 / r2_km)
    dv2 = v2 - v_trans2

    return dv1, dv2


def compute_keplerian_period_seconds(
    semi_major_axis_km: float,
    mu_km3_s2: float = EARTH_MU_KM3_S2
) -> float:
    """Compute two-body Keplerian orbital period in seconds."""
    if semi_major_axis_km <= 0:
        return 0.0
    return 2.0 * math.pi * math.sqrt((semi_major_axis_km ** 3) / mu_km3_s2)
