# Change Notes — phase3 close-out part 2 (T1–T6)

All changes below are intentional, sourced from `orbitlab_core/bodies.json` or
requirement text, and never invent numbers. FROZEN files (all v9/v9b datasets +
manifests/hashes, `body_expansion/golden_before.json`,
`golden_scripts_before.json`) are untouched.

## Step 1 — T1c generator fix: Venus potential file read from bodies.json
File: `orbitlab_core/compiler/generator.py`

- Imported `BODY_POTENTIAL_FILES` from `orbitlab_core.constants`.
- Replaced the hardcoded body-name branches:

      elif central_body == "Mars":   ... Mars50c.cof
      elif central_body == "Moon":   ... LP165P.cof

  with a generic lookup `BODY_POTENTIAL_FILES[central_body]` so that any
  non-point-mass body emits whatever `potentialFile` is declared in
  `bodies.json`, and point-mass-only bodies emit none. This correctly adds
  `GravityField.Venus.PotentialFile = MGNP180U.cof;` for Venus (previously the
  generator silently emitted NO potential file for Venus although
  `bodies.json` declares `MGNP180U.cof` and Venus is not point-mass-only).

- Effect on frozen Earth/Moon/Mars byte-identical output: none. Earth declares
  `potentialFile: null`, so it still emits no PotentialFile line; Moon/Mars
  names were already identical to `bodies.json` (`LP165P.cof`, `Mars50c.cof`).
  Golden diff = 0 mismatches across 4300 rows.

Note on T1c phrasing: task text said "other bodies emit ... a potential file",
but the frozen `bodies.json` has `potentialFile: null` for Earth (EGM96 default,
no explicit file needed), so the new behavior is: every body emits the
`potentialFile` named in `bodies.json`; bodies with null emit none. This is the
faithful, non-invented reading.

## Tests
File: `orbitlab_core/tests/test_new_bodies.py` (new, 12 tests)
- a) periapsis-altitude min boundary for all 7 bodies (just-below invalid, just-above valid),
- b) point-mass warning present for Sun/Mercury/Jupiter, absent for harmonic bodies and for Sun at degree 0,
- c) compiler emission for point-mass vs harmonic bodies, Venus potential file from bodies.json,
- d) SOI containment for Jupiter (inside valid / outside invalid with reason) and Sun never SOI-limited.

## Step 2 — T3 SOI radius provenance & replacement (all six)
File: `orbitlab_core/bodies.json` (single source of truth; NOT frozen) + `closeout2/soi_check.md`

Every `soiRadiusKm` previously had **no documented source** — the SOI formula had
been recorded as *deferred / spec-not-found* (`body_expansion/implementation_report.md`
l.103-105, l.176). Task T3 recomputed each value from a real NASA GMAT run at epoch
**01 Jan 2026 12:00:00.000 UTCGregorian**: distance `d` read in the body's parent frame
(Sun-centred for planets, Earth-centred for the Moon), then

    soiRadiusKm = d * (mu_body / mu_parent)^(2/5)

with mu from `bodies.json`. Per the T3 rule (replace any value with **no source** or
**>1% difference**), and per the user-approved decision, **all six** values were
replaced in `bodies.json`:

| Body | Current | Recomputed | Diff |
|---|---|---|---|
| Mercury | 112000.000 | **134530.210** | +20.116% |
| Venus | 616000.000 | **619750.031** | +0.609% |
| Earth | 925000.000 | **909222.284** | -1.706% |
| Moon | 66200.000 | **62065.619** | -6.245% |
| Mars | 577000.000 | **541047.733** | -6.231% |
| Jupiter | 48200000.000 | **48294715.423** | +0.197% |

- The frozen legacy **radius & mu** for Earth/Moon/Mars are untouched; only the SOI
  radius (an added, non-frozen containment-check parameter) changed.
- Dataset impact verified = 0: a sweep of all 4,300 v9b master rows found zero rows
  newly fail the SOI containment check (v9b holds only Earth/Moon/Mars rows; none has
  an apoapsis in the shrink bands). Mercury/Venus/Jupiter have no v9b rows and their
  SOI only grew. The prior guard condition ("apply only if no v9b row newly fails")
  is satisfied.
- The compiler/generator never reads SOI, so compiled-script output (golden diff)
  is unaffected — re-verified (0 mismatches). Only the validator's SOI containment
  check uses the new values.
- GMAT probe (rc=0, telemetry produced, no warnings): `closeout2/soi_work/soi_probe.script`,
  log `closeout2/soi_work/gmat.log`. Evidence: `closeout2/soi_check.md`.

## Step 3 — T5 SMA audit coverage extension
Files (new; originals `audit_v9c_sma.py` / `.json` untouched):
`datasets/v9/audit_v9c_sma_all.py`, `datasets/v9/audit_v9c_sma_all.json`

The original audit passed 2589 / N/A 1711. The 1711 N/A were broken into buckets to
see which are derivable from the row's own prompt values plus `bodies.json` radius:

- **Derivable directly (missing from original patterns):** orbit given by altitude
  (periapsis/perigee/pericenter, apoapsis/apogee, "X km above surface", circular
  altitude), by "a X km" semi-major axis, by "X km SMA / semi-major", by
  `elements[ X km ]`.

- **Genuinely N/A:** full Cartesian state (612), and one Hohmann-maneuver row (line 207)
  whose prompt gives a source orbit (7000 km) plus a *target radius* (12000 km) — no
  single unambiguous semi-major axis.

Counting: `1711 = 612 Cartesian + 1 maneuver + 1098 recoverable`.

The new script imports the original (guard-protected) audit, reuses its
`derive_expected` / `RADIUS` / `TOLERANCE_KM` / `_num` / `_first_num`, applies the
original pass first, then a keyword-anchored set of altitude / SMA / circular
patterns (checked periapsis/apoapsis/above **before** the direct-SMA patterns so
"periapsis altitude of X km, e=..." is not misread as a direct SMA), and for Maneuver
rows declines to recover target radii.

Guard choices (false-positive avoidance, all verified against the 4,300-row master):
- "a X km" direct SMA requires a number immediately after "a " and not followed by
  "target", so "a periapsis altitude of X km" and "a X km target radius" are excluded.
- "X km, e" direct-SMA was removed entirely (it collides with periapsis altitudes and
  maneuver source orbits, e.g. "7000 km, e=0.004 ... toward a 12000 km target").
- "periapsis altitude above the surface is X km" and "perigee height X km" phrasings
  added.

Result (`audit_v9c_sma_all.json`): **pass 3687, fail 0, still-N/A 613**.
- `direct-sma` 2659 pass / periapsis 1008 pass / circular-alt 20 pass,
- `output-Cartesian` 612 N/A, `not-derivable` 1 N/A (maneuver line 207).
- Numbers check: `3687 pass + 613 still-N/A = 4300`; every recovered row is within the
  original 0.01 km tolerance (fail 0).

Summary: original N/A 1711 → extended still-N/A **613** (612 Cartesian + 1 maneuver);
**1098 rows newly audited and passing**.

## Step 4 — temp probes retired
Moved to `closeout2/_to_delete/` (not deleted per Rule 4):
`_t5_probe.py`, `_t5_resid.py`, `_t5_resid2.py`, `_t5_resid3.py`.

## Step 5 — T6 report
File: `closeout2/report.md` (new). Consolidates T1–T5 status/evidence, final test counts
(48 OK), golden-diff result (0 mismatches), the T2 GMAT table, the T3 SOI table, the file
inventory, and a needs-decision list. Opens with a note correcting the **item-9 label
mismatch** between the part-1 `closeout/status.md` (item 9 = sentence-style prompt builder,
`frontstep.py:579`) and `closeout/report.md` (item 9 = "v9c leftover audit milestone",
which duplicates its own item 8 and drops the prompt builder). `status.md` is treated as
authoritative; no part-1 FROZEN files were touched.
