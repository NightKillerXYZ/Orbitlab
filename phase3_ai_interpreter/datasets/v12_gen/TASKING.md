# TASKING — v12_gen generated training dataset (OrbitLab)

Date: 2026-10-25

Do NOT modify any v9 / v9b / v10 / v11 file. Do NOT modify `datasets\v12\*.jsonl`
(the spec source). Work only in `datasets\v12_gen\` (new folder).

## INPUT (resolved)
Spec source = `datasets\v12\*.jsonl` (12 files x 40 = 480 spec rows).
Each spec row is a single dict with fields:
`id`, `body`, `form` (circ|peri|sma|au), `h`|`a`|`x` (altitude / SMA / AU),
`e`, `mass`, `inc`, `raan`, `aop`, `ta`, `dur`, `unit` (days|hours),
`integ` (RungeKutta89|PrinceDormand78), `class` (valid|below_min|beyond_soi|bad_incl),
optional `force` { `deg`, `pm` (list), `srp` }.

Expected counts: 360 valid (incl. 40 force rows) + 120 reject
(Earth 40 / Moon 40 / Mars 40; below_min 42, beyond_soi 39, bad_incl 39).
Forms: circ 199, peri 187, sma 84, au 10. Units: days 248, hours 232.
Bay 7 bodies: Earth, Moon, Mars, Mercury, Venus, Jupiter, Sun.

## GOAL
Build ONE ChatML training row per spec (480 rows) into
`datasets\v12_gen\orbitlab_v12_gen.jsonl` (LF line endings, no BOM).

## STEP 1 — TASKING.md (this file)
Write this tasking before generating anything.

## STEP 2 — Generator (script `datasets\v12_gen\build_v12_gen.py`)
For each spec row produce a ChatML row `{"messages":[system,user,assistant]}`:

1. SYSTEM — reuse the v11 system prompt verbatim (see
   `orbitlab_v11_tinker_train.jsonl`; identical across all v11 train/val rows).

2. USER — exact v10 wording (copy the sentence templates from
   `datasets\v10\fixed\batch_01..08_*_valid.jsonl` and `batch_09_all_reject.jsonl`):
   - Prefix: `I'd like an experiment call the run "RUN" with spacecraft "SCRUN"; use MASS kg for the dry mass; around BODY ...`
   - circ:  `a circular orbit at an altitude of H km,`
   - peri:  `a periapsis altitude of H km, eccentricity E (E formatted to 4 decimals, e.g. 0.1000),`
   - sma:   `with SMA A km, eccentricity E (E = str source value, 3-decimal stripped),`
   - au:    `with SMA X AU (K km) from the centre, eccentricity E (E=0 rendered "0", else str),` where K = round(X*149597870.691, 3)
   - angles: `inclination INC degrees, RAAN RAAN degrees, argument of periapsis AOP degrees, true anomaly TA degrees;`
   - duration: `propagate for DUR UNIT;`
   - integrator: `integrate with INTEG;`
   - force clause:
     - default (no force field): `use the model's default force settings; I'm not asking for extra options.`
     - force present: `use a degree-DEG and order-DEG gravity field` + (` with point masses ` + ", ".join(pm) if pm non-empty else ``) + ` and enable|disable solar radiation pressure.`
   - Number rendering (h, a, x, mass, inc, raan, aop, ta, dur): natural Python
     `str()` of the source value (e.g. 4508 → "4508", 19500.4 → "19500.4",
     21493.28 → "21493.28"). No trailing `.0`.

3. ASSISTANT — canonical v9b key order (see iteration in v9b/v11 rows), compact
   `json.dumps` (separators ",", ":") LF, no BOM. With:
   - `version`:"1.0"
   - `experimentName`: RUN (from id)
   - `spacecraft`:`{"name":"SC"+RUN,"dryMassKg":mass,"coefficientOfDrag":2.2,"dragAreaM2":1.0,"coefficientOfReflectivity":1.8,"srpAreaM2":1.0}`
   - `centralBody`: BODY
   - `epoch`:{"format":"UTCGregorian","value":"01 Jan 2026 12:00:00.000"}
   - `initialOrbit`:{"type":"Keplerian","coordinateSystem":CS,"elements":{...}}
     - CS per body from `orbitlab_core/bodies.json` (Moon -> LunaMJ2000Eq).
     - semiMajorAxisKm computed: circ -> R+h; peri -> round((R+h)/(1-e), 3); sma -> a as given; au -> round(X*149597870.691, 3).
     - elements: semiMajorAxisKm, eccentricity (float, render .0 for 0), inclinationDeg, raanDeg, argumentOfPeriapsisDeg, trueAnomalyDeg (all float).
   - `forceModel`: gravityDegree, gravityOrder (defaults: Earth/Moon/Mars/Venus 4/4, Mercury/Jupiter 0/0, Sun 0/0; force rows use force.deg for both), pointMasses (defaults: ["Luna","Sun"] for Earth/Moon/Mars/Venus & Mercury/Jupiter, [] for Sun; force rows use force.pm), atmosphericDrag{"enabled":false,"model":"JacchiaRoberts"}, solarRadiationPressure (default true unless force.srp explicitly says otherwise; force rows use force.srp).
   - `maneuvers`: []
   - `propagation`: integrator (RUN, INTEG), stopCondition{"type": ElapsedHours if unit=="hours" else ElapsedDays, "value": dur as float}, stepSizeSecs 60.0.

   NUMBERS: keep floats; json.dumps renders int-valued floats as ".0"
   (e.g. 47.0, 60.0, 2.0). Do NOT round orbit parameters (other than the SMA
   conversions above). Never clamp or "correct" reject rows.

## STEP 3 — Classification + validation (same script)
For every row:
1. Self-classify from spec fields + `orbitlab_core/bodies.json`:
   - bad_incl if inc > 180
   - else beyond_soi if apogee radius (sma*(1+e)) > soiRadiusKm (Sun: soi null -> never)
   - else below_min if perigee altitude (sma*(1-e) - R) < minPeriapsisAltKm
   - else valid
   Compare to the spec `class` field (the Gemini label). Drop + report any row
   where they disagree (expected 0 mismatches).
2. Valid rows: load assistant JSON into Pydantic model + AstrodynamicValidator;
   all must pass. Drop + report any that fail.
3. Reject rows: must fail with the correct reason —
   - bad_incl -> Pydantic (inclinationDeg > 180)
   - below_min / beyond_soi -> AstrodynamicValidator (minimum-altitude / SOI)
   Drop + report any reject row that does NOT fail with the expected reason.

## STEP 4 — Dedup (same script)
Drop a row if it duplicates (by user text OR by (body, semiMajorAxisKm, eccentricity)):
1. any other v12_gen row (already accounted for),
2. any v11 train or val row,
3. any blind set row (`datasets\v11_train\blind\`),
4. `eval\cases_realistic.jsonl` (known empty -> no-op),
5. T01-T12 test prompts (none found in repo -> no-op; note in report).
Keep the first occurrence; log the dropped id and reason.

## STEP 5 — Outputs (same script)
Write `datasets\v12_gen\orbitlab_v12_gen.jsonl` (LF, no BOM) containing only the
kept rows. Also print:
- per-body/form/class counts (kept rows),
- the full list of dropped rows with reason,
- if final count < 420, list the short cells (per body/form/class) to top up.

## STEP 6 — Report (`datasets\v12_gen\report.md`)
Counts + example ids per reject/drop reason, dedup summary, validation summary,
per-body/form/class table, and a one-line verdict READY or NOT READY.

## RULES
No guessing numbers — compute everything from the spec + bodies.json. Do not edit
the validator, compiler, schema, or any v9/v9b/v10/v11 file. If something fails,
report it, do not silently fix it. Commit only code and scripts, not the data,
tag `v12-gen-1`.

## Edge case — durations > 365 days (resolved)
`Pydantic` caps every stop-condition type at 365 elapsed days (ElapsedDays 365.0 /
ElapsedHours 8760 / ElapsedSeconds 31536000, models.py StopCondition). 7 physically
valid Sun rows (V12SunA007-010 au, V12SunA018-020 peri, `unit=days`, `dur` 380-890)
therefore have no schema-legal representation. Per RULES they are NOT clamped or
rewritten; they are reported distinctly as `unrepresentable` and dropped, bringing
the valid count to 353 (473 total kept). Short cells: Sun au 6/10, Sun peri 7/10.
