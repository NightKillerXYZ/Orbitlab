# Phase 5 Main-UI wiring (`phase5-main-ui-wiring`, from `phase5-ui-wiring-v2`)

Setup: `git branch -a` run first; new branch created from `phase5-ui-wiring-v2`.
Backend tests from inside `phase4_backend` (`python -m pytest ../tests -q`): **61 passed** before starting.
Core/sim suites run from repo root with the same commands as `phase4_integration_report.md`.

## Step 1 — how the live page works + every fake in Main (read-only)

How `orbitlab-live.js` drives `ui_adapter.js` (the pattern reused below):
- `adapter.runExperiment(text, onEvent)` (POST then WS; the adapter itself polls `GET /api/experiments/{id}` every 2 s if the socket drops).
- `onEvent` folds events into per-stage states (`stageStates`) for the 8-stage strip; `model_warming_up` shows the warming line.
- Final success → orbit polyline from `result.trajectory.points` (scaled to viewBox), telemetry ministats, Understood rows from `result.experiment`, Outcome rows + validator warnings, Graph = experiment JSON, Physics = `result.explanation`.
- Final failure → `error.stage`, readable `error.message`, `error.code`, `error.explanation` (top-level or `details.explanation`); never raw JSON/stack. 60 s without final → "still simulating…" notice; empty submit ignored; button not locked (live page has no busy lock).

Every function in `OrbitlabUI Main/app.js` that fakes data, and what it fills:
- `runScenario(prompt)` — keyword regex invents velocity/period/shape/outcome; fills Chat panel (`scenarioMarkup` chips via `renderTab('Chat')`), Results tab metrics (period/shape/velocity/outcome), and a toast. **Replaced with real adapter calls.**
- `scenarioMarkup(run)` — renders the invented chips in Chat. **Replaced with real stage/result markup.**
- `exportCSV()` — synthesizes 16 rows of Venus telemetry (0.723 AU, 35.0 km/s); downloaded via `#exportBtn` and Results `#resultsExport`. **Replaced with real last-run telemetry; disabled with tooltip when no finished run.**
- Static `content` object — hardcoded Chat welcome/suggestions, Understanding primer, Results baseline (224.7 d, 35.0 km/s, "Stable orbit"), Graph fixed SVG path, Physics values (Sun mass, 108.2 Mkm, 35.0 km/s). Kept for `?mock=1` and as the pre-run baseline; live results now override the same panes.
- Sim loop (`renderTime` + `setInterval`, Venus 224.7-day CSS animation, `#simTime`, `#timelineFill/Knob`, `#venusPlanet`, `#speedMetric`, `#captionSpeed`, telemetry row) — ambient mission animation, kept; on success the numeric metrics are overwritten with real values (speed, avg distance, eccentricity; period shows "n/a" when the result carries none).
- Note: `.suggestion` buttons are currently dead (bound once before first render; `renderTab` replaces them). Fixed via delegation in the panel click handler.
