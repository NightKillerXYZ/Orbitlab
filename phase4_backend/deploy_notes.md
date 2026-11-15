# Deploy notes — Phase 5 UI wiring

- The API serves the static `UIUX/` folder at `/` (FastAPI `StaticFiles`,
  mounted after `/api` and `/ws`, so API routes keep priority). `/` redirects
  to `/OrbitlabUI%20Main/` (the Main UI); `/main` does the same;
  `/ui_adapter.js` serves the backend adapter file. Later additions not
  covered here: `/sample-result` (fixture), `/api/experiments/{id}/script`
  (read-only script), `/api/experiments/{id}/open-in-gmat` (local-only,
  flagged), and the `mode` / `openInGmat` health fields — see RUNBOOK.
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

## Real model call

The interpreter client (`HttpInterpreterClient`) speaks OpenAI-compatible
chat completions: `POST {ORBITLAB_MODEL_URL}/v1/chat/completions` with
headers `Authorization: Bearer <key>` + `Content-Type: application/json` and
body `{model, messages: [{role: system}, {role: user}], temperature: 0}`. The
experiment JSON is read from `choices[0].message.content` (plain JSON object,
JSON string, or fenced block). Model name comes from `ORBITLAB_MODEL_NAME`
(default `orbitlab-interpreter`); set it to the hosted deployment name.
Timeouts: first call >= 180 s, retries exactly once on timeout/502/503/504,
no retry on other errors. No secret value is ever logged, returned, or
committed - variable names only, everywhere.
