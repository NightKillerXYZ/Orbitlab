# OrbitLab v9 Close-out — Part 2 Final Report (T1–T6)

Branch: `feature/physics-core`. Scope: Phase3 folders only (`phase3_ai_interpreter\`,
`orbitlab_core\`, `body_expansion\`). Phase 2 (v10) **not** started; UI folder untouched.
All FROZEN v9/v9b dataset, manifest and hash files and
`body_expansion\golden_before.json` / `golden_scripts_before.json` were **read-only**.

> **Note — item-9 label mismatch between `closeout\status.md` and `closeout\report.md`:**
> Both part-1 STEP-2 documents number an item 9, but they give it **different labels and
> evidence**:
> - `closeout\status.md` **item 9** = "Sentence-style prompt builder (Python builds prompt
>   from extracted+converted fields)" — evidence `frontstep.py:579 build_prompt`,
>   `:577-578`, `:536-573`, `:624+`.
> - `closeout\report.md` **item 9** = "v9c leftover audit milestone" — evidence "Verified per
>   item-8 evidence + `v9c_sha256.json`", which **duplicates report.md item 8** ("v9c
>   leftovers — new files only").
>
> The `report.md` table therefore (a) mis-labels row 9 and (b) silently drops the
> sentence-style prompt builder (status.md item 9) from the consolidated report, leaving 10
> rows that do not map 1:1 to the 11 status.md rows. This part-2 report corrects the record:
> **item 9 is the sentence-style prompt builder (`frontstep.py:579 build_prompt`)** as in
> `status.md`; `report.md`'s "v9c leftover audit milestone" is a redundant restatement of
> status.md item 8 and is not a distinct item. The 11 status.md items and their labels are
> authoritative.

## 1. Task status (T1–T5)

| T | Task | Status | Evidence |
|---|------|--------|----------|
| T1 | Permanent tests for the new bodies | **DONE** | `orbitlab_core/tests/test_new_bodies.py` (12 tests). Full `orbitlab_core` suite **48 tests OK**. Golden diff re-run **0 mismatches** across 4300 rows (`closeout/step2_golden_diff.json`). |
| T2 | Real GMAT run for every body | **DONE** | `closeout2/gmat_runs.py` + `gmat_runs.md` — **7/7 bodies PASS** (return 0, telemetry, distance & speed within 0.5%). |
| T3 | SOI provenance | **DONE** | `closeout2/soi_check.py` + `soi_check.md`. All six `soiRadiusKm` recomputed from GMAT epoch distance, replaced in `bodies.json`. T1 re-run (48 OK), golden diff re-run (0 mismatches). |
| T4 | Golden diff for warnings | **DONE** | `closeout2/warnings_diff.py` + `.json` + `.md` — **0 differences** across all 4300 rows (Earth 1492, Moon 1424, Mars 1384). |
| T5 | SMA audit coverage | **DONE** | `datasets/v9/audit_v9c_sma_all.py` + `.json` — **3687 pass, 0 fail, 613 still-N/A** (612 full-Cartesian + 1 maneuver). New script only; originals untouched. |

## 2. Final test counts and golden diff

| Suite | count | result |
|-------|-------|--------|
| `orbitlab_core` (existing + `test_new_bodies.py`) | 48 tests | **OK** (0 fail, 0 err) |

**Golden diff (Earth/Moon/Mars byte-identical compiled scripts):**
- `closeout/step2_golden_diff.json`: **0 mismatches** across all 4300 rows.
- Per body: Earth 1492/1492 (0), Moon 1424/1424 (0), Mars 1384/1384 (0).

**Warnings golden diff (T4):** `closeout2/warnings_diff.json` — **0 differences**, 4300/4300 rows, per_body Earth 1492 (0) / Moon 1424 (0) / Mars 1384 (0).

## 3. GMAT real-run table (T2)

GMAT console `C:\Users\canit\XY\Downloads\gmat-win-R2026a\bin\GmatConsole.exe`; reference values from `orbitlab_core/bodies.json` / `AU_KM = 149597870.691`. Full table and raw log paths: `closeout2/gmat_runs.md`.

| Body | Alts/Radius (km) | Exp R (km) | Min d (km) | Max d (km) | Exp v (km/s) | v0 (km/s) | Return | Status |
|---|---|---|---|---|---|---|---|---|
| Mercury | alt 500 | 2940.5 | 2940.5 | 2940.5 | 2.73725 | 2.73725 | 0 | PASS |
| Venus | alt 400 | 6451.8 | 6450.5 | 6453.1 | 7.09589 | 7.09589 | 0 | PASS |
| Earth | alt 400 | 6778.1 | 6758.7 | 6778.3 | 7.66856 | 7.66856 | 0 | PASS |
| Moon | alt 100 | 1837.4 | 1836.0 | 1838.1 | 1.63350 | 1.63350 | 0 | PASS |
| Mars | alt 300 | 3689.5 | 3676.6 | 3690.2 | 3.40708 | 3.40708 | 0 | PASS |
| Jupiter | alt 5000 | 76492.0 | 76492.0 | 76492.0 | 40.70073 | 40.70073 | 0 | PASS |
| Sun | 0.5 AU | 74798935.3 | 74798934.9 | 74798959.3 | 42.12192 | 42.12192 | 0 | PASS |

**Result: 7/7 PASS.**

## 4. SOI table (T3)

Formula `soiRadiusKm = d * (mu_body/mu_parent)^(2/5)`, `d` from GMAT at 01 Jan 2026 12:00 UTCGregorian, mu from `orbitlab_core/bodies.json`. Full provenance and dataset-impact (0 new failures) analysis: `closeout2/soi_check.md`.

| Body | Parent | d@epoch (km) | Current SOI (km) | Recomputed SOI (km) | Diff % | Action |
|---|---|---|---|---|---|---|
| Mercury | Sun | 69304633.3 | 112000.000 | **134530.210** | 20.116% | replace |
| Venus | Sun | 108818682.7 | 616000.000 | **619750.031** | 0.609% | replace |
| Earth | Sun | 147102351.3 | 925000.000 | **909222.284** | -1.706% | replace |
| Moon | Earth | 360486.1 | 66200.000 | **62065.619** | -6.245% | replace |
| Mars | Sun | 213652311.5 | 577000.000 | **541047.733** | -6.231% | replace |
| Jupiter | Sun | 779715403.5 | 48200000.000 | **48294715.423** | 0.197% | replace |

All six replaced (no recorded source). Sun SOI = null (no parent, no limit).
Frozen legacy radius & mu untouched. T1 re-run 48 OK, golden diff re-run 0 mismatches.

## 5. SMA audit (T5)

Original `datasets/v9/audit_v9c_sma.json`: **2589 pass / 1711 N/A**. The 1711 by reason:

| Reason bucket | Original N/A | Recovered (pass) | Still N/A |
|---|---|---|---|
| orbit given by full Cartesian state (`output-Cartesian`) | 612 | 0 | 612 |
| orbit given by altitude (periapsis/perigee/apogee/"X km above surface", circular altitude) | recoverable | ✓ | 0 |
| orbit given by "a X km" / "X km SMA / semi-major" / `elements[ X km ]` | recoverable | ✓ | 0 |
| not-derivable / maneuver (line 207 — source orbit + target radius) | 1 | 0 | 1 |

New `datasets/v9/audit_v9c_sma_all.py` (imports the original via importlib, reuses
`derive_expected`/`RADIUS`/`TOLERANCE_KM`, adds keyword-anchored altitude/SMA/circular
patterns; original `audit_v9c_sma.py`/`.json` untouched). Result (`audit_v9c_sma_all.json`):

- **pass 3687, fail 0, still-N/A 613** (612 `output-Cartesian` + 1 `not-derivable` maneuver row).
- `3687 + 613 = 4300`; every recovered row is within the original 0.01 km tolerance (fail 0).
- Categories: direct-sma 2659 pass, periapsis 1008 pass, circular-alt 20 pass, output-Cartesian 612 N/A, not-derivable 1 N/A.
- **1098 rows newly audited and passing** (1711 → 613 still-N/A).

## 6. Files created / changed / moved

**Changed (T1/T3):**
- `orbitlab_core/compiler/generator.py` — T1c: Venus potential file read from `bodies.json` (`BODY_POTENTIAL_FILES`) instead of hardcoded body-name branches.
- `orbitlab_core/bodies.json` — T3: all six `soiRadiusKm` replaced (Earth 909222.284, Moon 62065.619, Mars 541047.733, Mercury 134530.210, Venus 619750.031, Jupiter 48294715.423) with `_comment` provenance.

**Created (T1–T5, new):**
- `orbitlab_core/tests/test_new_bodies.py` (12 tests)
- `phase3_ai_interpreter/closeout2/TASKING.md`, `change_notes.md`, `report.md` (this file)
- `phase3_ai_interpreter/closeout2/gmat_runs.py`, `gmat_runs.md` (+ `gmat_work\`)
- `phase3_ai_interpreter/closeout2/soi_check.py`, `soi_check.md` (+ `soi_work\`)
- `phase3_ai_interpreter/closeout2/warnings_diff.py`, `warnings_diff.json`, `warnings_diff.md`
  (+ worker intermediates `_rows_old.json`, `_rows_current.json`)
- `phase3_ai_interpreter/closeout2/old_core\` — `orbitlab_core` archived at commit `4d5d3e8` (`git archive`)
- `phase3_ai_interpreter/datasets/v9/audit_v9c_sma_all.py`, `audit_v9c_sma_all.json`

**Moved to `closeout2\_to_delete\` (obsolete, not deleted per Rule 4):** `_t5_probe.py`, `_t5_resid.py`, `_t5_resid2.py`, `_t5_resid3.py`.

**FROZEN, verified unmodified:** all `datasets\v9\` master/manifest/hash files,
`body_expansion\golden_before.json`, `golden_scripts_before.json`.

## 7. Needs decision

1. **T3 — SOI provenance:** replacement applied because every current value had **no documented source** (per the T3 rule and user-approved "replace all six" decision). Nothing further required; recorded for transparency.
2. **T4/T5 — new warning & N/A categories:** current core adds point-mass warnings (Sun/Mercury/Jupiter gravity) and an SOI-escape error path; none fire for the Earth/Moon/Mars-only v9b rows (T4 = 0 diff). The SMA audit still marks the 612 full-Cartesian rows N/A by design (no SMA in prompt) — if coverage of those is ever wanted, it requires an orbit-propagator-based derivation, out of scope here.

## 8. Summary

T1–T5 all **DONE**. Final `orbitlab_core` suite **48 tests OK**; golden diff **0 mismatches** (4300 rows, Earth/Moon/Mars byte-identical); warnings golden diff **0 differences**; GMAT **7/7 PASS**; SMA audit **3687 pass / 0 fail / 613 still-N/A** (1098 rows newly audited). Item-9 label mismatch in the part-1 close-out documents corrected in the note at the top of this report.
