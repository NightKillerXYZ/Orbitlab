# Order-dependent test leak (`v1-desktop-launcher`)

## Step 1 — which earlier test leaves state behind (read only + runs)

Failing test: `tests/test_extractor_timeout.py::
test_api_carries_code_and_explanation` — expects `extractor_unavailable`
(the fake extractor always times out) but gets `needs_clarification`.
The shell has no `ORBITLAB_DEMO_MODE` set. With it set, the pipeline takes
the demo path and an unreadable prompt yields `needs_clarification`, so the
leak is a leftover `ORBITLAB_DEMO_MODE=true` (env and/or cached settings).

Proof (all from `phase4_backend/`, `python -m pytest ... -q -p no:cacheprovider`):

- `../tests/test_extractor_timeout.py` alone: **8 passed**.
- `../tests/test_desktop_app.py ../tests/test_extractor_timeout.py`:
  **1 failed, 16 passed** (the failing test).
- `../tests/test_desktop_app.py::test_apply_flags_demo` +
  `../tests/test_extractor_timeout.py::test_api_carries_code_and_explanation`:
  **1 failed, 1 passed** — single-test bisection points at the `--demo`
  wiring test.
- Full suite minus the desktop file
  (`../tests --ignore=../tests/test_desktop_app.py`): **225 passed,
  0 failed** — no second leaker.
- Full suite with it: **233 passed, 1 failed** (the same extractor test).

Mechanism (demonstrated, no repo code involved):

```python
os.environ.pop("ORBITLAB_DEMO_MODE", None)
m = MonkeyPatch()
m.delenv("ORBITLAB_DEMO_MODE", raising=False)  # absent: records nothing
os.environ["ORBITLAB_DEMO_MODE"] = "true"      # SUT (apply_flags) sets directly
m.delenv("ORBITLAB_DEMO_MODE", raising=False)  # present: records "true", deletes
m.undo()                                       # restores "true" -> LEAK
# after undo: 'true'
```

`tests/test_desktop_app.py::test_apply_flags_demo` calls
`monkeypatch.delenv(..., raising=False)` while the variable is absent
(records nothing), then `mod.apply_flags()` sets `os.environ[...]` directly
(untracked by monkeypatch), then a second `monkeypatch.delenv` records the
SUT-set `"true"` — so fixture teardown **restores `"true"`** and every later
test sees demo mode. The `cfg.reset_settings()` cache then bakes it in wherever
a later test resets settings.

Other writers checked and clean: `tests/test_demo_mode.py` (2 sites) and
`tests/e2e/test_e2e_demo.py` (`demo_client` fixture) set `os.environ` directly
but under `try/finally` with `del` + `cfg.reset_settings()`; Pipeline/store
rebinders (`test_failed_runs`, `test_open_in_gmat`, `test_script_route`,
`test_review_fixes`, e2e helpers) pin and restore in `finally`, and the
failing test pins `RealPipeline`/fresh `JobStore` itself. None of them leak
(the full-minus-desktop run above proves it).

## Fix plan (tests only, Step 2–3)

- `tests/test_desktop_app.py`: rewrite the `--demo` test so the SUT-set
  variable is removed in a `finally` (no second `monkeypatch.delenv` trap).
- New `tests/conftest.py`: autouse fixture scrubs
  `ORBITLAB_DEMO_MODE/EXTRACTOR_BASE_URL/EXTRACTOR_API_KEY/EXTRACTOR_MODEL/
  ORBITLAB_MODEL_URL/ORBITLAB_MODEL_KEY` before each test (via monkeypatch),
  restores originals directly afterwards and calls `cfg.reset_settings()`
  (imported lazily; env scrub still applies if the import ever fails).
  `GMAT_PATH` untouched. Compatible with tests that set these vars through
  monkeypatch (their own undo runs against the scrubbed baseline) and with
  the e2e fixtures (they set/reset what they need themselves).
- `tests/test_extractor_timeout.py::test_api_carries_code_and_explanation`:
  `monkeypatch.delenv("ORBITLAB_DEMO_MODE", raising=False)` before its
  `cfg.reset_settings()` (belt and braces alongside the fixture).

## Step 4 — verification (all green, expected 0 failed)

- Backend full suite from `phase4_backend`
  (`python -m pytest ../tests -q -p no:cacheprovider`), **twice in a row**:
  pass 1 **234 passed**, pass 2 **234 passed** (225 pre-existing + 9 new
  desktop tests), 0 failed both times.
- Order check (no pytest-reverse/collection-order plugin installed): the
  leaking file run *before* the formerly failing one explicitly —
  `test_extractor_timeout.py` then `test_desktop_app.py`: **17 passed**.
  (Alphabetical order already covers leak-before-victim; this covers the
  reverse.)
- Node (existing invocation, all files): **49 passed, 0 fail**.
- `scripts/e2e_all.py` from the repo root (`GMAT_PATH` from the shell only,
  never logged or committed): tests/e2e **49**, tests **185**, orbitlab_core
  **48**, simulation_engine **23** — **305 passed, total failed+errors 0**.

## Cause and fix (summary)

- Cause: `tests/test_desktop_app.py::test_apply_flags_demo` combined two
  `monkeypatch.delenv("ORBITLAB_DEMO_MODE", raising=False)` calls around a
  direct `os.environ` write by the SUT. The second `delenv` recorded the
  SUT-set `"true"`, so fixture teardown resurrected it; the cached settings
  then baked demo mode in and the extractor-timeout test took the demo path
  (`needs_clarification` instead of `extractor_unavailable`).
- Fix (tests only, no app/backend changes):
  1. `tests/test_desktop_app.py`: the SUT-set variable is removed in a
     `finally` with plain `os.environ.pop` (no second `delenv` trap).
  2. New `tests/conftest.py`: autouse fixture scrubs the six mode/endpoint
     variables before each test (via monkeypatch), restores originals
     directly afterwards, and calls `cfg.reset_settings()` (lazy import;
     scrub still applies if the import ever fails). `GMAT_PATH` untouched.
  3. `tests/test_extractor_timeout.py::test_api_carries_code_and_explanation`:
     explicit `monkeypatch.delenv("ORBITLAB_DEMO_MODE", raising=False)`
     before its `cfg.reset_settings()`.
  4. `tests/e2e/test_e2e_demo.py::demo_client`: `scope="module"` →
     `scope="function"` with a comment. The per-test scrub in (2) fires inside
     a module fixture's active window and would otherwise delete its demo
     setting mid-module (13 e2e demo tests failed until this change;
     TestClient rebuild per test is cheap next to the pipelines).

## Anything unsure

- The pre-existing failure was reproduced on pristine `v1-docs` (a82f244)
  with all task files removed, then the tree was restored and verified
  (all 5 task files present, 9 desktop tests passing). A `git stash -u` used
  mid-investigation swept 583 pre-existing untracked files and hit
  permission-locked paths on restore; everything was recovered (spot-checked)
  and the leftover stash entry dropped — avoid `stash -u` in this repo.
- No window to open in this task; the desktop launcher itself is covered by
  its 9 unit tests (missing-pywebview path exits 1, verified by hand too).
- The conftest guard also covers `tests/e2e/` (inherited); e2e_all proves no
  interference (305 passed).
