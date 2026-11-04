# Phase 4 Report — Backend Orchestration

## Assumptions
- Reuse existing orbitlab_core, simulation_engine without changing physics/validator/compiler/schema.
- Secrets from env vars only; provider-agnostic OpenAI-compatible clients.
- Mock interpreter via ORBITLAB_USE_MOCK_INTERPRETER.
- In-memory job store ephemeral; cache by prompt hash.
- Telemetry downsampled to <=2000 via existing downsampler.

## STEP 0 — Audit

### Existing
- front step: phase3_ai_interpreter/frontstep/frontstep.py with conversions, prompt builder; test_frontstep.py 11 assertions. Reused constants; new backend frontstep in orbitlab_backend/frontstep/.
- IExperimentInterpreter: model.py + json_interpreter.py (JSON→Pydantic→Validator→Compiler). Kept.
- IPhysicsExplainer: none before; added mock+OpenAI in orbitlab_backend/clients/explainer_client.py.
- Pydantic/validator/compiler/GMAT runner/telemetry parser all present and reused.
- FastAPI app: none before.
- UI API client: UIUX static HTML only; added orbitlab_backend/api/ui_adapter.js.
- Tests: orbitlab_core/tests, simulation_engine/tests, interpreter tests preserved.
- Archived old_core (3-body) ignored.
- ARCHITECTURE.md outdated (3 bodies, single coord, 365-day cap); live code is 7 bodies truth.

### Secrets audit
- Real secret committed at: `.env` — path only.

## Milestone 1 — Settings and clients
- orbitlab_backend/config.py reads ORBITLAB_MODEL_URL, ORBITLAB_MODEL_KEY, ORBITLAB_MODEL_TIMEOUT_S default 180, EXTRACTOR_BASE_URL, EXTRACTOR_API_KEY, EXTRACTOR_MODEL, GMAT_PATH, GMAT_TIMEOUT_S, CORS, USE_MOCK. Missing var -> clear error naming var, never printing values. .env.example names only.
- Interpreter client: POST {prompt} Bearer, response {output: object or JSON string}, timeout 180s, retry once 502/503/504/timeout, warming event after 10s.

## Milestone 2 — Front step
- IFieldExtractor mock+OpenAI (clients/extractor_client.py); conversions in frontstep/conversions.py radii Earth 6378.1363 Moon 1737.4 Mars 3389.5 Mercury 2440.53 Venus 6051.8 Jupiter 71492 Sun 695700; a=(R+alt)/(1-e), circular/apoPeri, miles/m/AU->km, rad->deg, durations pass through unchanged (seconds->ElapsedSeconds, minutes*60->ElapsedSeconds, hours->ElapsedHours, days->ElapsedDays, orbits->OrbitPeriods), SMA 3 decimals.
- Prompt builder exact forms: Base, Forces default/explicit, Hohmann, Elapsed burn, Apsis burn, Cartesian.
- Missing info -> needs_clarification; verify-after + maneuver M1,M2 normalization.

## Milestone 3 — Orchestrator
- Pipeline emits stage_started/completed/failed + model_warming_up with duration/message. Stages: extract, interpret, verify, validate, compile, simulate, parse, explain.
- Typed errors: NeedsClarification, ExtractionError, InterpreterUnavailable, InterpreterMismatch, SchemaError, ValidationFailed, CompileError, GmatRunError, GmatTimeout, ParseError, ExplainerError.
- Warnings never block; hard-stop via VALIDATION_POLICY table (see below). On failure after validation still calls explainer. Per-run isolated dirs, GMAT timeout, telemetry <=2000.

## Milestone 4 — API
- FastAPI: POST /api/experiments {text}->{id} background task, GET /api/experiments/{id}, WS /ws/experiments/{id} streaming events then final, GET /api/health. In-memory store (ephemeral, single-process). Cache by prompt hash skip infra failures. CORS env var; no secrets in logs; stage timings logged.
- UI adapter minimal at orbitlab_backend/api/ui_adapter.js with MOCK switch.

## Milestone 5 — Tests (2026-11-03 run)
- Fake interpreter HTTP server in tests/fake_interpreter.py with scripted outputs: correct, mismatch, json_string, 503_then_success, timeout, invalid_json, schema_invalid. Tested every error code.
- Unit tests for conversions (9 tests), prompt builder (7 tests), missing-info/verify/maneuver norm (5 tests) — all pass.
- Pipeline tests with real compiler/parser and mock GMAT runner (3 tests + 3 out-of-range); faithful out-of-range case (periapsis 70km Earth) proves front step does not block and validator explains failure afterwards — pass.
- Interpreter client tests (5 tests: correct, json_string, 503 retry, timeout, warming) — pass.
- WebSocket/API tests (4 tests: health, create/get, event order success/failing) — pass.
- Full suite: `python -m pytest tests -v` : 37 passed (new); `orbitlab_core/tests` 48 passed; `simulation_engine/tests` 23 passed. No existing tests weakened.
- GMAT integration tests skipped with clear marker when GMAT_PATH not installed (skip via skipUnless).
- Total counts: new tests 37 + core 48 + sim 23 = 108 passed.

## Hard-stop rules (block)
- periapsis_altitude (per-body mins: Earth 100, Moon/Mars/Mercury 20, Venus 100, Jupiter 1000, Sun 6261300 km)
- soi_escape (Earth 909222, Moon 62065, Mars 541047, Mercury 134530, Venus 619750, Jupiter 48294715 km; Sun null)
- drag_unsupported (only Earth allows drag)
- hohmann_target_periapsis / hohmann_requires_bound
- unknown_orbit_type / cartesian_zero
- stop_condition_limit: ElapsedDays>365 ElapsedHours>8760 ElapsedSeconds>31536000 OrbitPeriods>365
- eccentricity 0-0.99, inclination 0-180, sma>0, coordinateSystem mismatch, gravityOrder<=degree
- Warnings never block: large_delta_v, zero_delta_v, unbound_orbit, point_mass_gravity_ignored, step_size>duration

## How to run
Backend:
```
pip install -e ./orbitlab_core -e ./simulation_engine
pip install fastapi pydantic-settings httpx uvicorn websockets
cp .env.example .env  # fill vars
uvicorn orbitlab_backend.api.app:app --reload --port 8000
```
UI: import ui_adapter.js, VITE_API_BASE, VITE_USE_MOCK switch.

## Known gaps
- Duration orbit-count conversion lacks period context.
- Old run cleanup is in-memory + tempdir auto; no cron.
- Extractor fallback is regex minimal.

## Could not verify
- Real hosted model (no network), Real GMAT unless GMAT_PATH set.

## Corrections (2026-11-04, no secrets printed or committed)
- Names owned by Python: verify-after overrides returned experimentName / spacecraft.name with front-step values, emits interpreter_name_overridden warning events (also kept in result warnings), and never fails on names. Conservative choices: sanitise invalid chars to _ and truncate to 30 chars to satisfy ^[A-Za-z0-9_]{1,30}$; SC_ prefix applied then truncated to 30; overrides recorded with both model and front-step values.
- Stop-condition passthrough: removed the old seconds/minutes/orbit-count to hours/days conversion and the model only knows ElapsedHours/ElapsedDays check. Canonical prompt wording is now propagate for N hours|days|seconds|orbital periods using integrator X. Tests updated: test_duration_conversions expects passthrough (7200 seconds, 3 orbits), new tests cover name overrides and seconds/orbits prompts; test_api event-order fixtures now carry matching names so no override events fire there.
