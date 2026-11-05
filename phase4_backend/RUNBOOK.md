# OrbitLab UI runbook (local dev, mock mode — no keys needed)

Serve the backend + static UI from the repo root:

```powershell
$env:ORBITLAB_USE_MOCK_INTERPRETER='true'
$env:PYTHONPATH='phase4_backend'
python -m uvicorn orbitlab_backend.api.app:app --port 8000
```

Open http://localhost:8000/ (live page) or http://localhost:8000/orbitlab-live.html.
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
