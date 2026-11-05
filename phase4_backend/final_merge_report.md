# Final merge report (`release-candidate` = Line A + Line B)

No secret printed or committed. No physics, validator rules, compiler output, schema, or front-step conversion rules changed.

## Step 1 — branch picture

`git branch -a` shows (among others) `phase5-long-runs` and `phase6-e2e`, both descended from `phase5-ui-wiring-v2`:
- Line A = `phase5-ui-wiring-v2` -> `phase5-real-model` -> `phase5-long-runs` (real-model client + smoke harness + long-runs estimate/timeout/progress work).
- Line B = `phase5-ui-wiring-v2` -> `phase5-main-ui-wiring` -> `phase6-e2e` (Main-UI wiring + `/main` route + e2e suite + OpenAI client adaptation + failure explanations + 422).
- `git merge-base phase5-long-runs phase6-e2e` = `06fe17d` ("docs(phase5-ui): final report, runbook, deploy notes, smoke script + screenshot"), i.e. the two lines share everything up to the phase-5 UI work and diverge after it.

Files changed by BOTH lines since the merge-base (conflict candidates):
- `.env.example`, `phase4_backend/orbitlab_backend/api/app.py`, `phase4_backend/orbitlab_backend/clients/interpreter_client.py`, `phase4_backend/orbitlab_backend/config.py`, `phase4_backend/orbitlab_backend/orchestrator/pipeline.py`, `tests/test_interpreter_client.py`.
- Everything else is disjoint (Line A: estimate module, long-runs/smoke tests, smoke script, RUNBOOK/deploy appends, gmat reports; Line B: Main UI files, e2e suite, e2e_all.py, ARCHITECTURE appendix, static-UI tests, phase6 report at root).

## Step 2 — conflicts and resolutions

Only these files conflicted (auto-merge handled the rest, following renames into `phase4_backend/`):

1. `interpreter_client.py` — kept Line A as the base: single `INTERPRETER_SYSTEM_PROMPT` (verified byte-identical to the training text), OpenAI contract with `/v1/chat/completions`, `model` + `max_tokens` (from `ORBITLAB_MODEL_NAME` / `ORBITLAB_MODEL_MAX_TOKENS`), truncation error, no-retry rule, module-level fence stripper. Line B's three hunks were a duplicate constant, a comment block, and a duplicate nested fence-stripper — all dropped as redundant (Line B needs nothing absent from A).
2. `config.py` — kept Line A (it already has `ORBITLAB_MODEL_NAME`, `ORBITLAB_MODEL_MAX_TOKENS`, the GMAT estimate/timeout trio and `ORBITLAB_PROGRESS_INTERVAL_S`).
3. `tests/test_interpreter_client.py` — kept Line B's file (superset: request-shape incl. `max_tokens`, fence, missing-shape, truncation, retry, timeout, warming, system-prompt tests) and appended Line A's only unique test, `test_body_contains_max_tokens`.
4. Pipeline/app needed no manual resolution: the auto-merge kept Line A's estimate/timeout/progress code AND Line B's failure explanations, 422-on-empty-text, `/` + `/main` static mounts and `/ui_adapter.js` route. `.env.example` merged to all 17 names, values empty.

No "same function differs" case required the more-tests-passing rule — after the merge every test from both lines passes.

## Step 3 — test counts

Backend from `phase4_backend` (`python -m pytest ../tests -q`), GMAT set: **111 passed, 0 failed** (79 backend + 32 e2e, incl. the new `/main` test). Core (`orbitlab_core/tests`, repo root): **48 passed + 29 subtests**. Simulation-engine (`simulation_engine/tests`, repo root): **23 passed**. Total **182 + 29 subtests, 0 failed**.
`scripts/e2e_all.py` on the same machine: `tests/e2e 32/0/0`, `tests 79/0/0`, `orbitlab_core/tests 48/0/0`, `simulation_engine/tests 23/0/0`, exit 0.
Without `GMAT_PATH`: backend `95 passed + 16 skipped` (the 16 GMAT-gated e2e tests); core/sim unchanged.

## Step 4 — required tests

All three already existed on the merged tree and pass: system prompt equals the constant exactly; too-long estimate fails at validate with an explanation; progress events arrive from a slow fake simulator. Nothing added.

## Step 5 — live server (mock interpreter ON, real GMAT)

Start command (repo root, PowerShell):
`$env:ORBITLAB_USE_MOCK_INTERPRETER='true'; $env:PYTHONPATH='phase4_backend'; python -m uvicorn orbitlab_backend.api.app:app --port 8000`
`GET /` → 200, `GET /main` → 200 (Main UI), `GET /api/health` → 200 `{"status":"ok"}`.
`POST /api/experiments` with the task's verbatim text → `failed / needs_clarification`, missing `[orbit, duration]` (the regex fallback cannot parse "400 km altitude" word order or singular "1 day"). A parseable text (`Earth 500 kg 400 km circular for 2 hours`) reaches `verify` and fails with `interpreter_mismatch` **with** an explanation — because the fixed mock returns `i=28.5` / 2 h, which no fallback parse reproduces (fallback inclination is always 0). So `status: success` is NOT reachable through mock interpreter + regex fallback; that combination is documented here, not hidden. Real-GMAT success was confirmed at the route level with matching canned data (Earth 6778.136 km, e 0, i 28.5, 2 h): **88/88 telemetry points**.

## Unsure / not done

- The task's Step 5 success criterion (mock interpreter + real GMAT + task text = success) cannot be satisfied without changing the mock's fixed JSON or the fallback parser — both deliberately untouched. The failure paths above are the honest behavior, verified live.
- Nothing was merged into any other branch. Untracked workspace junk (`SummeryCHAT.txt`, `UIUX/*` drops, `phase3_ai_interpreter/*` artifacts, `tools/`) was left alone.
