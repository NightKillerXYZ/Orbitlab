# v11 evaluation harness

A model-agnostic harness that scores how well a candidate interpreter model
converts natural-language OrbitLab requests into valid, physically-correct
experiment JSON.

Every case is run through the *same* chain the dataset gate uses
(`interpreter/json_interpreter.py` -> `JsonExperimentInterpreter`):

1. strict JSON parse (no code / GMAT text tolerated),
2. Pydantic AST load,
3. `AstrodynamicValidator` physical validation,
4. deterministic GMAT compile.

The pass/fail verdict is the validator's accept/reject — never the model's
opinion.

## Layout

| file | purpose |
|---|---|
| `run_eval.py` | the harness (endpoints, scoring, reporting) |
| `cases_blind.jsonl` | 32 gold blind cases (auto-generated from the v10 `batch_10` blind set), all `expect: accept` |
| `cases_realistic.jsonl` | **empty** — user supplies realistic/in-distribution cases later (incl. the 270°-inclination reject) |
| `README.md` | this file |

## Case schema (one JSON object per line)

```json
{
  "id": "BlindMerc_001",
  "user_text": "I'd like an experiment call the run \"...\" ...",
  "expect": "accept" | "reject",
  "expect_reason": "altitude"             // optional, substring checked for rejects
  "expect_json": { /* full gold OrbitLab JSON, for accept element comparison */ }
}
```

For `expect: accept`, `expect_json` is the gold experiment; the harness compares
the model's orbital elements against it. For `expect: reject`, only the validator
rejecting matters, and `expect_reason` (optional substring) is checked against
the validator's rejection reason.

## Running

```bash
# OpenAI-compatible endpoint (hosted baseline / Kaggle-served tuned / local)
set EVAL_BASE_URL=https://host/v1
set EVAL_API_KEY=...
set EVAL_MODEL=my-model
python run_eval.py cases_blind.jsonl --out results

# Mock endpoints (no network) for CI / smoke tests
python run_eval.py cases_blind.jsonl --mock gold     # expect ~100%
python run_eval.py cases_blind.jsonl --mock garbage  # expect ~0%, no crash
```

Output is written as `<out>.<timestamp>.json` (full detail) and
`<out>.<timestamp>.report.md` (summary + failing cases), so attempts can be
compared over time.

## Scoring

| check | rule |
|---|---|
| JSON valid | strict `json.loads` |
| schema/physics valid | `JsonExperimentInterpreter` succeeds |
| verdict matches `expect` | validator accept/reject == `expect` |
| accepts: elements vs `expect_json` | SMA ±0.1%, angles (inc/RAAN/argPer/trueAnom) ±0.01°, ecc ±1e-4 |
| rejects: reason | rejection reason contains `expect_reason` (substring) |

## Verified

- `--mock gold` → **100%** (32/32) on `cases_blind.jsonl`
- `--mock garbage` → **0%** (0/32), no crash

## Adding realistic cases (user-supplied)

Populate `cases_realistic.jsonl` with the same schema. The planned 270°
inclination reject case is an example of an `expect: reject` entry whose
`expect_reason` documents why the orbit is invalid (e.g. retrograde below the
Sun's SOI). Do not fabricate cases; supply them from real OrbitLab/GMAT runs.
