# Phase 5 real-model prep (`phase5-real-model`, from `phase5-ui-wiring-v2`)

No secret value, token URL, or `.env` content is printed or committed in this report. Nothing physics/validator/compiler/schema-related changed (client + config + docs + harness only).

## What changed

- `HttpInterpreterClient` is now OpenAI-compatible: `POST {ORBITLAB_MODEL_URL}/v1/chat/completions`, headers `Authorization: Bearer <key>` + `Content-Type: application/json` (names only), body `{model, messages: [system, user], temperature: 0}`; experiment JSON parsed from `choices[0].message.content` (object, JSON string, or fenced block). Previously it used a custom `{"prompt"}`-in / `{"output"}`-out contract that no hosted OpenAI-compatible server speaks. Retry behavior kept: exactly once on timeout/502/503/504, immediate failure otherwise (malformed `choices` → `ValueError`, no retry).
- New `ORBITLAB_MODEL_NAME` setting (default `orbitlab-interpreter`; set it to the hosted deployment name). `.env.example` extended with the empty placeholder name.
- New `scripts/smoke_real_model.py`: env-only config (`ORBITLAB_MODEL_URL`/`ORBITLAB_MODEL_KEY` required → exit 2 naming the missing variable, never values; `ORBITLAB_MODEL_TIMEOUT_S` default 180); first call `max(180, configured)`s, later calls 60 s; runs the 6 prompts through front step → interpreter → verify → validator only (no compile/GMAT); prints PASS/WARN/FAIL + elapsed + body/sma/stop per prompt plus a summary; saves secret-free JSON (`--out`, default `smoke_results.json`).
- Appended "Real model smoke test" to `phase4_backend/RUNBOOK.md` and "Real model call" to `phase4_backend/deploy_notes.md` (existing content kept). `.env` confirmed gitignored; `.env.example` is names-only with empty values.

## Test counts

- Backend (`phase4_backend`, `python -m pytest ../tests -q`): **67 passed**.
- Core (`python -m pytest orbitlab_core/tests -q`, repo root): **48 passed + 29 subtests**.
- Simulation-engine (`python -m pytest simulation_engine/tests -q`, repo root): **23 passed**.
- Total **138 + 29 subtests, 0 failed**. New: 3 OpenAI-contract tests (request shape incl. `/v1/chat/completions` path + system/user messages + model, fenced JSON, missing-`choices` single attempt) and 3 exit-2 tests (both/one missing var). Existing retry/timeout/warming tests updated to the `choices` shape, same intent.

## What could NOT be verified (no real model available)

- No live call was made: there is no hosted key in this environment, and the script exits 2 without one (verified: prints missing names, no values). The harness itself was dry-run against a dead endpoint (`127.0.0.1:9`, dummy key): all 6 prompts FAIL fast and gracefully (mostly at `extract` — the regex fallback cannot parse several of these phrasings even before any network happens), summary + secret-free JSON written, exit 0. Real PASS/WARN/FAIL distribution, cold-start timing, and the model-name default all await your run with real variables.
- `tests/fake_interpreter.py` still serves the old `{"output"}` shape; it is unused by the suite (only `CORRECT_EXPERIMENT` is imported) and was left alone.
