# Deploy notes — Phase 5 UI wiring

- The API serves the static `UIUX/` folder at `/` (FastAPI `StaticFiles`,
  mounted after `/api` and `/ws`, so API routes keep priority). `/` returns
  `orbitlab-live.html`; `/ui_adapter.js` serves the backend adapter file.
- The UI uses same-origin relative URLs (no hard-coded localhost port). To
  point the UI elsewhere without code changes, set
  `window.ORBITLAB_API_BASE` before the adapter script loads.
- CORS default is local dev origins (`ORBITLAB_CORS_ORIGINS` env override);
  same-origin serving needs no CORS.
- Mock mode (`?mock=1`, `window.ORBITLAB_USE_MOCK`, or
  `ORBITLAB_USE_MOCK_INTERPRETER=true` server-side) never touches the
  network — safe for demos.
- No secrets are logged, returned, or committed. Secrets come from
  environment variables / `.env` (untracked, gitignored) and are named, never
  printed, in code and reports.
- Backend import root is `phase4_backend/` (`PYTHONPATH=phase4_backend`;
  pytest handles this via `pyproject.toml`).
