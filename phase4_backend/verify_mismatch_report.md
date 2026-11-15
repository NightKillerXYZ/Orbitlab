# Verify-stage 400 vs 400000 unit mismatch (`scripts/repro_verify_mismatch.py`)

Investigate-only task: no pipeline, model, dataset, or schema code was changed.
Probe script lives at `scripts/repro_verify_mismatch.py`; it sends four
prompts through the real extractor (`FrontStepExtractor.process`, async, the
same call the pipeline makes) and then the real HTTP interpreter
(`interpret_prompt`), printing both outputs side by side. Endpoint credentials
come from the environment only and are never printed (presence check only).

## Result: mismatch reproduced on 1 of 4 prompts

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

So the 400-vs-400000 site is: **extractor emits `400.0` (km altitude, not a
semi-major axis) into the canonical prompt; the interpreter returns
`400000.0` for that slot** — consistent with a km→m ×1000 slip on the
interpreter side (its schema unit is km). Which side "caused" it cannot be
decided from outside the models: the extractor text ("400.000 km") is
self-consistent but physically wrong for a 400 km circular orbit, and the
interpreter amplified it by 1000. Both observations above are single-run
results (temperature 0); reruns may vary in wording but the recorded numbers
stand as observed.

## Side observations (not changed, recorded for follow-up)

- With no configured endpoint (`FrontStepExtractor()` default client) the
  deterministic fallback cannot parse any of the four prompts
  (`missing: ['duration', 'orbit']`); only the real endpoint path was used
  for the numbers above.
- The apoapsis-burn prompt crashes extraction with a bare `TypeError`
  (surfacing as a generic extraction failure, never reaching verify).
- First probe runs predate the final script: an early version called the
  sync extractor inside the async loop and only proved the endpoint was
  reachable; all numbers in this report come from the final async
  `process()` + `interpret_prompt()` path, identical to the pipeline's.

## Verification (item 4 follow-up + item 5)

- The crash is fixed at its root in `prompt_builder.py`: burns with
  `deltaV: None` (or malformed vectors) are described without an invented
  vector instead of being unpacked. Pre-existing vector-present output is
  byte-identical (existing `test_prompt_builder.py` vector assertions pass
  unchanged).
- New regression tests (`tests/test_maneuver_no_deltav.py`, 5 tests): the
  exact recorded maneuver shape through the async-equivalent sync path ends
  `status == "ok"` with an apoapsis sentence and no `"None"` text; elapsed
  burns without vectors, malformed vectors, and the unaffected Venus
  semi-major-axis case are covered.
- Safety net (`api/app.py::run_job`): any unexpected exception in any stage
  becomes `{"code": "internal_error", "stage": <last seen stage>|"unknown",
  "message": <plain sentence>}`; the traceback goes to the server log only
  via `logger.exception`. New `tests/test_internal_error.py` forces a raw
  `RuntimeError` in each of the 8 stages plus the no-event case and asserts
  the typed shape and the absence of raw text.
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
