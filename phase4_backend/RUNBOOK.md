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
