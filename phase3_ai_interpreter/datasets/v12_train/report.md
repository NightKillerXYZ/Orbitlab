# v12_train report — training / validation dataset (OrbitLab)

Phase: v12-train. Date: 2026-10-25.
Build: `build_v12_train.py`. Inputs: v11 train/val (unchanged) + v12_gen 473 rows.

## Verdict
**READY** — train 4839, val 302, all checks pass.

## PART A — realistic eval verification (gold mock)
| set | rows | gold acc |
|-----|------|----------|
| blind (`batch_10_all_blind`, 32 accept) | 32 | **100%** (32/32 = 1.0000) |
| realistic (`cases_realistic.jsonl`, 30: 20 accept R01–R20, 10 reject X01–X10) | 30 | **100%** (30/30 = 1.0000) |

- Every realistic case parses as `{id, user_text, expect, note, expect_json|null, expect_reason|null}`; every accept has `expect_json`; every reject has `expect: reject` + a short, stable, case-insensitive `expect_reason` substring (reason matching is case-insensitive; verified).
- Reject gold returns a faithful (rejected) JSON, runs the full validation chain, and records the exact validator rejection message; `expect_reason` matches the printed rejection text.
- Accept gold overrides `coordinateSystem` to the canonical body system via `COORD_SYSTEM[body]` (Moon → `LunaMJ2000Eq`).
- Throwaway `results.2026*.json`/`.report.md` run outputs in `v11_train/eval` were cleaned up.

## PART B — build train/val
### Split
- v12_gen 473 rows split 90/10, **stratified by (body, form, class)**, `seed 42`:
  - gen train **426**, gen val **47** (sum 473).
- **train = v11 train (4413) + gen train (426) = 4839** (shuffled, seed 42).
- **val = v11 val (255) + gen val (47) = 302** (val keeps v11 order, gen appended; verified gen rows are contiguous at indices 255–301).
- Stratum detail (body, form, class) — full list (n = total, val/train):
  - Earth circ: bad_incl n=5 v0/t5, below_min n=7 v1/t6, beyond_soi n=5 v0/t5, valid n=38 v4/t34
  - Earth peri: bad_incl n=4 v0/t4, below_min n=7 v1/t6, valid n=37 v4/t33
  - Earth sma: bad_incl n=4 v0/t4, beyond_soi n=8 v1/t7, valid n=15 v2/t13
  - Jupiter circ: valid n=10 v1/t9; Jupiter peri: valid n=10 v1/t9
  - Mars circ: bad_incl n=5 v0/t5, below_min n=7 v1/t6, beyond_soi n=5 v0/t5, valid n=38 v4/t34
  - Mars peri: bad_incl n=4 v0/t4, below_min n=7 v1/t6, valid n=37 v4/t33
  - Mars sma: bad_incl n=4 v0/t4, beyond_soi n=8 v1/t7, valid n=15 v2/t13
  - Mercury circ: valid n=10 v1/t9; Mercury peri: valid n=10 v1/t9
  - Moon circ: bad_incl n=5 v0/t5, below_min n=7 v1/t6, beyond_soi n=5 v0/t5, valid n=38 v4/t34
  - Moon peri: bad_incl n=4 v0/t4, below_min n=7 v1/t6, valid n=37 v4/t33
  - Moon sma: bad_incl n=4 v0/t4, beyond_soi n=8 v1/t7, valid n=15 v2/t13
  - Sun au: valid n=6 v1/t5; Sun peri: valid n=7 v1/t6
  - Venus circ: valid n=14 v1/t13; Venus peri: valid n=13 v1/t12; Venus sma: valid n=3 v0/t3
  - (val/train sums: 47/426)

### Gate
- Re-gated all 473 gen rows with the interpreter: **re-gate problems 0** (every row still passes/still rejects).
- v12 reject classes re-gated via `interpreter.interpret` success==False (any reason) — NOT the v11 `gate_row` strict minalt/soi check (bad_incl rejects via Pydantic `input should be less than or equal to 90`).

### Leak check (v12_gen vs v11 train/val/blind + 30 realistic)
Checked by user text AND by (body, SMA, ecc) triple (Cartesian v11 rows converted to Keplerian via `a=-mu/(2ε)`, mu = `CENTRAL_BODY_PROPERTIES[body][1]`):
- `Part A triple overlap gen vs realistic`: **0**
- `gen user-text overlaps vs v11 or realistic`: **0**
- `gen triple overlaps vs v11 or realistic`: **0**
- All 473 gen rows present across train+val exactly once (426 + 47 = 473), no train↔val collision, no duplicate user keys.

### Files produced (all LF, no BOM)
| file | rows | sha256 (pinned in MANIFEST_v12.json) |
|------|------|----------------------------------------|
| `orbitlab_v12_tinker_train.jsonl` | 4839 | ed7192539d68584ffdb8d08a6ee53578702668ba4e8da155529a000cf93fc53f |
| `orbitlab_v12_tinker_val.jsonl` | 302 | 0907c4c89fb2574a7dcb08151e1a08a413571733cb0d41ad5532142f36fc30ae |
| `orbitlab_v12_train_google.jsonl` | 4839 | d19e64875affa41bfdc14675bd9615ac80074e82718aac03257f22780728142c |
| `orbitlab_v12_val_google.jsonl` | 302 | 6ad47644518e0586497f6cbe3942efedfb23847815eae92c74591f6fca7f56c4 |

- Google maps 1:1 byte-for-byte to ChatML: `train` 4839 rows, **0 mismatches**; `val` 302 rows, **0 mismatches**. Format: `systemInstruction` + `contents`, ChatML user→`user`, assistant→`model`, system text copied verbatim.

### MANIFEST_v12.json
Sources, per-file sha256 (verified equal to on-disk bytes), counts, split sizes, gen class counts, per-body train/val counts, leak-check booleans, front-step wording before/after. MANIFEST_v12.json sha256: `a0c20c4f8e106b3eb632dbaca913134a187474375594d574b44a01443b9e45f1` (recorded in ATTEMPTS.md attempt-2 row).

### Front-step wording before/after
Regex: `I'd like an experiment call the run `
| scope | front-step rows |
|-------|-----------------|
| v11 total (train+val) | 383 |
| v12 train | 768 |
| v12 val | 88 |
| v12 combined | 856 (= 383 + 473) |

### Per-body counts (from assistant experiment data, matches MANIFEST)
| body | train | val |
|------|-------|-----|
| Earth | 1545 | 77 |
| Jupiter | 100 | 12 |
| Mars | 1437 | 77 |
| Mercury | 100 | 12 |
| Moon | 1454 | 100 |
| Sun | 93 | 12 |
| Venus | 110 | 12 |

### gen class counts
valid 353, below_min 42, beyond_soi 39, bad_incl 39.

## Backup
`v12_train` and `v12_gen` backed up via robocopy `/E /NFL /NDL /NJH /NJS /NP` to `S:\orbitlab-ssd\v12_train` and `S:\orbitlab-ssd\v12_gen`. All source files verified byte-identical (sha256) to the backup; v12_gen 17/17 files match.

## Commit / tag
Committed scripts/docs only (data excluded): `v12_train/TASKING.md`, `v12_train/build_v12_train.py`, `v12_train/report.md`, `v11_train/ATTEMPTS.md` (attempt-2 row), `v11_train/eval/run_eval.py`, `v11_train/eval/build_realistic_gold.py`. Tag: `v12-train-1`.

## Notes
- ATTEMPTS.md attempt-2 row records data version hash = MANIFEST_v12.json sha256 `a0c20c4f...` (base model / LoRA / result columns left empty for the future attempt).
- v9b-internal shared-signature rows (informational only): some v12_gen rows share orbits with the v9b blind set by design; not dropped (expected, documented).
