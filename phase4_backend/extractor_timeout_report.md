# Extractor timeout report (`v1-hardening`)

## Step 1 — what the extractor client does today (read-only)

`OpenAIExtractor` (`phase4_backend/orbitlab_backend/clients/extractor_client.py:352-395`)
reads `EXTRACTOR_BASE_URL` / `EXTRACTOR_API_KEY` / `EXTRACTOR_MODEL`, uses a
hard-coded `httpx.AsyncClient(timeout=30.0)` with no retry, sends the strict-schema
system prompt (`temperature 0`, optional `response_format`), and records
`last_raw` / `last_parsed` for the debug script. `EXTRACTOR_TIMEOUT_S`
(default 150) exists in `config.py` but only the explainer reads it.

Failure paths today (`extract_raw`, single attempt, exception propagates):

- **Timeout** (30 s, cold start needs 80–90 s): `httpx` raises out of
  `extract()`. `FrontStepExtractor.process/process_sync` catches it, logs
  `orbitlab.frontstep` WARNING "extractor failed (ReadTimeout); falling back
  to regex", runs `_fallback_extract`, and converts that. If the regex text
  lacks fields, the run ends `needs_clarification` (e.g. misleading
  `missing [orbit, duration]`) — the model was never given its 90 s.
- **HTTP 502/503/504**: `r.raise_for_status()` raises; same fallback path as
  timeout, no retry.
- **HTTP 400/401**: `r.raise_for_status()` raises; same fallback path, no
  retry, nothing distinguishes auth/config errors from a cold model.
- **Bad JSON** (no `{...}` object): `extract_json_object` raises `ValueError`;
  same fallback path.
- **Empty reply**: `content` must be `str` (else `ValueError`); `""` parses to
  `ValueError("No JSON object found...")`; same fallback path.

`process`/`process_sync` (`frontstep/extractor.py:185-206`) cannot tell a
configured-but-unreachable model from an unconfigured one beyond
`self.extractor_client is not None` (the pipeline only passes a real
`OpenAIExtractor`, else `None`), and neither path raises a typed error —
every client failure degrades to regex + `needs_clarification`.
`extract`/`interpret` never call the explainer; only the pipeline extract
stage (`pipeline.py:64-80`) wraps this in `NeedsClarification` /
`ExtractionError`.

## Step 2 — timeout and retry (done)

- `OpenAIExtractor` now uses `EXTRACTOR_TIMEOUT_S` (default 150.0) for
  `httpx.AsyncClient(timeout=...)`, like the explainer; explicit `timeout_s`
  still wins.
- `extract_raw` retries ONCE (1 s pause, same timeout) only on
  `httpx.TimeoutException` or HTTP 502/503/504; any other error (400/401,
  bad JSON, empty reply, wrong content type) propagates immediately.
- Final failure logs ONE WARNING line (`orbitlab.extractor`: exception class
  + first 200 chars, never headers/keys), with "after retry" appended when a
  retry happened. The front step keeps its existing "falling back to regex"
  line.

## Step 3 — no more misleading clarification (done)

- `FrontStepExtractor.process/process_sync` records whether a *real*
  extractor client (`OpenAIExtractor` instance) raised; when it did and the
  regex fallback still does not fully succeed (`status != "ok"`), it raises
  the new typed `ExtractorUnavailable` (`orchestrator/errors.py`:
  stage `extract`, code `extractor_unavailable`, message "The language model
  that reads your request is starting up or unreachable. Please try again in
  a minute.", same text as `details.explanation`). The import is function-level
  to avoid an orchestrator/frontstep import cycle.
- When the regex fallback fully succeeds, the run continues with success (and
  the WARNING). When no extractor is configured (`None` client), behaviour is
  unchanged (regex + honest `needs_clarification`).
- `pipeline.py` catches `ExtractorUnavailable` before the generic
  `PipelineError` passthrough, emits `stage_failed/extract` ("Extractor
  unavailable: [extract:extractor_unavailable] ...", code in the message) and
  re-raises, so jobs and the API error payload carry the code + explanation.

## Steps 5–6 — RUNBOOK and UI (done)

- RUNBOOK gained "Extractor cold starts" (90 s first request,
  `EXTRACTOR_TIMEOUT_S` covers extractor + explainer, Modal
  `min_containers=1`, remove after the demo).
- UI: no render change needed — `extractor_unavailable` carries no
  `details.missing`, so `isClarErr` is false and the normal failure banner
  shows stage + message + explanation. Proven by a Node test
  (`ui_render.test.cjs`: banner shows the message/explanation, and the
  "More information needed" banner does NOT appear).

## Step 4 — tests (done)

New `tests/test_extractor_timeout.py` (8 tests, fake `httpx.MockTransport`
against a real `OpenAIExtractor` through `FrontStepExtractor.process`):
timeout-then-success (2 attempts, ok, a = 6778.136); timeout twice with an
unreadable sentence → `extractor_unavailable` with explanation + 2 attempts +
"after retry" WARNING; timeout twice with "500 kg satellite around Earth,
400 km circular, for 2 days" → success + WARNING; 503-then-success;
401 → 1 attempt, no retry, then unavailable; no extractor configured →
unchanged (`needs_clarification` / success). Plus: pipeline emits a failed
extract stage with the code in the message; API `POST` + poll `GET
/api/experiments/{id}` carries `code: extractor_unavailable` and the
explanation. Node: banner test in `tests/ui_render.test.cjs`.

## Verification

- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 154 passed + 16 skipped.
- Node: `node --test tests/ui_helpers.test.cjs tests/ui_render.test.cjs`: 16 pass.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell: tests/e2e 32, tests 138,
  orbitlab_core/tests 48, simulation_engine/tests 23 — 241 passed, 0 failed.
- Changed files: `phase4_backend/orbitlab_backend/clients/extractor_client.py`
  (timeout setting + retry), `.../frontstep/extractor.py` (real-failure gate),
  `.../orchestrator/errors.py` (`ExtractorUnavailable`),
  `.../orchestrator/pipeline.py` (failed-extract event), `tests/test_extractor_timeout.py`
  (new, 8 tests), `tests/test_extractor_client.py` (timeout now retries: 2 attempts),
  `UIUX/OrbitlabUI Main/app.js` (test-only `setError` hook),
  `tests/ui_render.test.cjs` (banner test), `phase4_backend/RUNBOOK.md`.
