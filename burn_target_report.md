# Burn-target report (vector-less burns, schema messages, grammar)

Branch: `v1-ui-fixes`. No model code or datasets touched. No stash / add / force-push.

## 1. Vector-less impulsive burns stop at extract

- `FrontStepExtractor.deterministic_convert` (phase4_backend/orbitlab_backend/frontstep/extractor.py,
  `_missing_burn_size`) already returns `needs_clarification` with `missing == ["deltaV"]`
  for any `ImpulsiveBurn` without a usable 3-component delta-V, so a target-radius-only
  burn (e.g. `{"type":"impulsive_burn","trigger":"apoapsis","targetRadiusKm":800,"deltaVKmS":null}`)
  records `deltaV=None`, produces no prompt, and `Pipeline.run` raises `NeedsClarification`
  before the interpreter stage. The interpreter is never called for this shape
  (new test asserts a counting interpreter gets 0 calls).
- `prompt_builder.build_canonical_prompt` keeps the earlier crash fix: a `None`/malformed
  `deltaV` renders burn text without a vector and never invents numbers.
- Chat wording (UIUX/OrbitlabUI Main/app.js, already on branch): for `missing == ["deltaV"]` the
  Chat tab shows `To run this I still need: the burn size (delta-V in m/s and direction). ...
  Burns defined by a target altitude aren't supported yet.` Backend explanation for the
  `["deltaV"]` case now mirrors it via `BURN_SIZE_ASK` (see §3).
- New tests: `tests/test_burn_target.py::test_exact_recorded_shape_stops_at_extract`
  (exact task shape, no `elapsedSecs` key) and
  `test_vectorless_burn_never_reaches_interpreter`.
- Existing coverage kept green: `tests/test_maneuver_no_deltav.py` (5 tests),
  `tests/test_maneuver_explicit_deltav.py` (vector burn runs end to end, now also
  duplicated in `test_burn_target.py::test_burn_with_explicit_deltav_runs_end_to_end`).

## 2. Validate-stage messages

- Schema (pydantic) failures: `Pipeline.run` validate block now logs the full error
  server-side (`logger.warning("validate schema failed: ...")`), emits a generic
  `stage_failed` event (`Schema error: mission format mismatch`), and raises
  `SchemaError` with `details.explanation == "The AI's answer didn't fit the mission format,
  so the run was stopped. Please rephrase and try again."` No explainer output is used
  for this path, so no pydantic text, field paths, or URLs can leak. The raw error stays
  in `details.raw` for the server log path only. The UI Chat tab and toast (app.js)
  already render this friendly string and ignore `message` for `schema_error`.
- Physics-rule rejections (`ValidationFailed`, e.g. periapsis below minimum) are untouched:
  they keep the validator's clear messages via the explainer/fallback path.
- New tests: `test_schema_error_is_friendly_and_hides_pydantic`
  (asserts exact friendly text, scans for `validation error`, `OrbitLabExperiment`,
  `pydantic`, `http(s)://`, `Field required`; asserts `details.raw` non-empty) and
  `test_physics_rejection_keeps_clear_message` (70 km periapsis still fails with `70` in the message).

## 3. Grammar

- `Pipeline._clarification_explanation` (new helper in
  phase4_backend/orbitlab_backend/orchestrator/pipeline.py): one missing item → `Add it`,
  several → `Add them`; the `["deltaV"]` case returns the burn-size ask + `Add it`.
  The UI (app.js `humanMissingList` + Chat render) already had the same singular/plural
  rule; backend now matches it for API consumers.
- New test: `test_clarification_grammar_singular_plural_and_burn_size`.

## 4. Files changed

- Modified: `phase4_backend/orbitlab_backend/orchestrator/pipeline.py`
  (+`SCHEMA_FRIENDLY`, +`BURN_SIZE_ASK`, +`_clarification_explanation`;
  extract branch uses the helper; schema-error block logs full error and raises the friendly explanation).
- Added: `tests/test_burn_target.py` (6 tests).
- No changes to model code, datasets, extractor prompts, or UI files.

## 5. Test counts

Run from `phase4_backend` (`python -m pytest ../tests -q`):

- Python: **236 passed, 28 skipped** (skips are pre-existing; ~70 s).
- New file: **6 passed** (`tests/test_burn_target.py`).
- Related existing: `test_maneuver_no_deltav` 5 passed, `test_maneuver_explicit_deltav` 1 passed,
  `test_prompt_builder` 8 passed, `test_pipeline`/`test_pipeline2` all passed.

Run from repo root (`node --test tests/ui_render.test.cjs`):

- UI render: **35 passed, 0 failed**, including `burn-size missing field uses Add it...`,
  `schema errors hide raw pydantic text...`, and `schema failure toast avoids raw pydantic text`.
