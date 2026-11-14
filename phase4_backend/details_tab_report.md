# Details tab report (`v1-details-tab`)

## Step 1 — where the script lives today (read-only)

- The compiled GMAT script exists only as an in-memory string: `pipeline.py`
  builds `script = self.compiler.compile_to_string(experiment_obj)` at the
  compile stage and passes it to `GmatExecutionRequest(compiled_script=...)`.
  `GmatRunner.execute` (`simulation_engine/.../runner.py:82-91`) writes it to
  `<sandbox>/experiment.script` inside a `TemporaryDirectory`, which is
  deleted when the run finishes. Nothing is kept afterwards.
- There is no per-run output folder today: `get_run_root()` (`api/
  run_cleanup.py`, `<tmp>/orbitlab-runs` unless `ORBITLAB_RUN_DIR` is set) is
  only used for age-based cleanup at startup and after each job. The job
  store (`api/store.py`) is in-memory only and keeps `result`/`error`/`events`
  per job id. `run_job` (`api/app.py`) stores the pipeline result as-is.
- Results are served by `GET /api/experiments/{id}` (`api/app.py`) from the
  in-memory store (404 when the id is unknown). `result.experiment` is the
  full experiment JSON: `version`, `experimentName`, `spacecraft{name,
  dryMassKg, coefficientOfDrag, dragAreaM2, coefficientOfReflectivity,
  srpAreaM2}`, `centralBody`, `epoch{format, value}`, `initialOrbit{type,
  coordinateSystem, elements{semiMajorAxisKm, eccentricity, inclinationDeg,
  raanDeg, argumentOfPeriapsisDeg, trueAnomalyDeg}}` (or Cartesian elements),
  `forceModel{gravityDegree, gravityOrder, pointMasses[], atmosphericDrag
  {enabled, model}, solarRadiationPressure}`, `maneuvers[]`,
  `propagation{integrator, stopCondition{type, value}, stepSizeSecs}`.

## Steps 2–3 — implementation (done)

- `pipeline.run` adds `"script"` (the compiled GMAT string) to the success
  result — additive only; the cached result keeps it so a cache-hit rerun
  writes its own per-job file too.
- `run_job` (api/app.py) persists `<run_root>/<jid>/experiment.script` on
  success (server-generated jid only, fixed file name) and sets
  `result["hasScript"]=True`. Failures write nothing (extract failures have
  no script; the error payload already carries the explanation). Old run
  folders are still cleaned by the existing retention pass. No other
  behaviour changed.
- `GET /api/experiments/{jid}/script` returns `text/plain`: unknown id → 404
  (checked against the in-memory store before touching disk), missing file →
  404, and any id containing `/`, `\` or `..` is rejected up front — the
  filesystem path is built only from the server-side job id plus the fixed
  file name, never from client text.
- Details tab (new `Details` button next to Physics; `tabs` array extended —
  it was write-only): experiment JSON pretty-printed read-only in a
  monospace scroll box (`.json-block`, existing palette) + Copy button;
  GMAT script fetched lazily from the endpoint (loading → text + Copy, or
  "No script available for this run" on 404/failure/fixture runs without a
  job id); the model/verify notice; static `content.Details` fallback before
  any run. Copy uses `navigator.clipboard` with a textarea+execCommand
  fallback and toast feedback, via a delegated `data-copy` handler.
- `ui_adapter.js runExperiment` now also resolves `{events, result, id}` /
  `{events, error, id}` so the UI learns the job id (mock id `mock-id`
  flows through unchanged).
- Footer: one muted line at the bottom of the right panel
  (`.app-footer`, in-flow, never covers controls):
  "OrbitLab is a research and education tool. Review the generated script
  and results before relying on them. Not for flight operations."

## Step 4 — tests (done)

- `tests/test_script_route.py` (3, real pipeline + synthetic trajectory + demo
  parser, no GMAT, isolated `ORBITLAB_RUN_DIR`): 200 with the exact script
  text — byte-identical to an independent `GmatScriptCompiler` recompile of
  the served experiment — plus `content-type: text/plain` and `hasScript`;
  404 for unknown id, `/../x`, `/.`; 404 for a run with no script
  (needs_clarification job writes nothing).

## Step 5 — Node tests (done)

- `ui_render.test.cjs` (+4, fake DOM): Details renders escaped JSON
  read-only; script loading → success → error states (fetch stubbed,
  job id asserted in the route); copy handler called for experiment and
  script (fallback path); index page has the Details tab button and the
  research footer text.

## Verification and anything unsure

- Node (all three files): 29 pass.
- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 169 passed + 28 skipped.
- Core / sim (repo root): 48 (+29 subtests) / 23 passed.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell: tests/e2e 49, tests 148,
  orbitlab_core/tests 48, simulation_engine/tests 23 — 268 passed, 0 failed.
- Unsure: script persistence was verified through the API with the synthetic
  trajectory path (no GMAT in this shell run — the task's e2e_all did run
  GMAT, but the script-file assertions live in the backend suite); cache-hit
  reruns share the cached `script` text, which is correct only because the
  cache key is the prompt hash; `hasScript` is absent (not false) when no
  file was written.
