# v10 dataset gate — final report

Physical core: **Mercury, Venus, Jupiter, Sun** (4 new bodies).
Scope: `datasets/v10/` — 10 batch files, 400 rows.
Gate status: **READY TO MERGE**.

---

## 1. Deliverable layout

| location | contents |
|---|---|
| `datasets/v10/raw/` | 10 incoming batches, byte-identical, **never edited** |
| `datasets/v10/fixed/` | final 10-file deliverable (batch_10 corrected; others storage-normalised to LF / no BOM) |
| `datasets/v10/TASKING.md` | task text |
| `datasets/v10/check_v10.py` | Step 3 gate script |
| `datasets/v10/step1_fix_batch10.py`, `step2_pointmasses.py`, `step4_gmat.py`, `step5_fixed.py` | step scripts |
| `datasets/v10/gate_report.{json,md}` | Step 3 output |
| `datasets/v10/gmat_sanity.md` | Step 4 output |

v9 / v9b files were not modified. `raw/` captures the incoming batches exactly as
provided; the SMA defect is corrected only in the `fixed/` deliverable (Step 1).

---

## 2. Per-file table (Step 3 gate, run against the `fixed/` deliverable)

| file | kind | rows | pass | fail | warnings | notes |
|---|---|---|---|---|---|---|
| batch_01_mercury_valid.jsonl | valid | 40 | 40 | 0 | 4 | pointmass/gravity warnings (lines 37–40 custom pointMasses) |
| batch_02_mercury_valid.jsonl | valid | 40 | 40 | 0 | 4 | pointmass/gravity warnings (lines 37–40) |
| batch_03_venus_valid.jsonl | valid | 40 | 40 | 0 | 0 | Venus not point-mass-only (gravity degree>0) |
| batch_04_venus_valid.jsonl | valid | 40 | 40 | 0 | 0 | |
| batch_05_jupiter_valid.jsonl | valid | 40 | 40 | 0 | 4 | pointmass/gravity warnings (lines 37–40) |
| batch_06_jupiter_valid.jsonl | valid | 40 | 40 | 0 | 4 | pointmass/gravity warnings (lines 37–40) |
| batch_07_sun_valid.jsonl | valid | 40 | 40 | 0 | 4 | Sun pointMasses `[]` (physical-correct) |
| batch_08_sun_valid.jsonl | valid | 40 | 40 | 0 | 4 | Sun pointMasses `[]` |
| batch_09_all_reject.jsonl | reject | 48 | 48 | 0 | 0 | all 48 must reject (and did) |
| batch_10_all_blind.jsonl | blind | 32 | 32 | 0 | 0 | Step 1 SMA defect corrected |
| **total** | | **400** | **400** | **0** | **24** | |

Gate checks (all **PASS**):

| check | result |
|---|---|
| key order (canonical v9b order) | 0 fail |
| Pydantic load + AstrodynamicValidator | 0 fail (352/352 expected valid pass) |
| reject rows | 48/48 rejected — 36 min-altitude + 12 SOI, 0 accepted, 0 unexpected |
| SMA audit (reused `audit_v9c_sma_all`, Sun AU handled) | 400/400 pass, 0 fail, 0 na |
| bodies vs `orbitlab_core/bodies.json` | PASS |
| duplicates (within 400 AND vs all 4300 v9b rows) | 0 |
| deterministic GMAT compile | all valid rows compile |

---

## 3. Failing rows

**None.** All 400 rows pass every gate check.

The only row ever flagged was the incoming `batch_10` line 28 defect (**BlindSun_028**),
which is corrected in the `fixed/` deliverable (not in `raw/`):

| field | raw (defective) | fixed (deliverable) |
|---|---|---|
| `semiMajorAxisKm` | `27782020.57` | `27782031.4541` |

Step 1 diff: only `semiMajorAxisKm` changes on that row; all other fields (experiment
name, epoch, elements, forceModel, spacecraft, propagation) and every other line are
byte-identical. On the raw value the SMA audit reports `('periapsis', 27782031.454070523, 'fail')`;
on the corrected value it passes — i.e. the gate validates the corrected deliverable.

Note: batch_09's 48 rows are the *expected* rejects (below-min-altitude / beyond-SOI),
which is why they are excluded from the valid set and count as "reject" by design.

---

## 4. Step 2 answer — point masses

**No STOP required.**

- **(a) Frontstep default** `SCHEMA_DEFAULTS['pointMasses'] = ['Luna', 'Sun']` — this
  default is body-**independent**; frontstep never overrides it per body when force
  settings are not customized, so every body defaults to `['Luna', 'Sun']`.
- **(b) v9b Moon / Mars** use varied patterns (e.g. `['Luna','Sun']`, `['Sun','Jupiter']`,
  `['Jupiter']`, `['Luna','Sun','Jupiter']`, `[]`, ...) — i.e. v9b already encodes
  custom point-mass choices per row; the frontstep default is not a strict per-body rule.
- **(c) v10 patterns per body (400 rows):**
  - Mercury `{('Luna','Sun'):94, ('Sun','Jupiter'):2, ('Luna','Sun','Jupiter'):2, ('Sun',):2}`
  - Venus `{('Luna','Sun'):94, ('Sun','Jupiter'):2, ('Luna','Sun','Jupiter'):2, ('Sun',):2}`
  - Jupiter `{('Luna','Sun'):96, ('Sun',):2, ('Luna',):2}`
  - Sun `{(): 100}` — all rows explicitly empty.
- **(d) mismatch assessment** — the v10 pattern is *not* literally equal to the
  `['Luna','Sun']` default in three places, each a justified row-level intent:
  1. **Mercury / Venus / Jupiter lines 38–40** (24 rows) explicitly request custom
     point masses in the prompt (adding/removing `Jupiter`, `Sun`, `Luna`). These are
     deliberate, prompt-driven choices, not a dataset inconsistency.
  2. **Sun `[]`** (100 rows) is the physically correct exception — a heliocentric run
     treats the Sun as the central body and its own gravity is the field, so no
     additional point masses are listed. Verified against interplay with gravity.

**Conclusion:** the dataset is consistent with the frontstep default
`['Luna','Sun']`; the non-default rows explicitly request custom point masses, and the
Sun `[]` case is physical-correct. **Do not STOP.**

---

## 5. GMAT sanity (Step 4) — 12 runs

Method (mirrors `closeout2/gmat_runs.py`): 3 validated rows per body (one **circular**,
one **periapsis**, one **SMA+e**) × 4 bodies, compiled with `GmatScriptCompiler` and run
in `GmatConsole.exe`. Independent two-body prediction: circular `v=sqrt(mu/SMA)`,
`r=SMA`; elliptical vis-viva `v=sqrt(mu(2/r − 1/SMA))` with `r ∈ [a(1−e), a(1+e)]`.
**PASS** = GMAT returncode 0, telemetry produced, distance & speed within 0.5%.

| Body | Type | Name | SMA (km) | e | r rel % | v rel % | Result |
|---|---|---|---|---|---|---|---|
| Mercury | circular | MercB1_001 | 2525.5300 | 0.0000 | 0.000 | 0.000 | PASS |
| Mercury | periapsis | MercB1_015 | 2614.5830 | 0.0400 | 0.000 | 0.000 | PASS |
| Mercury | SMA+e | MercB1_027 | 2650.0000 | 0.0320 | 0.000 | 0.000 | PASS |
| Venus | circular | VenB3_001 | 6231.8000 | 0.0000 | 0.001 | 0.004 | PASS |
| Venus | periapsis | VenB3_015 | 7000.0000 | 0.1000 | 0.001 | 0.001 | PASS |
| Venus | SMA+e | VenB3_027 | 6520.5000 | 0.0250 | 0.004 | 0.001 | PASS |
| Jupiter | circular | JupB5_001 | 73342.0000 | 0.0000 | 0.000 | 0.000 | PASS |
| Jupiter | periapsis | JupB5_015 | 80000.0000 | 0.0500 | 0.000 | 0.000 | PASS |
| Jupiter | SMA+e | JupB5_027 | 82400.5000 | 0.0450 | 0.000 | 0.000 | PASS |
| Sun | circular | SunB7_001 | 14959787.0690 | 0.0000 | 0.001 | 0.001 | PASS |
| Sun | periapsis | SunB7_015 | 20000000.0000 | 0.1000 | 0.000 | 0.000 | PASS |
| Sun | SMA+e | SunB7_027 | 25400000.0000 | 0.0450 | 0.000 | 0.000 | PASS |

**12/12 runs PASS.** (Venus ran with gravity degree/order 4 and still matched two-body
within 0.5%, confirming the sanity check holds for the non-point-mass body too.)

---

## 6. Body table used (Step 3 numbers vs `orbitlab_core/bodies.json`)

| body | radius (km) | mu (km³/s²) | min periapsis alt (km) | SOI radius (km) | point-mass-only |
|---|---|---|---|---|---|
| Mercury | 2440.53 | 22032.080486 | 20 | 134530.21 | yes |
| Venus | 6051.8 | 324858.598827 | 100 | 619750.031 | no |
| Jupiter | 71492 | 126712767.857614 | 1000 | 48294715.423 | yes |
| Sun | 695700 | 132712440017.74652 | 6261300 | (no SOI) | yes |

Sun AU rows: JSON SMA == round(AU × 149597870.691, 3). All numbers match `bodies.json`;
no problems detected.

---

## 7. Storage

- `raw/`: incoming files stored exactly as delivered (mixed BOM / CRLF preserved).
- `fixed/`: all 10 files in project standard — **LF line endings, no BOM**, matching
  every v9/v9b JSONL file. Row JSON text is byte-identical to `raw/` except the single
  Step 1 SMA correction in `batch_10`.

---

## Verdict

**READY TO MERGE** — 400/400 rows pass the gate (0 failures), Step 2 requires no STOP,
all 12 GMAT sanity runs pass the 0.5% two-body bound, and the only incoming defect
(SMA of BlindSun_028) is corrected in the `fixed/` deliverable.
