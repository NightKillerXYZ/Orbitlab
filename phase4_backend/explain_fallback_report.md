# Explainer fallback report (`fix-extractor`)

## Step 1 — what happens today (read-only)

`OpenAIExplainer` (`phase4_backend/orbitlab_backend/clients/explainer_client.py:23-46`)
reads `EXTRACTOR_BASE_URL` / `EXTRACTOR_API_KEY` / `EXTRACTOR_MODEL`, uses a
hard-coded `httpx.AsyncClient(timeout=30)` with no retry, sends one long f-string
prompt that dumps the entire experiment dict and the entire trajectory summary
into the user message, sets no `max_tokens` (server default applies; the model
server has a 4096-token context), and always uses `temperature 0`.

### Every failure path today

- **Not configured** (any of the three env vars missing/blank): `OpenAIExplainer()`
  raises `RuntimeError` in `__init__`, but `get_explainer()` catches it and
  returns `MockExplainer`, which never fails (canned text). So "unconfigured"
  never errors — it silently returns mock text.
- **Timeout** (30 s, no retry): the `httpx` exception propagates out of
  `explain()`. On the success path (`pipeline.py:315-318`) it is caught,
  a `stage_failed` event is emitted, and `raise ExplainerError(str(e))` fails
  the whole run (`run_job` marks the job `failed`). Nothing is logged
  (no `logger.warning` in that `except` block).
- **HTTP 400/401/5xx**: `r.raise_for_status()` raises `HTTPStatusError`.
  Same outcome as timeout: success path raises `ExplainerError` and fails the
  run; failure paths (below) swallow it.
- **Empty reply**: `data["choices"][0]["message"]["content"]` returns `""`
  as-is, no error. Success path stores `explanation: ""`; the UI then shows
  "No explanation returned." Failure paths store `explanation: None`/`""`,
  and `app.py` (`if expl:`) omits it from the error payload.

### Pipeline call sites (`pipeline.py`)

Explainer calls on FAILED runs (errors before explain) — all swallow explainer
errors so the original error still raises:

- `verify` mismatch (:126): `try/except` logs `logger.warning("explainer
  failed after verify: ...")`; `explanation` stays `None`.
- `validate` schema error (:150): `except: schema_expl=None` → falls back to a
  deterministic "not valid JSON against the schema" string.
- `validate` validation-failed (:176): `try/except` logs a warning;
  `explanation` stays `None`.
- `compile` (:202), `simulate` timeout (:279) / run error (:287), `parse`
  (:302): bare `except: pass`; `explanation` stays `None`.

Explainer call on the success path (:312): the ONLY place that raises
`ExplainerError`, which fails an otherwise fully successful run
(extract → parse all `stage_completed`, then `stage_failed:explain`).
`extract` and `interpret` never call the explainer.

## Step 2 — timeout and retry (done)

- `config.py`: new `EXTRACTOR_TIMEOUT_S` (default 150.0) in both the
  pydantic-settings branch and the fallback branch; name added to
  `.env.example` (value not set there).
- `OpenAIExplainer` uses it for `httpx.AsyncClient(timeout=...)`; retries
  ONCE on `httpx.TimeoutException` or HTTP 502/503/504 only (1 s pause;
  other errors propagate immediately). On final failure it logs ONE
  WARNING line (`orbitlab.explainer`: exception class + first 200 chars of
  the message; headers/keys are never logged) and re-raises; the pipeline
  does not log a second line.

## Step 3 — digest prompt (done)

`build_explain_digest()` in `explainer_client.py` builds the user message
from a small structured digest (capped at ~1500 chars), never a raw dump:
body, mass, orbit type + present elements (a, e, i, RAAN, AoP, TA),
periapsis/apoapsis altitude from the repo's body radii
(`orbitlab_core.ast.validation.get_body_constants`, radius-only fallback to
`frontstep.conversions.BODY_RADII_KM`), period `T = 2*pi*sqrt(a^3/mu)` with
the repo's body mu, stop condition, maneuvers (type, trigger, delta-v or
target radius), force switches in one line, up to 5 validator warnings, and
from `trajectory_summary` only scalars if present (point count, min/max/final
altitude, final speed). System message is the tutor prompt; `max_tokens` 400;
temperature 0.2 for success, 0 for failure explanations (as before).
Failure prompts keep the stage/error text with the error capped at 600 chars.
A huge `trajectory_summary` cannot push the request body past ~3000 chars
(covered by a test).

## Steps 4–5 — fallback + never-fail explain (done)

- `fallback_explanation()` (deterministic, never raises): 4–6 plain sentences
  from the same digest (body/mass, circular-or-elliptical + a/e, apsis
  altitudes, period in hours/minutes, inclination, stop condition, maneuver +
  delta-v if present, up to 2 validator warnings); sentences are skipped when
  inputs are missing; no invented numbers.
- `failure_explanation()` (never raises): one deterministic sentence
  naming the stage and the (capped) error.
- Pipeline success path: unconfigured explainer (`MockExplainer`), explainer
  failure, or empty text → run still succeeds with the fallback text,
  `"explanationSource": "fallback"`, and a `stage_completed` event
  "Explanation ready (automatic summary)". Model text → `"model"`.
- FAILED runs keep current behaviour, except an explainer failure now yields
  the one-sentence deterministic error instead of `explanation: None`
  (still raises the original error). `ExplainerError` is no longer raised
  anywhere (class kept in `errors.py`).

## Step 6 — UI (done)

- `UIUX/OrbitlabUI Main/app.js`: Physics tab shows `explanation` when present
  plus "Automatic summary (the AI explainer was unavailable)" when
  `explanationSource === "fallback"`; Understanding tab shows the same
  explanation text + fallback note. Success rendering is driven by
  `out.result` presence, so a success run never shows the "Run failed" banner.
- `orbitlab-live.js` does not exist in the repo (only `OrbitlabUI Main/app.js`
  is tracked) — nothing to do there. `node --check app.js` passes.

## Step 7 — tests (done)

New `tests/test_explain_fallback.py` (15 tests, fake `httpx.MockTransport`):
unconfigured → success + fallback; timeout twice → success + fallback +
WARNING; 503-then-200 → model text + 2 calls; 400 → success + fallback +
WARNING, no retry; empty reply → fallback; model answer → `"model"`;
digest cap with a 200 KB trajectory blob (digest ≤ 1500 chars, body ≤ 3000
chars; `max_tokens` 400; temp 0.2/0); fallback text for a = 6778.136 km
Earth circular orbit contains "1.54 hours"; elliptical Mars and Hohmann cases;
failure-path explainer error still yields a deterministic explanation;
`get_explainer()` unconfigured → `MockExplainer`.
- Test updates for "expected a failed run when the explainer fails": none
  needed — no existing test asserts that (`ExplainerError` appears only in
  `errors.py`, `pipeline.py`, and one report). Failure-before-explain tests
  are untouched.

## Step 8 — verification

- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 144 passed + 16 skipped.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell: tests/e2e 32, tests 128,
  orbitlab_core/tests 48 (+29 subtests), simulation_engine/tests 23 — 231 passed, 0 failed.
- Debug command (defaults; explainer shares extractor vars):
```powershell
$env:PYTHONPATH='phase4_backend'; python scripts/debug_extractor.py
```
