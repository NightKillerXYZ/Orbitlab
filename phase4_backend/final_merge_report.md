# Final merge report (`release-candidate` = Line A + Line B)

No secret printed or committed. No physics, validator rules, compiler output, schema, or front-step conversion rules changed.

## Step 1 — branch picture

`git branch -a` shows (among others) `phase5-long-runs` and `phase6-e2e`, both descended from `phase5-ui-wiring-v2`:
- Line A = `phase5-ui-wiring-v2` -> `phase5-real-model` -> `phase5-long-runs` (real-model client + smoke harness + long-runs estimate/timeout/progress work).
- Line B = `phase5-ui-wiring-v2` -> `phase5-main-ui-wiring` -> `phase6-e2e` (Main-UI wiring + `/main` route + e2e suite + OpenAI client adaptation + failure explanations + 422).
- `git merge-base phase5-long-runs phase6-e2e` = `06fe17d` ("docs(phase5-ui): final report, runbook, deploy notes, smoke script + screenshot"), i.e. the two lines share everything up to the phase-5 UI work and diverge after it.

Files changed by BOTH lines since the merge-base (conflict candidates):
- `.env.example`, `phase4_backend/orbitlab_backend/api/app.py`, `phase4_backend/orbitlab_backend/clients/interpreter_client.py`, `phase4_backend/orbitlab_backend/config.py`, `phase4_backend/orbitlab_backend/orchestrator/pipeline.py`, `tests/test_interpreter_client.py`.
- Everything else is disjoint (Line A: estimate module, long-runs/smoke tests, smoke script, RUNBOOK/deploy appends, gmat reports; Line B: Main UI files, e2e suite, e2e_all.py, ARCHITECTURE appendix, static-UI tests, phase6 report at root).
