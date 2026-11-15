# Repo-complete: untracked interpreter package (`v1-repo-complete`)

## Step 1 — every `phase3_ai_interpreter` import and what it needs (read only)

Real code imports (reports `.md`, `.html` logs and the desktop test's own
expectation strings excluded):

| Importing file | Import statement | Needed file | Tracked? (`git ls-files`) |
|---|---|---|---|
| `phase4_backend/orbitlab_backend/clients/interpreter_client.py:6` | `from phase3_ai_interpreter.interpreter.model import IExperimentInterpreter, InterpretationResult` | `phase3_ai_interpreter/interpreter/model.py` (2123 B) | **no** |
| same `:7` | `from phase3_ai_interpreter.interpreter.json_interpreter import JsonExperimentInterpreter` | `phase3_ai_interpreter/interpreter/json_interpreter.py` (6671 B) | **no** |
| (package init, executed by either import above) | `from .json_interpreter import ...` / `from .model import ...` | `phase3_ai_interpreter/interpreter/__init__.py` (678 B) | **no** |
| `phase3_ai_interpreter/closeout/step2_stage4_prompt1.py:34` | same package | — (file itself is untracked workspace material, out of scope) | n/a |

Transitive closure of the three needed files: stdlib only (`abc`,
`dataclasses`, `json`, `typing`) plus `orbitlab_core.ast.models`,
`orbitlab_core.ast.validation`, `orbitlab_core.compiler.generator` — all
tracked in-repo. No third-party or network imports. `__main__.py`,
`interpreter/tests/*` and `__pycache__/` are NOT needed for these imports.
`phase3_ai_interpreter/` has no top-level `__init__.py`; imports resolve as a
namespace package (verified working in this environment; the clean-clone
proof in Step 3 re-verifies from scratch).

`.gitignore` does not exclude them (`git check-ignore` exit 1; the file only
ignores `__pycache__/`, `*.py[cod]`, `.env`, venvs, one datasets jsonl and
`tools/gmat/*`), so no ignore-rule change was needed.

Secret screen of the three files (`api_key|token|secret|bearer|hf_`,
long random strings; matches reported by file name only, values never
printed): `__init__.py` — none; `model.py` — none; `json_interpreter.py` —
none. All three are small `.py` source files well under 1 MB. Nothing under
`datasets/`, `training/`, `closeout2/`, `agent_test_muse/`, no checkpoints,
logs or `.tgz` files is added by this task.

## Plan (Steps 2–4)

- `git add` exactly the three paths above (never `git add .`/`-A`) + commit.
- Clean-clone proof: local `git clone` to a new temp dir outside the repo,
  check out `v1-repo-complete`, `PYTHONPATH=".;phase4_backend"`,
  (a) `python -c "import orbitlab_backend.api.app"`,
  (b) backend suite from `phase4_backend`,
  (c) uvicorn demo + `GET /api/health`; delete the clone; report verbatim.
- Node tests + `scripts/e2e_all.py` in the normal folder, counts, commits.

## Step 2 — what was added (exact paths, one commit)

- `phase3_ai_interpreter/interpreter/__init__.py` (678 B)
- `phase3_ai_interpreter/interpreter/model.py` (2123 B)
- `phase3_ai_interpreter/interpreter/json_interpreter.py` (6671 B)
- Commit `edc424b` ("track interpreter package needed by backend imports").
  Nothing else was staged (`git add` with the three exact paths only).

## Step 3 — clean-clone proof (verbatim results)

Local `git clone` of this repo to a temp dir outside the repo, checked out
`v1-repo-complete` (commit `edc424b`), `PYTHONPATH=".;phase4_backend"`:

- (a) `python -c "import orbitlab_backend.api.app"` → printed `IMPORT_OK`,
  exit 0. The `ModuleNotFoundError: No module named
  'phase3_ai_interpreter'` is gone (namespace package resolves without a
  top-level `__init__.py`; none was added).
- (b) Backend suite from `phase4_backend`
  (`python -m pytest ../tests -q -p no:cacheprovider`):
  **243 passed, 0 failed** in 89.66 s — byte-identical count to the normal
  folder (243 = 225 pre-existing + 13 desktop + 2 textures + 3 provenance).
- (c) `uvicorn orbitlab_backend.api.app:app` on a free port with
  `ORBITLAB_DEMO_MODE=true`, `GET /api/health` → verbatim
  `{"status":"ok","mode":"demo"}` (HTTP 200).
- No test failed or was skipped-for-cause in the clean clone; nothing was
  installed into it (same system Python/pytest as the normal folder).
- The clone was deleted afterwards (directory confirmed gone).

## Step 4 — suites in the normal folder + what is still missing

- Backend: **243 passed, 0 failed** (identical to the clean clone).
- Node (existing invocation, all files): **69 passed, 0 fail**
  (64 pre-existing incl. view3d spin/texture/3D checks + 5 audit additions).
- `scripts/e2e_all.py` (`GMAT_PATH` from the shell only): tests/e2e **49**,
  tests **194**, orbitlab_core **48**, simulation_engine **23** —
  **314 passed, total failed+errors 0**.

Still missing from git (intentionally, per task rules — datasets, training,
closeout, logs, checkpoints, archives stay untracked): everything else under
`phase3_ai_interpreter/` (frontstep, training corpora, gmat_work telemetry,
logs, `closeout*/`, `agent_test_muse/`, `__pycache__/`), plus the usual
pre-existing workspace clutter. Nothing added here changed any code file.

## Anything unsure

- `test_desktop_app.py::test_imports_work_from_unrelated_cwd` (added on the
  launcher branch) already covered the missing-import symptom with a
  subprocess whose cwd differs; it keeps passing and now also passes in the
  clean clone by construction.
- The `__pycache__/` directories inside `phase3_ai_interpreter/interpreter/`
  were not added (git-ignored `__pycache__/` + `*.py[cod]` rules cover them).
