# v2 spec report (docs + test-data only)

Branch: `v2-spec` (from tip of `v1-guided-json`). No code changes — only new
files, plus the two README sections (Roadmap, Known limitations). The
`[FILL IN]` block was not touched (verified: zero diff lines contain it).
No stash, no `git add .`/`-A`, no force push.

## File list

- `docs/V2_SPEC.md` — architecture, v1.x prerequisites, v2a (8 features),
  v2b (5 features) each with schema additions, compiler work, validator
  rules, UI work, tests, size S/M/L; dependencies; modular versioned schema;
  cut line; v3+; dataset policy (one version per phase, 20–30 variations per
  template, eval-before-training).
- `docs/ROADMAP.md` — one page: v1 done, v2a, v2b, v3, out of scope.
- `README.md` — Roadmap section rewritten (points at both docs); Known
  limitations rewritten from real tests (target-altitude burns, missing
  mass/duration ask, sun-sync unreliability, 365-day cap, not for flight).
- `evals/v2/` — 14 JSONL files, 79 cases total, fields
  `prompt / expectedBehavior (run|ask|refuse) / expectedFields`; every file
  has 5–10 cases and includes ask or refuse cases:
  what_if_followups (6), new_bodies (6), force_models (6),
  frames_states_timescales (5), events (6), export (5), sweeps (5),
  fuel_budget (5), finite_burns (6), target (5), templates (8),
  constellations (5), two_body_view (5), v1_gaps (6).
- This report.

## Test counts (nothing broke)

`python scripts/e2e_all.py` (GMAT_PATH unset → GMAT-gated e2e skip):

| folder | passed | failed | skipped | errors |
|---|---|---|---|---|
| tests/e2e | 21 | 0 | 28 | 0 |
| tests | 216 | 0 | 0 | 0 |
| orbitlab_core/tests | 61 | 0 | 0 | 0 |
| simulation_engine/tests | 23 | 0 | 0 | 0 |
| total failed+errors | | 0 | | |

Node (5 suites): **81 passed, 0 failed**.
