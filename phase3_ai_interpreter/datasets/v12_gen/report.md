# v12_gen report — generated training dataset (OrbitLab)

Input specs: 480 rows from `datasets/v12/*.jsonl`. Output: 473 rows in `orbitlab_v12_gen.jsonl`.

## Verdict
**READY** — kept 473 rows

Classification mismatches (self vs Gemini): 0
Valid rows that failed validation: 0
Valid rows unrepresentable (duration > 365-day schema cap): 7
Reject rows failing with wrong reason: 0
Dedup drops: 0

## Class counts (kept)
- valid: 353
- below_min: 42
- beyond_soi: 39
- bad_incl: 39

## Per-body / form counts (kept)
| body | form | count |
|------|------|-------|
| Earth | circ | 55 |
| Earth | peri | 48 |
| Earth | sma | 27 |
| Jupiter | circ | 10 |
| Jupiter | peri | 10 |
| Mars | circ | 55 |
| Mars | peri | 48 |
| Mars | sma | 27 |
| Mercury | circ | 10 |
| Mercury | peri | 10 |
| Moon | circ | 55 |
| Moon | peri | 48 |
| Moon | sma | 27 |
| Sun | au | 6 |
| Sun | peri | 7 |
| Venus | circ | 14 |
| Venus | peri | 13 |
| Venus | sma | 3 |

## Valid rows unrepresentable (dropped)
These physically-valid rows exceed the 365-day schema cap for all 
stop-condition types (ElapsedDays max 365.0 / ElapsedHours max 8760 / 
ElapsedSeconds max 31536000), so no schema-legal representation exists.
Per TASKING, the user-requested duration is never clamped/rewritten.
- V12SunA007: ["pydantic: 1 validation error for OrbitLabExperiment\npropagation.stopCondition\n  Value error, ElapsedDays value must be between 0.001 and 365.0 [type=value_error, input_value={'type': 'ElapsedDays', 'value': 380.0}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/value_error"]
- V12SunA008: ["pydantic: 1 validation error for OrbitLabExperiment\npropagation.stopCondition\n  Value error, ElapsedDays value must be between 0.001 and 365.0 [type=value_error, input_value={'type': 'ElapsedDays', 'value': 520.0}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/value_error"]
- V12SunA009: ["pydantic: 1 validation error for OrbitLabExperiment\npropagation.stopCondition\n  Value error, ElapsedDays value must be between 0.001 and 365.0 [type=value_error, input_value={'type': 'ElapsedDays', 'value': 680.0}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/value_error"]
- V12SunA010: ["pydantic: 1 validation error for OrbitLabExperiment\npropagation.stopCondition\n  Value error, ElapsedDays value must be between 0.001 and 365.0 [type=value_error, input_value={'type': 'ElapsedDays', 'value': 850.0}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/value_error"]
- V12SunA018: ["pydantic: 1 validation error for OrbitLabExperiment\npropagation.stopCondition\n  Value error, ElapsedDays value must be between 0.001 and 365.0 [type=value_error, input_value={'type': 'ElapsedDays', 'value': 480.0}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/value_error"]
- V12SunA019: ["pydantic: 1 validation error for OrbitLabExperiment\npropagation.stopCondition\n  Value error, ElapsedDays value must be between 0.001 and 365.0 [type=value_error, input_value={'type': 'ElapsedDays', 'value': 640.0}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/value_error"]
- V12SunA020: ["pydantic: 1 validation error for OrbitLabExperiment\npropagation.stopCondition\n  Value error, ElapsedDays value must be between 0.001 and 365.0 [type=value_error, input_value={'type': 'ElapsedDays', 'value': 890.0}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/value_error"]

## Short cells (below spec target) — top-up candidates
| body | form | got | target |
|------|------|-----|--------|
| Sun | au | 6 | 10 |
| Sun | peri | 7 | 10 |

## Notes
- System prompt reused verbatim from v11 train rows (1 distinct value across all v11 rows).
- User text uses exact v10 sentence templates; reject rows use the same templates with failing values.
- `eval/cases_realistic.jsonl` is empty (0 rows) — no-op dedup source.
- T01–T12 test-prompt files were not found anywhere in the repo — treated as no-op dedup source.
- Reject assistant JSON computed with the same SMA formulas as valid rows (not copied from v10 batch_09).
