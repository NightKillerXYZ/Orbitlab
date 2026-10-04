# OrbitLab Experiment Interpreter seed dataset

This directory contains the initial supervised fine-tuning seed dataset for the OrbitLab AI Experiment Interpreter. It teaches one transformation only: a student's natural-language simulation request into an OrbitLab `Experiment` JSON object.

The model response never contains GMAT script. NASA GMAT syntax remains the responsibility of OrbitLab's deterministic compiler.

## Files and split

- `orbitlab_interpreter_train.jsonl`: 200 training examples.
- `orbitlab_interpreter_validation.jsonl`: 50 independently generated holdout examples.
- `validate_dataset.py`: structural, schema, physical-validity, duplicate, and split-integrity checks.

The main dataset contains only requests with enough information to produce valid experiment JSON. Clarification and rejection examples are intentionally excluded because the repository does not define a compatible structured response contract for them.

## Gemini JSONL format

Each line is one JSON object containing:

1. the same `systemInstruction`,
2. one natural-language `user` message, and
3. one `model` message whose text is directly parseable Experiment JSON.

Model text uses compact canonical JSON with double quotes, no comments, no Markdown fences, and no explanatory text.

## Category distribution

| Category | Training | Validation |
|---|---:|---:|
| Basic orbits | 35 | 8 |
| Natural-language paraphrases | 35 | 8 |
| Multi-parameter requests | 35 | 9 |
| Cartesian initial states | 20 | 5 |
| Maneuvers | 30 | 7 |
| Force models | 15 | 4 |
| Propagation | 15 | 4 |
| Cross-feature scenarios | 15 | 5 |
| **Total** | **200** | **50** |

Cross-feature examples also exercise maneuvers, force models, and propagation, so capability counts overlap the primary categories.

## Authority and assumptions

The output contract comes from:

- `orbitlab_core/ast/models.py`,
- `orbitlab_core/ast/validation.py`,
- `schemas/experiment.schema.json`, and
- the existing Phase 1 tests and `ARCHITECTURE.md`.

No separate GMAT/OrbitLab research or knowledge-pack document is present in this repository. No requirements were inferred from an unavailable document.

All examples use Earth because Earth is the currently executable deterministic compiler path. They do not narrow the schema's declared central-body enum. Defaults serialized into model responses are only defaults implemented by the Pydantic models. Unit conversions are explicit in the requests: altitude is converted to geocentric semi-major axis with OrbitLab's Earth radius, and maneuver vectors stated in m/s are converted to km/s.

## Validation

From the repository root, run:

```text
python phase3_ai_interpreter/datasets/validate_dataset.py
```

The validator:

1. parses every JSONL record and checks the Gemini message structure,
2. requires one consistent system instruction,
3. parses model text as JSON,
4. validates it against `schemas/experiment.schema.json`,
5. loads it through `OrbitLabExperiment`,
6. runs `AstrodynamicValidator`,
7. verifies exact split sizes and category distributions,
8. rejects raw GMAT syntax, duplicate requests/responses, near-duplicate requests, and train/validation overlap, and
9. exits nonzero if any check fails.

The validation set uses separate numerical combinations and request formulations; it is not copied or trivially paraphrased from the training split.
