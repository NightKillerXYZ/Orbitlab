# Open in GMAT report (`v1-open-in-gmat`)

## Step 1 — stored script path and GMAT_PATH (read only)

- Stored script path (written on successful runs, `api/app.py:202-206`; served
  by `GET /api/experiments/{id}/script`, `api/app.py:77-95`):
  `get_run_root(ORBITLAB_RUN_DIR or <tmp>/orbitlab-runs) / <job-id> /
  "experiment.script"`, where `<job-id>` is the server-generated UUID from
  the in-memory job store — never client text. 404 when the id is unknown or
  the file is absent; traversal-safe (store lookup first, fixed file name,
  `..`/`/`/`\` rejected).
- `GMAT_PATH` (optional setting, env `GMAT_PATH`, `config.py`): read in the
  pipeline simulate stage (`pipeline.py:221`) as the path to the
  **GmatConsole** binary; if set and the file exists, the real GMAT runner
  executes the compiled script, otherwise a synthetic trajectory is used.
  In a standard GMAT install the GUI `GMAT.exe` sits next to
  `GmatConsole.exe` in the same `bin/` folder.

## Steps 2–4 — implementation (done)

- `config.py` (+ both branches) and `.env.example`: `ORBITLAB_GMAT_GUI_PATH`
  (absolute path to `GMAT.exe`, optional) and `ORBITLAB_ALLOW_OPEN_GMAT`
  (default false).
- `resolve_gmat_gui()` (`api/app.py`): explicit `ORBITLAB_GMAT_GUI_PATH`
  wins when non-empty; otherwise `GMAT.exe` next to `GMAT_PATH` but only if
  that file exists; else None. The open-in-GMAT feature counts as enabled
  only when the flag is true AND the exe resolves to an existing file
  (conservative: a shown button must work) — `GET /api/health` then
  includes `"openInGmat": true` and omits the key otherwise.
- `POST /api/experiments/{id}/open-in-gmat`: 403 unless the flag is on;
  403 unless the caller is `127.0.0.1`/`::1` (checked first, so the check
  leaks nothing about runs); id validated against known runs (same `..`/
  `/` guards as the script route) → 404 unknown id; stored script path
  built from the server-side job id + fixed file name → 404 if missing;
  500 with a clear message if `GMAT.exe` is not found; otherwise launches
  `[gui, "--run", script]` via `subprocess.Popen` with an argument list
  (never `shell=True`), does not wait, returns `{"status": "started"}`.
- UI: the Results tab shows an "Open in GMAT" button only when health said
  `openInGmat` and a job id exists; clicking POSTs and toasts "GMAT is
  opening…" or the error message. Disabled by default; the read-only Details
  tab is unchanged.

## Step 5 — tests (done)

- `tests/test_open_in_gmat.py` (11, fake `subprocess.Popen`, no real GMAT):
  locality helper unit tests; resolver precedence/existence; 403 disabled;
  403 non-local; 404 unknown id (+ traversal rejected without launching);
  404 missing script; exact argv `[gui, --run, <run-dir>/<id>/experiment.script]`
  with no `shell` kwarg and `{status: started}`; 500 missing exe;
  health flag present/absent.
- `ui_render.test.cjs` (+2): button hidden without flag/job, shown with both;
  `openInGmat` POSTs only the id and reports started/failed/no-job.

## Step 6 — verification

- Node (all five files, same `node --test` invocation): 49 pass.
- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 180 passed + 28 skipped.
- Core / sim (repo root): 48 (+29 subtests) / 23 passed.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell: tests/e2e 49, tests 159,
  orbitlab_core/tests 48, simulation_engine/tests 23 — 279 passed, 0 failed.
- Unsure: the `--run` flag is used exactly as the task specifies; I did not
  verify it against a real GMAT GUI install (no desktop GMAT here — only
  `GmatConsole.exe` for the sim suites). Enabling the feature is a conscious
  local-only decision; the RUNBOOK carries a warning not to expose such a
  backend to a network.
