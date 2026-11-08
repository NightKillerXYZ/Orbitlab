# Extractor schema report (`fix-extractor`)

## Step 1 — what the converter reads today (read-only)

`FrontStepExtractor.deterministic_convert` (`phase4_backend/orbitlab_backend/frontstep/extractor.py`) reads:

- `centralBody` (string; must be a key of `BODY_RADII_KM`, else `needs_clarification ["centralBody"]`).
- `dryMassKg` (number or numeric string via `float()`; `None`/missing → `needs_clarification ["dryMassKg"]`).
- `orbit`: dict with `kind` in `semiMajorAxisKm | circularAltitudeKm | circularAltitude | periapsisAltitudeKm | apsisAltitudes | apoPeriRadii | circularRadiusKm`, carrying `value` (+ `unit` in km/miles/m/AU, default km) and `eccentricity` where applicable; or fallback dict keys `semiMajorAxisKm` / `sma` (+ `eccentricity`); or a bare `{"value": N}` (treated as circular-altitude); anything else → `needs_clarification ["orbit"]`. `cartesian` dict bypasses orbit math (`sma=None`).
- `eccentricity` (top-level or inside orbit; number, numeric string, or `{value, unit:"rad"}` dict).
- `inclinationDeg`, `raanDeg`, `argumentOfPeriapsisDeg` (or alias `aopDeg`), `trueAnomalyDeg` (number, numeric string, or rad-dict; default 0).
- `duration` dict `{"value", "unit"}` (unit lowercased; seconds/minutes->`ElapsedSeconds`, hours->`ElapsedHours`, days->`ElapsedDays`, orbit-ish->`OrbitPeriods`; non-dict / null value / unknown unit now → `needs_clarification ["duration"]`).
- `integrator` (`RungeKutta89`|`PrinceDormand78`, else default `RungeKutta89`); `forces` passed through untouched; `maneuvers` list passed through untouched.
- Maneuver shapes the converter reads (front-step form, NOT validator form): `Hohmann {type:"Hohmann", id, targetOrbitRadiusKm, apsis: periapsis|apoapsis, targetEccentricity?}` and `ImpulsiveBurn {type:"ImpulsiveBurn", id, trigger: ElapsedTimeSecs|AtApoapsis|AtPeriapsis, elapsedSecs?, apsis?, deltaV:[x,y,z]}`. The `verify` step maps these onto `TargetedHohmannTransfer`/`ImpulsiveBurn` validator objects.
- Names: previously read `experimentName`/`spacecraftName` from the model output when present. Removed (Python owns names: always generated + sanitised).

`_fallback_extract` regexes (`_fallback_extract` in the same file): body keyword; `dryMass` from `(\d) kg`; orbit only from `N km circular` -> circular-altitude, `altitude N km` (+ optional `e N`) -> periapsis-altitude, or `sma N`; `eccentricity N`; duration from `propagate ... N <unit>` or `for N <unit>` with units hours|days|seconds|minutes|orbit(s)|(orbital )period(s); integrator from "prince"/"runge" keywords. Anything else (e.g. "400 km altitude" order, singular "day") yields missing fields.

## The exact cause (Step 1 reproduction)

Feeding the six real model replies through the shared path (`process` -> normalize -> convert) fails every one with `missing ["orbit"]`: the debug script bypassed `normalize_extracted` and handed the raw model dict straight to `deterministic_convert`, whose legacy branch only reads `value` (not the schema's `valueKm`) key. The model output was correct all along - the script was testing a path the pipeline never uses. Fix: one shared code path - `normalize_extracted` runs inside `FrontStepExtractor.process`/`process_sync` for every caller (pipeline, debug script, tests); `OpenAIExtractor.extract` returns the parsed reply and records `last_raw`/`last_parsed` for display. Verified with a 6-fixture test file through `process()`/`process_sync`: tolerant shapes clarify or convert exactly as specified.

## Step 2 - what changed (strict schema + normalizer + json_schema mode)

- `OpenAIExtractor` sends the SAME `messages` shape as before; new `EXTRACTOR_JSON_SCHEMA` const (all keys required, `additionalProperties: false`, nullable `type: [...]` unions; `maneuvers` items fully specified) is sent only when `EXTRACTOR_JSON_MODE=json_schema`, as `{"type":"json_schema","json_schema":{"name":"orbitlab_extraction","strict":true,"schema":<schema>}}`. `prompt` (default) sends no `response_format`; `json_object` sends `{"type":"json_object"}` as before. A 400/422 from a strict endpoint surfaces as an HTTP error, is logged once as a WARNING, and falls back to the regex path with no retry loop.
- New `normalize_extracted()` maps EITHER the strict schema output OR observed tolerant shapes into the converter's existing input shape, without inventing values: `quantity` altitude|periapsis_altitude|semi_major_axis|radius become `circularAltitudeKm|periapsisAltitudeKm|semiMajorAxisKm|circularRadiusKm` (unit always km); unknown `kind` values with a `values` dict are interpreted (`periapsisAltitudeKm`/`semiMajorAxisKm` keys) or passed through for the converter; bare `{"kind":"circular","values":...}` is left untouched so the converter asks for clarification (see below); `duration` accepts a dict, a bare number (unit taken from a sibling key if present, else clarified), or strings like "3 hours"/"5 orbits"/"90 minutes" (minutes convert to seconds, the one documented exception); hohmann free text ("Hohmann transfer to 9000 km at periapsis") becomes a Hohmann dict (default apsis periapsis, documented); unknown maneuver shapes pass through for honest downstream failure; `""`, `"unnamed"`, `"none"`, `"null"` strings become null.
- `deterministic_convert` no longer reads model-provided names at all: names are always generated by `_safe_defaults` + sanitized (Python owns names, verified by `test_names_always_generated`). A `duration` with missing/non-string unit now yields `needs_clarification ["duration"]` instead of silently assuming hours. A `{"kind":"circular"}` orbit without an explicit semi-major axis yields `needs_clarification ["orbit.quantity (is it an altitude or a radius?)"]` instead of guessing altitude.

## Step 3 - system prompt

Rewritten in `extractor_client.py` as one `SYSTEM_PROMPT` constant: strict schema, the four quantity meanings (altitude = surface height of a circular orbit; periapsis_altitude = lowest point; semi_major_axis = stated sma; radius = centre distance, equal to sma for circular), copy-exactly/no-compute/no-convert-except-unit-field/null-instead-of-inventing rules, an explicit bare-circular rule (altitude only if the sentence says altitude/height, radius only if it says radius/distance-from-centre, else null orbit), a no-names rule, and 7 few-shot user/assistant pairs with numbers deliberately different from the six debug sentences (except the Hohmann shape).

## Step 4 - json_schema mode + RUNBOOK

`EXTRACTOR_JSON_MODE=json_schema` sends the schema above; `prompt` (default) and `json_object` unchanged. `.env.example` already lists the variable (names only, empty). `RUNBOOK.md` "Extractor setup" now documents all three modes and tells vLLM+Qwen users to stay on `prompt`, noting the single WARNING + regex fallback on 400/422 with no retries.

## Step 5 - tolerant cases covered

Bare `{"kind":"circular","values":...}` (number or single-element list) is deliberately NOT converted - the converter asks which quantity it is. Numbers as strings pass through (`float()` downstream). Unknown keys are ignored by `dict.get` reads everywhere; the strict schema additionally forbids them server-side.

## Step 6 - new tests (all in `tests/test_extractor_schema.py`, 20 total)

Tolerant fixtures (observed shapes): s1/s4/s6 bare-circular + s5 list-value clarify with the exact message; s2 periapsis-dict converts (a=4611.875, e=0.2); s3 sma-dict converts (a=9000, e=0.05, inc 30, OrbitPeriods 5); hohmann free text parses; "90 minutes" -> 5400 s ElapsedSeconds; null duration -> needs_clarification; unknown keys ignored. New-schema end-to-end for all six debug sentences (s1 a=6778.136 e=0 1 day; s2 a=4611.875 e=0.2; s3 a=9000 e=0.05 inc 30 OrbitPeriods 5; s4 a=6528.136 inc 4 12 h; s5 a=1837.4 6 h; s6 radius 7000 e=0 Hohmann M1 AtPeriapsis 9000 2 days). Plus: names always generated; json_schema body shape; no `response_format` under `prompt`; sync `process_sync` path uses the same normalizer.

## Step 7 - debug script + verification

`scripts/debug_extractor.py` (unchanged wire-up) now prints, per sentence: the sentence, the first 600 chars of the raw reply, the parsed schema fields, and the converter result (a, e, inclination, duration) or the missing list. Run it yourself with:

```powershell
$env:EXTRACTOR_BASE_URL='<host>'; $env:EXTRACTOR_API_KEY='<key>'; $env:EXTRACTOR_MODEL='<model>'; $env:EXTRACTOR_JSON_MODE='json_schema'; $env:PYTHONPATH='phase4_backend'; python scripts/debug_extractor.py [--out extractor_debug.json]
```

(Test counts below were produced WITHOUT a model: backend `../tests` 129 passed + 16 skipped (GMAT-gated e2e); with GMAT set: `scripts/e2e_all.py` reports tests/e2e 32, tests 113, orbitlab_core/tests 48 (+29 subtests), simulation_engine/tests 23 — 216 passed, 0 failed, exit 0.)
