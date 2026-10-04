"""GMAT Script Templates and Procedural AST Helpers."""

from __future__ import annotations

import math
from typing import Tuple
from orbitlab_core.constants import EARTH_MU_KM3_S2


def normalize_gmat_path(path: str) -> str:
    """Normalize file paths for GMAT scripts by replacing Windows backslashes with forward slashes.

    GMAT script parser fails on raw Windows backslashes due to escape parsing.
    """
    return path.replace("\\", "/")


def compute_hohmann_delta_v(
    r1_km: float,
    r2_km: float,
    mu_km3_s2: float = EARTH_MU_KM3_S2,
    initial_velocity_km_s: float | None = None,
    target_eccentricity: float = 0.0,
) -> Tuple[float, float]:
    """Compute tangential impulses for an apsis-to-apsis transfer.

    Returns:
        (dv1_km_s, dv2_km_s): Transfer insertion and target-orbit insertion burns.
    """
    if r1_km <= 0.0 or r2_km <= 0.0 or mu_km3_s2 <= 0.0:
        raise ValueError("Hohmann radii and gravitational parameter must be positive")
    if math.isclose(r1_km, r2_km):
        raise ValueError("Hohmann target apsis radius must differ from initial apsis radius")
    if not math.isfinite(target_eccentricity) or not 0.0 <= target_eccentricity < 1.0:
        raise ValueError("Target eccentricity must satisfy 0 <= e < 1")

    if initial_velocity_km_s is not None and (
        not math.isfinite(initial_velocity_km_s) or initial_velocity_km_s <= 0.0
    ):
        raise ValueError("Initial tangential speed must be finite and positive")

    v1 = (
        initial_velocity_km_s
        if initial_velocity_km_s is not None
        else math.sqrt(mu_km3_s2 / r1_km)
    )
    v_trans1 = math.sqrt(mu_km3_s2 * ((2.0 / r1_km) - (2.0 / (r1_km + r2_km))))
    dv1 = v_trans1 - v1

    v_trans2 = math.sqrt(mu_km3_s2 * ((2.0 / r2_km) - (2.0 / (r1_km + r2_km))))
    if r2_km >= r1_km:
        target_semi_major_axis = r2_km / (1.0 + target_eccentricity)
    else:
        target_semi_major_axis = r2_km / (1.0 - target_eccentricity)
    v2 = math.sqrt(mu_km3_s2 * (2.0 / r2_km - 1.0 / target_semi_major_axis))
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
