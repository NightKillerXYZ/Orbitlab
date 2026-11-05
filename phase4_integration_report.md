# Phase 4 Integration Report (branch `phase4-integration`)

No secret value is printed or committed in this report. `GMAT_PATH` was set for the shell session only, never written to a tracked file. No physics, validator rules, compiler output or experiment JSON schema were changed. Nesting arrangement kept: backend code stays at `phase4_backend/orbitlab_backend/`, reports under `phase4_backend/`, review file under `phase4_backend/review/` — nothing in this merge moved them.

## 1) Branch picture

`git log --graph` shows `phase4-gmat` and `phase4-review` diverging from merge-base `2f21db5` ("docs(phase4-gmat): step1-5 gmat report"):

- `phase4-gmat` side (5 commits): `2994b7d` revert orbit conversion → `50586a5` failed-run explanations → `8e26ebf` gmat round-2 report → `04e91be` consolidate reports under `phase4_backend/` → `c3ebdf0` nest `orbitlab_backend/` under `phase4_backend/`.
- `phase4-review` side (5 commits): `998dc1d` retry-only-on-unavailable → `3157de1` CORS local default → `d95b40e` bounded store/cache → `ea6305a` drop orbit conversion → `484ae61` review report.
- Remotes: `origin` (github NightKillerXYZ/Orbitlab) only; local branches also include `main`, `phase5-ui-wiring`, `phase4-orchestration`, `feature/physics-core`.

New branch `phase4-integration` was created from `phase4-gmat` and `phase4-review` merged in (`dd17326`).

## 2) Conflicts and resolutions

Only 2 files conflicted; everything else auto-merged (git followed the `orbitlab_backend/` → `phase4_backend/orbitlab_backend/` renames, combining both sides' edits to `pipeline.py`, `conversions.py`, `extractor.py`, `store.py`, `interpreter_client.py`, `config.py`, `app.py`):

1. `tests/test_conversions.py` — HEAD (gmat) had `test_orbits_to_hours_earth` (helper) + `test_orbit_count_passthrough_in_extractor`; review side had deleted both. Per the rule (passthrough wins, helper + its test deleted): kept the passthrough test, deleted the helper test. The `orbits_to_hours` helper itself was already deleted by the review side's auto-merged `conversions.py`.
2. `tests/test_frontstep_verify.py` — comment-only conflict on the orbit passthrough test (`"3 orbits" passes...` vs `Review item 13: ...`); merged into one comment. No behavior difference on either side.

Kept from `phase4-gmat` (no review-side counterpart to choose against): failed-run explanation fields in `pipeline.py`/`app.py` + `tests/test_failed_runs.py`, run-directory cleanup (`run_cleanup.py`, config vars, `test_run_cleanup.py`), name-override behavior, nested layout, `pyproject.toml` pytest `pythonpath`.

Kept from `phase4-review`: bounded `JobStore` (`MAX_JOBS=1000`) + bounded prompt cache (`MAX_CACHE_ENTRIES=500`, failures uncached), retry-only-on-`InterpreterUnavailableError`, CORS default `http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000`, `tests/test_review_fixes.py` (9 tests), `.env.example` new var names.

Other-differences rule ("keep the version with more tests passing") was not needed: no remaining same-function behavioral divergence — both sides agreed on passthrough, names, and cleanup; I verified by running the suites (below) rather than by inspection alone.

Arrangement note: the merge brought in `phase4_review.md` at the repo root; the identical copy already lived at `phase4_backend/review/phase4_review.md`, so the root duplicate was removed (`git rm`) to keep the workspace clean per the standing arrangement. The deliverable `phase4_integration_report.md` stays at the repo root as instructed.

## 3) Test counts (GMAT_PATH set, shell only)

- `python -m pytest tests -v`: **58 passed, 0 failed** (50 gmat + 9 review − 1 deleted helper test).
- `python -m pytest orbitlab_core/tests -v`: **48 passed, 29 subtests passed, 0 failed**.
- `python -m pytest simulation_engine/tests -v`: **23 passed, 0 failed** (includes the real-GMAT integration tests; console present on disk).
- Total: **129 passed + 29 subtests, 0 failures, 0 skipped**.

## 4) Scenario re-runs (fake interpreter + real compiler/GMAT/parser, `GMAT_TIMEOUT_S=120`)

a–h: a 424 pts/1.0 s, b 1378/1.3 s, c 525/1.0 s, d 333/0.8 s, e 512/0.9 s, f 352/0.8 s, g 69/0.8 s — all `explain` (success). h fails at `validate` (`periapsis altitude 70.00 km < 100.0 km Earth`), `0.0 s`, with the explanation present in the result (asserted by `test_failed_validation_run_contains_explanation`, passing on this branch).

i–o: i 174/0.8 s, j 146/0.8 s, k 207/0.9 s, l 85/0.7 s, m 199/0.9 s (OrbitPeriods end-to-end), n 540/1.0 s, o 38/1.2 s — all `explain` (success), no warnings. Same outcomes as the pre-merge runs.

## Unsure / not done

- Nothing was skipped. One judgment call: deleting the root-duplicate `phase4_review.md` (byte-identical to the `phase4_backend/review/` copy) to honor the nesting arrangement; the content is preserved in both the `phase4-review` branch and the nested copy.
- The `VALIDATION_POLICY`-as-code-symbol question from the review still stands (behavior passes; name exists only in docs) — unchanged by this merge, flagged again for a decision.
