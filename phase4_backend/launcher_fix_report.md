# Desktop launcher import-path fix (`v1-launcher-fix`)

## Step 1 — why the window never opens (read only)

Symptom: `.\\scripts\\start_desktop.ps1 -Demo` from the repo root fails with
`ModuleNotFoundError: No module named 'phase3_ai_interpreter'` inside the
uvicorn thread, so `GET /api/health` never answers and the launcher sits in
the 30 s health wait with no cause.

- `scripts/start_desktop.ps1:22` sets
  `$env:PYTHONPATH = Join-Path $repoRoot 'phase4_backend'` — the repo root
  itself is missing, and any pre-existing `PYTHONPATH` is clobbered.
- `scripts/desktop_app.py` does no `sys.path` handling of its own; it inherits
  whatever environment it was started with, so it breaks from any working
  directory that is not the repo root (and even from the root if
  `PYTHONPATH` lacks it and `python scripts/...` rather than `python -m`
  is used, since only `python -m` adds the cwd).
- The import genuinely needs the root:
  `phase4_backend/orbitlab_backend/clients/interpreter_client.py:6-7` does
  `from phase3_ai_interpreter.interpreter.model import ...` (and
  `...json_interpreter import ...`) at module top; `phase3_ai_interpreter/`
  lives at the repo root. `orbitlab_backend` itself resolves via
  `phase4_backend/`.
- RUNBOOK convention: plain `$env:PYTHONPATH='phase4_backend'` works only
  because those commands run `python -m ...` from the repo root (cwd lands
  on `sys.path` automatically); the one script needing the root uses the
  explicit two-entry style `$env:PYTHONPATH='phase4_backend;.'`
  (`scripts/smoke_real_model.py`; bash form `PYTHONPATH=phase4_backend:.`).
  A launcher must work from any cwd, so relative entries are not enough.

## Plan (Steps 2–4)

- `start_desktop.ps1`: `PYTHONPATH = "<repoRoot>;<repoRoot>\\phase4_backend"`
  as absolute paths from `$PSScriptRoot`, appended after with any pre-existing
  `PYTHONPATH` entries preserved behind them.
- `desktop_app.py`: compute repo root + `phase4_backend` from `__file__` and
  insert both at the front of `sys.path` (deduped, absolute) before importing
  or starting uvicorn, so `python scripts/desktop_app.py` works from any cwd
  even without the `.ps1`.
- Health-wait timeout message gains the server thread's last exception
  (class name + message only, never values/headers) when the thread died.
- Tests (no GUI/network): path setup puts both folders first; ps1 mentions
  both paths (plain-text); thread-death message carries the exception class;
  a fresh-subprocess import test for both packages with an unrelated cwd.

## Step 5 — verification and counts

- Backend from `phase4_backend` (`python -m pytest ../tests -q`):
  **238 passed, 0 failed** (234 pre-existing + 4 new launcher tests).
- New tests in `tests/test_desktop_app.py` (13 total, all pass): path setup
  puts repo root first + `phase4_backend` second with no duplicates; the ps1
  text builds the backend dir from `$repoRoot` and prepends both to
  `PYTHONPATH`; `last_error`/`describe_wait_failure` carry the exception class
  (`ModuleNotFoundError: ...`) and omit the detail when empty; a fresh
  `python -c` subprocess with empty `PYTHONPATH` and an unrelated cwd imports
  `phase3_ai_interpreter` + `orbitlab_backend` using only desktop_app's path
  setup.
- Node (existing invocation, all files): **64 passed, 0 fail**.
- `scripts/e2e_all.py` from the repo root (`GMAT_PATH` from the shell only,
  never logged or committed): tests/e2e **49**, tests **189**, orbitlab_core
  **48**, simulation_engine **23** — **309 passed, total failed+errors 0**.

## Whether the window opened

Not tested visibly (no display in this session). Closest attainable proof,
detached run from `C:\` with the fixed files:

- `python -u scripts/desktop_app.py --demo` logged
  `Starting OrbitLab backend on http://127.0.0.1:9079 ...` then
  `Backend is up. Opening the OrbitLab window ...` and blocked in
  `webview.start()` (killed afterwards) — i.e. the import failure is gone,
  health answered (`{"status":"ok","mode":"demo"}` over HTTP), and window
  creation was attempted but could not show without a desktop.
- Note: `pywebview` 6.2.1 turned out to be installed in this Python's
  site-packages (an earlier probe on the parent branch had reported it
  missing), so the launcher now proceeds past the install-message path;
  that path remains unit-tested via forced `ImportError`.

## Anything unsure

- `start_desktop.ps1` preserves pre-existing `PYTHONPATH` entries behind the
  two prepended absolute paths (deduped); `desktop_app.py` does the same on
  `sys.path`. Either entry point now works from any working directory.
- The thread-death detail is class name + message only; a thread that dies
  without an exception keeps the original timeout text.
- The earlier hang seen when running the `.ps1` end-to-end was the GUI call
  blocking without a display, not the import bug — verified by the log lines
  above. No stray server processes were left behind (PIDs killed after each
  probe; `git status` clean).
- No `git stash` was used at any point in this task.
