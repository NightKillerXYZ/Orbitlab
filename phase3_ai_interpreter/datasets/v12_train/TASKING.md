# TASKING — v12_train training/validation dataset (OrbitLab)

Date: 2026-10-25

Do NOT modify any v9 / v9b / v10 / v11 data file, any `datasets\v12_gen` input, or
any blind set. Work only in `datasets\v12_train\` (new folder). Everything is
verified by running scripts — no guessing.

## INPUTS (resolved)
- Realistic eval cases: **30** rows (20 accept R01–R20, 10 reject X01–X10) at
  `datasets\cases_realistic.jsonl` (user-confirmed source of truth; the
  `datasets\v11_train\eval\cases_realistic.jsonl` placeholder is empty since v11).
- v12_gen rows: `datasets\v12_gen\orbitlab_v12_gen.jsonl` (**473** ChatML rows,
  LF, no BOM). Metadata (body/form/class) is taken from the authoritative spec
  dir `datasets\v12_gen\v12\*.jsonl` (480 rows; 7 Sun rows were dropped, leaving
  473 in the gen file), keyed by `experimentName`==spec `id`. Verified 1:1:
  all 473 gen IDs match a spec row and `centralBody` agrees in every row.
- v11 base files: `datasets\v11_train\orbitlab_v11_tinker_train.jsonl` (4413) and
  `_val.jsonl` (255).
- Blind sets: `datasets\v11_train\blind\batch_10_all_blind.jsonl` (32) and
  `blind\v9b_blind_eval.jsonl` (120) — never modified, used for overlap checks.
- Google converter: reuse the exact v11 structure:
  `{"systemInstruction":{"role":"system","parts":[{"text":SYS}]},
    "contents":[{"role":"user","parts":[{"text":USER}]},
                {"role":"model","parts":[{"text":ASST}]}]}`
  mapping byte-for-byte from the ChatML row (verified for v11).

## PART A — realistic eval verification
1. Check every one of the 30 realistic cases parses as `{id, user_text, expect,
   note, expect_json|null, expect_reason|null}`; every accept has `expect_json`,
  every reject has `expect: reject`.
2. Build the gold-answer mock: `--mock gold` returns each accept case's
   `expect_json` serialised (harness already does this); for rejects return a
   JSON that is faithful to the case (interpret as a "model answer"), run the
   full validation chain, and record the exact validator rejection message.
3. For each reject (incl. `X01` bare inclination 270), fill `expect_reason` with
   a **short, stable, case-insensitive substring** that reliably appears in the
   validator's rejection text (the only field that may change).
4. Harness changes (script-only, under `eval\`): reason matching already
   case-insensitive — verify. Add: print the **full** rejection text for every
   reject case.
5. Run `--mock gold` on blind (32) AND realistic (30): both must hit **100%**.
6. Check (body, SMA, ecc) overlap between the 473 v12_gen rows and the 30
   realistic cases — report any collision (none expected).

## PART B — build train/val
1. Split the 473 v12_gen rows 90/10, stratified by **(body, form, class)**,
   fixed `seed 42`. (form = circ|peri|sma|au; class = valid|below_min|beyond_soi|bad_incl.)
2. train = v11 train (4413) + v12_gen 90% (≈426); val = v11 val (255) + v12_gen
   10% (≈47). Shuffle train with `seed 42`; val keeps v11 order with gen appended.
3. Verify **zero overlap** (by user text AND by (body, SMA, ecc)) between every
   new v12_gen row and: v11 train, v11 val, blind (batch_10 + v9b), and the 30
   realistic cases. Report the ~25 v9b-internal shared-signature rows purely as
   informational (they share orbits with v9b blind — expected, not dropped).
4. Every new v12_gen row must still pass the v12 gate (re-gate all); every reject
   must still be rejected.
5. Write 4 files (2 ChatML: train/val; 2 Google: train/val — all LF, no BOM);
   verify row counts and that Google maps 1:1 byte-for-byte to ChatML.
6. Write `MANIFEST_v12.json`: sources, per-file sha256, counts per
   body/form/class, split sizes. Include a before/after table of the front-step
   wording "I'd like an experiment call the run ..." row counts v11 vs v12.
7. Append a **2nd attempt row** to `datasets\v11_train\ATTEMPTS.md` (data version
   v12, MANIFEST hash; result columns left empty).
8. Back up `v12_train` AND `v12_gen` to the SSD (robocopy like v11).
9. Commit **scripts only** (not data), tag `v12-train-1`.
10. Write `datasets\v12_train\report.md`.

## RULES
No guessing numbers — compute/recompute everything. Never edit
v9/v9b/v10/v11 data, v12_gen inputs, or blind sets. If something fails, report
it, do not silently fix it. Commit only code and scripts, tag `v12-train-1`.
