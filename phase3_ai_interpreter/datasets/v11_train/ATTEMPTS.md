# v11 Attempt log

Track every training / fine-tuning attempt against the **blind** set
(`eval/cases_blind.jsonl`, 32 accept) and the **realistic** set
(`eval/cases_realistic.jsonl`, user-supplied) so results can be compared across
runs.

## Run one attempt

1. Run the eval harness against your current adapter/checkpoint:
   ```bash
   python eval\run_eval.py eval\cases_blind.jsonl --out results
   python eval\run_eval.py eval\cases_realistic.jsonl --out results
   ```
2. Record the row below.
3. **Back up to the SSD** — copy the whole `datasets\v11_train` folder **and all
   adapter/checkpoint files** to the SSD *after every attempt* before starting the
   next one. Example:
   ```bash
   robocopy datasets\v11_train      E:\orbitlab-ssd\v11_train      /E /NFL /NDL /NJH /NJS
   robocopy <adapter_dir>           E:\orbitlab-ssd\adapters\attempt-N /E /NFL /NDL /NJH /NJS
   ```
   The SSD copy is the durable record; the repo worktree can be rebuilt.

## Data version hash

The data used by every attempt is pinned by the SHA-256 hashes in
`MANIFEST.json` (see `outputs.*.sha256` and the per-file hashes). Always record
the current MANIFEST hash in the table.

## Attempts table

| # | date | base model | LoRA rank | learning rate | epochs | data version hash | blind acc | realistic acc | notes |
|---|------|-----------|-----------|---------------|--------|-------------------|-----------|---------------|-------|
| 1 |        |            |           |               |        |                   |           |               | attempt 1 pasted-output field score 137/168 (81.5%), 0 fully correct (blind/realistic not run for A1) |       |
| 2 | 2026-10-26 | deepseek-v4-flash (0731) |  |  |  | a0c20c4f8e106b3eb632dbaca913134a187474375594d574b44a01443b9e45f1 | 0/32 (0%) | 0/30 (0%) | v12-train dataset (MANIFEST_v12.json): v11 train/val unchanged + v12_gen 473 split 90/10 stratified seed 42; train 4839, val 302 · A2 pasted-output field score 133/168 (79.2%), 0 fully correct; all 14 verdicts reject (wrong-schema drag keys + top-level frame + stale epoch 2023/2024); see training/realtime/report_A2.md |       |
| 3 |        |            |           |               |        |                   |           |               |       |
