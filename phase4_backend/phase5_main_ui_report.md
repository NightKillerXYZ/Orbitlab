# Phase 5 Main-UI wiring (`phase5-main-ui-wiring`, from `phase5-ui-wiring-v2`)

Setup: `git branch -a` run first (no branch created blindly; `phase5-main-ui-wiring` did not exist).
Backend tests from inside `phase4_backend` (`python -m pytest ../tests -q`): **61 passed** before starting (58 carried over + 3 static-UI tests from the v2 task).
Core/sim suites run from repo root with the same commands as `phase4_integration_report.md`.

## Step 1 — read-only: how the live page works + every fake in Main

Live-page pattern reused verbatim: `adapter.runExperiment(text, onEvent)` (POST then WS; the adapter polls `GET /api/experiments/{id}` every 2 s if the socket dies), stage strip from WS events, `model_warming_up` line, orbit polyline from `result.trajectory.points`, Understood/Outcome/Graph/Physics panes from the payload, failure = `stage` + readable `message` + `error.explanation`, 60 s notice, empty-submit guard.

Fake-data functions in `OrbitlabUI Main/app.js` (all replaced or retired, mock path keeps them):
- `runScenario()` — keyword-regex invented velocity/period/shape/outcome; filled Chat (via `scenarioMarkup`), Results metrics, toast. Renamed intact to `runScenarioMock()`; the live `runScenario()` posts to the backend and fills the same elements with real values.
- `scenarioMarkup()` — invented result chips. Replaced by live Chat markup (real numbers or `n/a`).
- `exportCSV()` — 16 rows of synthetic Venus telemetry. Renamed intact to `exportSampleCSV()` (mock only); live `exportCSV()` exports real `trajectory.points` and refuses with a toast when there is no finished run.
- Static `content` object — hardcoded welcome/suggestions, baseline Results (224.7 d, 35.0 km/s, "Stable orbit"), fixed Graph SVG, Physics values. Kept for `?mock=1` and as the pre-run baseline; live panes override it after a real run.
- Venus sim loop + `renderTime` — ambient animation kept; numeric telemetry cells are overwritten with real values on success (speed, mean distance, eccentricity; period shows `n/a` since no result carries one).
- Also fixed (dead code found while reading): `.suggestion` buttons never fired (bound before first render, then replaced); clicks are now delegated in the panel handler.

## Steps 2–7 — implementation

- `index.html`: `<script src="../ui_adapter.js"></script>` before `app.js`. One adapter copy only (served by the backend at `/ui_adapter.js`).
- `app.js`: `useMock()` (adapter missing or `?mock=1` → sample stays, zero network). Live path mirrors `orbitlab-live.js`: stage progress card in Chat, `runExperiment` + 2 s adapter polling, success renders real orbit stats/telemetry/Graph JSON+polyline/Physics explanation + latest-run Understanding numbers; failures show stage/message/explanation (escaped, never stack/JSON); needs_clarification lists missing fields; 60 s "Still simulating - this can take a few minutes." banner + toast; empty text toasts and refocuses; submit controls disabled mid-run; `#exportBtn`/`#resultsExport` disabled with tooltip until a finished run exists.
- Backend `GET /main` → `RedirectResponse("/OrbitlabUI%20Main/")` (trailing slash keeps relative css/js/assets working; no extra routes, no backend code exposed). `/`, `/api/*`, `/ws/*`, live page untouched.
- `orbitlab-live.html` / `orbitlab-live.js`: **not edited**.
- Tests: `tests/test_static_ui.py::test_main_page_redirect_and_assets` — `/main` redirects, Main page/css/js return 200, adapter tag present.

## Step 8 — verification (no Playwright: not installed, nothing installed)

- Backend: **62 passed** from `phase4_backend` (61 + 1 new). Core: **48 passed + 29 subtests**. Simulation-engine: **23 passed**. Total **133 + 29 subtests, 0 failed**.
- Live server (mock switches ON, no keys): `/OrbitlabUI%20Main/` + css + js + `/ui_adapter.js` all 200; served `app.js` contains the full live path (`runScenarioMock`, `useMock()`, `runExperiment`, 60 s notice, export lock, busy lock); index references the adapter. Same submit→WS→final flow the Main page uses was proven over real HTTP on the v2 task (final `verify/interpreter_mismatch` with explanation, since the fixed mock returns i=28.5 which the regex fallback cannot reproduce).
- Could not check: real browser interaction (clicking Send, watching stages paint, screenshot) — needs Playwright + browsers, absent here. `scripts/ui_smoke.py` covers the live page; an equivalent Main-page script was not added (same flow, same adapter).

## Run command + unsure

- Start: `$env:ORBITLAB_USE_MOCK_INTERPRETER='true'; $env:PYTHONPATH='phase4_backend'; python -m uvicorn orbitlab_backend.api.app:app --port 8000` → app at http://localhost:8000/, Main UI at http://localhost:8000/main, live page at `/`.
- Changed: `UIUX/OrbitlabUI Main/index.html` (adapter tag), `.../app.js` (live wiring), `api/app.py` (`/main`), `tests/test_static_ui.py` (Main test). `orbitlab-live.*` untouched.
- Unsure: (1) Main page shows `n/a` for orbital period — no result field carries it and inventing one is banned. (2) A failed run leaves the previous successful numbers in place. (3) `file://` use of Main shows the sample (adapter missing → mock), same graceful fallback as the live page.
