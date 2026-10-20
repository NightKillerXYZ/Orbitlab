import math
from frontstep import (
    BODY_RADII_KM,
    build_prompt,
    rad_to_deg,
    radius_and_altitude_from_gravity_fraction,
    sma_and_ecc_from_apses_altitudes,
    sma_from_circular_altitude,
    sma_from_periapsis_altitude,
    tons_to_kg,
)

# 1. Mars circular 400 km -> a = 3789.5
a_mars_circ = sma_from_circular_altitude(BODY_RADII_KM["Mars"], 400.0)
assert round(a_mars_circ, 3) == 3789.5, f"Expected 3789.5, got {a_mars_circ}"

# 2. Moon periapsis altitude 100 km, e = 0.1 -> a = 2041.556 (3 decimals)
a_moon_ell = sma_from_periapsis_altitude(BODY_RADII_KM["Moon"], 100.0, 0.1)
assert round(a_moon_ell, 3) == 2041.556, f"Expected 2041.556, got {round(a_moon_ell, 3)}"

# 3. Earth gravity fraction 0.7 -> r = 7623.331, altitude = 1245.195
r_earth_gf, alt_earth_gf = radius_and_altitude_from_gravity_fraction(BODY_RADII_KM["Earth"], 0.7)
assert round(r_earth_gf, 3) == 7623.331, f"Expected 7623.331, got {round(r_earth_gf, 3)}"
assert round(alt_earth_gf, 3) == 1245.195, f"Expected 1245.195, got {round(alt_earth_gf, 3)}"

# 4. Earth apoapsis alt 800 km, periapsis alt 300 km -> a = 6928.136, e = 0.036085
a_apses, e_apses = sma_and_ecc_from_apses_altitudes(BODY_RADII_KM["Earth"], 800.0, 300.0)
assert round(a_apses, 3) == 6928.136, f"Expected 6928.136, got {round(a_apses, 3)}"
assert round(e_apses, 6) == 0.036085, f"Expected 0.036085, got {round(e_apses, 6)}"

# 5. Inclination pi/8 rad -> 22.5 deg
inc_deg = rad_to_deg("pi/8")
assert round(inc_deg, 3) == 22.5, f"Expected 22.5, got {inc_deg}"
assert round(rad_to_deg(math.pi / 8), 3) == 22.5

# 6. 200 t -> 200000 kg
assert tons_to_kg(200) == 200000.0

# 7. Earth periapsis altitude 50 km, e = 0.1 -> a = 7142.374 (passes through, no correction)
res_unphys_earth = build_prompt({
    "status": "ok",
    "extracted": {
        "centralBody": "Earth",
        "orbitSize": {"kind": "periapsisAltitudeKm", "value": 50},
        "eccentricity": 0.1,
        "runTime": {"value": 1, "unit": "hours"},
    },
    "missing": [],
    "unsupported": [],
    "quotedUserNumbers": ["50", "0.1", "1"],
})
assert res_unphys_earth["status"] == "ok"
assert res_unphys_earth["derived"][0]["result"] == 7142.374

# 8. Mars "400 km from the center" -> radiusFromCenterKm 400 -> a = 400 (no correction)
res_unphys_mars = build_prompt({
    "status": "ok",
    "extracted": {
        "centralBody": "Mars",
        "orbitSize": {"kind": "radiusFromCenterKm", "value": 400},
        "runTime": {"value": 2, "unit": "hours"},
    },
    "missing": [],
    "unsupported": [],
    "quotedUserNumbers": ["400", "2"],
})
assert res_unphys_mars["status"] == "ok"
assert res_unphys_mars["derived"][0]["result"] == 400.0

# 9. A missing run time -> status "missing"
res_missing_rt = build_prompt({
    "status": "missing",
    "extracted": {
        "centralBody": "Earth",
        "orbitSize": {"kind": "circularAltitudeKm", "value": 400},
        "runTime": None,
    },
    "missing": ["runTime"],
    "unsupported": [],
    "quotedUserNumbers": ["400"],
})
assert res_missing_rt["status"] == "missing"
assert "runTime" in res_missing_rt["missing"]
assert res_missing_rt["prompt"] is None

# 10. Sun is now supported (heliocentric "x AU from the centre").
res_sun = build_prompt({
    "status": "ok",
    "extracted": {
        "centralBody": "Sun",
        "orbitSize": {"kind": "radiusFromCenterAu", "value": 1.0},
        "runTime": {"value": 1, "unit": "hours"},
    },
    "missing": [],
    "unsupported": [],
    "quotedUserNumbers": ["1.0", "1"],
})
assert res_sun["status"] == "ok", f"Sun should be supported now, got {res_sun['status']}"
assert "AU from the centre" in res_sun["prompt"], f"AU phrase missing: {res_sun['prompt']}"
assert "149597870.691 km" in res_sun["prompt"], f"AU->km SMA missing: {res_sun['prompt']}"

# 11. A planet as the ORBITING OBJECT is still rejected (only a spacecraft may orbit).
res_orb = build_prompt({
    "status": "unsupported",
    "extracted": {
        "centralBody": "Sun",
        "orbitSize": {"kind": "radiusFromCenterAu", "value": 1.0},
        "orbitingObject": "Earth",
        "runTime": {"value": 1, "unit": "hours"},
    },
    "missing": [],
    "unsupported": [
        {"what": "orbitingObject=Earth", "why": "A planet as the orbiting object is unsupported."},
    ],
    "quotedUserNumbers": [],
})
assert res_orb["status"] == "unsupported", f"Expected unsupported, got {res_orb['status']}"
assert res_orb["prompt"] is None
assert any("orbitingObject=Earth" in u["what"] for u in res_orb["unsupported"])

print("ALL 11 ASSERTIONS PASSED.")

# ---- pi-fraction parsing (added after the 12pi/8 bug) ----
from frontstep import parse_pi_or_float
assert round(rad_to_deg("12pi/8"), 6) == 270.0
assert round(rad_to_deg("3pi/2"), 6) == 270.0
assert round(rad_to_deg("2pi/3"), 6) == 120.0
assert round(rad_to_deg("pi/8"), 6) == 22.5
assert round(rad_to_deg("1.5*pi"), 6) == 270.0
assert round(rad_to_deg("-pi/2"), 6) == -90.0
for bad in ("y**2+8", "__import__('os')", "x", "pi**2"):
    try:
        parse_pi_or_float(bad)
        raise SystemExit("should have rejected " + bad)
    except ValueError:
        pass

# prompt 1: gravity 65%, 12pi/8, 192 t, 2 days -> inclination 270 passes through
r = build_prompt({
    "status": "ok",
    "extracted": {
        "centralBody": "Earth",
        "orbitSize": {"kind": "gravityFraction", "value": 0.65},
        "inclination": {"value": "12pi/8", "unit": "rad"},
        "dryMass": {"value": 192, "unit": "t"},
        "runTime": {"value": 2, "unit": "days"},
    },
    "missing": [], "unsupported": [], "quotedUserNumbers": [],
})
assert r["status"] == "ok"
assert "inclination 270 degrees" in r["prompt"]
assert "192000 kg" in r["prompt"]
assert "1532.968" in r["prompt"]

print("PI PARSING TESTS PASSED.")
