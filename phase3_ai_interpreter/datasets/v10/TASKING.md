# TASKING — v10 dataset gate (OrbitLab)

Date: 2026-10-21

Do NOT touch any v9 / v9b file. Work only in a new folder `datasets\v10\`.

## INPUT
10 Gemini batch files (batch_01..batch_10, JSONL, CRLF line endings, 400 rows total,
row format `{"messages":[system,user,assistant]}`). Copy them unchanged into
`datasets\v10\raw\` and never edit `raw\`.
Expected counts: batch_01-08 = 40 valid rows each (01-02 Mercury, 03-04 Venus,
05-06 Jupiter, 07-08 Sun), batch_09 = 48 reject rows, batch_10 = 32 blind rows.

## STEP 1 — Known defect fix (write result to datasets\v10\fixed\, not raw\)
batch_10 line 28 (experimentName BlindSun_028): periapsis altitude 24830430.5 km,
ecc 0.0812, Sun radius 695700 -> semiMajorAxisKm must be
(695700+24830430.5)/(1-0.0812) = 27782031.4541 but the row says 27782020.57.
Correct the number in the assistant JSON only. Report the diff.

## STEP 2 — pointMasses question (do not change data yet, just report)
a) Print what the front step (frontstep.py) emits as default pointMasses for each of the
7 bodies when the user says "use the model's default force settings".
b) Print what pointMasses the frozen v9b rows use for Moon and Mars.
c) Count pointMasses patterns per body across the 400 v10 rows.
   Known: Mercury/Venus/Jupiter rows almost all use ["Luna","Sun"], Sun rows use [].
d) State whether the v10 pattern equals the front-step default. If the front step really
emits ["Luna","Sun"] for those bodies, the dataset is consistent with it: leave as is.
If the front step emits something different (e.g. ["Sun"] or []), list the mismatching
rows and STOP for my decision.

## STEP 3 — Gate every row (script datasets\v10\check_v10.py, JSON report
datasets\v10\gate_report.json + report.md)
For each of the 400 rows:
1. Parse. Assistant content must be valid JSON with the same key order as the v9b rows.
2. Valid rows (batch_01-08) and blind rows (batch_10): load into the Pydantic model, run
   AstrodynamicValidator, compile with the deterministic GMAT script compiler. All must
   pass; list any warnings per row (point-mass body with gravity degree > 0 is a warning,
   expected on 4 rows per file for Mercury/Jupiter/Sun - count them but do not fail).
3. Reject rows (batch_09): the assistant output is the reject case. Show exactly how the
   pipeline handles each (what the training target looks like, what Pydantic/validator
   does). Confirm all 36 below-minimum-altitude rows are rejected by the validator with
   the minimum-altitude reason and all 12 beyond-SOI rows with the SOI reason. If a
   reject row is NOT rejected, list it.
4. Reuse audit_v9c_sma_all logic: SMA vs prompt text (circular = R+alt, periapsis =
   (rp+ra)/2 style, SMA+e as given, Sun AU rows: AU*149597870.691 equals SMA).
   Zero mismatches expected.
5. Duplicate check on user text, experiment name and (SMA, ecc) across all 400 rows AND
   against all v9b rows (train + validation). Blind set (batch_10) must share no user
   text and no (body, SMA, ecc) with any other v10 file or any v9b file.
6. Numbers per body must match bodies.json (radius, mu, min altitude, SOI): print the
   table used.

## STEP 4 — GMAT sanity
For each of the 4 new bodies pick 3 valid rows (one circular, one periapsis, one SMA+e),
compile, run in GMAT, check distance and speed after propagation within 0.5% of an
independent Python two-body prediction (same method as closeout2\gmat_runs.py). 12 runs
total.

## STEP 5 — Report (datasets\v10\report.md)
Per-file table (rows, pass, fail, warnings), list of every failing row with reason, the
answer to Step 2, GMAT result table, and a one-line verdict: READY TO MERGE or NOT READY
with the reason. If everything passes, also write datasets\v10\fixed\ with all 10 files
(batch_10 corrected), LF or CRLF as the trainer expects (check how v9b files are stored
and match them).

## RULES
No guessing numbers, run everything. Do not edit validator, compiler, schema or any v9
file. If something fails, report it, do not silently fix it (except the Step 1 defect).
Commit only code and scripts, not the data, tag v10-gate-1.
