# OrbitLab UI runbook (local dev, mock mode — no keys needed)

Serve the backend + static UI from the repo root:

```powershell
$env:ORBITLAB_USE_MOCK_INTERPRETER='true'
$env:PYTHONPATH='phase4_backend'
python -m uvicorn orbitlab_backend.api.app:app --port 8000
```

Open http://localhost:8000/ (redirects to the Main UI) or http://localhost:8000/main.
Health: http://localhost:8000/api/health. `?mock=1` forces mock mode (no network).

Backend tests (run from inside `phase4_backend/`):

```powershell
cd phase4_backend
python -m pytest ../tests -q
```

Core / simulation-engine suites (from repo root):

```powershell
python -m pytest orbitlab_core/tests -q
python -m pytest simulation_engine/tests -q
```

Browser smoke (needs Playwright, not installed here):

```powershell
python -m pip install playwright
python -m playwright install chromium
python scripts/ui_smoke.py
```

Result: `phase4_backend/phase5_ui_smoke.png`. Without Playwright, the same
submit→poll→final flow can be checked over plain HTTP (see
`phase4_backend/phase5_ui_report.md`, Step 5).

## Real model smoke test

Set the three variables in your own terminal (names only here - never paste values into chat or files):

```powershell
$env:ORBITLAB_MODEL_URL='<host-root>'
$env:ORBITLAB_MODEL_KEY='<key>'
$env:ORBITLAB_MODEL_TIMEOUT_S='180'   # optional, default 180
```

```bash
export ORBITLAB_MODEL_URL='<host-root>' ORBITLAB_MODEL_KEY='<key>'
export ORBITLAB_MODEL_TIMEOUT_S=180   # optional, default 180
```

Run the smoke (front step -> interpreter -> verify -> validate, no compile/GMAT):

```powershell
$env:PYTHONPATH='phase4_backend;.'; python scripts/smoke_real_model.py
```

```bash
PYTHONPATH=phase4_backend:. python scripts/smoke_real_model.py
```

Start the backend against the real model (same terminal env as above):

```powershell
$env:PYTHONPATH='phase4_backend'; python -m uvicorn orbitlab_backend.api.app:app --port 8000
```

```bash
PYTHONPATH=phase4_backend python -m uvicorn orbitlab_backend.api.app:app --port 8000
```

Open the UI: http://localhost:8000/main (Main) or http://localhost:8000/ (live page).

If the first call times out (cold start, can take ~90 s): the smoke script
already allows 180 s+ for the first call and 60 s after. If it still times
out, raise `ORBITLAB_MODEL_TIMEOUT_S` (e.g. 300) and retry - the model may
still be warming up. Check the server logs for stage timings; a timeout at
`interpret` with nothing after it means the model never answered.

## Extractor setup

The front-step extractor (`FrontStepExtractor`) calls an OpenAI-compatible
chat endpoint when configured, else it uses a built-in regex fallback:
- `EXTRACTOR_BASE_URL` — base URL of the chat endpoint (the client posts to `{base}/chat/completions`).
- `EXTRACTOR_API_KEY` — Bearer key (name only; never commit it).
- `EXTRACTOR_MODEL` — model/deployment name the endpoint serves.
- `EXTRACTOR_JSON_MODE` — `prompt` (default: ask for JSON in the system prompt, no extra parameters; works with vLLM + Qwen as-is) or `json_object` (sends `response_format: {"type": "json_object"}`), or `json_schema` (sends the full `orbitlab_extraction` JSON schema with `strict: true`; only use this if the endpoint was started with structured output for this schema — on HTTP 400/422 the extractor logs a warning and falls back to regex, no retries).
- Without these set, the regex fallback only handles simple phrasings (e.g. `400 km circular`, `for 2 hours`); anything else yields `needs_clarification`. For robust phrasings — or the exact training-form sentences — point the extractor at a real model or use `scripts/smoke_real_model.py --skip-extract`.

## Explainer setup

The physics explainer shares the extractor's endpoint variables
(`EXTRACTOR_BASE_URL`, `EXTRACTOR_API_KEY`, `EXTRACTOR_MODEL`) plus one more:
- `EXTRACTOR_TIMEOUT_S` — request timeout in seconds (default 150; the first
  call after idle can take ~90 s on a cold model). Retried once on timeout or
  HTTP 502/503/504 only.
- Without these set, or if the explainer call fails/returns empty text, a
  successful run still succeeds: the `explanation` field holds a deterministic
  automatic summary and `explanationSource` is `"fallback"` (vs `"model"`).
  The explain stage never fails a run that simulated fine; the UI shows
  "Automatic summary (the AI explainer was unavailable)" in that case.

## Demo mode

No language models, no keys: the deterministic local extractor, interpreter
and fallback explainer run the full pipeline with real GMAT. Set
`ORBITLAB_DEMO_MODE=true` (default `false`; also listed in `.env.example`).
`GET /api/health` then returns `{"status":"ok","mode":"demo"}` and results
carry `"mode":"demo"` (the UI shows a "DEMO MODE" badge).

```powershell
$env:ORBITLAB_DEMO_MODE='true'
$env:PYTHONPATH='phase4_backend'
$env:GMAT_PATH='<path-to>\GmatConsole.exe'
python -m uvicorn orbitlab_backend.api.app:app --port 8000
```

```bash
export ORBITLAB_DEMO_MODE=true
export GMAT_PATH='<path-to>/GmatConsole'
PYTHONPATH=phase4_backend python -m uvicorn orbitlab_backend.api.app:app --port 8000
```

No `EXTRACTOR_*` / `ORBITLAB_MODEL_*` variables are needed in demo mode.
Unset the flag (or restart without it) to return to model mode.

## Extractor cold starts

The first request after the extractor endpoint went idle can take ~90 s
(cold start). `EXTRACTOR_TIMEOUT_S` (default 150) controls the wait for both
the extractor and the explainer; the extractor retries once on timeout or
HTTP 502/503/504. If the model is still unreachable after the retry and the
regex fallback cannot read the request either, the run fails at `extract`
with code `extractor_unavailable` ("...starting up or unreachable. Please try
again in a minute.") instead of a misleading `needs_clarification`.
To keep containers warm on Modal, set `min_containers=1` on the extractor
(and explainer) app and remove it after the demo to stop the charge.

## Open in GMAT

The Results tab can open the run's generated script in the full GMAT desktop
app on the same PC as the backend (off by default; read-only inspection is
always available in the Details tab):

```powershell
$env:ORBITLAB_ALLOW_OPEN_GMAT='true'
$env:ORBITLAB_GMAT_GUI_PATH='C:\GMAT\R2024a\bin\GMAT.exe'
$env:PYTHONPATH='phase4_backend'
python -m uvicorn orbitlab_backend.api.app --port 8000
```

If `ORBITLAB_GMAT_GUI_PATH` is unset, `GMAT.exe` next to `GMAT_PATH`
(`GmatConsole.exe`) is used when that file exists. `GET /api/health` then
reports `"openInGmat": true`, which is the only thing that shows the button.
The endpoint only accepts local connections (`127.0.0.1`/`::1`) and launches
`GMAT.exe --run <stored script>` without waiting. Do not expose a backend
with this flag on to a network: anyone who can reach it can start programs.

## Getting GMAT

GMAT is optional: without it the pipeline returns a synthetic trajectory.
To use the real simulator, either set `GMAT_PATH` to your `GmatConsole(.exe)`,
or drop a build into `tools/gmat/` (explicit `GMAT_PATH` always wins):

```powershell
.\scripts\setup_gmat.ps1 -Url '<paste-the-release-zip-link>' [-Sha256 '<hex>']
$env:GMAT_PATH='C:\GMAT\R2024a\bin\GmatConsole.exe'  # optional when bundled
$env:PYTHONPATH='phase4_backend'
python scripts/e2e_all.py
```

```bash
./scripts/setup_gmat.sh --url '<paste-the-release-zip-link>' [--sha256 <hex>]
GMAT_PATH='<path-to>/bin/GmatConsole' PYTHONPATH=phase4_backend python scripts/e2e_all.py
```

The setup script downloads only the URL you give it (no token, no headers),
verifies the optional SHA-256, extracts into `tools/gmat/`, and prints the
resolved console path. `tools/gmat/` is git-ignored (binaries are never
committed); only `tools/gmat/README.md` is tracked.

## Realistic cases

`scripts/realistic_cases.py` sends 14 free-text prompts through the running
backend exactly like the UI does (POST + poll) and writes
`phase4_backend/realistic_cases_results.md` with a verdict per case
(exit code non-zero only if a non-`info` case fails):

```powershell
$env:ORBITLAB_DEMO_MODE='true'
$env:PYTHONPATH='phase4_backend'
python -m uvicorn orbitlab_backend.api.app --port 8000
python scripts/realistic_cases.py --mode demo
```

```bash
export ORBITLAB_DEMO_MODE=true
PYTHONPATH=phase4_backend python -m uvicorn orbitlab_backend.api.app --port 8000 &
python scripts/realistic_cases.py --mode demo
```

Real-model mode (needs the model variables, same names as in `.env.example`,
plus GMAT for the simulate stage; first request can take ~90 s cold):

```powershell
$env:ORBITLAB_MODEL_URL='<host-root>'; $env:ORBITLAB_MODEL_KEY='<key>'
$env:ORBITLAB_DEMO_MODE=''; $env:PYTHONPATH='phase4_backend'
python -m uvicorn orbitlab_backend.api.app --port 8000
python scripts/realistic_cases.py --mode real --base-url http://127.0.0.1:8000 --timeout-s 600
```

```bash
export ORBITLAB_MODEL_URL='<host-root>' ORBITLAB_MODEL_KEY='<key>'
unset ORBITLAB_DEMO_MODE
PYTHONPATH=phase4_backend python -m uvicorn orbitlab_backend.api.app --port 8000 &
python scripts/realistic_cases.py --mode real --timeout-s 600
```

Useful flags: `--only 1,3,5` (subset of case ids), `--timeout-s 400`
(per-case budget in seconds), `--out <file>`.

## 3D view and textures

The "Orbital view" panel has a 2D/3D toggle. 3D renders the real trajectory
with three.js r160 vendored at `UIUX/OrbitlabUI Main/vendor/three/`
(`three.module.min.js` + `OrbitControls.js` + LICENSE, no CDN at run time).
Planet surfaces come from `UIUX/OrbitlabUI Main/assets/textures/<body>.jpg`
(lowercase body name; see `assets/textures/README.md` for the file list,
equirectangular requirement and credits) when the files exist, otherwise a
plain shaded sphere in the body's colour is used and nothing throws.
Drag to orbit, scroll to zoom (OrbitControls with damping); play/pause/speed
and the time slider drive the 3D marker exactly like the 2D one. Re-vendoring:
`npm install three@0.160.0` in a temp folder outside the repo, copy the two
files above, fix the `from 'three'` import in `OrbitControls.js` to
`./three.module.min.js`, copy the LICENSE. Never commit `node_modules`.

## Desktop window

Run the same backend + Main UI in its own desktop window (Edge WebView2, no
browser). First install the optional extra (core requirements are unchanged):

```powershell
python -m pip install -r requirements-desktop.txt
```

Then, from the repo root:

```powershell
.\scripts\start_desktop.ps1 [-Demo] [-Port <n>]
```

`-Demo` sets `ORBITLAB_DEMO_MODE=true` before starting. The script sets
`PYTHONPATH=phase4_backend` itself and picks up `GMAT_PATH` from a bundled
`tools/gmat/**/bin/GmatConsole(.exe)` only when `GMAT_PATH` is not already
set (explicit `GMAT_PATH` always wins). The launcher binds 127.0.0.1 only
(`--port` overrides the free-port pick), waits up to 30 s for
`GET /api/health`, opens the `OrbitLab` window at `/main` (1400x900,
resizable), and stops the server when the window closes. Without pywebview
it prints the install command and exits 1. Direct equivalent without the
`.ps1`:

```powershell
$env:PYTHONPATH='phase4_backend'
python scripts/desktop_app.py [--demo] [--port <n>]
```
