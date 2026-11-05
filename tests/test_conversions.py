import pytest, math
from orbitlab_backend.frontstep.conversions import BODY_RADII_KM, sma_from_circular_altitude, sma_from_periapsis_altitude, convert_miles_to_km, convert_m_to_km, convert_au_to_km, radians_to_degrees, convert_duration_to_hours_or_days

def test_earth_400_circular():
    assert round(sma_from_circular_altitude(BODY_RADII_KM["Earth"], 400),3)==6778.1363 or sma_from_circular_altitude(BODY_RADII_KM["Earth"],400)==6778.1363
    assert sma_from_circular_altitude(BODY_RADII_KM["Earth"],400)==6778.1363

def test_mars_500_circular():
    assert sma_from_circular_altitude(BODY_RADII_KM["Mars"],500)==3889.5

def test_mercury_847_23_e01342():
    a=sma_from_periapsis_altitude(BODY_RADII_KM["Mercury"],847.23,0.1342)
    assert abs(a-3797.367) <0.001, f"got {a}"

def test_venus_612_84_e00842():
    a=sma_from_periapsis_altitude(BODY_RADII_KM["Venus"],612.84,0.0842)
    assert abs(a-7277.397) <0.001, f"got {a}"

def test_jupiter_circular():
    assert sma_from_circular_altitude(BODY_RADII_KM["Jupiter"],14832.5)==86324.5

def test_edge_e_ge_1_not_crash():
    # e>=1 should not crash, pass through faithfully
    a=sma_from_periapsis_altitude(BODY_RADII_KM["Earth"],200,1.0)
    assert math.isinf(a) or a!=None
    a2=sma_from_periapsis_altitude(BODY_RADII_KM["Earth"],200,1.5)
    assert a2!=None
    a3=sma_from_periapsis_altitude(BODY_RADII_KM["Earth"],-10,0.1)
    assert a3!=None

def test_miles_m_au_conversion():
    assert abs(convert_miles_to_km(100)-160.9344)<1e-6
    assert convert_m_to_km(1000)==1.0
    assert abs(convert_au_to_km(1)-149597870.691)<1e-3

def test_rad_to_deg():
    assert abs(radians_to_degrees(math.pi)-180)<1e-6
    assert abs(radians_to_degrees(math.pi/2)-90)<1e-6

def test_duration_conversions():
    # Passthrough: user unit preserved, no hours/days conversion.
    v,u,t=convert_duration_to_hours_or_days(7200, "seconds")
    assert v==7200 and u=="seconds" and t=="ElapsedSeconds"
    v,u,t=convert_duration_to_hours_or_days(3600, "seconds")
    assert v==3600 and u=="seconds" and t=="ElapsedSeconds"
    v,u,t=convert_duration_to_hours_or_days(30, "minutes")
    assert v==1800 and u=="seconds" and t=="ElapsedSeconds"
    v,u,t=convert_duration_to_hours_or_days(2, "hours")
    assert v==2 and u=="hours" and t=="ElapsedHours"
    v,u,t=convert_duration_to_hours_or_days(2, "days")
    assert v==2 and u=="days" and t=="ElapsedDays"
    v,u,t=convert_duration_to_hours_or_days(3, "orbits")
    assert v==3 and u=="orbital periods" and t=="OrbitPeriods"
    v,u,t=convert_duration_to_hours_or_days(3, "orbital periods")
    assert v==3 and u=="orbital periods" and t=="OrbitPeriods"

def test_orbit_count_passthrough_in_extractor():
    # "1 orbit" passes through unchanged as OrbitPeriods value 1 (helper orbits_to_hours kept but unused by pipeline).
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    ext = FrontStepExtractor()
    res = ext.deterministic_convert({"centralBody": "Earth", "dryMassKg": 500, "orbit": {"kind": "circularAltitudeKm", "value": 400, "unit": "km"}, "duration": {"value": 1, "unit": "orbits"}, "integrator": "RungeKutta89", "forces": None, "maneuvers": [], "cartesian": None}, "Earth 500 kg 400 km circular for 1 orbit")
    assert res.status == "ok"
    assert res.data["stopConditionType"] == "OrbitPeriods" and res.data["durationUnit"] == "orbital periods"
    assert res.data["durationValue"] == 1

