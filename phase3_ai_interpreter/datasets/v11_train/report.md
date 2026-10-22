# v11 Phase 2 report

Phase 2 merges the v10 batch data into training/validation and stands up an
evaluation harness for the OrbitLab interpreter. Output lives entirely in
`datasets\v11_train\`; no v9/v9b file, `datasets\v10\raw\` or
`datasets\v10\fixed\` was modified.

## Counts

| split | total | valid | reject | source |
|---|---|---|---|---|
| train | 4413 | 4369 | 44 | v9b train (4085) + v10 90% (328) |
| val | 255 | 251 | 4 | v9b val (215) + v10 10% (40) |
| blind (tinker) | 32 | 32 | 0 | v10 `batch_10`, untouched copy |
| blind (v9b eval) | 120 | 120 | 0 | v9b blind eval, untouched copy |

- v10 pool = 368 (batch_01–08 valid: 320; batch_09 reject: 48), split 90/10
  stratified by (body, template), seed 42 → **train 328 / val 40**. Reject rows
  are stored identically to valid rows; they are only *learned* from the 48
  batch_09 rows (44 train / 4 val).
- Reconciliation: valid 4369 + 251 = 4620 = 4085 + 215 (v9b) + 320 (v10 valid). ✓

### Per body (train / val)

| body | train valid | train reject | val valid | val reject |
|---|---|---|---|---|
| Earth | 1428 | 0 | 64 | 0 |
| Moon | 1337 | 0 | 87 | 0 |
| Mars | 1320 | 0 | 64 | 0 |
| Mercury | 71 | 11 | 9 | 1 |
| Venus | 72 | 10 | 8 | 2 |
| Jupiter | 70 | 12 | 10 | 0 |
| Sun | 71 | 11 | 9 | 1 |

### Per orbit template (train / val)

| template | train | val |
|---|---|---|
| SMA+e | 2629 | 140 |
| periapsis | 1062 | 63 |
| not-derivable | 366 | 29 |
| cartesian | 213 | 4 |
| circular | 116 | 16 |
| AU | 27 | 3 |

## Format notes summary

Documented in `FORMAT_NOTES.md` (STEP 1). Key points reproduced exactly:
ChatML `{system, user, assistant}` rows; canonical assistant key order `version,
experimentName, description, spacecraft, centralBody, epoch, initialOrbit,
forceModel, maneuvers, propagation`; LF, no BOM; split format inferred from the
v9b tinker train/val (deterministic `index % 20 == 7` → val 215 / train 4085;
Phase 2 adds shuffle seed 42).

## Overlap / leak check

Coverage and semantics per the tasking resolution ("gate the data this phase
actually adds"):

- **Hard gate — all zero:**
  - user text vs user text: train↔val, train↔blind, val↔blind → 0 / 0 / 0
  - (body, SMA, ecc) signature of the added v10 data: v10-train↔v10-val,
    v10-train↔blind, v10-val↔blind → 0 / 0 / 0
- **Informational (out of scope):** the frozen v9b train/val legitimately share
  25 (body,SMA,ecc) signatures because both derive from the same 4300-row master
  split as mandated. Not treated as a leak.
- The v10 pool (368) has zero internal duplicate signatures and zero duplicate
  user text. Full report in `MANIFEST.json` → `overlap.details`.

## Harness mock-test results (`eval\`)

| mock | cases_scored | accuracy | note |
|---|---|---|---|
| gold (returns expect_json) | 32/32 | 100% | verdict + element comparison all pass |
| garbage (non-JSON junk) | 32/32 | 0% | every case fails cleanly, no crash |

- `cases_blind.jsonl`: 32 accept cases auto-generated from the `batch_10` blind
  rows (works immediately).
- `cases_realistic.jsonl`: left empty per tasking — the user will supply 25–30
  hand-written realistic prompts (incl. a 270°-inclination case that must be
  rejected). No realistic prompts were invented.

## Decisions made and why

1. **Overlap gate = v11-added data only.** A literal global (body,SMA,ecc) gate
   cannot be zero while using the frozen v9b split as-is (25 shared signatures).
   Per direction, the gate targets only data Phase 2 adds; v9b-internal sharing
   is reported informationally.
2. **Reject rows unlabelled.** Stored identically to valid rows; the validator
   (not a label) is the arbiter. Reject signal is learned from batch_09.
3. **v10 pool re-gated (368), v9b trusted as-is.** Only the v10 pool passes
   through `check_v10.py`-style gating again; v9b rows are frozen and trusted
   (579 cartesian rows would legitimately fail `check_key_order`).
4. **Template mapping to categories:** direct-sma→SMA+e, periapsis→periapsis,
   circular-alt/circular-other→circular, `SMA N AU (...)`→AU.

## Deliverables in `datasets\v11_train\`

- `build_v11.py`, `MANIFEST.json`, `FORMAT_NOTES.md`, `ATTEMPTS.md`
- `orbitlab_v11_tinker_train.jsonl` (4413), `orbitlab_v11_tinker_val.jsonl` (255)
- `blind\batch_10_all_blind.jsonl` (32), `blind\v9b_blind_eval.jsonl` (120)
  (byte-identical copies of sources)
- `eval\run_eval.py`, `eval\README.md`, `eval\cases_blind.jsonl`,
  `eval\cases_realistic.jsonl` (empty)
