# Phase 5 long runs (`phase5-long-runs`, from `phase5-real-model`)

No secret printed or committed. No physics, compiler output, schema, or validator-rule values changed (the 365-day cap is untouched). New settings: `ORBITLAB_GMAT_SECS_PER_DAY` is named `ORBITLAB_GMAT_SECS_PER_SIM_DAY` (0.5), `ORBITLAB_GMAT_MAX_TIMEOUT_S` (900), `ORBITLAB_PROGRESS_INTERVAL_S` (10).

## What changed

- New `orbitlab_backend/orchestrator/estimate.py`: `estimate_run_seconds(experiment, secs_per_sim_day)` — stop condition to seconds (all four types; `OrbitPeriods` uses `T = 2*pi*sqrt(a^3/mu)` with repo `BODIES` mu **only for the estimate**; the stop condition sent to GMAT is unchanged), times `sim_days * 0.5 * max(1, 60/step)`. Floor constant 0.5 s/sim-day derives from the worst measured case (Mars 687 d in 317.8 s = 0.4626, rounded up).
- `pipeline.py` validate stage: after the validator passes, if estimate > max timeout the run fails **at validate** (`validation_failed`, "Run too long: ... Shorten the duration ...") with `details.errors/warnings/explanation` — no validator rule touched.
- `pipeline.py` simulate stage: per-run `timeout = clamp(estimate*2, GMAT_TIMEOUT_S, MAX)` used for the GMAT request; plus a `progress` WS event every 10 s (`{"type":"progress","stage":"simulate","elapsedSecs","estimateSecs"}`), existing shapes unchanged. `run_job` promotes the two fields to top-level on progress events.
- `config.py` + `.env.example`: the three new settings (names only, defaults above).
- Measurement-driven fix (committed separately): the first version scaled the estimate by `60/step_size`, which starved 300 s-step runs (estimate 36.5 s -> 73 s timeout on runs that need ~100-270 s). Clamped the factor at 1x: smaller steps get a bigger (safe) budget, larger steps never shrink it.

## Step 4 — 365-day GMAT measurements (fake interpreter, real compiler/GMAT)

Compiler settings for all runs: integrator `RungeKutta89`; the only script difference is `InitialStepSize = 60.00` vs `300.00`. Estimate for 365 d is 182.5 s -> per-run timeout 365 s.

| Case | 60 s step: wall / points | 300 s step: wall / points | Final-pos diff (60 vs 300) |
|------|--------------------------|---------------------------|----------------------------|
| Earth 6778.136 km circ, 365 d | 92.1 s, full 371806 -> viz 2000 | 94.3 s, full 371804 -> viz 2000 | **0.141 km** |
| Mars 3889.5 km circ, 365 d | 185.9 s, full 279356 -> viz 2000 | 172.4 s, full 279483 -> viz 2000 | **0.028 km** |
| Moon 1837.4 km circ (100 km alt), 365 d | 187.9 s, full 290758 -> viz 2000 | 266.8 s, full 290719 -> viz 2000 | **0.186 km** |

Final elements agree to ~1e-9 (ecc) / ~1e-3 deg (inc worst case Moon 38.278465 vs 38.277069). The 2000-point cap held in all runs. Step size barely moves wall time or the answer at these durations (max diff 0.19 km after a full year) — which is exactly why the estimator no longer scales the budget down for large steps.

## Step 5 — test counts

- Backend (`phase4_backend`, `python -m pytest ../tests -q`): **77 passed**.
- Core (repo root): **48 passed + 29 subtests**. Simulation-engine (repo root): **23 passed**.
- Total **148 + 29 subtests, 0 failed**. New: estimate unit tests (incl. OrbitPeriods math and no-mutation of the stop condition), too-long validate failure with explanation, floor-timeout capture, 0.2 s-interval progress events from a fake slow simulator.

## Recommendations for lifting the 365-day cap later

1. Keep the validator cap where it is until a product decision; the pipeline guard (`estimate > max -> validate fail with explanation`) already gives users a plain-language stop without touching validator rules.
2. If the cap is lifted, raise `ORBITLAB_GMAT_MAX_TIMEOUT_S` first: a 687-day Mars run needs ~318 s, so multi-year runs need the max in the thousands; the estimator will then set the per-run timeout automatically.
3. Expect ~0.5 M telemetry points per simulated year (measured 280-370 k for 365 d); the 2000-point visualization cap handled all of them, but watch server memory on multi-year runs.
4. Do not use step-size scaling below 1x (proven unsafe here); if anything, only scale up for small steps.
5. Anything not verified: no run longer than 687 d was attempted; the Sun-730 d case from the earlier round (8.7 s) suggests heliocentric long runs are cheap, but that was not re-run on this branch.
