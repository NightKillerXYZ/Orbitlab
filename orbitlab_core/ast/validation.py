"""Astrodynamic Sanity and Physical Boundary Validator for OrbitLab[cite: 7].

Enforces orbital mechanics constraints:
- Atmospheric boundary and impact prevention (periapsis altitude >= 100 km)[cite: 7].
- Orbit eccentricity bounds (0 <= e < 1 for bound missions)[cite: 7].
- Cartesian state physical sanity (energy, angular momentum, derived periapsis)[cite: 7].
- Maneuver delta-V feasibility[cite: 7].
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple  # noqa: UP035

from orbitlab_core.ast.models import (
    CartesianElements,
    KeplerianElements,
    OrbitLabExperiment,
)
from orbitlab_core.constants import (
    EARTH_MU_KM3_S2,
    EARTH_RADIUS_KM,
    MARS_MU_KM3_S2,
    MIN_PERIAPSIS_ALTITUDE_KM,
    MIN_PERIAPSIS_RADIUS_KM,
    MOON_MU_KM3_S2,
)


@dataclass
class AstrodynamicProperties:
    """Calculated orbital characteristics for verification and reporting[cite: 7]."""
    semi_major_axis_km: float
    eccentricity: float
    periapsis_radius_km: float
    apoapsis_radius_km: float
    periapsis_altitude_km: float
    apoapsis_altitude_km: float
    orbital_period_secs: float
    specific_energy_km2_s2: float
    is_bound: bool


@dataclass
class ValidationResult:
    """Result of astrodynamic and physical validation[cite: 7]."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)


def get_body_constants(central_body: str) -> Tuple[float, float]:
    """Return (radius_km, mu_km3_s2) for the given central body[cite: 7]."""
    if central_body.lower() == "moon":
        return 1737.4, MOON_MU_KM3_S2
    elif central_body.lower() == "mars":
        return 3389.5, MARS_MU_KM3_S2
    else:
        # Default Earth
        return EARTH_RADIUS_KM, EARTH_MU_KM3_S2


def compute_orbital_properties_from_keplerian(
    elements: KeplerianElements,
    radius_body_km: float,
    mu_km3_s2: float
) -> AstrodynamicProperties:
    """Compute physical orbital properties from Keplerian elements[cite: 7]."""
    a = elements.semiMajorAxisKm
    e = elements.eccentricity
    rp = a * (1.0 - e)
    ra = a * (1.0 + e)
    alt_p = rp - radius_body_km
    alt_a = ra - radius_body_km
    energy = -mu_km3_s2 / (2.0 * a) if a > 0 else 0.0
    period = 2.0 * math.pi * math.sqrt((a ** 3) / mu_km3_s2) if a > 0 else 0.0

    return AstrodynamicProperties(
        semi_major_axis_km=a,
        eccentricity=e,
        periapsis_radius_km=rp,
        apoapsis_radius_km=ra,
        periapsis_altitude_km=alt_p,
        apoapsis_altitude_km=alt_a,
        orbital_period_secs=period,
        specific_energy_km2_s2=energy,
        is_bound=(0.0 <= e < 1.0),
    )


def compute_orbital_properties_from_cartesian(
    elements: CartesianElements,
    radius_body_km: float,
    mu_km3_s2: float
) -> AstrodynamicProperties:
    """Compute physical orbital properties from Cartesian state vector[cite: 7]."""
    r_vec = (elements.xKm, elements.yKm, elements.zKm)
    v_vec = (elements.vxKmS, elements.vyKmS, elements.vzKmS)

    r = math.sqrt(r_vec[0]**2 + r_vec[1]**2 + r_vec[2]**2)
    v2 = v_vec[0]**2 + v_vec[1]**2 + v_vec[2]**2
    v = math.sqrt(v2)

    # Specific orbital energy epsilon = v^2/2 - mu/r
    energy = (v2 / 2.0) - (mu_km3_s2 / r)

    # Angular momentum vector h = r x v
    hx = r_vec[1] * v_vec[2] - r_vec[2] * v_vec[1]
    hy = r_vec[2] * v_vec[0] - r_vec[0] * v_vec[2]
    hz = r_vec[0] * v_vec[1] - r_vec[1] * v_vec[0]
    h2 = hx**2 + hy**2 + hz**2
    h = math.sqrt(h2)

    # Eccentricity vector e_vec = (v x h)/mu - r_vec/r
    # v x h:
    vh_x = v_vec[1] * hz - v_vec[2] * hy
    vh_y = v_vec[2] * hx - v_vec[0] * hz
    vh_z = v_vec[0] * hy - v_vec[1] * hx

    ex = (vh_x / mu_km3_s2) - (r_vec[0] / r)
    ey = (vh_y / mu_km3_s2) - (r_vec[1] / r)
    ez = (vh_z / mu_km3_s2) - (r_vec[2] / r)
    e = math.sqrt(ex**2 + ey**2 + ez**2)

    if abs(energy) > 1e-12:
        a = -mu_km3_s2 / (2.0 * energy)
    else:
        a = float("inf")

    p = h2 / mu_km3_s2

    if e < 1.0:
        rp = a * (1.0 - e)
        ra = a * (1.0 + e)
        period = 2.0 * math.pi * math.sqrt((a ** 3) / mu_km3_s2) if a > 0 else 0.0
        is_bound = True
    else:
        rp = p / (1.0 + e)
        ra = float("inf")
        period = float("inf")
        is_bound = False

    alt_p = rp - radius_body_km
    alt_a = ra - radius_body_km if is_bound else float("inf")

    return AstrodynamicProperties(
        semi_major_axis_km=a,
        eccentricity=e,
        periapsis_radius_km=rp,
        apoapsis_radius_km=ra,
        periapsis_altitude_km=alt_p,
        apoapsis_altitude_km=alt_a,
        orbital_period_secs=period,
        specific_energy_km2_s2=energy,
        is_bound=is_bound,
    )


class AstrodynamicValidator:
    """Validates OrbitLabExperiment AST against physical boundaries[cite: 7]."""

    @classmethod
    def validate(cls, experiment: OrbitLabExperiment) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        props_dict: Dict[str, Any] = {}

        radius_body, mu_body = get_body_constants(experiment.centralBody)

        min_allowed_alt = (
            MIN_PERIAPSIS_ALTITUDE_KM
            if experiment.centralBody == "Earth"
            else 20.0
        )
        min_allowed_radius = radius_body + min_allowed_alt

        # 1. Orbit state check
        orbit = experiment.initialOrbit
        props: AstrodynamicProperties

        if orbit.type == "Keplerian":
            if not isinstance(orbit.elements, KeplerianElements):
                errors.append(
                    f"Expected KeplerianElements for orbit type 'Keplerian', "
                    f"got {type(orbit.elements)}"
                )
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    properties=props_dict,
                )

            # For a Keplerian state, the supplied semi-major axis and
            # eccentricity are already the authoritative orbital elements.
            a = orbit.elements.semiMajorAxisKm
            e = orbit.elements.eccentricity

            # Basic physical sanity checks.
            if a <= 0:
                errors.append(f"Semi-major axis must be positive, got {a:.6f} km.")
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    properties=props_dict,
                )

            if e < 0.0 or e >= 1.0:
                errors.append(
                    f"Keplerian eccentricity must satisfy 0 <= e < 1 "
                    f"for a bound elliptical orbit, got {e:.6f}."
                )
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    properties=props_dict,
                )

            # Classical Keplerian relationships.
            rp = a * (1.0 - e)
            ra = a * (1.0 + e)
            orbital_period = 2.0 * math.pi * math.sqrt((a ** 3) / mu_body)
            specific_energy = -mu_body / (2.0 * a)
            periapsis_altitude = rp - radius_body
            apoapsis_altitude = ra - radius_body

            props = AstrodynamicProperties(
                semi_major_axis_km=a,
                eccentricity=e,
                periapsis_radius_km=rp,
                apoapsis_radius_km=ra,
                periapsis_altitude_km=periapsis_altitude,
                apoapsis_altitude_km=apoapsis_altitude,
                orbital_period_secs=orbital_period,
                specific_energy_km2_s2=specific_energy,
                is_bound=True,
            )

        elif orbit.type == "Cartesian":
            if not isinstance(orbit.elements, CartesianElements):
                errors.append(
                    f"Expected CartesianElements for orbit type 'Cartesian', "
                    f"got {type(orbit.elements)}"
                )
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    properties=props_dict,
                )

            props = compute_orbital_properties_from_cartesian(
                orbit.elements,
                radius_body,
                mu_body,
            )

        else:
            errors.append(f"Unknown initial orbit type: '{orbit.type}'")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                properties=props_dict,
            )

        # Store calculated properties
        props_dict = {
            "semiMajorAxisKm": props.semi_major_axis_km,
            "eccentricity": props.eccentricity,
            "periapsisRadiusKm": props.periapsis_radius_km,
            "apoapsisRadiusKm": props.apoapsis_radius_km,
            "periapsisAltitudeKm": props.periapsis_altitude_km,
            "apoapsisAltitudeKm": props.apoapsis_altitude_km,
            "orbitalPeriodSecs": props.orbital_period_secs,
            "specificEnergyKm2S2": props.specific_energy_km2_s2,
            "isBound": props.is_bound,
        }

        # 2. Check periapsis altitude
        if props.periapsis_altitude_km < min_allowed_alt:
            errors.append(
                f"Trajectory violates safe periapsis threshold: "
                f"periapsis altitude is {props.periapsis_altitude_km:.2f} km "
                f"(radius: {props.periapsis_radius_km:.2f} km), "
                f"which is below the minimum safe altitude of "
                f"{min_allowed_alt:.1f} km for central body "
                f"'{experiment.centralBody}'."
            )

        # 3. Check bound orbit condition
        if not props.is_bound:
            warnings.append(
                f"Orbit has eccentricity e = {props.eccentricity:.4f} >= 1.0 "
                f"(unbound hyperbolic/parabolic trajectory)."
            )

        # 4. Check maneuvers
        for m in experiment.maneuvers:
            if m.type == "ImpulsiveBurn" and m.burnVector:
                dv_vec = m.burnVector.deltaVVectorKmS
                dv_mag = math.sqrt(sum(v ** 2 for v in dv_vec))
                props_dict[f"maneuver_{m.id}_deltaV_km_s"] = dv_mag

                if dv_mag > 15.0:
                    warnings.append(
                        f"Maneuver '{m.id}' has exceptionally large Delta-V ({dv_mag:.2f} km/s). "
                        f"Exceeds typical orbital chemical propulsion budgets."
                    )

                if dv_mag == 0.0:
                    warnings.append(f"Maneuver '{m.id}' has zero Delta-V.")

            elif m.type == "TargetedHohmannTransfer" and m.targetObjectives:
                tgt_r = m.targetObjectives.targetOrbitRadiusKm
                if tgt_r and tgt_r < min_allowed_radius:
                    errors.append(
                        f"TargetedHohmannTransfer '{m.id}' specifies target radius {tgt_r:.2f} km "
                        f"below safe radius {min_allowed_radius:.2f} km."
                    )

        # 5. Check propagation duration
        stop = experiment.propagation.stopCondition
        step = experiment.propagation.stepSizeSecs
        duration_secs = 0.0

        if stop.type == "ElapsedDays":
            duration_secs = stop.value * 86400.0
        elif stop.type == "ElapsedHours":
            duration_secs = stop.value * 3600.0
        elif stop.type == "ElapsedSeconds":
            duration_secs = stop.value
        elif stop.type == "OrbitPeriods" and props.orbital_period_secs > 0:
            duration_secs = stop.value * props.orbital_period_secs

        if duration_secs > 0 and step > duration_secs:
            warnings.append(
                f"Propagation step size ({step:.1f}s) is greater than total mission duration ({duration_secs:.1f}s)."
            )

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            properties=props_dict,
        )