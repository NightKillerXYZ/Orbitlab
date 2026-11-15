# Realistic cases results

Run: 2026-11-15 03:56 UTC | mode label: demo | server mode: demo | timeout per case: 400.0s
Base URL host recorded only (no keys, tokens or headers anywhere).

| id | prompt | expected | actual | stage | code | explSrc | seconds | a | e | duration | verdict |
|----|--------|----------|--------|-------|------|---------|---------|---|---|----------|---------|
| 1 | 500 kg satellite around Earth, circular orbit at 400 km altitude, 1 day | success | success | n/a | n/a | fallback | 2.1 | 6778.136 | 0.0 | 1.0 ElapsedDays | PASS |
| 2 | 260 kg satellite around Earth at 550 km altitude, inclination 53 degrees, 2 days | success | success | n/a | n/a | fallback | 2.1 | 6928.136 | 0.0 | 2.0 ElapsedDays | PASS |
| 3 | 500 kg satellite around the Moon, 100 km altitude, 6 hours | success | success | n/a | n/a | fallback | 2.1 | 1837.4 | 0.0 | 6.0 ElapsedHours | PASS |
| 4 | 800 kg satellite around Mars, periapsis altitude 300 km, eccentricity 0.2, 2 days | success | success | n/a | n/a | fallback | 2.1 | 4611.875 | 0.2 | 2.0 ElapsedDays | PASS |
| 5 | Spacecraft around Venus, semi-major axis 9000 km, 5 orbits | success | failed | extract | needs_clarification | n/a | 0.0 | n/a | n/a | n/a | FAIL |
| 6 | 500 kg satellite around Earth in a 7000 km circular orbit, Hohmann transfer to 9000 km at periapsis, 2 days | success | success | n/a | n/a | fallback | 2.1 | 7000.0 | 0.0 | 2.0 ElapsedDays | PASS |
| 7 | 500 kg satellite around Earth, 500 km altitude, burn at apoapsis to 800 km, 1 day | success | failed | validate | validation_failed | n/a | 0.0 | n/a | n/a | n/a | FAIL |
| 8 | 400 kg satellite around Mercury, circular 300 km altitude, 2 days | success | success | n/a | n/a | fallback | 2.1 | 2740.53 | 0.0 | 2.0 ElapsedDays | PASS |
| 9 | Earth, 90 minutes | needs_clarification | failed | extract | needs_clarification | n/a | 0.0 | n/a | n/a | n/a | PASS |
| 10 | 400 km circular | needs_clarification | failed | extract | needs_clarification | n/a | 0.0 | n/a | n/a | n/a | PASS |
| 11 | 500 kg satellite around Earth, periapsis altitude 50 km, 1 day | failed_at:validate | failed | validate | validation_failed | n/a | 0.0 | n/a | n/a | n/a | PASS |
| 12 | 500 kg satellite around Earth, circular 400 km, 400 days | info | failed | extract | needs_clarification | n/a | 0.0 | n/a | n/a | n/a | INFO |
| 13 | 500 kg satellite around Earth, circular 400 km, 2 days, sun-synchronous | info | failed | extract | needs_clarification | n/a | 0.0 | n/a | n/a | n/a | INFO |
| 14 | Spacecraft around Jupiter, 80000 km altitude circular, 3 days | info | failed | extract | needs_clarification | n/a | 0.0 | n/a | n/a | n/a | INFO |

## Observations (generated)

- cases: 14 total, 11 non-info, 9 passed; failed ids: [5, 7]
- slowest case: 1 (2.1 s)
- automatic (fallback) explanations on cases: 1, 2, 3, 4, 6, 8

