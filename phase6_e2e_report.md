# Phase 6 E2E report (`phase6-e2e`, from `phase5-main-ui-wiring`)

No secret printed or committed. No physics, validator rules, compiler output, schema, or front-step conversion rules changed (Step 1 adaptation only changed the interpreter HTTP wire format and messages).

## Setup

`git branch -a` first; `phase6-e2e` did not exist, so it was created fresh from `phase5-main-ui-wiring`. Backend baseline before work: 62 passed. Step 1 finding: the client still used the custom contract (`POST {url}` body `{"prompt"}`, response `{"output"}`), NOT the OpenAI shape — so it was adapted: `POST {base}/v1/chat/completions` with `model` + `messages: [system, user]` + `temperature: 0` + `max_tokens: 1500` (`ORBITLAB_MODEL_MAX_TOKENS`, default 1500), system text = the training text verbatim (single `INTERPRETER_SYSTEM_PROMPT`), answers read from `choices[0].message.content` (object / JSON string / fenced). `finish_reason: "length"` raises typed `InterpreterOutputTruncatedError` (never retried, like all non-timeout/5xx errors). Existing retry/timeout/warming tests updated to the `choices` shape, same intent.

## Test counts (GMAT set, via `scripts/e2e_all.py` equivalent runs)

| folder | passed | failed | skipped |
|---|---|---|---|
| tests/e2e | 32 | 0 | 0 |
| tests (rest) | 67 | 0 | 0 |
| orbitlab_core/tests | 48 (+29 subtests) | 0 | 0 |
| simulation_engine/tests | 23 | 0 | 0 |
| **total** | **170 (+29 subtests)** | **0** | **0** |

Without `GMAT_PATH`: `tests/` = 83 passed + 16 skipped (the 16 GMAT-gated e2e tests skip with reason "GMAT not installed (set GMAT_PATH to GmatConsole.exe)"); core/sim unchanged. `scripts/e2e_all.py` runs all four folders, prints this table, exits 1 on any failure/error.

Coverage: 7 bodies + Cartesian + 3 burn triggers + Hohmann + 4 stop types (success, GMAT-gated); validate fails (periapsis below surface, outside SOI, drag on non-Earth, ecc 1.2, inc 200, duration over limit); interpret fails (invalid JSON, unknown field, timeout retried once then typed error); extract fails (timeout, empty fields); API (404 unknown id, 422 empty text, store bound, late-join WS gets final, concurrent runs isolated). Every failure test asserts final status + failing stage + a present `explanation` (top-level and in `details`).

## Bugs found and fixed

1. `run_job` mirrored the top-level `explanation` for generic `PipelineError` but not for `NeedsClarification` — clarification failures had the text only inside `details`. Fixed (same mirror).
2. `SchemaError` carried no explanation (and no explainer call, unlike every other validate failure). Now calls the explainer with a deterministic fallback.
3. Extract/interpret failures carried no explanation at all. Now: needs-clarification names the missing fields; extraction errors name the cause; interpreter-unavailable names timeout/warming. Deterministic strings (no experiment exists yet at those stages), so no model call.
4. `POST /api/experiments` with empty/whitespace text fell through to a confusing clarification failure; now 422 with a plain message (existing tests use non-empty text, unaffected).
5. Not a code bug, but a test-design correction: an immediately-raised transport timeout does NOT hit the client's retry arm (only >10 s warming-window timeouts and 502/503/504 do). The e2e timeout test uses a genuinely slow timeout and asserts exactly 2 attempts + typed `InterpreterUnavailableError` (~25 s).

## Skipped / not verified

- The 16 GMAT-gated tests skip without `GMAT_PATH`; with it they ran real GMAT (~1–3 s each here). No other skips.
- No live hosted model exists in this environment, so the OpenAI wire format was verified against `httpx.MockTransport`, not a real endpoint. `tests/fake_interpreter.py` still serves the old `{"output"}` shape and is unused by the suite (left alone).
- New UI (`/main`) is served and covered by static tests, but no browser ran here (no Playwright); interaction was verified at the HTTP/WS level only.
