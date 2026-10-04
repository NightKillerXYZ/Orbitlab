"""Physical and Astrodynamical Constants for OrbitLab."""

# Central Body Constants
# Earth equatorial radius in kilometers (WGS-84 / GMAT standard)
EARTH_RADIUS_KM: float = 6378.1363

# Earth gravitational parameter mu (G * M_Earth) in km^3 / s^2
EARTH_MU_KM3_S2: float = 398600.4415

# Moon gravitational parameter in km^3 / s^2
MOON_MU_KM3_S2: float = 4902.800066

# Mars gravitational parameter in km^3 / s^2
MARS_MU_KM3_S2: float = 42828.375214

CENTRAL_BODY_PROPERTIES = {
    "Earth": (EARTH_RADIUS_KM, EARTH_MU_KM3_S2, "Earth", "EarthMJ2000Eq"),
    "Moon": (1737.4, MOON_MU_KM3_S2, "Luna", "LunaMJ2000Eq"),
    "Mars": (3389.5, MARS_MU_KM3_S2, "Mars", "MarsMJ2000Eq"),
}

# Minimum allowable periapsis altitude above Earth surface in kilometers
# (Karman line / dense thermosphere entry limit)
MIN_PERIAPSIS_ALTITUDE_KM: float = 100.0

# Minimum allowable periapsis altitude above the Moon or Mars surface.
MIN_OTHER_BODY_PERIAPSIS_ALTITUDE_KM: float = 20.0

# Maximum eccentricity for bound closed orbits
MAX_BOUND_ECCENTRICITY: float = 0.999

# Speed of light in km/s (for reference)
SPEED_OF_LIGHT_KM_S: float = 299792.458
