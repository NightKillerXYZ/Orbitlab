# Defaults fix report — point-mass perturbers (Part 2)

Branch: `v1-defaults-fix`, created from the tip of `v1-ui-fixes` (`b6ed3e4`).
(The `burn-target` commit `9784f7f` lives on branch `burn-target` and is not in
this branch's history.) No stash, no `git add .`/`-A`, no force push.
No model code, training data, or schema field names touched — only defaults
logic, the compiler, the pipeline normalize step, new tests, and these reports.

Companion: `dataset_defect_audit.md` (Part 1, read-only audit of
`orbitlab_v13f_main_train.jsonl`).

## 1. Where force-model defaults and pointMasses are applied (quotes)

### 1a. Schema default — `orbitlab_core/ast/models.py:189-192`

```python
pointMasses: List[Literal["Luna", "Sun", "Jupiter", "Mars", "Mercury", "Venus", "Earth"]] = Field(
    default_factory=lambda: ["Luna", "Sun"],
    description="Third-body celestial point masses (GMAT body names: Luna for the Moon)"
)
```

Body-agnostic: every central body gets `["Luna", "Sun"]` unless the interpreter
supplies a list. This is the source of the training-data defect (Moon runs with
`Luna`, Mars runs without `Earth`).

### 1b. Validator — `orbitlab_core/ast/validation.py:183-193`

```python
if (
    experiment.centralBody in POINT_MASS_ONLY_BODIES
    and (experiment.forceModel.gravityDegree > 0
         or experiment.forceModel.gravityOrder > 0)
):
    warnings.append(
        f"Central body '{experiment.centralBody}' is modelled as a point "
        f"mass, so the specified gravity field degree/order "
        f"({experiment.forceModel.gravityDegree}/{experiment.forceModel.gravityOrder}) "
        "is ignored."
    )
```

The validator never inspected `pointMasses` against the central body — no
self-perturber check existed here. (Unchanged by this fix.)

### 1c. Compiler — `orbitlab_core/compiler/generator.py:135` (before)

```python
point_masses = [body for body in fm.pointMasses if body != gmat_body]
```

A Moon run therefore could NOT end up with Luna as a perturber in the script —
it was silently dropped, with no note. Observable consequence: a Moon run with
the default `["Luna", "Sun"]` compiled to `PointMasses = {Sun}` — silently
missing Earth, the dominant lunar perturber (see §3 before/after).

## 2. Fix (compile/normalize time)

- `orbitlab_core/constants.py`: new `DEFAULT_POINT_MASSES_BY_BODY =
  {"Earth": ["Luna", "Sun"], "Moon": ["Earth", "Sun"], "Mars": ["Sun"]}`.
  Other bodies keep whatever list they carry.
- `orbitlab_core/ast/validation.py`: new `normalize_point_masses(central_body,
  point_masses, user_specified)` — applies the per-body default when the user
  did not specify perturbers; always removes the central body (GMAT name, e.g.
  `Luna` for the Moon), dedupes, and returns notes for warnings/log.
- Compiler (`generator.py`): same helper with `user_specified=True` (explicit
  lists kept, central body stripped) + `orbitlab.compiler` log note where the
  old code was silent.
- Pipeline (`phase4_backend/.../orchestrator/pipeline.py`, after verify / before
  validate): user-specified = front-step `forces` carries `pointMasses`
  (extractor never provides it today, so interpreter output counts as
  unspecified). Normalized list replaces `experiment_json`'s; each note is
  appended to run warnings as `force_model_normalized: ...` and emitted as an
  event. Physics validation, verify, and all other stages are untouched.

## 3. Moon 100 km, 6 h case — before vs after

Input: circular Moon orbit, SMA 1837.4 km, 6 h, interpreter-style
`pointMasses ["Luna", "Sun"]`, user-specified = False.

Before (old compiler filter only):
```
OrbitLabForceModel.CentralBody = Luna;
OrbitLabForceModel.PrimaryBodies = {Luna};
OrbitLabForceModel.GravityField.Luna.PotentialFile = LP165P.cof;
OrbitLabForceModel.GravityField.Luna.Degree = 4;
OrbitLabForceModel.GravityField.Luna.Order = 4;
OrbitLabForceModel.PointMasses = {Sun};
OrbitLabForceModel.SRP = On;
```

After (normalize → `["Earth", "Sun"]` + note):
```
OrbitLabForceModel.CentralBody = Luna;
OrbitLabForceModel.PrimaryBodies = {Luna};
OrbitLabForceModel.GravityField.Luna.PotentialFile = LP165P.cof;
OrbitLabForceModel.GravityField.Luna.Degree = 4;
OrbitLabForceModel.GravityField.Luna.Order = 4;
OrbitLabForceModel.PointMasses = {Earth, Sun};
OrbitLabForceModel.SRP = On;
```

Key results: `PointMasses` changes `{Sun}` → `{Earth, Sun}` (Luna was silently
dropped before; Earth was missing). Normalize notes:
`pointMasses default applied for central body 'Moon': ['Earth', 'Sun'] (user
did not specify perturbers).` CentralBody/PrimaryBodies/GravityField/SRP lines
identical. End-to-end pipeline test (`test_moon_unspecified_defaults_to_earth_sun`)
returns success with `forceModel.pointMasses == ["Earth", "Sun"]` and the
`force_model_normalized` warning.

## 4. Tests added

- `orbitlab_core/tests/test_force_defaults.py` (13 tests): helper defaults for
  Moon/Earth/Mars/other bodies, explicit-list preservation, dedupe, `None`
  input, compiler emission (`{Sun}` strip, `{Earth, Sun}`, `{Luna, Sun}`,
  `{Sun}` for Mars) and never-self-perturbing across Earth/Moon/Mars/Venus.
- `tests/test_force_defaults.py` (4 tests): pipeline Moon→`[Earth, Sun]`,
  Mars→`[Sun]`, Earth unchanged without note, explicit Moon list stripped to
  `[Sun]` — all `success` with script assertions.

## 5. Full test counts

`python scripts/e2e_all.py` from repo root (GMAT_PATH unset in the shell, so
GMAT-gated e2e tests skip — reported, not failures):

| folder | passed | failed | skipped | errors |
|---|---|---|---|---|
| tests/e2e | 21 | 0 | 28 | 0 |
| tests | 213 | 0 | 0 | 0 |
| orbitlab_core/tests | 61 | 0 | 0 | 0 |
| simulation_engine/tests | 23 | 0 | 0 | 0 |
| total failed+errors | | 0 | | |

Node (repo root): `node --test tests/ui_render.test.cjs
tests/ui_helpers.test.cjs tests/groundtrack.test.cjs tests/plots.test.cjs
tests/view3d.test.cjs` → **81 passed, 0 failed**.

## 6. Files changed

- Modified: `orbitlab_core/constants.py`, `orbitlab_core/ast/validation.py`,
  `orbitlab_core/compiler/generator.py`,
  `phase4_backend/orbitlab_backend/orchestrator/pipeline.py` (86 insertions, 1 deletion).
- Added: `orbitlab_core/tests/test_force_defaults.py`,
  `tests/test_force_defaults.py`, `dataset_defect_audit.md`, this report.
- Touched nothing else; training data only read, never written.
