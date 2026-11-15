# Docs audit report (`v1-docs`)

Read: `ARCHITECTURE.md`, `phase4_backend/RUNBOOK.md`, `phase4_backend/deploy_notes.md`,
`.env.example`, all `phase4_backend/*report*.md`, `phase4_backend/*_report.md`,
`phase4_integration_report.md`, `phase6_e2e_report.md`, root `README.md`,
against the code on this branch. Only claims that are no longer true are
listed below; point-in-time test counts in old task reports are history, not
errors, and are called out only where a report presents them as current.

## ARCHITECTURE.md (root)

- §A table: workspace path `C:\Users\canit\DevSwarmProjects\Orbitlab` is not
  this checkout; branch/commit `main`/`8be0961` "initial (empty tree)" is not
  current history; "Frontend/Backend not yet initialized" and "No build
  system/dependencies" are false (pyproject, backend, Main UI all exist);
  the GMAT path baked in is one machine's download folder.
- §C "Preliminary Experiment JSON Schema": lists only Earth/Moon/Mars and
  only `EarthMJ2000Eq`; the schema now covers 7 central bodies with
  per-body coordinate systems. Its stop-condition `value` cap (365 for all
  types) disagrees with the per-type caps in code (365 d / 8760 h /
  31536000 s / 365 periods).
- §D invocation shows `GmatConsole.exe --run <script> --exit`; the runner
  does not pass `--exit` (checked `simulation_engine/.../runner.py`).
  The "0.047 s" benchmark and the `Sat.Earth.*`-qualified ReportFile column
  list describe the original plan, not measured current output.
- §E workspaces: React/Vite UI that was never built (the UI is static
  HTML/JS + SVG/Canvas + vendored three.js; no Vite anywhere); workspace
  names do not match the repo layout.
- §H "current state": true as far as it goes, but stops before the Details
  tab, plots + maneuver table, 3D view, ground track, open in GMAT,
  realistic-cases runner, bundled GMAT, the `/sample-result` endpoint,
  `openInGmat`/`hasScript`/`mode` fields, and demo mode wiring; its report
  list omits the ~10 reports written since. Its `UIUX/orbitlab-live.html`
  reference is stale: that file no longer exists in `UIUX/` (only an
  untracked copy under `.devswarm-temp/`).

## phase4_backend/RUNBOOK.md

- Fixed this task: the "Open http://localhost:8000/ (live page) or
  .../orbitlab-live.html" line was dead (no such file is served; `/`
  302-redirects to the Main UI) and now reads "redirects to the Main UI".
  The `?mock=1` note was and is true. Otherwise current, including the
  newer sections (extractor json_schema, explainer, demo mode, cold starts,
  Open in GMAT with its warning, Getting GMAT with `tools/gmat` +
  `GMAT_PATH` fallback, realistic cases).
  No command in it mismatches a script flag (verified against
  `setup_gmat.ps1/.sh`, `realistic_cases.py`, `debug_extractor.py`,
  `smoke_real_model.py`, `e2e_all.py` argument parsers); the three
  `uvicorn` commands assume the repo root as CWD (stated once at the top;
  kept as-is).

## phase4_backend/deploy_notes.md

- Fixed this task: "`/` returns orbitlab-live.html" was false (`/`
  302-redirects to `/OrbitlabUI Main/`); the line now states the redirect
  and points at RUNBOOK for the newer routes. Mock-mode, CORS, `.env`, and
  `PYTHONPATH` notes were and are accurate.

## README.md (repo root)

- Almost entirely stale: React/Vite app that was never built; `import {
  createExperiment ... } from ui_adapter` is not the adapter's API (it
  exposes `globalThis.OrbitLabAdapter` + CommonJS `module.exports` with
  `runExperiment` et al.); `python -m pytest tests -v` from the repo root
  is the wrong CWD (backend suite runs from `phase4_backend/`) and drops
  the `-q`/`--tb` flags the suites use; branch `phase4-orchestration`
  does not exist; install/start commands lack `PYTHONPATH` and the demo
  path; env list is a subset (missing extractor/explainer/demo/GUI/bundled
  names); no mention of Details tab, plots, 3D, ground track, open in
  GMAT, demo mode, bundled GMAT, or realistic cases. Rewritten by this
  task (see Step 2 section below for the method, not the content).

## .env.example

- Complete: all 22 names read by `config.py` are present with empty values,
  none extra (verified programmatically). No change needed.

## Historical task reports (still true as history; stale only as present tense)

- `extractor_fix_report.md` Step 1(b–c): "nothing in the backend ever calls
  `get_extractor()`" and "`Pipeline.__init__` builds `FrontStepExtractor()`
  with NO client" were fixed by that same task (wired, then extended to
  any non-mock client for demo mode). Step 2's "ONE WARNING line" is now
  two lines in practice (client-side plus the kept front-step fallback
  line) — see `extractor_timeout_report.md`.
- `extractor_schema_report.md` Step 7 counts (129 passed, 216 total) are
  superseded by later runs (current: backend 197+28, Node 49, e2e_all 279).
- `ui_real_results_report.md` Step 1 ("after a real run ... keep showing
  Venus") and Step 6 (2-chart Graph, `n/a` period, no maneuver table) are
  superseded by that task's own Steps 2–4 plus v1-plots (4 charts,
  computed period, MANEUVERS section); Step 7 counts superseded.
- `explain_fallback_report.md` Step 1 (30 s, raw-dump prompt, no retry,
  `ExplainerError` fails runs) is the pre-fix snapshot; Steps 2–5 document
  what replaced it. Step 7 counts (144/231) superseded.
- `extractor_timeout_report.md` Step 1 (30 s default, no retry, no typed
  error) is the pre-fix snapshot; counts (154/241) superseded.
- `demo_mode_report.md` verification counts (166/17/265) superseded.
- `plots_report.md` verification counts superseded (Node/file counts grew).
- `view3d_report.md` Step 1 line numbers drifted; Step 6 "25 pass / three
  files" superseded (now five files, 49 Node tests).
- `details_tab_report.md` Step 5 "Node (all three files)" is stale
  (five files now); the rest is current.
- `phase4_report.md`: "ARCHITECTURE.md outdated" is itself outdated (§H now
  exists); "Known gaps: orbit-count conversion lacks period context" is
  resolved (OrbitPeriods passthrough); "Extractor fallback is regex
  minimal" understates the strict-schema parser + demo parser (regex
  remains the last resort); "How to run" lacks `PYTHONPATH`.
- `phase4_gmat_report.md` Step 3 (convert orbits to hours in the
  extractor) was explicitly reverted — `phase4_gmat2_report.md` Step 1
  documents the revert, so the pair is consistent only when read together.
- `phase5_ui_report.md`: Step 1(b) "Main app.js fakes everything", Step 2
  "`/` → orbitlab-live.html", and Unsure (2) ("wired orbitlab-live, not
  the Main UI") are all inverted by later work; `orbitlab-live.*` no
  longer ships in `UIUX/`. Counts are historical.
- `phase5_main_ui_report.md`: "Main UI shows n/a for orbital period" (now
  computed), "Graph JSON+polyline" (now 4 labelled charts), counts
  historical. Steps 2–4 otherwise match the current wiring.
- `phase6_e2e_report.md` (root) and `phase4_integration_report.md` (root):
  historical merge/test records; coverage lists predate the demo,
  timeout, fallback, script-route, open-in-gmat, plots, view3d,
  ground-track, bundled-gmat, and realistic-cases suites.
- `final_merge_report.md`: historical; its "success NOT reachable through
  mock interpreter + regex fallback" predates demo mode (DemoExtractor +
  DemoInterpreter reach success with no keys).
- `realistic_cases_results.md`: current (generated 2026-11-15; the two
  FAILs are recorded verdicts, see that report).
- `bundled_gmat_report.md`, `ground_track_report.md`, `open_in_gmat_report.md`:
  current; no stale claims found. (`bundled_gmat_report.md` duplicates one
  bullet — Step 1 lists the `app.py resolve_gmat_gui` line twice;
  cosmetic, noted here instead of editing another branch's report.)
- `phase5_real_model*.md`, `phase4_gmat2_report.md`, `phase5_long_runs_report.md`:
  historical measurements/decisions, no current-state claims to correct.
- `phase5_ui_smoke.png` exists (`phase4_backend/phase5_ui_smoke.png`,
  referenced by `phase5_ui_report.md`); `scripts/ui_smoke.py` opens `/`,
  which now serves the Main UI, not the live page its comments describe —
  flagged, not changed (test tooling is out of scope for this task).

## Verification and unsure (run for this report, 2026-11-15)

- Node (`node --test tests/plots.test.cjs tests/ui_helpers.test.cjs
  tests/ui_render.test.cjs tests/view3d.test.cjs tests/groundtrack.test.cjs`,
  repo root): 49 pass, 0 fail.
- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 197 passed
  + 28 skipped (GMAT-gated skips).
- Core / sim (repo root): 48 passed + 29 subtests / 23 passed.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell only: tests/e2e 49,
  tests 176, orbitlab_core/tests 48, simulation_engine/tests 23 —
  296 passed, 0 failed, exit 0.
- Live check of the new README/RUNBOOK demo commands: server booted
  exactly as documented (`ORBITLAB_DEMO_MODE=true`,
  `PYTHONPATH='phase4_backend'`, repo root as CWD), `/api/health`
  returned `{"status":"ok","mode":"demo"}`, and a POSTed Moon prompt ran to
  success with `hasScript: true` and a 200 `text/plain` script response;
  unknown id returned 404. Server stopped afterwards (port verified closed).
- `bash -n` passes on `scripts/setup_gmat.sh`; `setup_gmat.ps1` parses
  (PowerShell AST). Neither downloader was executed (would fetch a
  multi-hundred-MB archive and, for the .sh, needs a Unix shell).
- Unsure: the Open-in-GMAT `--run` flag was never exercised against a real
  GMAT GUI here (documented as-is in the new report); the `openInGmat`
  button path is covered only by stub-DOM Node tests, like the rest of the
  UI; `phase5_ui_smoke.png` is referenced but was generated long ago
  against a different UI.
