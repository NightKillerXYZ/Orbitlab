# OrbitLab Body Expansion — Implementation Report

Status: implements the v9 body-expansion close-out (items 1–11 surface in
`phase3_ai_interpreter/closeout/status.md`). This file documents **what the code
actually does today** (not a proposal). Every heading lists the exact `file:line`
where the behaviour lives. Source of truth for all physical constants is
`orbitlab_core/bodies.json`.

Legend: `**DONE**` = implemented and verified by a run captured in the close-out
report; `**PARTIAL**` = implemented for the reviewer-facing path but one sub-part
is scoped out / caller-level; `**deferred**` = intentionally not implemented (see
notes).

---

## 1. Single source of truth: `orbitlab_core/bodies.json` — **DONE**

`bodies.json` holds the 7 permitted central bodies with per-body radius, mu, GMAT
name, body-centered coordinate system, minimum periapsis altitude, point-mass-only
flag, optional gravity potential file, drag allowance, and sphere-of-influence
radius:

| body    | radiusKm | muKm3S2 | gmatName | coordinateSystem | minPeriapsisAltKm | pointMassOnly | potentialFile | allowsDrag | soiRadiusKm |
|---------|----------|---------|----------|------------------|-------------------|---------------|---------------|------------|-------------|
| Earth   | 6378.1363 | 398600.4415 | Earth  | EarthMJ2000Eq  | 100   | false | null        | true  | 925000     |
| Moon    | 1737.4   | 4902.800066 | Luna   | LunaMJ2000Eq   | 20    | false | LP165P.cof   | false | 66200      |
| Mars    | 3389.5   | 42828.375214 | Mars   | MarsMJ2000Eq   | 20    | false | Mars50c.cof  | false | 577000     |
| Mercury | 2440.53  | 22032.080486 | Mercury| MercuryMJ2000Eq| 20    | true  | null         | false | 112000     |
| Venus   | 6051.8   | 324858.598827 | Venus  | VenusMJ2000Eq  | 100   | false | MGNP180U.cof | false | 616000     |
| Jupiter | 71492    | 126712767.857614 | Jupiter | JupiterMJ2000Eq | 1000 | true  | null         | false | 48200000   |
| Sun     | 695700   | 132712440017.746521 | Sun | SunMJ2000Eq    | 6261300 | true | null       | false | null       |

Notes:
- Earth/Moon/Mars values are the frozen legacy constants (`bodies.json:4-45`);
  the mu read-back probes that confirm the new values are in
  `mu_readback.md` / `mu_readback.json`.
- `soiRadiusKm` is `null` for the Sun (`bodies.json:100`): the Sun is the
  heliocentric reference body with no enclosing parent, so it imposes no SOI
  restriction.
- Sun min periapsis altitude 6261300 km ≈ photosphere radius (695700) + 100 km
  margin is not meaningful astronomically; per-body handling is documented in §5.

---

## 2. `orbitlab_core/constants.py` — table load + backward compat — **DONE**

Implements a table-driven loader with every public legacy name preserved.

- Loads `bodies.json` once (`constants.py:7-9`), builds a per-body config via
  `_load_body_config()` (`constants.py:11-29`), exposed as `BODIES` (`:31`).
- Legacy individual constants now read from the table, so they can never drift
  from `bodies.json`: `EARTH_RADIUS_KM`/`EARTH_MU_KM3_S2`/`MOON_MU_KM3_S2`/
  `MARS_MU_KM3_S2` (`constants.py:34-44`).
- Derived tables (`constants.py:46-78`):
  - `CENTRAL_BODY_PROPERTIES` — (radius_km, mu_km3_s2, gmat_name, coord_system)
    for all 7 bodies (`:54`).
  - `MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY` (`:60`).
  - `BODY_ALLOWS_DRAG` (`:64`).
  - `POINT_MASS_ONLY_BODIES` → Sun/Mercury/Jupiter (`:68`).
  - `BODY_POTENTIAL_FILES` (`:72`).
  - `BODY_SOI_RADIUS_KM` (`:76`).
- Legacy default minima kept as aliases (`constants.py:80-88`):
  `MIN_PERIAPSIS_ALTITUDE_KM` = Earth 100, `MIN_OTHER_BODY_PERIAPSIS_ALTITUDE_KM`
  = 20.
- `AU_KM = 149597870.691` (DE405) at `constants.py:104`.

Consumers confirmed: `validation.py:19-27` (imports), `models.py:13`
(`CENTRAL_BODY_PROPERTIES`), `generator.py:32` (`CENTRAL_BODY_PROPERTIES`,
`POINT_MASS_ONLY_BODIES`), `templates.py:7` (`EARTH_MU_KM3_S2`).

---

## 3. `orbitlab_core/ast/models.py` — 7-body enums — **DONE**

- `InitialOrbitConfig.coordinateSystem` literal now allows all 7 body-centered
  systems: Earth/Luna/Mars/Mercury/Venus/Jupiter/Sun `MJ2000Eq`
  (`models.py:138`).
- `ForceModelConfig.pointMasses` literal now allows Luna, Sun, Jupiter, Mars,
  Mercury, Venus, Earth (`models.py:189`) — GMAT body names (Luna = the Moon).
- `OrbitLabExperiment.centralBody` literal now allows Earth/Moon/Mars/Mercury/
  Venus/Jupiter/Sun (`models.py:377`).
- The default/auto coordinate-system validator is now table-driven: it looks up
  `CENTRAL_BODY_PROPERTIES[body][3]` instead of a hard-coded 3-entry map
  (`models.py:408-414`).

---

## 4. `orbitlab_core/ast/validation.py` — per-body rules — **DONE / PARTIAL**

- Per-body minimum periapsis altitude now uses
  `MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY[centralBody]` instead of the old
  Earth-vs-other split (`validation.py:173`).
- Drag allowance is table-driven via `BODY_ALLOWS_DRAG[centralBody]`
  (`validation.py:176`).
- **Point-mass gravity warning (item 3)** — `validation.py:180-190` (added): when
  the central body is in `POINT_MASS_ONLY_BODIES` and a non-zero gravity
  degree/order was requested, an explicit warning is emitted that the gravity
  field degree/order is ignored.
- **SOI containment (item 3)** — `validation.py:319-331` (added): when a body has
  a `BODY_SOI_RADIUS_KM` entry, the apoapsis radius must not exceed the SOI
  radius; an escape beyond the SOI is an error. The Sun (`soiRadiusKm` null) is
  skipped, so heliocentric orbits are unrestricted.
- **SOI formula `d` (GMAT epoch distance) — `deferred`**: the spec's `d *(mu/mu_parent)^(2/5)` formula with the epoch-01-Jan-2026 12:00 UTCGregorian distance
  read from GMAT is **not documented anywhere under Phase3** → recorded as
  "spec not found" in `closeout/status.md`. The static `soiRadiusKm` value is
  used instead and the containment check is enforced.

---

## 5. `orbitlab_core/compiler/generator.py` — point-mass emission — **DONE**

- Point-mass-only central bodies (Sun/Mercury/Jupiter) now emit
  (`generator.py:136-144`):
  - `PrimaryBodies = {};` (no harmonic primary body)
  - `PointMasses = {<central>, ...};` — the central body added as a point mass,
    de-duplicated against the configured third bodies
  - **no** `GravityField.<body>.Degree/Order` lines and no potential file
- Non-point-mass bodies (Earth/Moon/Mars/Venus) keep the existing emission:
  `PrimaryBodies = {<gmat_body>};`, optional potential file (Mars `Mars50c.cof`,
  Moon `LP165P.cof`), gravity degree/order, and the third-body `PointMasses`
  (`generator.py:145-156`).
- **ReportFile.Add single-line** — the `ReportFile.Add` line is appended once
  per filename (`generator.py:273-280`) — verified unchanged.
- **Absolute ReportFile.Filename (item 4)**: `normalize_gmat_path`
  (`templates.py:10`) replaces backslashes with forward slashes; the callers pass
  an absolute path (including `test_gmat_execution.py:85-90`), so the absolute
  requirement is satisfied at the caller level. The default
  `compile_to_string` path still uses the relative `telemetry.txt` so the golden
  diff for Earth/Moon/Mars is untouched.

---

## 6. Front step — `phase3_ai_interpreter/frontstep/frontstep.py` — **DONE**

Frontstep is fully self-contained (standard library only); its body constants are
mirrored locally **in lock-step with `bodies.json`**.

- Body tables extended to all 7 (`frontstep.py:25-52`): `BODY_RADII_KM`
  (Earth/Moon/Mars/Mercury/Venus/Jupiter/Sun), `BODY_COORD_SYSTEM` (7 body
  `MJ2000Eq` systems), `POINT_MASS_ONLY_BODIES` frozenset (Sun/Mercury/Jupiter),
  and `AU_KM = 149597870.691`.
- Central-body enum check now accepts all 7 (`frontstep.py:213-219`); the Sun is
  described as a point mass with no spherical-harmonic field.
- **Planet as orbiting object still rejected** — `frontstep.py:225-231` actively
  rejects `orbitingObject` when it names one of the 7 bodies; upstream
  pre-populated `unsupported` entries are preserved and forwarded.
- **"x AU from the centre" for the Sun** — new orbit-size kind
  `radiusFromCenterAu` converts AU → km via `AU_KM` and emits a derived
  `semi_major_axis_au` (`frontstep.py:500-522`). Prompt rendering uses "x AU from
  the centre" for the Sun in the Template-A branch (`frontstep.py:725-730`) and
  the default branch (`frontstep.py:878-890`).
- Verified: `python test_frontstep.py` → **ALL 11 ASSERTIONS PASSED**.
  Case #10 (formerly "Sun unsupported") now asserts the Sun is supported
  (`status "ok"`, "AU from the centre", 1 AU → 149597870.691 km); case #11
  asserts a planet as the orbiting object is rejected (`test_frontstep.py`).

Because the frontstep is a self-contained prompt builder that trusts the
upstream `status`/`unsupported` list, the "planet as orbiting object still
rejected" behaviour is preserved for every body including the Sun.

---

## 7. Golden diff (item 6) — verify in close-out STEP 2

`body_expansion/golden_before.json` and `golden_scripts_before.json` are the
frozen 4300-row v9b baseline. `golden_snapshot.py` re-captures success/errors/
warnings and compiled-script SHA-256; the close-out STEP 2 must report **zero
differences** (see `closeout/status.md` item 6 / `closeout/report.md`).

---

## 8. Caller-level satisfactions and scoped items

| Item | State | Note |
|------|-------|------|
| Item 3 SOI formula `d` | deferred / spec-not-found | formula documented nowhere under Phase3; static `soiRadiusKm` containment enforced |
| Item 4 absolute ReportFile.Filename | caller-level | `templates.py:10` + callers pass absolute; default left relative to preserve golden diff |
| Item 6 golden diff zero | verify STEP 2 | run `golden_snapshot.py`, must be 0 diff |
| Item 7 this file | DONE | exists and matches code |
| Item 11 270° & Stage 4 | REPORT | no code change; see `closeout/status.md` item 11 |

---

*Generated for the OrbitLab v9 close-out. All physical values are from
`orbitlab_core/bodies.json` or cited `file:line`; no invented numbers.*
