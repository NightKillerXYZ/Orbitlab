# v11 train/validation format notes (STEP 1)

Findings from inspecting how the v9b train/validation files are stored and what
the trainer expects.  These notes define the exact format `build_v11.py`
reproduces (matching v9b, extended with the v10 Mercury/Venus/Jupiter/Sun body
coverage and reject rows).

## 1. Where the v9b train/validation files live and what they are named

Relevant files in `datasets\v9\`:

| file | purpose | rows |
|---|---|---|
| `orbitlab_interpreter_train_v9b_master.jsonl` | frozen 4300-row Gemini-format master | 4300 |
| `orbitlab_v9b_tinker_train.jsonl` | actual training split (ChatML) | 4085 |
| `orbitlab_v9b_tinker_val.jsonl` | actual validation split (ChatML) | 215 |
| `orbitlab_v9b_tinker.jsonl` | whole-master ChatML export (unsplit) | 4300 |

The tinker train/val split is produced by `datasets\v9\convert_v9b_for_tinker_v9c.py`
and consumed by a trainer (see `datasets\v7\targeted_500\train_orbitlab_v8.py` +
`convert_v8_for_tinker.py` for the identical template used to train the OSS-20B
model).  The v11 build therefore writes tinker-style files named to match the
pattern:

- `datasets\v11_train\orbitlab_v11_tinker_train.jsonl`
- `datasets\v11_train\orbitlab_v11_tinker_val.jsonl`

## 2. Row format (must match exactly)

Each line is one JSON object with a single `messages` array of ChatML messages:

```json
{"messages": [
  {"role": "system", "content": "..."},
  {"role": "user", "content": "natural-language request"},
  {"role": "assistant", "content": "{OrbitLab Experiment JSON, one line}"}
]}
```

- `messages[0]` = system prompt.  It is **identical** in v9b and v10
  (852 characters, byte-for-byte equal — verified).  build_v11.py reuses the
  v10/v9b system prompt verbatim so the model sees the same task framing.
- `messages[1]` = user request (the prompt text).
- `messages[2]` = assistant target = the experiment JSON as a compact string
  (single line, canonical v9b key order — see below).

The trainer's renderer (`FromConversationFileBuilder`, `test_size=0`)
consumes this `messages` array directly.  Every record must have >= 3 messages,
end with a non-empty assistant message, and contain at least one user message
(asserted by the v9b converter's round-trip check).

## 3. Canonical assistant JSON key order (frozen v9b storage; v10 matches)

Top level:
`version, experimentName, description, spacecraft, centralBody, epoch,
initialOrbit, forceModel, maneuvers, propagation`

- `initialOrbit`: `type, coordinateSystem, elements`
- `elements`: `semiMajorAxisKm, eccentricity, inclinationDeg, raanDeg,
  argumentOfPeriapsisDeg, trueAnomalyDeg`
- `forceModel`: `gravityDegree, gravityOrder, pointMasses, atmosphericDrag,
  solarRadiationPressure`
- `spacecraft`: `name, dryMassKg, coefficientOfDrag, dragAreaM2,
  coefficientOfReflectivity, srpAreaM2`
- `propagation`: `integrator, stopCondition, stepSizeSecs`

## 4. Split ratio

- v9b: a deterministic **index-based** split (`index % 20 == 7` -> validation)
  yields 215 validation (5%) / 4085 training (95%).  There is no trainer-side
  holdout (the trainer config uses `test_size=0`).
- Phase 2 changes the ratio for the v10 contribution only: batch_01-08 (320
  valid) + batch_09 (48 reject) = 368 rows are split **90/10** into
  train/validation, stratified by body and by orbit template
  (circular / periapsis / SMA+e / AU) with fixed seed 42.
- Validation = the existing v9b validation set (215 rows, kept intact) **+** the
  v10 10% split.

## 5. How reject rows are handled

- v9b contains **no** reject rows: all 4300 assistant outputs are valid
  experiments.
- In v10, a reject row is stored in exactly the same ChatML format as a valid
  row.  The only difference is physical: its assistant experiment JSON places
  the spacecraft below the body's minimum periapsis altitude or outside its
  sphere of influence, so the `AstrodynamicValidator` returns `is_valid=False`.
  batch_09 holds 48 such rows (36 min-altitude + 12 SOI).
- v11 therefore inherits the v10 convention: *the reject label is not stored
  explicitly* — the model must learn to reject by producing an experiment JSON
  that the deterministic validator rejects.  Rejects only ever come from
  batch_09 (48 rows).

## 6. Shuffling

- v9b files preserve master order (no shuffle; the split is by index).
- Phase 2 requires the v11 **train** file to be shuffled.  build_v11.py uses
  `random.Random(42)`.  The v9b validation rows are not shuffled.

## 7. Storage encoding (verified for v9b and for v10 `fixed\`)

- UTF-8, **no BOM** (byte 0 = `{`, checked `raw[:3] != EF BB BF`).
- **LF** line endings only (0 occurrences of `\r\n`).
- One JSON object per line (`json.dumps(..., ensure_ascii=False)`), trailing LF.

## 8. Overlap / leak gate semantics (STEP 2, per tasking resolution)

The build verifies zero overlap of user text and of (body, SMA, ecc) between
train / validation / blind.  Because the frozen v9b train and v9b val both derive
from the same 4300-row master and legitimately share 25 (body,SMA,ecc) signatures
(plus a small amount of template-level user text), a *literal global* gate cannot
be zero while "using v9b as-is" — the requirement is applied to the data this
phase actually adds:

- **Hard gate (all confirmed 0):** user text does not overlap across train / val /
  blind (all three pairwise); and the new v10 contribution has zero (body,SMA,ecc)
  overlap between v10-train and v10-val, and between v10/blind and the blind set.
- **Informational (out of scope):** v9b-internal signature sharing (25) is
  pre-existing in the frozen split and documented in the MANIFEST's overlap
  report, not treated as a leak.
- The v10 pool (368) contains zero internal duplicate signatures and zero
  duplicate user text, and its rows already exclude v9b duplicates (v10 gate).

## 9. Body coverage differences (v10 adds new bodies)

- v9b train/val bodies: Earth, Moon, Mars only (per-body counts recorded in
  build_v11.py output).
- v11 train/val adds Mercury, Venus, Jupiter, Sun from v10 batch_01-08/09.
- The v9b validation set stays Earth/Moon/Mars; the v10 10% validation rows are
  Mercury/Venus/Jupiter/Sun.  Validation therefore spans all 7 bodies.
