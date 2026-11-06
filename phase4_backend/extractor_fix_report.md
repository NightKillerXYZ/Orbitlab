# Extractor fix (`fix-extractor`)

No secret value is printed, logged or committed in this report (names only).

## Step 1 — what the extractor client does today (read-only)

(a) Exact request (`OpenAIExtractor.extract`, `phase4_backend/orbitlab_backend/clients/extractor_client.py`):
- `POST {EXTRACTOR_BASE_URL}/chat/completions` (base URL rstripped of `/`, then `+ "/chat/completions"`; no `/v1` segment).
- Headers (names only): `Authorization: Bearer <key>`, `Content-Type: application/json`.
- Body fields: `model`, `messages` (`[{role: system, content: SYSTEM_PROMPT}, {role: user, content: <user text>}]`), `temperature: 0`. It does NOT set `response_format`, `max_tokens`, `stream`, or anything else.
- System prompt text (exact): "You are a field extractor. Extract structured fields from user text exactly as given, do not compute. Output JSON with keys: centralBody, spacecraftName, experimentName, dryMassKg, orbit (with kind and values), eccentricity, inclinationDeg, raanDeg, aopDeg, trueAnomalyDeg, integrator, duration, forces, maneuvers, cartesian. Numbers must be exact as user gave them."
- Timeout: 30 s per request (httpx default for that client).

(b) Reply parsing and EVERY failure path:
- Success path: `data["choices"][0]["message"]["content"]` → `json.loads`. No `finish_reason` check, no fence handling here.
- Non-JSON reply: fallback regex `\{.*\}` (greedy, DOTALL) takes first `{` to LAST `}`, then `json.loads` — recovers fenced JSON and JSON with surrounding prose, UNLESS trailing text after the fence contains another `}` (parse error) or there are no braces at all (no match → re-raise).
- Timeout (30 s), HTTP error (`raise_for_status`: 400/401/404/5xx), unparsable reply: all raise inside `extract()` — and `FrontStepExtractor.process/process_sync` catches EVERY exception and silently runs `_fallback_extract` instead. Nothing is logged anywhere.
- Different key names: unknown keys are ignored (`dict.get` everywhere); an `orbit` dict without a recognized `kind`/`semiMajorAxisKm`/`sma`/`value` key, or a `duration` without `value`, yields `needs_clarification` (missing `orbit`/`duration`). A `duration` object with `value: null` raises `TypeError` in `float(...)` — that escapes `process()` (the try only wraps `extract`) and becomes a hard `ExtractionError` in the pipeline, not clarification.
- Null values: treated as missing (`dryMassKg: null` → missing; `orbit: null` → missing; explicit nulls in numbers mostly coerce via `or 0`, except duration value / orbit value as above).
- Extra text around the JSON: handled by the greedy brace regex in the common case.
- Numbers as strings (`"500"`, `"7200"`): already accepted — every numeric read goes through `float(...)`.

(c) Where the fallback runs and whether it hides errors: `process()` lines 128-133 and `process_sync()` lines 134-139 — any exception from the real client falls back with zero logging. Worse, the fallback is not just a fallback: `Pipeline.__init__` builds `FrontStepExtractor()` with NO client, and nothing in the backend ever calls `get_extractor()`. So even with `EXTRACTOR_*` configured, the regex fallback is the ONLY thing that runs. That alone explains the reported symptom: the fallback regexes need `"<N> km circular"` (number BEFORE km BEFORE the word circular) and plural units (`days`, not `day`), while the sentence has "circular orbit at 400 km altitude" and "for 1 day" — hence missing `[orbit, duration]` without the model ever being asked.

## Step 2 - what changed

- `FrontStepExtractor.process/process_sync`: any exception from a configured extractor now logs ONE WARNING line (`extractor failed (<ClassName>); falling back to regex: <first 200 chars of message>`, no headers/keys) and only then falls back; success logs ONE INFO line with the returned field names (`extractor ok; fields: ...`). Deterministic regex behavior with no client configured is unchanged.
- `Pipeline.__init__`: when no extractor is passed explicitly, it now asks `get_extractor()` and wires it in only if it is a real `OpenAIExtractor` (i.e. env-configured). Without env vars the empty `MockExtractor` is ignored and the regex fallback stays the default, so all existing tests behave exactly as before.
- New tests: 12 fake-transport tests (`tests/test_extractor_client.py`: success, 400, 401, timeout, fenced reply, surrounding-text reply, null fields, null->clarification x2, string numbers, json_object flag on/off), 2 debug-script exit-code tests.

## Step 3 - parser hardening

- New `extract_json_object()`: strips fences, then takes the first balanced `{...}` object that parses (brace-aware, string/escape aware). No more greedy `.*` that could swallow trailing text.
- `deterministic_convert` no longer crashes on malformed model output: non-dict `duration`, null/non-numeric `duration.value`, and null/non-numeric orbit numbers for known kinds now yield `needs_clarification` (naming the field) instead of an uncaught `TypeError`.
- Numbers-as-strings already worked via `float()` and still do (covered by test). No synonym mapping was added: the prompt's key set is exactly the set the converter reads, so per the task rule there was nothing to map.

## Step 4 - JSON-mode setting

- `EXTRACTOR_JSON_MODE` (both settings branches + `.env.example`, default `"prompt"`): default sends no `response_format` (works with vLLM + Qwen out of the box); `"json_object"` sends `{"type": "json_object"}`. Both covered by tests asserting the request body.

## Step 5 - debug script

- `scripts/debug_extractor.py` reads only the three `EXTRACTOR_*` vars (missing => prints the NAME, exit 2; verified by unit tests and by hand). First call 300 s timeout, later calls 60 s. For each of the 6 sentences it prints the sentence, the raw reply (first 600 chars), the parsed fields, and the final ok/missing result, then writes `extractor_debug.json` with no secrets (verified: no URL, key, or env content in the file).
- Exact PowerShell to run it (from the repo root; PYTHONPATH needed so `scripts/` can import the backend):
  `$env:EXTRACTOR_BASE_URL='<host>'; $env:EXTRACTOR_API_KEY='<key>'; $env:EXTRACTOR_MODEL='<model>'; $env:PYTHONPATH='phase4_backend'; python scripts/debug_extractor.py [--out extractor_debug.json]`

## Step 6 - test counts and verdict

- `scripts/e2e_all.py` (with GMAT set for this shell only): tests/e2e 32 passed, tests 93 passed, orbitlab_core/tests 48 passed (+29 subtests), simulation_engine/tests 23 passed — **196 passed, 0 failed, 0 errors, exit 0**. Without GMAT: `tests/` = 95 passed + 16 skipped (the GMAT-gated e2e tests).
- Also fixed while here: `scripts/smoke_real_model.py` had an inconsistent Mars case (sent sma 4237.5 with e 0.2 = ~0.5 km periapsis altitude, contradicting its own "300 km" sentence); corrected both prompt and sent data to sma 4611.875 km (rp 3689.5 km = 300 km altitude), prompt text included.
- Could not verify: any live model behavior (no key, no endpoint here). The debug script is the instrument for that on your machine; the logging + parser changes were proven against fake transports covering every failure path in Step 1(b).
