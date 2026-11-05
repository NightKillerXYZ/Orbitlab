"""Conservative GMAT wall-time estimate (pure Python, no GMAT).

Estimate = simulated_days * ORBITLAB_GMAT_SECS_PER_SIM_DAY * (60 / step_size_secs).

The constant is measurement-based (see config comment): the worst measured
case was Mars 687 days in 317.8 s, i.e. ~0.463 s per simulated day, rounded
up to 0.5 for conservatism. The reference step (60 s) is the model default;
larger steps need fewer GMAT steps, hence the scaling factor.

For OrbitPeriods the orbital period T = 2*pi*sqrt(a^3/mu) is used ONLY for
this estimate; the stop condition itself is always sent to GMAT unchanged
as OrbitPeriods.
"""

from __future__ import annotations

import math
from typing import Any, Dict

REFERENCE_STEP_SECS = 60.0


def _mu_for_body(central_body: str) -> float:
    from orbitlab_core.constants import BODIES as _BODIES

    try:
        return float(_BODIES[central_body]["muKm3S2"])
    except KeyError as e:
        raise ValueError(f"Unknown central body for estimate: {central_body}") from e


def _sma_of(experiment: Dict[str, Any]) -> float:
    try:
        els = experiment["initialOrbit"]["elements"]
        sma = els.get("semiMajorAxisKm")
        if sma is not None:
            return float(sma)
    except (KeyError, TypeError):
        pass
    raise ValueError("Estimate needs semiMajorAxisKm (Keplerian orbit)")


def stop_condition_to_seconds(experiment: Dict[str, Any]) -> float:
    """Convert the experiment's stop condition to plain seconds (estimate only)."""
    try:
        stop = experiment["propagation"]["stopCondition"]
        stop_type = stop["type"]
        value = float(stop["value"])
    except (KeyError, TypeError) as e:
        raise ValueError(f"Experiment has no usable stopCondition: {e}") from e
    if stop_type == "ElapsedSeconds":
        return value
    if stop_type == "ElapsedHours":
        return value * 3600.0
    if stop_type == "ElapsedDays":
        return value * 86400.0
    if stop_type == "OrbitPeriods":
        try:
            body = experiment.get("centralBody", "Earth")
        except AttributeError:
            body = "Earth"
        mu = _mu_for_body(body)
        a = _sma_of(experiment)
        period = 2.0 * math.pi * math.sqrt(a ** 3 / mu)
        return value * period
    raise ValueError(f"Unknown stop condition type for estimate: {stop_type}")


def estimate_run_seconds(experiment: Dict[str, Any], secs_per_sim_day: float) -> float:
    """Conservative wall-time estimate in seconds for a GMAT run."""
    total_secs = stop_condition_to_seconds(experiment)
    try:
        step = float(experiment["propagation"].get("stepSizeSecs", REFERENCE_STEP_SECS))
    except (KeyError, TypeError, AttributeError):
        step = REFERENCE_STEP_SECS
    if step <= 0:
        step = REFERENCE_STEP_SECS
    sim_days = total_secs / 86400.0
    return sim_days * float(secs_per_sim_day) * (REFERENCE_STEP_SECS / step)
