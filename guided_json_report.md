# Guided JSON report — schema-constrained interpreter decoding

Branch: `v1-guided-json` (from tip of `v1-defaults-fix`). No stash, no
`git add .`/`-A`, no force push. No Modal file edited or deployed; no keys or
tokens printed anywhere. No Modal deploy run.

## 1. Server findings (read-only)

Both serve files in the repo folder implement the interpreter/extractor as a
**vLLM OpenAI-compatible chat-completions server**:

| file | model | server | served name |
|---|---|---|---|
| `modal_serve.py` | `NightKillerX/orbitlab-interpreter-v13f` | `vllm==0.10.2` (`transformers==4.56.2`), A10G, port 8000, `--max-model-len 4096`, `--dtype bfloat16` | `orbitlab-interpreter` |
| `modal_extractor.py` | `Qwen/Qwen2.5-7B-Instruct` | `vllm==0.10.2`, same shape/flags | `orbitlab-extractor` |

The backend calls `{base_url}/v1/chat/completions` with system+user messages
(`phase4_backend/orbitlab_backend/clients/interpreter_client.py:93-95`).

Structured-output support on this stack:

- **`response_format: {"type": "json_schema", ...}` — supported.** vLLM's
  OpenAI-compatible server implements constrained decoding for `response_format`
  `json_schema` on chat completions (xgrammar-backed). In-repo precedent: the
  extractor client already sends exactly this shape when
  `EXTRACTOR_JSON_MODE=json_schema`
  (`phase4_backend/orbitlab_backend/clients/extractor_client.py`, covered by
  `tests/test_extractor_schema.py::test_json_schema_body_sent`), against the
  same vLLM 0.10.2 endpoint family.
- **`guided_json` via `extra_body` — supported as an alternative**
  (`extra_body={"guided_json": {...}}` on the chat-completions request).
  Equivalent constraint; `response_format` was chosen because it is the
  standard OpenAI-compatible mechanism and matches the existing extractor
  precedent.

## 2. Client change (applied, backend only)

- `phase4_backend/orbitlab_backend/config.py`: new `ORBITLAB_GUIDED_JSON`
  (default `False`) in `Settings` and in the no-pydantic-settings fallback;
  `.env.example` documents it.
- `phase4_backend/orbitlab_backend/clients/interpreter_client.py`:
  `guided_experiment_json_schema()` builds the schema from the live pydantic
  model (`OrbitLabExperiment.model_json_schema()`, title
  `OrbitLabExperiment`, cached), so the constraint can never drift from the
  validator; `guided_json_enabled()` reads the flag per request.
  When the flag is true the payload gains
  `response_format: {"type": "json_schema", "json_schema":
  {"name": "orbitlab_experiment", "strict": true, "schema": ...}}`.
  **When false the payload dict is byte-identical to before** (no
  `response_format` key) — asserted by test.
- No change to response parsing: guided mode may return an already-parsed
  object, which `interpret_prompt` already accepts.

## 3. Modal serve change (DIFF PROPOSAL ONLY — not applied, not deployed)

No server change is required: the current `vllm serve` invocation already
accepts `response_format` json_schema. If operators want to pin the guided
decoding backend explicitly instead of vLLM's default, the optional change is:

```diff
     cmd = [
         "vllm", "serve", MODEL_REPO,
         "--served-model-name", SERVED_NAME,
         "--host", "0.0.0.0", "--port", "8000",
         "--max-model-len", "4096",
         "--dtype", "bfloat16",
+        # Optional: pin the structured-output backend. Default already
+        # handles response_format json_schema; add only if server logs show
+        # a fallback or guided-decoding warnings.
+        # "--guided-decoding-backend", "xgrammar",
     ]
```

(Same shape would apply to `modal_extractor.py` if guided decoding is ever
wanted there; not proposed now.)

## 4. Env flags

- `ORBITLAB_GUIDED_JSON=true` — enable schema-guided interpreter requests.
  Default (unset/false): previous behavior, byte-identical payloads.
- Unchanged, still required for live runs: `ORBITLAB_MODEL_URL`,
  `ORBITLAB_MODEL_KEY`, `ORBITLAB_MODEL_NAME`.
- Local verification needs none of these (mocked transport + mock/GMAT-stub
  paths only).

## 5. Test plan for when the servers are up

For each prompt below, run the full backend once with
`ORBITLAB_GUIDED_JSON` unset (control) and once with `=true` (guided),
same model deployment, and compare: stage reached, verify mismatches,
validate outcome, `PointMasses`/force-model content, wall time.

1. Sun-synchronous 400 km: `500 kg satellite around Earth, sun-synchronous
   circular orbit at 400 km altitude, propagate for 2 days.`
2. Apoapsis burn (vector-less): `500 kg satellite around Earth, 500 km
   altitude, burn at apoapsis to 800 km, 1 day.` Expect extract
   `needs_clarification` (missing burn size) on both settings.
   Variant with explicit vector: `... burn 100 m/s prograde at apoapsis ...`
   Expect end-to-end success on both.
3. Normal A: `500 kg satellite, 400 km circular orbit around Earth, 2 hours,
   inclination 28.5 degrees.`
4. Normal B: `1200 kg spacecraft around Mars, periapsis altitude 300 km,
   eccentricity 0.2, for 3 days.`
5. Normal C: `800 kg probe around Venus, semi-major axis 9000 km,
   eccentricity 0.05, inclination 30 degrees, for 5 orbits.`

Acceptance: guided runs reach at least the control's stage on all 5 (6 with
the burn variant); schema/verify failure count with guided ≤ control; no new
failure modes; experiment JSONs equivalent up to front-step-owned names.
Record the per-prompt table in the run log.

## 6. Automated tests (this branch)

- `tests/test_guided_json.py` (3 tests, mocked `httpx` transport):
  flag-off payload byte-identical (exact key set, values checked);
  flag-on payload carries `response_format.json_schema` with the
  `OrbitLabExperiment` schema; a schema-violating mock response is still
  rejected at verify/validate (`PipelineError`, stage `verify`/`validate`).
- Full counts: see §7.

## 7. Files changed

- Modified: `phase4_backend/orbitlab_backend/config.py`,
  `phase4_backend/orbitlab_backend/clients/interpreter_client.py`,
  `.env.example`.
- Added: `tests/test_guided_json.py`, this report.
- Not touched: `modal_serve.py`, `modal_extractor.py`, model code, datasets,
  schema field names.

## 8. Test counts (this branch, all suites green)

`python scripts/e2e_all.py` from repo root (GMAT_PATH unset in the shell, so
GMAT-gated e2e tests skip — reported, not failures):

| folder | passed | failed | skipped | errors |
|---|---|---|---|---|
| tests/e2e | 21 | 0 | 28 | 0 |
| tests (incl. 3 new `test_guided_json.py`) | 216 | 0 | 0 | 0 |
| orbitlab_core/tests | 61 | 0 | 0 | 0 |
| simulation_engine/tests | 23 | 0 | 0 | 0 |
| total failed+errors | | 0 | | |

Node (repo root): 5 suites, **81 passed, 0 failed**.

- Modified: `phase4_backend/orbitlab_backend/config.py`,
  `phase4_backend/orbitlab_backend/clients/interpreter_client.py`,
  `.env.example`.
- Added: `tests/test_guided_json.py`, this report.
- Not touched: `modal_serve.py`, `modal_extractor.py`, model code, datasets,
  schema field names.
