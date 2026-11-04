# Phase 4 GMAT round 2 (branch `phase4-gmat`)

No secret value is printed or committed in this report. `GMAT_PATH` was set for the shell session only, never written to a tracked file. No physics, validator rules, compiler output or experiment JSON schema were changed.

## STEP 1 — revert the orbit-count conversion

Removed the `orbits_to_hours` wiring in `orbitlab_backend/frontstep/extractor.py::deterministic_convert`, so "N orbits" / "N orbital periods" pass through unchanged again (`OrbitPeriods`, same value, canonical unit `orbital periods`). The `orbits_to_hours` helper in `conversions.py` and its unit tests (`test_orbits_to_hours_earth`) were kept as required — nothing in the pipeline calls it (verified by grep: only defined and tested). Updated tests: `test_stop_orbits_passthrough_prompt` ("3 orbits" → `OrbitPeriods` value 3, prompt `propagate for 3 orbital periods using integrator RungeKutta89.`) and `test_orbit_count_passthrough_in_extractor` ("1 orbit" → `OrbitPeriods` value 1).

## STEP 2 — explanations on failed runs

Checked the real routes (`POST /api/experiments` → poll `GET /api/experiments/{id}` → `WS /ws/experiments/{id}`). Before the fix, a FAILED run's error payload was `{stage, code, message, details}` with **no** explanation, even though the pipeline had already asked the explainer (validate/compile/simulate/parse) — the text was computed then dropped. The verify-mismatch path never called the explainer at all.

Changes (`orchestrator/pipeline.py`, `api/app.py`), without changing any exception class meaning (only the generic `details` dict contents):
- verify mismatch: call the explainer (`stage="verify"`) and raise `InterpreterMismatch(mismatches, details={"mismatches", "explanation"})`.
- validate: `details={"errors", "warnings", "explanation"}`.
- compile/simulate(GmatTimeout/GmatRunError)/parse: `details={"explanation"}` (was `None`).
- `run_job` mirrors the text as a top-level `explanation` field on the error object, so both `GET` and the WS `final` message carry it.
- New tests: `tests/test_failed_runs.py` drives all three failure kinds through the real routes (HTTP + WS) and asserts stage/code/message/details/errors-or-mismatches plus `explanation` top-level and in `details`.

Example failed-run JSON (validation failure, Earth sma 6448.136 km / 70 km periapsis; mock-explainer text, no secrets):

```json
{
  "id": "<uuid>",
  "status": "failed",
  "error": {
    "stage": "validate",
    "code": "validation_failed",
    "message": "Trajectory violates safe periapsis threshold: periapsis altitude is 70.00 km (radius: 6448.14 km), which is below the minimum safe altitude of 100.0 km for central body 'Earth'.",
    "details": {
      "errors": ["Trajectory violates safe periapsis threshold: periapsis altitude is 70.00 km (radius: 6448.14 km), which is below the minimum safe altitude of 100.0 km for central body 'Earth'."],
      "warnings": [],
      "explanation": "Mock explanation for failure at validate: Trajectory violates safe periapsis threshold: periapsis altitude is 70.00 km (radius: 6448.14 km), which is below the minimum safe altitude of 100.0 km for central body 'Earth'.. Warnings: []"
    },
    "explanation": "Mock explanation for failure at validate: Trajectory violates safe periapsis threshold: ..."
  }
}
```

The WS stream for the same job ends with `{"type": "final", "error": {<same shape>}}`. Mismatch failures look the same with `stage="verify"`, `code="interpreter_mismatch"`, `details={"mismatches", "explanation"}`; GMAT failures with `stage="simulate"`, `code="gmat_run_error"`, `details={"explanation"}`.

## STEP 3 — real GMAT scenarios round 2 (fake interpreter + real compiler/GMAT/parser)

`GMAT_TIMEOUT_S=120`. All reached `explain` (success); no warnings; no unexpected failures.

| # | Scenario | GMAT finished | Telemetry viz / full | Wall time | Final stage | Warnings/errors |
|---|----------|---------------|----------------------|-----------|-------------|-----------------|
| i | Cartesian Earth r=[6778.136,0,0] v=[0,7.6686,0], 4 h | yes | 174 / 174 | 0.4 s | explain | none |
| j | Earth 6878.136 e0, ImpulsiveBurn @1440 s [0.001,0.004,0.007], 3 h | yes | 146 / 146 | 0.4 s | explain | none |
| k | Mars 4189.5 e0.02, burn at apoapsis [0.006,0.009,0.012], 6 h | yes | 207 / 207 | 0.4 s | explain | none |
| l | Earth 6878.136 e0.001, ElapsedSeconds 7200 | yes | 85 / 85 | 0.4 s | explain | none |
| m | Earth 6878.136 e0, OrbitPeriods 3 | yes | 199 / 199 | 0.4 s | explain | none |
| n | Mars Hohmann radius 9000 + targetEccentricity 0.1 | yes | 540 / 540 | 0.4 s | explain | none |
| o | Moon 5080.432 e0.075, burns @420 s [0.004,0.007,0.01] + @1500 s [-0.008,-0.005,-0.002], 4 h | yes | 38 / 38 | 0.5 s | explain | none |

All point counts were below the 2000 cap, so visualization == full (no downsampling needed).

## STEP 4 — long durations (measurement only, validator untouched)

Called the compiler + `GmatRunner` directly, bypassing the pipeline. The `StopCondition` model caps `ElapsedDays` at 365, so over-limit values cannot be constructed normally; for measurement only, a schema-valid experiment (365 days) was built and its `.value` set post-validation in the scratch script (validator/schema/compiler code untouched). Compiler settings as today: integrator `RungeKutta89` (model default), `stepSizeSecs` 60.0 (model default), same generator for all.

| Case | 120 s timeout | 600 s timeout | Telemetry full → viz |
|------|---------------|---------------|----------------------|
| Mars 3889.5 km e0, 687 days | TIMEOUT (`GmatTimeoutError` at 120.3 s) | finished in 317.8 s | 526034 → 2000 |
| Jupiter 200000 km e0.1, 4333 days | TIMEOUT (`GmatTimeoutError` at 120.3 s) | finished in 261.7 s | 465189 → 2000 |
| Sun 149597870.7 km e0.0167, 730 days | finished in 8.7 s | n/a (already finished) | 23365 → 2000 |

Takeaway: Mars-687d needs ~5 min, Jupiter-4333d ~4.4 min (larger orbit ⇒ fewer, longer steps); Sun-730d is cheap (8.7 s). The 2000-point visualization cap holds in all cases; the full (pre-downsample) series is ~0.5 M points for the two long runs.

## STEP 5 — test counts

- `python -m pytest tests -q`: **50 passed** (47 before + 3 new failed-run tests).
- `python -m pytest orbitlab_core/tests -q`: **48 passed, 29 subtests passed**.
- `python -m pytest simulation_engine/tests -q`: **23 passed** (with `GMAT_PATH` set in the shell).
- Total: **121 passed + 29 subtests, 0 failed**.

## Could not do

- Nothing in Steps 1–5 was skipped. Note: Step 4's over-limit values required post-construction mutation in the throwaway measurement script because the schema/model itself enforces the 365-day cap; no repo code was changed for this.
