# T4 — Golden Diff for Warnings (OLD vs CURRENT core)

Result: **0 differences** across all **4,300** v9b master rows.

- Script: `closeout2/warnings_diff.py` (two-process orchestrator).
- Old code: `orbitlab_core` extracted from git commit **4d5d3e8** into
  `closeout2/old_core/` (`git archive 4d5d3e8 orbitlab_core`).
- Current code: the repo's own `orbitlab_core`.
- Input: `datasets/v9/orbitlab_interpreter_train_v9b_master.jsonl` (4,300 rows).

## Method

Because both code versions share the module name `orbitlab_core` (they cannot be
imported together in one process), the diff runs two identical worker passes in
separate subprocesses:

1. **`--worker old`** — same 4,300 rows through the archived `4d5d3e8` core,
   recording per-row `is_valid`, the error list, and the warning list.
2. **`--worker current`** — the same 4,300 rows through the current core, same
   per-row recording.
3. Compare row-for-row (same line number, same centralBody, same ok/is_valid,
   identical `errors` and `warnings` lists).

## Result (`closeout2/warnings_diff.json`)

```
row_count:   [4300, 4300]
mismatches:  0
examples:    []
per_body:
  Earth: same=1492 diff=0
  Moon:  same=1424 diff=0
  Mars:  same=1384 diff=0
```

Every row that parses, its validity verdict, and its exact error/warning lists
are identical between the pre-7-body (4d5d3e8) core and the current core.

## Note on scope

The v9b master set contains only Earth / Moon / Mars rows (1492 / 1424 / 1384).
The current core adds new warning categories for the point-mass bodies
(Sun/Mercury/Jupiter) and an SOI-escape error path, but none of those fire for
the Earth/Moon/Mars rows present in v9b, so there is nothing new to diff for
those rows — confirmed by the 0-mismatch result and the fail-fast worker
architecture (any divergence in any comparable row would be reported).
