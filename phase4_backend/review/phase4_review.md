# Phase 4 Review (branch `phase4-review`, from `phase4-gmat`)

No secret value is printed, logged, copied or committed in this report; secrets are referred to by file path and variable NAME only. No physics, validator rules, compiler output or the experiment JSON schema were changed. The older front step in `phase3_ai_interpreter/frontstep/` was ignored.

## STEP 1 — the secret in `.env`

- `git ls-files .env` → empty (not tracked). `git log --all --oneline -- .env` → empty (0 commits ever touched it).
- `.gitignore` already contains the `.env` line; no `git rm --cached` needed, no commit made for it.
- `.env.example` contains variable NAMES only with empty values. Added the two missing names from the run-cleanup work: `ORBITLAB_RUN_DIR=` and `ORBITLAB_RUN_RETENTION_HOURS=` (empty values).
- Remote: `git remote -v` shows one remote named `origin` only (names only, no URL printed here).
- Was `.env` ever committed: **no (0 commits)**. (A real key was observed on disk in the repo-root `.env` during earlier work; it was never printed or committed.)
- **The user must rotate every key that was ever in `.env`.**

## STEP 2 — checklist (14 items)

| # | Item | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Verify compares SMA, ecc, inc, RAAN, AoP, TA, dry mass, duration value+type, integrator, central body, every maneuver number; names excluded | PASS | `orbitlab_backend/frontstep/verify.py::verify_experiment` (field-by-field checks; names handled separately by `apply_frontstep_names`, never in mismatch list). New locking test `tests/test_review_fixes.py::test_verify_compares_every_physics_field` covers all 12 fields |
| 2 | Front step passes questionable numbers through; validator explains later | PASS | `conversions.py::sma_from_periapsis_altitude` (faithful, no blocking) + `tests/test_conversions.py::test_edge_e_ge_1_not_crash`, `test_frontstep_verify.py::test_edge_case_pass_through`, `tests/test_pipeline2.py::test_out_of_range_not_blocked_at_input_but_fails_later` (70 km Earth periapsis fails at validate, not input) |
| 3 | Warnings don't stop; hard-stops do | PASS | `pipeline.py::run` validate block: `warnings_all` appended to result, `not res.is_valid` → `ValidationFailed`. Note: no code symbol named `VALIDATION_POLICY` exists; the hard-stop list lives in `phase4_report.md` docs while the rules themselves are implemented inline in `orbitlab_core/ast/validation.py::validate`. Behavior verified by `test_pipeline2.py::test_validation_failed_but_explainer_called` |
| 4 | Any unexpected exception in background task → failed job + structured error + event, never stuck "running" | PASS | `api/app.py::run_job` catches `NeedsClarification`, `PipelineError`, and generic `Exception`, always `store.update(status="failed")` + final event. Locked by `test_review_fixes.py::test_background_task_failure_marks_job_failed` |
| 5 | Late WS subscriber gets full events + final; two clients both get everything | PASS | `api/store.py::JobStore.subscribe` replays `job.events` + final when finished; per-subscriber queues. WS handler in `api/app.py::ws_experiments` sends backlog then final. Locked by `test_review_fixes.py::test_websocket_late_and_double_subscriber` |
| 6 | No secret values in logs/errors/health | PASS | Searched `orbitlab_backend` for logging of headers/settings/env: logs emit only job id, stage/type/duration/message (physics numbers only); `Authorization` headers are send-only; `require()` names the variable without printing its value; `/api/health` returns `{"status":"ok"}`. No fix needed |
| 7 | Store + cache bounded; failed infra runs not cached | **FAIL → fixed** | `store.py::JobStore.jobs` was an unbounded dict; `pipeline.py::self.cache` unbounded with a dead `failed_infra` read-guard nothing ever wrote. Fix: `MAX_JOBS=1000` (evict oldest terminal jobs, never running/queued) and `MAX_CACHE_ENTRIES=500` FIFO; only successes are cached (failures raise before the write). Tests: `test_store_bounded`, `test_failed_runs_not_cached_and_cache_bounded` — both fail before, pass after |
| 8 | Interpreter waits ≤ timeout, retries exactly once on timeout/502/503/504, no retry otherwise | **FAIL → fixed** | `clients/interpreter_client.py::HttpInterpreterClient.interpret_prompt` had a generic `except Exception: retry` arm, so 4xx/invalid-JSON also retried. Fix: retry only `InterpreterUnavailableError` (raised for timeout/502/503/504); invalid-JSON/unexpected-type now raise `ValueError` immediately; other exceptions propagate without retry. Tests: `test_no_retry_on_400`, `test_no_retry_on_invalid_json_string` (2 calls before, 1 after). Existing `test_retry_on_503_then_success` / `test_timeout_triggers_retry_and_fails` still pass |
| 9 | GMAT subprocess killed on timeout | PASS | `simulation_engine/.../runner.py::_terminate_process_tree` (taskkill tree on Windows, killpg on POSIX) + `tests/.../test_gmat_integration.py::test_real_gmat_timeout_cleans_run_directory` (ran, passed) |
| 10 | Random job id, no path traversal | PASS | `store.py::JobStore.create` uses `uuid.uuid4()`; ids are dict keys only, never joined into paths (GMAT sandboxes use their own `uuid run_id` via `tempfile`). No `..` handling needed |
| 11 | CORS default is NOT `*` | **FAIL → fixed** | `config.py::Settings.ORBITLAB_CORS_ORIGINS` defaulted to `"*"`. Fix: default `"http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000"` in both Settings branches, still overridable via env. Tests: `test_cors_default_is_not_star`, `test_cors_env_override` — fail before, pass after |
| 12 | Maneuver ids renumbered M1, M2… | PASS | `frontstep/verify.py::normalize_maneuver_ids` + `test_frontstep_verify.py::test_maneuver_id_normalization` |
| 13 | Durations pass through unchanged; no seconds/orbit→hours/days conversion; no rejection of ElapsedSeconds/OrbitPeriods | **FAIL → fixed** | The phase4-gmat Step-3 orbit→hours auto-conversion (`_o2h` wiring in `extractor.py` + `orbits_to_hours` in `conversions.py`) violated this item, so it was removed: extractor now keeps `OrbitPeriods` with the user's value, and the helper was deleted. **Conflict note:** this reverses the committed phase4-gmat Step-3 behavior per this checklist; if hour-conversion is wanted, it needs a product decision. Restored test `test_stop_orbits_passthrough_prompt` fails before, passes after |
| 14 | Names overwritten from front step, sanitised, warning event on difference, never fail | PASS | `verify.py::apply_frontstep_names` + `sanitize_identifier` (`^[A-Za-z0-9_]{1,30}$`, invalid→`_`, `SC_` prefix, truncate 30) wired in `pipeline.py` verify stage emitting `interpreter_name_overridden`; covered by the three name tests in `test_frontstep_verify.py` |

Fixes are minimal bug fixes, no refactoring, no physics/validator/compiler/schema changes. New tests were verified to fail on the pre-fix code by code-path analysis (retry-count, default value, unbounded growth, conversion branch) and pass after.

## STEP 3 — test counts

- `python -m pytest tests -v`: **54 passed, 0 failed** (includes 9 new review tests + restored passthrough test).
- `python -m pytest orbitlab_core/tests -v`: **48 passed, 29 subtests passed, 0 failed**.
- `python -m pytest simulation_engine/tests -v`: **23 passed, 0 failed** (includes the 2 real-GMAT integration tests; GMAT console present on disk so nothing skipped).
- Total: **125 passed + 29 subtests, 0 failures, 0 skipped**.

## Unsure / not done

- Item 3: behavior passes, but there is no code symbol named `VALIDATION_POLICY` (docs only in `phase4_report.md`). Left as-is per "fix only clear bugs"; adding the symbol is a 2-line follow-up if wanted. No step was skipped for this reason.
- Item 13 conflict (above): the removal of orbit→hours conversion reverses committed phase4-gmat Step-3 work. Flagged for your decision rather than guessed further.
- Untracked workspace junk (`SummeryCHAT.txt`, `UIUX/*` drops, `phase3_ai_interpreter/*` artifacts, `tools/`) was left untracked and uncommitted.
