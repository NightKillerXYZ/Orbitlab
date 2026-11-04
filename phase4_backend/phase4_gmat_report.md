# Phase 4 GMAT Report (branch `phase4-gmat`)

No secret is printed in this report. GMAT_PATH was set for the shell session only, never written to a tracked file. No physics, validator, compiler, or schema code was changed.

## STEP 1 — real GMAT availability

- `orbitlab_backend/config.py`: `GMAT_PATH` is an optional setting (install folder or executable); `pipeline.py` builds a `GmatRunner` with `executable_path=Path(GMAT_PATH)` when the path exists, otherwise falls back to a synthetic trajectory.
- Found on this machine: `C:\Users\canit\XY\Downloads\gmat-win-R2026a\bin\GmatConsole.exe` (set via `$env:GMAT_PATH` for the shell only).
- Previously skipped tests now run: `simulation_engine/tests/test_gmat_integration.py` (2) + `orbitlab_core/tests/test_gmat_execution.py` (3) = **5 ran, 5 passed, 0 skipped**.

## STEP 2 — real end-to-end runs (fake interpreter + real compiler/GMAT/parser)

Each scenario used the canonical experiment JSON the fake interpreter would return, with matching front-step `sent` data so verify passes on physics. `GMAT_TIMEOUT_S=120`.

| # | Scenario | GMAT finished | Telemetry pts (visualization, ≤2000) | Wall time | Final stage |
|---|----------|---------------|--------------------------------------|-----------|-------------|
| a | Earth 6778.136 km e 0 i 51.6, 10 h, default forces | yes | 424 | ~0.9 s | explain (success) |
| b | Moon 1937.4 km e 0.05, 8x8, SRP off, 2 days | yes | 1378 | ~1.3 s | explain (success) |
| c | Mars 3889.5 km e 0, Hohmann at periapsis to 9000 km, 48 h | yes | 525 | ~1.1 s | explain (success) |
| d | Mercury 2640.53 km e 0.03, 8 h | yes | 333 | ~0.8 s | explain (success) |
| e | Venus 6351.8 km e 0.02, 12 h | yes | 512 | ~1.1 s | explain (success) |
| f | Jupiter 90000 km e 0.1, 24 h | yes | 352 | ~0.9 s | explain (success) |
| g | Sun 7000000 km e 0, 48 h | yes | 69 | ~0.8 s | explain (success) |
| h | Earth 6448.136 km e 0 (periapsis ~70 km) — faithful out-of-range | n/a (blocked before simulate) | 0 | ~0.0 s | validate (failed as expected) |

Scenario h detail: pipeline did not block at input; validator hard-stopped with `ValidationFailed: ... periapsis altitude is 70.00 km ..., minimum safe altitude 100.0 km for 'Earth'`. A counting-explainer probe confirmed the explainer **was called** with `stage='validate'` and that error; the `ValidationFailed.details` carries `errors`/`warnings` but the explanation string itself lives in the explainer call, not in the exception payload (pre-existing pipeline behavior, unchanged per scope). No scenario failed unexpectedly.

## STEP 3 — orbit-count durations

- Searched repo: mu constants already exist as the single source of truth in `orbitlab_core/constants.py` (`BODIES`, loaded from `orbitlab_core/bodies.json`), reused — no new assumed values, so no `assumption` comment was needed. Values: Earth 398600.4415, Moon 4902.800066, Mars 42828.375214, Mercury 22032.080486, Venus 324858.598827, Jupiter 126712767.857614, Sun 132712440017.74652.
- Implemented in `orbitlab_backend/frontstep/conversions.py`: `orbits_to_hours(a_km, body, N)` with `T = 2*pi*sqrt(a^3/mu)` seconds, `hours = N*T/3600` (rounded to 6 decimals), returning `("hours", "ElapsedHours")`.
- Wired in `extractor.py deterministic_convert`: when the parsed duration is orbits/periods **and** sma is known, it converts to hours via `orbits_to_hours`; Cartesian (sma None) keeps the passthrough value.
- Note: this branch also carries the earlier front-step name-ownership/passthrough work; Step 3 intentionally supersedes the orbit part of that passthrough (orbits now arrive at the model as hours), while seconds/minutes/hours/days passthrough is unchanged. The model therefore still only receives hours/days (or seconds/days for time units) — never `OrbitPeriods` from the extractor when sma is known.
- Unit tests: `orbits_to_hours(6778.136, Earth, 1)` ≈ 1.5427 h (task text says "about 1.5398"; measured exact value is 1.542673, within 0.01); `N=10` gives 10x within rounding (15.426731); extractor test converts "3 orbits" (400 km Earth circular) to `ElapsedHours`.

## STEP 4 — run directory cleanup

- New `orbitlab_backend/api/run_cleanup.py`: `get_run_root()` (defaults to `<tmp>/orbitlab-runs`) + `cleanup_old_run_dirs(root, max_age_hours)` deleting immediate subdirs older than the retention by mtime, best-effort, returns count.
- `config.py`: new `ORBITLAB_RUN_DIR` (optional) and `ORBITLAB_RUN_RETENTION_HOURS` (default 24.0), env-overridable.
- `api/app.py`: cleanup runs once at backend startup (logged count only) and in a `finally` after each finished job.
- Test: `tests/test_run_cleanup.py` creates a fake old dir (mtime backdated 30 h) and a fresh dir; asserts the old dir is deleted and the fresh one kept; missing root returns 0.

## STEP 5 — full test counts

- `tests`: **47 passed** (includes 2 new cleanup + 2 new orbit tests; GMAT-dependent API tests use mocks).
- `orbitlab_core/tests`: **48 passed, 29 subtests passed** (includes 3 real-GMAT execution tests).
- `simulation_engine/tests`: **23 passed** (includes 2 real-GMAT integration tests).
- Total: **118 passed + 29 subtests, 0 failed, 0 skipped** (with `GMAT_PATH` set in the shell).

## Could not do / limitations

- Scenario table telemetry `pts` are visualization counts from the pipeline result; full (pre-downsample) counts were not separately recorded.
- Scenario h explanation string is produced by the explainer call but is not attached to the `ValidationFailed` exception payload (pipeline raises with `details={errors, warnings}`); verified the call happens via a counting explainer.
- Untracked workspace junk (`SummeryCHAT.txt`, `UIUX/*` drops, `phase3_ai_interpreter/*` artifacts, `tools/`) was left untracked, not committed.
