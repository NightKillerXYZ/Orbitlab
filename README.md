# OrbitLab

## Run backend locally
```bash
python -m venv .venv
.venv\\Scripts\\activate  # Windows
pip install -e .
pip install -e ./simulation_engine
pip install fastapi pydantic-settings httpx uvicorn websockets python-dotenv pytest pytest-asyncio jsonschema

cp .env.example .env
# Fill env vars (names only in .env.example):
# ORBITLAB_MODEL_URL, ORBITLAB_MODEL_KEY, ORBITLAB_MODEL_TIMEOUT_S=180
# EXTRACTOR_BASE_URL, EXTRACTOR_API_KEY, EXTRACTOR_MODEL
# GMAT_PATH, GMAT_TIMEOUT_S
# ORBITLAB_CORS_ORIGINS, ORBITLAB_USE_MOCK_INTERPRETER

uvicorn orbitlab_backend.api.app:app --reload --port 8000
# health: curl http://localhost:8000/api/health
# create: curl -X POST http://localhost:8000/api/experiments -H "Content-Type: application/json" -d '{"text":"Earth 400 km circular, 500 kg, 2 hours"}'
```

## Run UI locally
The UI in `UIUX/` is a static mock. For a React/Vite app, set:
```bash
VITE_API_BASE=http://localhost:8000
VITE_USE_MOCK=false  # true keeps mock data
```
Import the adapter in your app:
```js
import { createExperiment, getExperiment, subscribeExperiment } from '../orbitlab_backend/api/ui_adapter.js'
```
The adapter routes through one module and preserves MOCK mode without redesigning the UI.

## Tests
```bash
python -m pytest tests -v
python -m pytest orbitlab_core/tests -v --import-mode=importlib
python -m pytest simulation_engine/tests -v
```

## Branch
`phase4-orchestration` contains all milestones. Secrets are never logged; `.env.example` has names only. Real secret path reported in `phase4_report.md`.
