# Both Extract crash and Verify Mismatch Report

Investigate-then-fix task: `scripts/repro_verify_mismatch.py` sends four
prompts through the real extractor (`FrontStepExtractor.process`, async, the
same call the pipeline makes) and then the real HTTP interpreter
(`interpret_prompt`), printing both outputs side by side. Endpoint credentials
come from the environment only and are never printed (presence check only).

## Part 1 — Verify-stage 400 vs 400000 unit mismatch (investigation only)

No pipeline, model, dataset, or schema code was changed for this part.

### Result: mismatch reproduced on 1 of 4 prompts

Prompt: **"500 kg satellite around Earth, circular 400 km, 2 days,
sun-synchronous"**

- Extractor output: `"semiMajorAxisKm": 400.0` (it kept the 400 km altitude
  as the semi-major axis instead of adding the body radius: 400 + 6378.14 =
  6778.14 km), `inclinationDeg: 98.2`, duration 2 days. Status ok.
- Canonical prompt handed to the interpreter:
  `... semi-major axis 400.000 km ... inclination 98.2 degrees ...`.
- Interpreter output: `"semiMajorAxisKm": 400000.0` (same other elements).
- Ratio extractor/interpreter = **0.001 — a 1000x unit mismatch**.
- A verify stage comparing these two would raise `interpreter_mismatch`
  (`stage: "verify"`) and stop the run — exactly the reported symptom.

The other three prompts did **not** mismatch:

- *"500 kg satellite around Earth, circular 400 km, 1 day"* (no
  sun-synchronous): extractor wrote the correct `6778.1363`; interpreter
  returned `6778.136`; ratio 1.0000000443 (float noise only). The altitude→
  semi-major-axis handling differs between the two phrasings: the
  sun-synchronous variant skipped adding the body radius.
- *"500 kg satellite around Venus, semi-major axis 9000 km, 1 day"*:
  9000.0 vs 9000.0, ratio exactly 1.0.
- *"500 kg satellite around Earth, 500 km altitude, burn at apoapsis to
  800 km, 1 day"*: the extractor itself raised
  `TypeError: cannot unpack non-iterable NoneType object` — an extract-stage
  failure, so no interpreter output exists and no verify comparison happens.
  (This crash is Part 2 of this report.)

So the 400-vs-400000 site is: **extractor emits `400.0` (km altitude, not a
semi-major axis) into the canonical prompt; the interpreter returns
`400000.0` for that slot** — consistent with a km→m ×1000 slip on the
interpreter side (its schema unit is km). Which side "caused" it cannot be
decided from outside the models: the extractor text ("400.000 km") is
self-consistent but physically wrong for a 400 km circular orbit, and the
interpreter amplified it by 1000. Both observations above are single-run
results (temperature 0); reruns may vary in wording but the recorded numbers
stand as observed.

### Side observations (not changed, recorded for follow-up)

- With no configured endpoint (`FrontStepExtractor()` default client) the
  deterministic fallback cannot parse any of the four prompts
  (`missing: ['duration', 'orbit']`); only the real endpoint path was used
  for the numbers above.
- First probe runs predate the final script: an early version called the
  sync extractor inside the async loop and only proved the endpoint was
  reachable; all numbers in this report come from the final async
  `process()` + `interpret_prompt()` path, identical to the pipeline's.

## Part 2 — Extract-stage crash: `TypeError: cannot unpack non-iterable NoneType object`

### Trigger

Prompt: **"500 kg satellite around Earth, 500 km altitude, burn at apoapsis
to 800 km, 1 day"** (real extractor, key from the environment only).

### Traceback (absolute path prefixes trimmed to the repo root)

```
Traceback (most recent call last):
  File "scripts/repro_verify_mismatch.py", line 15, in main
    res = await ex.process(...)
  File "phase4_backend/orbitlab_backend/frontstep/extractor.py", line 216, in process
    res=self.deterministic_convert(normalize_extracted(extracted), user_text)
  File "phase4_backend/orbitlab_backend/frontstep/extractor.py", line 202, in deterministic_convert
    prompt=build_canonical_prompt(normalized)
  File "phase4_backend/orbitlab_backend/frontstep/prompt_builder.py", line 102, in build_canonical_prompt
    v,n,b = m.get("deltaV",[0,0,0])
TypeError: cannot unpack non-iterable NoneType object
```

The live model returned a maneuver the extractor normalized to:

```json
{"type": "impulsive_burn", "trigger": "apoapsis", "targetRadiusKm": 800,
 "elapsedSecs": null, "deltaVKmS": null}
```

### Root cause

Neither a function wrongly returning `None` nor a malformed model output:
the extractor output is a **legitimate shape** — an apoapsis burn specified
by target radius with no explicit delta-V vector. The normalizer records
that faithfully as `deltaV: None`, and `verify.py` explicitly treats `None`
as "do not check the vector", so `None` is meaningful pipeline state, not
an error. The bug is the consumer: `prompt_builder.py` unpacked
`m.get("deltaV", [0, 0, 0])` unconditionally, and the `[0, 0, 0]` default
only covers a *missing* key, never an explicit `None`.

### Fix (no exception-swallowing; no invented physics)

In `build_canonical_prompt`, an ImpulsiveBurn with a missing, `None`, or
malformed `deltaV` is now described *without* a vector
(`At the next apoapsis, apply the LocalVNB burn.`) instead of being
unpacked. Real 3-vectors render exactly as before, so all pre-existing
vector output is byte-identical. A `None` vector stays `None` downstream,
preserving the verify stage's skip-the-check semantics.

### The other prompts, checked for the same crash

- Venus semi-major-axis prompt: no maneuvers at all, unaffected path;
  covered by a regression test (`status == "ok"`).
- Elapsed-time burns and malformed vectors (short list, string, dict):
  covered by regression tests — all render without a vector, never crash.

## Part 3 — Safety net for unexpected stage failures (item 5)

`api/app.py::run_job` tracks the last stage seen on the event callback; any
exception escaping `pipeline.run` (i.e. anything that is not already a typed
`PipelineError`) becomes
`{"code": "internal_error", "stage": <last seen stage or "unknown">,
"message": <plain sentence>}` — "Something went wrong while reading your
request (stage: extract). Please try rephrasing." for extract, and
"Something went wrong while running this step (stage: X). Please try again
or rephrase the request." otherwise. The full traceback goes to the server
log only via `logger.exception`; no Python internals, keys, or endpoint
details ever reach the user payload. The desktop UI chat shows the message
verbatim for `internal_error` (no "Run failed at" prefix, since the message
is already complete).

## Part 4 — Verification and counts

- New regression tests (`tests/test_maneuver_no_deltav.py`, 5 tests): the
  exact recorded maneuver shape through the async-equivalent sync path ends
  `status == "ok"` with an apoapsis sentence and no `"None"` text; elapsed
  burns without vectors, malformed vectors, and the unaffected Venus
  semi-major-axis case are covered.
- New safety-net tests (`tests/test_internal_error.py`, 9 tests): a raw
  `RuntimeError` is forced in each of the 8 stages plus the no-event case;
  each asserts the typed shape, the plain message, and the absence of raw
  text/tracebacks.
- Updated one pre-existing assertion that locked in the old raw-message
  contract (`test_review_fixes.py::test_background_task_failure_marks_job_failed`
  now expects `internal_error` without the raw message).
- Counts: backend **257 passed, 0 failed** (incl. 14 new);
  Node (existing invocation, all files) **78 passed, 0 fail** (incl. 4 new:
  3 failure-chat/failed-run tests + 1 internal_error chat test);
  `scripts/e2e_all.py` (GMAT_PATH from the shell only): tests/e2e **49**,
  tests **208**, orbitlab_core **48**, simulation_engine **23** —
  **328 passed, total failed+errors 0**.
- The desktop UI chat shows the plain internal_error sentence verbatim
  (`app.js` branch added; no "Run failed at" prefix since the message is
  already complete).
