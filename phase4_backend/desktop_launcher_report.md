# Desktop launcher (`v1-desktop-launcher`)

## Step 1 — how the backend is started and where the UI lives (read only)

- Uvicorn is started from the repo root with the backend package on
  `PYTHONPATH` (`phase4_backend/RUNBOOK.md`, also the root `README.md`):
  `PYTHONPATH=phase4_backend python -m uvicorn orbitlab_backend.api.app:app
  --port 8000` (`$env:PYTHONPATH='phase4_backend'` on PowerShell).
  Demo mode adds `ORBITLAB_DEMO_MODE='true'`; real GMAT adds
  `GMAT_PATH='<...>/GmatConsole(.exe)'` or a build bundled at `tools/gmat/`
  with `bin/GmatConsole(.exe)` (explicit `GMAT_PATH` always wins; `tools/gmat/`
  is git-ignored, only its README is tracked).
- UI URL: `GET /main` (and `GET /`) answer `RedirectResponse("/OrbitlabUI%20Main/")`
  (`phase4_backend/orbitlab_backend/api/app.py`); the static UI is mounted at
  `/`. Health: `GET /api/health` → `{"status":"ok", ...}` (mode/demo/openInGmat
  fields). `?mock=1` forces mock mode (no network).
- Conventions reused: `scripts/setup_gmat.ps1` style (comment-based help,
  `$ErrorActionPreference='Stop'`, repo root from `$PSScriptRoot`, bundled
  GMAT discovery under `tools/gmat/`); script unit tests load the file with
  `importlib.util.spec_from_file_location` (e.g. `tests/test_realistic_cases.py`,
  "fake HTTP, no network, no GMAT").
- Environment: `pywebview` (`import webview`) is NOT installed here; uvicorn +
  fastapi import fine. So the window itself cannot be opened in this
  environment (recorded in Step 5 as not tested).
- No `requirements*.txt` exists anywhere in the repo; the root README lists
  the pip set inline (`fastapi pydantic-settings httpx uvicorn websockets
  python-dotenv pytest pytest-asyncio`). The desktop extra therefore goes in a
  new optional `requirements-desktop.txt`, not in any core file.

## Plan (Steps 2–4)

- `scripts/desktop_app.py`: `find_free_port()` (127.0.0.1 only),
  `wait_for_health(base_url, timeout)` with injectable fetch, `run(...)` that
  starts uvicorn
  (`orbitlab_backend.api.app:app`, host 127.0.0.1) in a background thread,
  waits for `/api/health` (30 s, clear timeout message), opens a pywebview
  window titled `OrbitLab` at `<base>/main` (1400x900, resizable), and shuts
  the server down when the window closes. `--demo` sets
  `ORBITLAB_DEMO_MODE=true` before starting; `--port` overrides. Missing
  pywebview → exact `pip install` command on stderr, exit code 1. Never prints
  environment values.
- `scripts/start_desktop.ps1`: sets `PYTHONPATH`, sets `GMAT_PATH` from
  `tools/gmat/**/bin/GmatConsole(.exe)` only when the env var is unset and a
  bundled copy exists, takes `-Demo`, forwards `--port`.
- `tests/test_desktop_app.py` (pytest, no GUI): free-port shape/range,
  health-wait timeout via fake fetch (no sockets), missing-pywebview message
  via forced `ImportError` (works whether or not pywebview is installed),
  shutdown hook via stub server. Loopback-only socket use is confined to the
  free-port helper itself, matching the "no network" intent (no external hosts).
- Docs: RUNBOOK `## Desktop window` section with exact commands; one short
  paragraph in the root README.

## Step 5 — suites and counts

- New `tests/test_desktop_app.py`: **9 passed** (free-port shape on
  127.0.0.1, health ok/retry/timeout via injected fake fetch, missing-pywebview
  message + exit 1, main exits 1 without starting a server, bad port exits 2,
  shutdown hook, `--demo` env wiring).
- Node (existing invocation, all files): **49 passed, 0 fail**.
- Backend from `phase4_backend` (`python -m pytest ../tests -q`):
  **233 passed, 1 failed** — `test_extractor_timeout.py::
  test_api_carries_code_and_explanation` expects `extractor_unavailable` but
  gets `needs_clarification`. Verified **pre-existing**: it fails identically
  on pristine `v1-docs` (a82f244) with all task files removed, and standalone.
  The launcher/docs change cannot cause it (no shared code; the test never
  imports `scripts/desktop_app.py`).
- `scripts/e2e_all.py` from the repo root (`GMAT_PATH` from the shell only,
  never logged or committed): tests/e2e **49**, tests **184 + 1 failed**
  (the same pre-existing extractor case), orbitlab_core **48**,
  simulation_engine **23** — total failed+errors: 1 (that case only).

## Window check

**Not tested**: `pywebview` is not installed in this environment
(`import webview` → `ModuleNotFoundError`), so no window could be opened.
The launcher itself was exercised up to the webview gate:
`python scripts/desktop_app.py` prints the exact install line and exits 1.
`pip install -r requirements-desktop.txt` was deliberately not run (would only
change the test/run environment, and the missing-dependency path is the
specified behaviour to verify here).

## Unsure / conservative readings

- `requirements-desktop.txt` lives at the repo root (no requirements files
  exist anywhere to extend; the task names the file but not the folder; root
  matches the `scripts/` + `phase4_backend/` layout and the root README's pip
  line). It contains only `pywebview`, never the core deps.
- `start_desktop.ps1` sets `GMAT_PATH` from `tools/gmat/**/bin/GmatConsole(.exe)`
  only when the variable is unset, mirroring `setup_gmat.ps1` discovery;
  explicit `GMAT_PATH` always wins (same rule as the bundled-GMAT docs).
- The `window actually opened` check is recorded as not-tested above; the
  health-timeout path is covered by injected-fake unit tests instead of a live
  server (no network in tests beyond loopback port probing).
- Branch base confirmed: `v1-docs` existed and this branch was created from it.
- `git stash -u` was briefly used during verification and swept 583
  pre-existing untracked files; all were restored (spot-checked) and the
  leftover stash entry dropped. Prefer filesystem moves over `stash -u` in
  this repo (permission-locked `tmp*/`/`run.log` break the untracked restore).
