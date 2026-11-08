"""E2E: one valid scenario per central body through the real API + GMAT."""
import pytest

from tests.e2e.helpers import (
    NEEDS_GMAT, canned_for, client_for, extracted_for,
    run_text, sent_kepler,
)

CASES = [
    ("Earth", "EarthMJ2000Eq", 6778.136, 0.0, 28.5, 500, "ElapsedHours", 2, None),
    ("Moon", "LunaMJ2000Eq", 1937.4, 0.05, 30.0, 500, "ElapsedDays", 2,
     {"gravityDegree": 8, "gravityOrder": 8, "pointMasses": ["Earth", "Sun"],
      "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
      "solarRadiationPressure": False}),
    ("Mars", "MarsMJ2000Eq", 3889.5, 0.0, 25.0, 500, "ElapsedHours", 48, None),
    ("Mercury", "MercuryMJ2000Eq", 2640.53, 0.03, 10.0, 500, "ElapsedHours", 8, None),
    ("Venus", "VenusMJ2000Eq", 6351.8, 0.02, 20.0, 500, "ElapsedHours", 12, None),
    ("Jupiter", "JupiterMJ2000Eq", 90000.0, 0.1, 15.0, 500, "ElapsedHours", 24, None),
    ("Sun", "SunMJ2000Eq", 7000000.0, 0.0, 5.0, 500, "ElapsedHours", 48, None),
]


@NEEDS_GMAT
@pytest.mark.parametrize("body,coord,sma,ecc,inc,mass,stop_type,stop_val,forces", CASES)
def test_body_success(body, coord, sma, ecc, inc, mass, stop_type, stop_val, forces):
    name = "E2E" + body
    sent = sent_kepler(name, body, sma, ecc, inc, mass, stop_val,
                       {"ElapsedHours": "hours", "ElapsedDays": "days"}[stop_type],
                       stop_type)
    canned = canned_for(sent, coord, forces=forces)
    routes = [("CASE", canned)]
    extracted = {"CASE-" + body: extracted_for(sent)}
    client = client_for(routes, extracted)
    job = run_text(client, "CASE-" + body, timeout_s=300)
    assert job["status"] == "success", job.get("error")
    res = job["result"]
    assert res["experiment"]["centralBody"] == body
    assert isinstance(res.get("explanation"), str) and res["explanation"]
    assert res["trajectory"]["visualization_count"] >= 1
