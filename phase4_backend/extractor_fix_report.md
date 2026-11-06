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
