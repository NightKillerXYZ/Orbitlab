# Realistic cases report (`v1-realistic-cases`)

## Step 1 — request/poll shapes reused (read only)

- `scripts/e2e_all.py`: runs pytest folders as subprocesses (no HTTP itself).
- `scripts/smoke_real_model.py`: in-process front-step → interpreter → verify →
  validate (no compile/GMAT, no HTTP to the backend); reads
  `ORBITLAB_MODEL_URL`/`ORBITLAB_MODEL_KEY`/`ORBITLAB_MODEL_TIMEOUT_S` from the
  environment, never prints them.
- `api/app.py` routes (the UI's contract, reused verbatim, no new endpoints):
  `POST /api/experiments` with `{"text": ...}` → `{"id": ...}`;
  `GET /api/experiments/{id}` → `{"id","status","events","result"?,"error?"}`;
  `GET /api/health` → `{"status":"ok"}` (+ `"mode":"demo"` in demo mode).
  The UI (`ui_adapter.js runExperiment`) POSTs, then polls the GET every
  2 seconds until `status` is `success`/`failed` (plus a `final` websocket
  event); the runner below does the same with plain polling.

## Steps 2–4 — decisions

- `scripts/realistic_cases.py` (stdlib only: argparse/json/time/urllib):
  the 14 prompts verbatim as data; `--base-url` (default
  `http://127.0.0.1:8000`), `--mode demo|real` (label only — the real mode
  is read from `/api/health` and printed), `--timeout-s` per case (default
  400), `--only` (comma-separated ids), `--out` (default
  `phase4_backend/realistic_cases_results.md`, resolved from the script path).
  Records per case: status, failing stage, error code, explanationSource,
  seconds, a/e/duration taken from `result.experiment` (elements +
  stopCondition; absent when the run never got that far — the front-step
  `sent` values are not in the result payload, so the experiment echo is
  the honest source; stated in the table, not hidden), verdict
  (PASS/FAIL vs the expectation; INFO always INFO). Only
  `scheme://host:port` is ever written (user info/query/fragment stripped);
  no headers are sent beyond `Content-Type: application/json`, no auth.
  Exit code non-zero only when a non-info case FAILs. Markdown table columns
  are a superset of the required list (adds code, explSrc, a, e, duration)
  so every recorded field is visible in one place; Observations
  (counts, slowest case, fallback cases) are generated, not hand-written.
- `tests/test_realistic_cases.py` (9, fake `api_post`/`api_get` via
  monkeypatch — no network, no GMAT): case table (14, unique ids,
  valid expectations), verdict logic for all four kinds + timeout/harness,
  `parse_job` on success/failure/garbage/`None` (the `None` guard was added
  after a test caught the crash), observations + markdown rendering,
  URL sanitising, `run_case` success/timeout paths, `main` exit codes and
  `--only` filtering.
- RUNBOOK "Realistic cases" with exact PowerShell + bash for demo mode and
  real-model mode.
- Decisions on the two demo-mode FAILs (recorded honestly, not massaged):
  case 5's prompt states no mass, so `needs_clarification` (missing
  `dryMassKg`) is the correct behaviour — the task's `success` expectation
  looks like a prompt defect. Case 7 reads "to 800 km" as a target *radius*
  (the schema field is `targetOrbitRadiusKm`); 800 km < Earth radius, so
  `validation_failed` is the validator working as intended. The alternative
  reading (800 km *altitude*) is ambiguous English, not a code bug.

## Step 5 — verification

- Node (all five files, same `node --test` invocation): 49 pass.
- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 197 passed + 28 skipped.
- Core / sim (repo root): 48 (+29 subtests) / 23 passed.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell: tests/e2e 49, tests 176,
  orbitlab_core/tests 48, simulation_engine/tests 23 — 296 passed, 0 failed.
- Live demo run (server on 127.0.0.1:8017, `ORBITLAB_DEMO_MODE=true`,
  real GMAT via `GMAT_PATH` in the shell only): 14 cases, 11 non-info,
  9 PASS, FAIL on #5 (no mass in prompt → honest `needs_clarification`)
  and #7 (800 km target radius below Earth surface → `validation_failed`);
  info cases recorded as INFO. Slowest 2.1 s (all successes tied);
  fallback explanations on all 6 successes, none on failures.
- Untracked leftovers: none of mine (probes live in /tmp; the results table
  and this report are committed).
- Unsure: case 7's "to 800 km" is ambiguous English (radius read is literal
  per the schema field name); real-model mode was not exercised (no model
  keys here) — expectations for cases 5/12/13/14 may differ under the real
  extractor; server lifecycle used `Start-Process`/PID kill because the
  WindowsApps interpreter runs as `python3.12`, not `python`.
- Server stopped after the run (port 8017 verified closed); the run used a
  temp `ORBITLAB_RUN_DIR`, so no stray run folders were left in the repo.
