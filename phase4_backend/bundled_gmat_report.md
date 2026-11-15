# Bundled GMAT report (`v1-bundled-gmat`)

## Step 1 — how GMAT_PATH is read and used (read only)

- `config.py`: `GMAT_PATH: Optional[str] = Field(default=None)` / fallback
  `os.getenv("GMAT_PATH")`. Also `GMAT_TIMEOUT_S` (floor 30 s for the
  per-run timeout computation).
- `pipeline.py` simulate stage (`pipeline.py:220-254`): `gmat_path =
  settings.GMAT_PATH`; if set **and the file exists**, a real `GmatRunner`
  executes the compiled script with `executable_path=gmat_path`; otherwise a
  synthetic 10-point trajectory is returned (no GMAT needed for tests).
- `api/app.py` open-in-GMAT (`resolve_gmat_gui`, v1-open-in-gmat): explicit
  `ORBITLAB_GMAT_GUI_PATH` wins, else `GMAT.exe` next to `settings.GMAT_PATH`
  if that file exists.
- `api/app.py` open-in-GMAT (`resolve_gmat_gui`, v1-open-in-gmat): explicit
  `ORBITLAB_GMAT_GUI_PATH` wins, else `GMAT.exe` next to `settings.GMAT_PATH`
  if that file exists.
- Nothing else reads `GMAT_PATH`. e2e/CI set it in the shell only.

## Steps 2–4 — implementation (done)

- `.gitignore`: `tools/gmat/*` ignored except tracked `tools/gmat/README.md`
  (explains the setup script fills the folder; `*` form used because git
  cannot re-include files under an excluded directory).
- `config.py`: `find_bundled_gmat_console` (recursive `bin/GmatConsole(.exe)`
  scan, `bin/` parent required), `resolve_gmat_console_path`
  (explicit `GMAT_PATH` always wins), `resolve_gmat_gui_path` (explicit GUI
  wins, else `GMAT.exe` next to the resolved console if it exists).
  Default search roots: repo root derived from `config.py`'s own path plus
  CWD, deduplicated; callers can pass temp folders (tests do).
- `pipeline.py` simulate: `gmat_path` now resolves bundled when `GMAT_PATH`
  is unset, logging the resolved path at INFO (no env values logged);
  explicit path behaviour unchanged (existence still checked before use).
- `api/app.py` `resolve_gmat_gui` now delegates to the same resolver, so
  "Open in GMAT" also finds a bundled install.
- `scripts/setup_gmat.ps1` (`-Url` mandatory, `-Sha256` optional,
  `-OutDir` defaulting to `<repo>/tools/gmat`) and `scripts/setup_gmat.sh`
  (`--url` mandatory, `--sha256/--out-dir` optional): download (no tokens,
  no auth headers), optional hash check, extract, require
  `bin/GmatConsole(.exe)` (either spelling), print the resolved path, fail
  loudly otherwise. URL is never invented — the user supplies it.
- `tests/test_bundled_gmat.py` (8, temp folders, no network): explicit wins,
  `.exe`/extensionless discovery, non-`bin` files ignored, empty → None,
  GUI explicit/sibling/missing.
- RUNBOOK "Getting GMAT" with exact PowerShell + bash commands.

## Step 5 — verification

- Node (all five files, same `node --test` invocation): 49 pass.
- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 188 passed + 28 skipped.
- Core / sim (repo root): 48 (+29 subtests) / 23 passed.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell: tests/e2e 49, tests 167,
  orbitlab_core/tests 48, simulation_engine/tests 23 — 287 passed, 0 failed.
  (GMAT_PATH was set, so the bundled path was exercised only by unit tests.)
- Unsure: the setup scripts were not executed end-to-end (that would download
  a multi-hundred-MB archive — the one thing this branch must not commit);
  they were reviewed for flags, failure paths, and the `bin/` check only.
  The `.sh` has the executable bit set; Windows checkouts may need
  `git update-index --chmod=+x` reapplied after editing it.
