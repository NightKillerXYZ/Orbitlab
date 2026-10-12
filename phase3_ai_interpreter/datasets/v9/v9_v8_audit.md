# V8 audit details (as part of V9)

- Audited records: 500 new V9; JSON/schema/Pydantic/physical/compiler pass: 500/500/500/500/500.
- Semantic unmatched: 0; semantic issue count by type: {}.
- Unsupported fields, raw-GMAT leakage, Python code leakage, schema drift: 0, 0/0, 0, 0.
- Duplicate totals: {'within_v9_prompt': 0, 'within_v9_answer': 0, 'v8_prompt_overlap': 0, 'master_prompt_duplicates': 0}; numeric-masked prompt collisions: 0; unique normalized prompts: 500; repeated experiment names: 0.
- Coverage: bodies {'Moon': 175, 'Mars': 175, 'Earth': 150}; low-periapsis-band rows (<340 km): 353; Earth drag-enabled rows: 150; drag models {'JacchiaRoberts': 78, 'MSISE90': 72}; distinct drag coefficients 109; distinct drag areas 145.
- Low-periapsis ranges: Moon 25.0001-334.9999 km, Mars 31.0001-334.0000 km (both within the validated 20-340 km band); Earth-drag periapsis 322.0-1484.0 km (>= 100 km periapsis-safe).
- V9 generator log rejected 103 candidates (resulting in these accepted records); accepted V9 rows remain structurally, physically, and compiler-valid.
- Master is V8 master (3300) + V9 corrections (500) = 3800 rows. 1422 inherited master problems remain, of which 883 are inherited V8 rows lacking an explicit `forceModel` (preserved verbatim; not a V9 correction concern).
- Product gap: no structured missing-required-field or contradiction response is implemented; no error schema was introduced.
