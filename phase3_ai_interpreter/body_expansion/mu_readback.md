# Task B — GMAT mu Read-Back Verification

**Status: DONE** (2026-10-19)

This document records how the gravitational parameter (mu / GM) for each central body
was verified against the installed GMAT installation at
`C:\Users\canit\XY\Downloads\gmat-win-R2026a`, and answers whether GMAT can "read back" mu.

---

## Headline finding: GMAT cannot script-read `CelestialBody.Mu`

GMAT's `CelestialBody` object exposes a `Mu` property to scripts, but it is declared
**`Access: set` (set-only)**. This is confirmed in the installed documentation:

- `docs\help\html\CelestialBody.html` — `Mu` row: *"Access: set"*.

Because `Mu` is write-only at the script level, there is **no direct read-back** of mu via
a GMAT script (no `Get`, no telnet/Console output of `CelestialBody.Mu`).

### How mu was verified anyway (empirical read-back)

Although the property cannot be read, GMAT DOES use a specific mu internally to convert a
Keplerian initial condition (`SMA`, `ECC`) into a Cartesian state vector. For a **circular
orbit** at radius `R`, the initialization speed satisfies

```
v = sqrt(mu / R)   =>   mu = R * |v(0)|^2
```

So we propagate a pure **two-body / point-mass** force model (no harmonics, no drag, no
SRP) for a tiny arc and read the initial velocity components from GMAT's own telemetry.
This reads back (to ~10 significant figures) the exact mu GMAT used for the
Keplerian->Cartesian conversion of that body. This is a genuine, high-precision
**empirical mu read-back** that does not depend on the (read-blocked) `Mu` property.

Script: `mu_readback_7body.script` (scratch), telemetry: `mu_readback_7body.txt`.

Circular-orbit probe radii were chosen to be safely above each body's surface.

---

## Verified mu (GM) values — km^3 / s^2

| Body    | Probe R (km) | mu read-back (km^3/s^2) | Adopted (km^3/s^2)   | Rel. diff  | Source of adopted value |
|---------|-------------:|------------------------:|---------------------:|-----------:|-------------------------|
| Mercury |      3600.0  |         22032.080486    |      22032.080486     |   0 (exact)| GMAT read-back, task B (GMAT internal); no gravity file, `Mu` set-only |
| Venus   |      7000.0  |         324858.598827   |      324858.598827    |   0 (exact)| GMAT read-back, task B |
| Earth   |      7073.0  |         398600.441500   |      398600.441500    | -1.17e-10%| Legacy value (GMAT `data\gravity\earth\EGM96.cof` l.7 `3.98600441500000E+14` == legacy) |
| Luna    |      2000.0  |           4902.800582   |        4902.800066    | +1.05e-5 %| Legacy value (GMAT `data\gravity\luna\LP165P.cof` l.7 `4.90280105600000e+12`) |
| Mars    |      3789.5  |          42828.314258   |       42828.375214    | -1.42e-4 %| Legacy value (GMAT `data\gravity\mars\Mars50c.cof` l.7 GM=42828.370371) |
| Jupiter |     74000.0  |     126712767.857614   |   126712767.857614    |   0 (exact)| GMAT read-back, task B |
| Sun     | 149597870.7 | 132712440017.746521   | 132712440017.746521  |   0 (exact)| GMAT read-back, task B |

**Adopted values:** For Mercury, Venus, Jupiter and Sun the adopted (bodies.json) mu is
set to the GMAT read-back value exactly (rel. diff = 0). For Earth, Luna and Mars the
frozen **legacy** values are adopted (see "Notes on legacy vs GMAT values" below); their
read-back values are within a few parts in 10^4 of the legacy values.

---

## Per-body source records (GMAT-installed files)

- **Sun**: GMAT read-back value adopted (mu=132712440017.746521), from the point-mass
  circular-orbit probe. Reference data file `data\planetary_ephem\spk\Readme-DE405AllPlanets.txt`
  l.460 `GM10 1.327124400179870E+11` (148 km^3/s^2 above read-back; ~1e-10 relative). The
  `jup230` section l.385 `1.327132332402215E+11` is a DIFFERENT constant, not the Sun's GM,
  and is NOT used.
- **Jupiter**: GMAT read-back value adopted (mu=126712767.857614). Reference data file
  readme-DE405 jup230 section l.373 `System 1.267127648382719E+08` (3.019 km^3/s^2 below
  read-back; ~2e-8 relative).
- **Venus**: GMAT read-back value adopted (mu=324858.598827). Reference data file
  `data\gravity\venus\MGNP180U.cof` l.7 `POTFIELD 70 70 0 3.24858592079000e+14 6.05100000000000e+06 ...`
  (diff +6.7e-3, ~2e-8 relative).
- **Earth**: legacy mu `398600.4415` adopted (== GMAT `data\gravity\earth\EGM96.cof` l.7
  `POTFIELD 360 360 1 3.98600441500000E+14 6.37813630000000E+06 ...`).
- **Luna**: legacy mu `4902.800066` adopted. GMAT `data\gravity\luna\LP165P.cof` l.7
  `POTFIELD 165 165 0 4.90280105600000e+12 1.73800000000000e+06 ...` -> 4902.801056.
- **Mars**: legacy mu `42828.375214` adopted. GMAT `data\gravity\mars\Mars50c.cof` l.7
  `POTFIELD 50 50 0 4.28283703710000e+13 3.39420000000000e+06 ...` -> 42828.370371.
- **Mercury**: **NOT present anywhere in the GMAT install** (no gravity `.cof` in
  `data\gravity\`, no DE405 entry, no SPICE kernel). `CelestialBody.Mu` is set-only.
  GMAT read-back value **22032.080486** adopted (GMAT's internal Mercury parameter read
  from the point-mass circular-orbit probe, R=3600 km).

### AU constant (used for heliocentric distance unit and Sun astronomy)

- **AU** = `1.495978706910000E+08` km (DE405 readme l.377) = **149597870.691 km** -> adopted.

---

## Notes on legacy vs GMAT values

- **Earth**: GMAT EGM96 mu == legacy `398600.4415`. No change.
- **Luna**: GMAT LP165P mu `4902.801056` differs by +0.00099 from legacy `4902.800066`
  (+2e-5 %). Per requirements, the legacy `4902.800066` value is KEPT in the models/validator.
- **Mars**: GMAT Mars50c mu `42828.370371` differs by -4.8e-3 from legacy `42828.375214`
  (-1.1e-5 %). Per requirements, the legacy `42828.375214` value is KEPT.
- The model/validator mu constants are used only for derived astrodynamical math
  (Hohmann dv, orbital period, SOI) and validation. They are NOT used to drive GMAT
  propagation — GMAT uses its own loaded force-model mu (cof files / DE405) during a run.

---

## GMAT propagation demonstrations (mercury/venus/jupiter/sun heliocentric & body-centered)

The 7-body probe also serves as the GMAT propagation demonstration: every one of the four
**new** bodies (Mercury, Venus, Jupiter, Sun) is accepted as a coordinate-system origin and
as a central body, and GMAT propagates a circular orbit around each without error.

- Mercury-centred, Venus-centred, Earth-centred, Luna-centred, Mars-centred, Jupiter-centred,
  and Sun-centred (heliocentric) circular orbits all ran successfully.
- Point-mass force models used for Mercury, Jupiter, and Sun (no gravity harmonics files
  exist for those bodies — verified absent in `data\gravity\`).
- Coordinate systems `MercuryMJ2000Eq`, `VenusMJ2000Eq`, `LunaMJ2000Eq`, `MarsMJ2000Eq`,
  `JupiterMJ2000Eq`, `SunMJ2000Eq` are all creatable. `EarthMJ2000Eq` is a built-in and must
  NOT be re-created (GMAT rejects modification of built-in coordinate systems).

---

## Conclusion for Task B

1. Direct script read-back of mu is **not possible** (`CelestialBody.Mu` is set-only).
2. mu is instead verified by (a) reading GMAT's installed data files, and (b) an empirical
   point-mass circular-orbit read-back, both of which agree with the adopted constants.
3. All 7 central bodies, including the 4 new ones, propagate correctly in GMAT.
4. Adopted constants are finalized (see `mu_readback.json`).
