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

# Minimum allowable periapsis altitude above Earth surface in kilometers
# (Karman line / dense thermosphere entry limit)
MIN_PERIAPSIS_ALTITUDE_KM: float = 100.0

# Minimum allowable periapsis radius from Earth center (Earth radius + 100 km)
MIN_PERIAPSIS_RADIUS_KM: float = EARTH_RADIUS_KM + MIN_PERIAPSIS_ALTITUDE_KM  # 6478.1363 km

# Maximum eccentricity for bound closed orbits
MAX_BOUND_ECCENTRICITY: float = 0.999

# Speed of light in km/s (for reference)
SPEED_OF_LIGHT_KM_S: float = 299792.458
