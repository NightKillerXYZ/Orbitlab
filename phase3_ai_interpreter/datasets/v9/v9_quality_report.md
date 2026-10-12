# OrbitLab V9 targeted pass: V8 audit and expansion

## V8 audit (independent, using current code)

- V8 new examples audited: 500; JSON/Schema/Pydantic/physical/compiler valid: 500/500/500/500/500.
- Unsupported fields / raw GMAT leakage / Python leakage: 0 / 0 / 0.
- Semantic issue records: 0; semantic issue count by type: {}.
- Duplicate checks: exact V9-internal prompt/answer, V8 overlap, and numeric-masked collisions all zero; unique numeric-masked templates 500; repeated experiment/spacecraft names 0.
- Coverage observed in the new V9 segment: bodies {'Moon': 175, 'Mars': 175, 'Earth': 150}; low-periapsis band (<340 km) 353; Earth atmospheric-drag-enabled rows 150 with drag models {'JacchiaRoberts': 78, 'MSISE90': 72}; distinct drag coefficients 109; distinct drag areas 145.
- No V9 new example is structurally invalid, physically invalid, compiler-rejected, unsupported-field, raw-GMAT, or Python-leaking.

## V9 coverage-gap closure (vs. V8)

- V8 left two coverage gaps: (1) the Moon/Mars low-periapsis band (20-340 km) was empty, and (2) no Earth atmospheric-drag constraint rows. Both are closed by the V9 new segment below.
- Moon periapsis (km): min 25.0001 / max 334.9999; Mars periapsis (km): min 31.0001 / max 334.0000. All within the validated 20-340 km band.
- Earth drag rows periapsis (km): min 322.0 / max 1484.0, periapsis-safe for drag (>= 100 km) with weights on the validated propagation range.
- Drag is applied only for Earth; the canonical drag answers set `solarRadiationPressure: false` and carry explicit `coefficientOfDrag` + `dragAreaM2` per the drag prompt (which also disables solar radiation pressure).

## V9 new training records

- New records: 500; JSON/schema/Pydantic/physical/compiler pass: {'examples': 500, 'json': 500, 'schema': 500, 'pydantic': 500, 'physical': 500, 'compiler': 500}.
- Rejected/regenerated candidates: 103.
- Category distribution (new segment): {'moon-low-orbit': 175, 'mars-low-orbit': 175, 'earth-drag': 150}.
- Master is V8 master (3300) + V9 corrections (500) = 3800 rows, verified as object-level prefix equality `master[:3300] == v8` (row/object equality, not byte equality because V8 is CRLF) plus the new segment appended.
- Diversity: exact duplicates 0; numeric-masked prompt collisions 0; unique numeric-masked templates 500; repeated experiment names 0.
- Semantic checks include prompt-grounded mass, Keplerian elements, central body/frame, low periapsis altitude in band, drag model (JacchiaRoberts/MSISE90), drag coefficient and area, and SRP state.

## Blind evaluation

- Held-out prompts: 100 across categories {'moon-low-orbit': 18, 'mars-low-orbit': 17, 'earth-drag': 18, 'schema-and-defaults': 12, 'maneuvers': 12, 'force-model': 10, 'integrator-stop': 7, 'Moon-Luna-frame': 6}; exact training overlap: 0; Jaccard near prompt overlap (0.90): 0; reference outputs passing schema/Pydantic/physical/compiler: 100/100.
- Missing-input and contradiction cases are excluded from training and from the blind set; no error object is invented and no under-specified prompt is presented.
- Model inference and accuracy: NOT RUN. The repository contains no interpreter implementation or configured model endpoint; the existing caller references a placeholder host and external credential path and was not invoked. Predictions are null.

## Compiler and GMAT

- Compiler acceptance: new 500/500; master 3800/3800.
- GMAT smoke tests: inherited from the V8 run (available=True, attempted=5, successful=5, failed=0, telemetry parsed=5). No new training job is submitted as part of V9.

## Product/schema gap

- Required `spacecraft.dryMassKg`, initial orbit, and propagation stop condition cannot be omitted for a valid experiment. No structured clarification/error response is defined in the canonical schema or repository; omission examples that require such a response are therefore evaluation-only/product-gap notes, not fake training targets.

## Five remaining weaknesses

1. The repository has no callable interpreter implementation or configured inference endpoint, so model generalization cannot be measured from held-out prompt performance (blind accuracy unmeasured).
2. There is no canonical structured response for omitted required inputs or contradictory requests; clarification behavior remains an application/schema contract gap.
3. V8's 883 inherited legacy rows that lack an explicit `forceModel` (and some lack a usable `centralBody`) are carried verbatim into the V9 master. They are preserved V8 heritage and out of scope for V9's corrections, but they remain a source of structural heterogeneity in the master.
4. V9 uses sequential synthetic names and a restricted prompt-family structure; natural student-language coverage remains incomplete despite no exact or numeric-masked duplicate templates.
5. Frame-only inference plus body synonyms such as Luna versus Moon have repository-consistent references, but no model predictions establish that a trained interpreter learned those mappings.
