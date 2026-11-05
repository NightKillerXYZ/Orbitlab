"""E2E: Cartesian starts, burns, Hohmann, and all four stop types."""
import pytest

from tests.e2e.helpers import (
    NEEDS_GMAT, canned_for, client_for, extracted_cartesian_for,
    extracted_for, run_text, sent_cartesian, sent_kepler,
)


def _run(sent, canned, text, timeout_s=300):
    routes = [(sent["experimentName"], canned)]
    client = client_for(routes, {text: extracted_for(sent)} if sent.get("cartesian") is None else {text: extracted_cartesian_for(sent)})
    job = run_text(client, text, timeout_s=timeout_s)
    assert job["status"] == "success", job.get("error")
    res = job["result"]
    assert isinstance(res.get("explanation"), str) and res["explanation"]
    assert res["trajectory"]["visualization_count"] >= 1
    return res


@NEEDS_GMAT
def test_cartesian_start():
    sent = sent_cartesian("E2ECart", "Earth", [6778.136, 0, 0], [0, 7.6686, 0], 4, "hours", "ElapsedHours")
    canned = canned_for(sent, "EarthMJ2000Eq")
    res = _run(sent, canned, "CASE-CART")
    els = res["experiment"]["initialOrbit"]
    assert els["type"] == "Cartesian"


@NEEDS_GMAT
def test_impulsive_burn_at_periapsis():
    maneuvers = [{"type": "ImpulsiveBurn", "id": "M1", "trigger": "AtPeriapsis",
                  "apsis": "periapsis", "deltaV": [0.001, 0.0, 0.0]}]
    sent = sent_kepler("E2EBurnP", "Earth", 6878.136, 0.0, 0.0, 500, 3, "hours", "ElapsedHours", maneuvers=maneuvers)
    canned = canned_for(sent, "EarthMJ2000Eq")
    res = _run(sent, canned, "CASE-BURNP")
    assert res["experiment"]["maneuvers"][0]["trigger"]["condition"] == "AtPeriapsis"


@NEEDS_GMAT
def test_impulsive_burn_at_apoapsis():
    maneuvers = [{"type": "ImpulsiveBurn", "id": "M1", "trigger": "AtApoapsis",
                  "apsis": "apoapsis", "deltaV": [0.006, 0.009, 0.012]}]
    sent = sent_kepler("E2EBurnA", "Mars", 4189.5, 0.02, 0.0, 500, 6, "hours", "ElapsedHours", maneuvers=maneuvers)
    canned = canned_for(sent, "MarsMJ2000Eq")
    res = _run(sent, canned, "CASE-BURNA")
    assert res["experiment"]["maneuvers"][0]["trigger"]["condition"] == "AtApoapsis"


@NEEDS_GMAT
def test_elapsed_time_burn():
    maneuvers = [{"type": "ImpulsiveBurn", "id": "M1", "trigger": "ElapsedTimeSecs",
                  "elapsedSecs": 1440, "deltaV": [0.001, 0.004, 0.007]}]
    sent = sent_kepler("E2EBurnT", "Earth", 6878.136, 0.0, 0.0, 500, 3, "hours", "ElapsedHours", maneuvers=maneuvers)
    canned = canned_for(sent, "EarthMJ2000Eq")
    res = _run(sent, canned, "CASE-BURNT")
    assert res["experiment"]["maneuvers"][0]["trigger"]["condition"] == "ElapsedTimeSecs"


@NEEDS_GMAT
def test_hohmann_transfer():
    maneuvers = [{"type": "Hohmann", "id": "M1", "targetOrbitRadiusKm": 9000, "apsis": "periapsis"}]
    sent = sent_kepler("E2EHoh", "Mars", 3889.5, 0.0, 0.0, 500, 48, "hours", "ElapsedHours", maneuvers=maneuvers)
    canned = canned_for(sent, "MarsMJ2000Eq")
    res = _run(sent, canned, "CASE-HOH")
    assert res["experiment"]["maneuvers"][0]["type"] == "TargetedHohmannTransfer"


@NEEDS_GMAT
@pytest.mark.parametrize("stop_type,unit,value", [
    ("ElapsedSeconds", "seconds", 7200),
    ("ElapsedHours", "hours", 2),
    ("ElapsedDays", "days", 2),
    ("OrbitPeriods", "orbital periods", 3),
])
def test_stop_types(stop_type, unit, value):
    sent = sent_kepler("E2EStop", "Earth", 6878.136, 0.001, 0.0, 500, value, unit, stop_type)
    canned = canned_for(sent, "EarthMJ2000Eq")
    res = _run(sent, canned, "CASE-STOP")
    assert res["experiment"]["propagation"]["stopCondition"] == {"type": stop_type, "value": value}
