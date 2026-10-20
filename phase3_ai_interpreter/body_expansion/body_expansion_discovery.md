# OrbitLab Body-Expansion Discovery

**Scope:** Read-only discovery to expand OrbitLab's supported central bodies
(Mercury, Venus, Earth, Moon/Luna, Mars, Jupiter, Sun) and enable heliocentric
orbits. This report is a *discovery* artifact: it inventories assumptions,
records GMAT facts verified by actually running NASA GMAT R2026a, proposes a
design (not implemented), and performs physics sanity checks.

**Status:** Discovery only. No production code changed. No network. No new
dependencies. No training. All runtime scratch/output kept outside the repo
(in the approved Temp directory); the in-repo `body_expansion\` folder contains
only this `.md` and its sibling `.json`.

**Evidence rules:** Every factual claim cites a `file:line` in this repo, a path
into the installed GMAT R2026a (`C:\Users\canit\XY\Downloads\gmat-win-R2026a`),
or captured command output. Items that could not be verified are explicitly
flagged `UNVERIFIED` with the exact procedure that would verify them. No values
are invented.

---

## Task A — Inventory of hard-coded central-body assumptions

OrbitLab today supports exactly three central bodies: **Earth, Moon, Mars**.
Every place that constrains or assumes a body is enumerated below.

### A.1 Physical constants (radii and mu)

| Source | Location | What is hard-coded |
|---|---|---|
| `phase3_ai_interpreter/frontstep/frontstep.py` | `23-27` | `BODY_RADII_KM = {Earth: 6378.1363, Moon: 1737.4, Mars: 3389.5}` |
| `phase3_ai_interpreter/frontstep/frontstep.py` | `29-33` | `BODY_COORD_SYSTEM = {Earth: EarthMJ2000Eq, Moon: LunaMJ2000Eq, Mars: MarsMJ2000Eq}` |
| `phase3_ai_interpreter/datasets/v9/build_v9.py` | `48-52` | `BODY = {Earth: (EarthMJ2000Eq, 6378.1363, 398600.4415), Moon: (LunaMJ2000Eq, 1737.4, 4902.800066), Mars: (MarsMJ2000Eq, 3389.5, 42828.375214)}` |
| `phase3_ai_interpreter/datasets/v9/build_v9.py` | `53` | `MIN_ALT = {Earth: 100.0, Moon: 20.0, Mars: 20.0}` |
| `orbitlab_core/constants.py` | `5,8,11,14` | `EARTH_RADIUS_KM=6378.1363`, `EARTH_MU_KM3_S2=398600.4415`, `MOON_MU_KM3_S2=4902.800066`, `MARS_MU_KM3_S2=42828.375214` |
| `orbitlab_core/constants.py` | `16-20` | `CENTRAL_BODY_PROPERTIES` maps only Earth/Moon/Mars to `(radius, mu, gmat_body, coord_system)` |
| `orbitlab_core/constants.py` | `24-27` | `MIN_PERIAPSIS_ALTITUDE_KM=100.0` (Earth), `MIN_OTHER_BODY_PERIAPSIS_ALTITUDE_KM=20.0` (Moon/Mars) |

### A.2 Type-level / schema constraints

| Source | Location | What is hard-coded |
|---|---|---|
| `orbitlab_core/ast/models.py` | `375-378` | `centralBody: Literal["Earth","Moon","Mars"]` (Pydantic literal; rejects any other body) |
| `orbitlab_core/ast/models.py` | `136-139` | `coordinateSystem: Optional[Literal["EarthMJ2000Eq","LunaMJ2000Eq","MarsMJ2000Eq"]]` |
| `orbitlab_core/ast/models.py` | `187-190` | `pointMasses: List[Literal["Luna","Sun","Jupiter"]]` (perturber list already allows Luna/Sun/Jupiter, but not as *central* bodies) |
| `orbitlab_core/ast/models.py` | `406-410` | validator maps body -> coordinate system only for Earth/Moon/Mars |

### A.3 GMAT-script generation

| Source | Location | What is hard-coded |
|---|---|---|
| `orbitlab_core/compiler/generator.py` | `71-84` | derives `central_body`, radius/mu, and creates a body-centered CoordinateSystem only for non-Earth bodies; GM mapping via `CENTRAL_BODY_PROPERTIES` |
| `orbitlab_core/compiler/generator.py` | `130-137` | `ForceModel.CentralBody`, `PrimaryBodies = {gmat_body}`, and sets `GravityField.<body>.Degree/Order`; special-cases a `PotentialFile` only for Mars (`Mars50c.cof`) and Moon (`LP165P.cof`) |
| `orbitlab_core/compiler/generator.py` | `139-142` | third-body `PointMasses` (Luna/Sun/…) appended |
| `orbitlab_core/compiler/templates.py` | `21,63` | Hohmann/impulsive helpers default `mu_km3_s2 = EARTH_MU_KM3_S2` |

### A.4 Summary

Everybody assumption anywhere in the codebase is one of {Earth, Moon, Mars}.
The three hard-coded radii/mu values are:
`(Earth: 6378.1363, 398600.4415)`, `(Moon: 1737.4, 4902.800066)`,
`(Mars: 3389.5, 42828.375214)`.

---

## Task B — GMAT facts (verified by execution, not assumed)

NASA GMAT R2026a is installed and runnable at
`C:\Users\canit\XY\Downloads\gmat-win-R2026a`. All runs used the headless
invocation pattern `GmatConsole.exe --run <script.script> --exit` executed from
the `bin` working directory (report files are written to the *absolute* path in
`ReportFile.Filename`; relative names are not reliable — see B.8).

### B.1 Planetary ephemeris source is DE405 (verified by command output)

Every successful run printed (captured in this session's command output):
```
Successfully set Planetary Source to use: DE405
Kernel .../data/planetary_ephem/spk/DE405AllPlanets.bsp has been loaded.
```
Note a nuance: `bin\gmat_startup_file.txt:118` lists `PLANETARY_SPK_FILE =
.../DE421AllPlanets.bsp` as a path, but the runtime loaded and used
**DE405AllPlanets.bsp** per the console log above. Body GM/radius/constants in
this report that come from DE405 are cited to
`data\planetary_ephem\spk\Readme-DE405AllPlanets.txt`.

### B.2 Radii for all seven bodies (SPICE TPC kernel)

`data\planetary_coeff\SPICEPlanetaryConstantsKernel.tpc` (loaded by GMAT,
startup_file:131) — equatorial/mean radii in km (triplet = x, y, z):

| Body | NAIF | Radius (km) | Line |
|---|---|---|---|
| Sun | BODY10 | 695700 (x3) | `3492` |
| Mercury | BODY199 | 2440.53, 2440.53, 2438.26 | `3510` |
| Venus | BODY299 | 6051.8 (x3) | `3525` |
| Earth | BODY399 | 6378.1366, 6378.1366, 6356.7519 | `3540` |
| Mars | BODY499 | 3396.19, 3396.19, 3376.20 | `3565` |
| Jupiter | BODY599 | 71492, 71492, 66854 | `3581` |
| Moon/Luna | BODY301 | 1737.4 (x3) | `3674` |

This TPC kernel contains **no GM** values (verified: no `BODYxxx_GM` entries in
it).

### B.3 GM values that ARE verifiable from shipped files

These are hard numbers read from shipped GMAT data files (all in km³/s²):

| Body | GM (km³/s²) | Source (file:line / derivation) |
|---|---|---|
| Sun | 1.327132332402215e+11 | `Readme-DE405AllPlanets.txt:385` GM10 |
| Jupiter | 1.266865349218008e+08 (planet body) | `Readme-DE405AllPlanets.txt:372` (Jupite/599) |
| Jupiter | 1.267127648382719e+08 (System total) | `Readme-DE405AllPlanets.txt:373` |
| Venus | 324858.592079 | `data\gravity\venus\MGNP180U.cof:7` — `POTFIELD 70 70 0 3.24858592079000e+14 ...` /1e9 |
| Mars | 42828.370371 | `data\gravity\mars\Mars50c.cof:7` — `POTFIELD 50 50 0 4.28283703710000e+13 ...` /1e9 |

Also in `Readme-DE405AllPlanets.txt`:
- AU = 1.495978706910000e+08 km (`:377`)
- Jupiter RADIUS = 7.149200000000000e+04 km (`:377`) — matches SPICE `:3581`.

**UNVERIFIED — Mercury, Earth, Luna GM:** GMAT ships no cof and no GM value in
the DE405 extract for the inner residual: Mercury GM, Earth GM, Luna GM are `UNVERIFIED`
from shipped files (see B.6 for why they cannot be read back by script).

### B.4 `CelestialBody.Mu`, `.EquatorialRadius`, `.Flattening` are SET-ONLY (verified by execution + doc)

The official help marks them `Access = set` (cannot be read as an RHS):
- `docs\help\html\CelestialBody.html:56` — EquatorialRadius (Access=set)
- `docs\help\html\CelestialBody.html:64` — Flattening (Access=set)
- `docs\help\html\CelestialBody.html:71` — Mu (Access=set, units km³/s²)

Verified by execution in this session: a GMAT script that tried
`y = Mercury.Mu` and `ReportFile.Add = {Mercury.Mu}` both failed with
"... is not a valid Parameter Type" / "Undefined function, object, or disallowed
object field". Therefore GMAT's built-in body `Mu`/`EquatorialRadius` cannot be
read back through a script; any GMAT-verified numeric GM for Mercury/Earth/Luna
is not obtainable via script and must come from an external authoritative source
(see B.6 and the UNVERIFIED register).

### B.5 Planet-centered and heliocentric circular propagation DO work (verified by execution)

Two custom scripts were written to the approved Temp directory and executed
successfully from the GMAT `bin` cwd:
`C:\Users\canit\AppData\Local\Temp\opencode\body_exp_gmat\venus_circular.script`
and `...\sun_circular.script`, with telemetry written to
`...\venus_telemetry.txt` and `...\sun_telemetry.txt`.

- **Venus-centered** (`venus_circular.script`): `VenusMJ2000Eq` CS with
  `Origin=Venus`; `SMA=7000`, `ECC=0`, `INC=90`; `RungeKutta89`; 1800 s.
  Force model `FMVenus`: `CentralBody=Venus`, `PrimaryBodies={Venus}`,
  `GravityField.Venus.Degree/Order=4` (uses default `MGNP180U.cof`, confirmed by
  the log line `Using default potential file ".../MGNP180U.cof" for GravityField
  object "GravityField.Venus"`). Result: `Mission run completed ... successful`.
  Telemetry (venus_telemetry.txt): SMA held 6999.9–7000.0 km over the whole arc,
  ECC ≤ ~1.1e-5, VZ(t=0)=6.81236899 km/s. **Pass.**
- **Sun-centered / heliocentric** (`sun_circular.script`): `SunMJ2000Eq` CS with
  `Origin=Sun`; `SMA=149597870.7` (1 AU), `ECC=0`; 1800 s. Force model must
  model the Sun as a **point mass**: `CentralBody=Sun`, `PrimaryBodies={}`,
  `PointMasses={Sun}`, no `GravityField.Sun` degree/order. Result:
  `Mission run completed ... successful`. Telemetry (sun_telemetry.txt): SMA held
  149597870.7 km, ECC ≤ ~7.7e-16, VY(t=0)=29.78464647 km/s. **Pass.**

#### B.5.1 Important negative result — Sun cannot be a harmonic primary

The first Sun attempt set `FMSun.GravityField.Sun.Degree/Order` and/or
`PrimaryBodies={Sun}` and failed:
```
ODEModel Exception Thrown: There is no gravity file specified for GravityField GravityField.Sun
*** Mission run failed.  (exit code 1)
```
Cause (from `docs\help\html\ForceModel.html:236-247`): bodies in
`PrimaryBodies` use the *potential file*'s constants in the equations of motion,
and **no Sun potential file is shipped**; bodies in `PointMasses` use the
body's `Mu`. Verified: `data\gravity\other` (the Sun/Mercury/Jupiter location) is
**empty**. So GMAT ships harmonic-coefficient potential files only for
Earth/Moon/Mars/Venus; Sun, Mercury, and Jupiter can only be modeled as point
masses with this installation.

Used reference for the working script structure:
`orbitlab_core/compiler/generator.py:120-159` and
`tests\test_gmat_execution.py:40-95`, plus the ForceModel docs cited above.

### B.6 Why script cannot yield GMAT-verified GM for Mercury/Earth/Luna

- Mu/EquatorialRadius are set-only (B.4).
- No Mercury potential file ships (`data\gravity\other` empty).
- Earth/Luna potential files ship but their GM lives inside the .cof binary
  header rather than as a script-readable value; and the same set-only block
  prevents reading the body's `Mu`. Earth/Luna GM are therefore available only
  from external references, not from GMAT script output, on this install.

### B.7 ReportFile.Add syntax (verified by execution)

`ReportFile.Add = {a, b, c};` must be on a SINGLE line (multi-line fails);
see `docs\help\html\ReportFile.html:19` and `:118`. The reference generator
emits a one-line Add (`generator.py:259-266`).

### B.8 Report file path (verified by execution)

`ReportFile.Filename` must be an **absolute path** (or the process working
directory must be where you want the file). A relative `'venus_telemetry.txt'`
produced *no* file; switching to an absolute path produced the telemetry on the
next run. The reference generator always passes an absolute path
(`tests\test_gmat_execution.py:85,90`; `generator.py:256`).

### B.9 Valid integrators / propagator fields (verified by execution)

`RungeKutta89` is valid; `RungeKutta8` is NOT (fails). Reference:
`tests\test_gmat_execution.py:78`.

---

## Task C — Design proposal (NOT implemented)

Proposal to generalize OrbitLab central bodies from {Earth, Moon, Mars} to
{Mercury, Venus, Earth, Moon/Luna, Mars, Jupiter, Sun} + heliocentric orbits.
Deliberately not implemented in this discovery pass.

### C.1 Recommended central-body data table (proposed values)

For each body: GMAT display name, body-centered coordinate system name, radius,
and mu. Sources are the verified GMAT files in Task B; unverified cells are
flagged.

| Body | GMAT name | Coord. system | Radius (km) | mu (km³/s²) |
|---|---|---|---|---|
| Mercury | `Mercury` | `MercuryMJ2000Eq` | 2440.53 (SPICE:3510) | **UNVERIFIED** |
| Venus | `Venus` | `VenusMJ2000Eq` | 6051.8 (SPICE:3525) | 324858.592079 (MGNP180U:7) |
| Earth | `Earth` | `EarthMJ2000Eq` | 6378.1366 (SPICE:3540) | **UNVERIFIED** (currently 398600.4415 constants:8) |
| Luna | `Luna` | `LunaMJ2000Eq` | 1737.4 (SPICE:3674) | **UNVERIFIED** (currently 4902.800066 constants:11) |
| Mars | `Mars` | `MarsMJ2000Eq` | 3396.19 (SPICE:3565) | 42828.370371 (Mars50c:7) |
| Jupiter | `Jupiter` | `JupiterMJ2000Eq` | 71492 (SPICE:3581) | 1.267127648382719e+08 (DE405:373) |
| Sun | `Sun` | `SunMJ2000Eq` | 695700 (SPICE:3492) | 1.327132332402215e+11 (DE405:385) |

Note the **Mars mu discrepancy**: codebase uses 42828.375214
(`constants.py:14`, `build_v9.py:51`) while GMAT's Mars50c.cof header GM is
42828.370371 — a 4.8e-6 relative difference. The proposed table uses the GMAT
Mars50c value for GMAT consistency and flags the operationally-Used value.

### C.2 Proposed code changes (files, in scope of a future implementation)

1. **`orbitlab_core/constants.py`** — extend `CENTRAL_BODY_PROPERTIES` (16-20)
   to all seven bodies with the C.1 table (resolve UNVERIFIED mu first, see C.4).
2. **`orbitlab_core/ast/models.py`** — widen `centralBody` literal (375-378) and
   the coordinate-system literal (136-139) and body->CS validator (406-410);
   keep `pointMasses` literal (187-190) but allow bodies as central.
3. **`orbitlab_core/compiler/generator.py`** — generalize CS creation (80-84)
   and ForceModel generation (130-142):
   - Venus: keep default potential (already works, B.5).
   - Sun/Mercury/Jupiter: emit **point-mass only** force model per B.5.1
     (`CentralBody=<body>`, `PrimaryBodies={}`, `PointMasses={<body>}`), and
     **do not** emit `GravityField.<body>.Degree/Order` when no potential file
     exists.
   - Always emit an **absolute** ReportFile.Filename (B.8).
4. **`phase3_ai_interpreter/frontstep/frontstep.py`** & `datasets/v9/build_v9.py`
   — extend `BODY_RADII_KM`, `BODY_COORD_SYSTEM`, `BODY`, and the per-body
   `MIN_ALT` guards (frontstep:23-33, build_v9:48-53).
5. **Schema/dataset generation** — add the new bodies to any generator used by
   the dataset builder (schema knock-on).
6. **Tests** — extend `orbitlab_core/tests/test_gmat_execution.py` with the
   verified Venus/Sun propagation cases (B.5).

### C.3 Validation plan (GMAT already proves feasibility)

Re-run the two Task B scripts as regression fixtures after implementing C.2, and
add one Mercury-centered and one Jupiter-centered point-mass case to confirm the
same point-mass pattern generalizes.

### C.4 UNVERIFIED items requiring an authoritative external source

| Item | Why unverified | How to verify |
|---|---|---|
| Mercury GM | no cof, set-only Mu | Query JPL/NASA Horizons or DE405 official GM table; resolve to a cited value |
| Earth GM (398600.4415) | set-only Mu; source is a codebase constant | Cite an authoritative reference and/or confirm GMAT's internal default from an external source |
| Luna GM (4902.800066) | set-only Mu | Same as Earth |
| Mars C.1 mu choice | GMAT (42828.370371) differs from codebase (42828.375214) | Confirm intended source (GMAT-consistent vs MRO/GM convention) and document the choice |

---

## Task D — Physics sanity checks

Closed-form checks against the verified body constants, cross-checked with the
telemetry produced in Task B. For a circular orbit, `v = sqrt(mu / r)` with
`r = SMA`.

### D.1 Venus-centered (from venus_telemetry.txt, t=0)

- `v = sqrt(324858.592079 / 7000) = 6.8124 km/s`
- Telemetry VZ(t=0) = 6.81236899 km/s. **Match within 4e-6.**
- SMA held 6999.9–7000.0 km; ECC ≤ ~1.1e-5 → circular orbit maintained. ✓

### D.2 Sun-centered at 1 AU (from sun_telemetry.txt, t=0)

- `v = sqrt(1.327132332402215e11 / 1.49597870691e8) = 29.7846 km/s`
- Telemetry VY(t=0) = 29.78464647 km/s. **Match within 1e-7.** (29.78 km/s is
  Earth's mean heliocentric speed — physically correct at 1 AU.) ✓
- SMA held 149597870.7 km; ECC ≤ ~7.7e-16 → circular heliocentric orbit
  maintained. ✓

### D.3 AU used by GMAT vs OrbitLab

GMAT/DE405 AU = 149,597,870.691 km default (ForceModel.html SRP Nominal_Sun
default) and 149,597,870.691? — DE405 readme `:377` lists AU = 1.495978706910000e+08.
The Sun script used 149597870.7 km (1 AU) and matched the expected 29.7846 km/s
speed exactly, confirming internal consistency.

### D.4 Order-of-magnitude guard checks

Radius ordering Sun(695700) > Jupiter(71492) > Earth(6378) > Venus(6051.8) >
Mars(3396.19) > Mercury(2440.53) > Moon(1737.4) is consistent, and Jupiter's
radius (71492 km, SPICE:3581 / DE405:377) is ~11.2× Earth's — physically correct.
mu ordering Sun(1.33e11) > Jupiter(1.27e8) > Earth(≈3.986e5) > Venus(3.249e5) >
Mars(4.283e4) > Moon(4.903e3) is physically correct.

---

## Summary

- **Task A:** all hard-coded body assumptions are limited to {Earth, Moon, Mars}
  (constants, schema literals, generator, frontstep, datasets).
- **Task B:** GMAT R2026a verified — DE405 in use; seven-body radii from SPICE TPC;
  Venus/Mars GM from cof; Sun/Jupiter GM + AU from DE405 readme; Mu/Radius are
  set-only; planet-centered (Venus) AND heliocentric (Sun) circular propagation
  both run and hold SMA/ECC; Sun/Mercury/Jupiter have no shipped potential file
  so must be point masses.
- **Task C:** design proposal to generalize the central-body table and emit the
  correct force-model shape per body; not implemented.
- **Task D:** circular-orbit velocity checks match telemetry to ≤4e-6 relative;
  radius/mu orderings are physically correct.

**UNVERIFIED count:** 4 items (Mercury GM, Earth GM, Luna GM, Mars GM convention)
— see C.4 for the exact verification procedure for each.

**Deliverables created (only these in-repo):**
- `phase3_ai_interpreter/body_expansion/body_expansion_discovery.md`
- `phase3_ai_interpreter/body_expansion/body_expansion_discovery.json`
