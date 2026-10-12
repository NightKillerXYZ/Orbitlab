# Blind evaluation set audit

- Prompt count: 100; category counts: {'moon-low-orbit': 18, 'mars-low-orbit': 17, 'earth-drag': 18, 'schema-and-defaults': 12, 'maneuvers': 12, 'force-model': 10, 'integrator-stop': 7, 'Moon-Luna-frame': 6}.
- Reference outputs parsed from prompt semantics and checked by JSON Schema/Pydantic/physics/compiler: 100/100.
- Exact overlap with training: 0; Jaccard near prompt overlap (0.90): 0.
- Interpreter inference: not run; there is no local interpreter/model implementation or configured inference endpoint. Accuracy is therefore unmeasured.
