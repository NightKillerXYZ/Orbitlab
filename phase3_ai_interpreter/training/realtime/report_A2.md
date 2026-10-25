# A2 — attempt-2 (data v12) interpreter score report

Tasking saved to `TASKING_A2.md`; raw model outputs (14 blocks) saved unchanged
to `outputs_raw_A2.txt`; full machine-readable scores in `results_A2.json`.

- **Mode:** realistic "blind" scoring of 14 pasted interpreter outputs (no
  editing, no fixing; JSON parse errors would count as FAIL — all 14 parsed clean).
- **Verdicts:** computed with the full `JsonExperimentInterpreter` chain
  (strict parse → Pydantic `ExperimentConfig` → `AstrodynamicValidator` →
  deterministic GMAT compile where the case asks for accept). Field-level scores
  are computed independently on the parsed JSON.
- **Headline set:** T01–T12 (gold expected values defined in the tasking) over a
  14-field rubric → **168 cells**. T13 (`MercB2_027`) and T14
  (`ParaphraseTrain033`) have **no gold** for orbit elements in the tasking, so
  they are scored only on default-driven / schema-conformance fields.

---

## 1. Pipeline verdicts

| test | expected | verdict | reason (exact) |
|------|----------|---------|----------------|
| T01 | accept | ❌ reject | `unsupported:$.forceModel.atmosphericDrag.solarApsectRatio` |
| T02 | accept | ❌ reject | `unsupported:$.forceModel.atmosphereModel` |
| T03 | accept | ❌ reject | `unsupported:$.coordinateSystem` **+ drag keys** |
| T04 | accept | ❌ reject | `unsupported:$.coordinateSystem` **+ drag keys** |
| T05 | accept | ❌ reject | `unsupported:$.coordinateSystem` **+ drag keys** |
| T06 | accept | ❌ reject | `unsupported:$.forceModel.atmosphericDrag.spaceWeatherSensitivity` |
| T07 | accept | ❌ reject | `unsupported:$.coordinateSystem` **+ drag keys** |
| T08 | accept | ❌ reject | `unsupported:$.coordinateSystem` + drag boolean |
| T09 | reject | ✅ reject | `unsupported:$.forceModel.atmosphericDrag.maxDensityGPerCm3` (masks the intended min-altitude reason) |
| T10 | reject | ✅ reject | Pydantic `less_than_equal` (inclinationDeg 200 > 180) — **correct expected reason** |
| T11 | reject | ✅ reject | `unsupported:$.coordinateSystem` (masks intended beyond-SOI reason) |
| T12 | reject | ✅ reject | `unsupported:$.forceModel.atmosphericDrag.solarActivityIndex` (masks intended min-altitude reason) |
| #13 MercB2_027 | — | ❌ reject | `unsupported:$.coordinateSystem` + `unsupported:$.forceModel.atmosphericDrag.solarWindSpeedKmS` |
| #14 ParaphraseTrain033 | — | ❌ reject | `unsupported:$.forceModel.atmosphericDrag.solarActivityIndex` |

**Verdict summary:** 0/14 accepted. Every `accept`-expected test (T01–T08) is
rejected on a hallucinated `unsupported:` key — the worst possible outcome
(that class of test exists to check the compiler/validator, and none of them
even reach it). T10 is the only test that rejects for its *intended* reason.

---

## 2. Field-level rubric (T01–T12, 14 fields)

14 fields: version, experimentName, spacecraft block, centralBody, epoch
(default `01 Jan 2026 12:00:00.000`), frame (inside `initialOrbit`), SMA
(tol 0.002 km), eccentricity + 4 angles, gravity degree/order, pointMasses,
atmosphericDrag object (schema-conforming), solarRadiationPressure, maneuvers
key present, propagation (integrator/stopCondition/step 60 s).

### 2a. Grid (P = pass, `.` = fail)

| field | T01 | T02 | T03 | T04 | T05 | T06 | T07 | T08 | T09 | T10 | T11 | T12 |
|-------|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| version | . | P | P | P | P | P | P | P | P | P | P | P |
| experimentName | P | P | P | P | P | P | P | P | P | P | P | P |
| spacecraft | P | P | P | P | P | P | P | P | P | P | P | P |
| centralBody | P | P | P | P | P | P | P | P | P | P | P | P |
| epoch | . | . | . | . | P | P | . | . | . | . | . | . |
| frame | P | P | . | . | . | P | . | . | P | P | . | P |
| SMA | P | . | . | P | . | P | . | P | . | . | P | . |
| ecc + angles | P | P | P | P | P | P | P | P | P | P | P | P |
| gravity | P | P | P | P | P | P | P | P | P | P | P | P |
| pointMasses | P | P | P | P | P | P | P | P | P | P | P | P |
| drag object | . | . | . | . | . | . | . | . | . | P | P | . |
| SRP | P | P | P | P | P | P | P | P | P | P | P | P |
| maneuvers key | P | P | P | P | . | P | P | P | P | P | P | P |
| propagation | P | P | P | P | P | P | P | P | P | P | P | P |

### 2b. Per-test totals

| test | T01 | T02 | T03 | T04 | T05 | T06 | T07 | T08 | T09 | T10 | T11 | T12 |
|------|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| /14  | 11 | 11 | 10 | 11 | 10 | **13** | 10 | 11 | 11 | 12 | 12 | 11 |

**Total 133/168 = 79.2%. Fully correct tests (14/14): 0.**

### 2c. Per-field totals (of 12)

| field | correct |
|-------|---------|
| version | 11/12 |
| experimentName | 12/12 |
| spacecraft | 12/12 |
| centralBody | 12/12 |
| epoch | 2/12 |
| frame | 6/12 |
| SMA | 5/12 |
| ecc + angles | 12/12 |
| gravity | 12/12 |
| pointMasses | 12/12 |
| drag object | 2/12 |
| SRP | 12/12 |
| maneuvers key | 11/12 |
| propagation | 12/12 |

### 2d. Group breakdown

| group | fields | result |
|-------|--------|--------|
| structure (version, experimentName, spacecraft, centralBody, propagation, maneuvers) | 6×12=72 | 70/72 |
| copied numbers (SMA, ecc+angles, gravity, pointMasses, SRP) | 5×12=60 | 53/60 |
| defaults (epoch, frame, drag, version) | 4×12=48 | 21/48 ← weak spot |
| SMA arithmetic (SMA field) | 1×12=12 | 5/12 |
| Earth/Moon/Mars vs new bodies (T01–T04, T09–T12 vs T05–T08) | — | no body-specific signal in the field scores; failures are body-agnostic (defaults/keys) |

The decisive weakness is the **defaults group (21/48)**: epoch wrong-default,
frame placed at top level, and drag extended with non-schema keys — all of which
also flip the accept-expected verdicts to reject.

---

## 3. Failure classes (counts over T01–T12, 35 failed cells)

| class | count | tests → got vs expected |
|-------|-------|--------------------------|
| **wrong schema key** (extra key inside drag/forceModel) | 9 | T01 `atmosphericDrag.solarApsectRatio`; T02 `forceModel.atmosphereModel` (scalar, not an object); T03 `atmosphericDrag.solarActivityLevel`; T04 `atmosphericDrag.solarCycle`; T05 `atmosphericDrag.solarActivityIndex`; T06 `atmosphericDrag.spaceWeatherSensitivity`; T07 `atmosphericDrag.rateCoefficient`; T09 `atmosphericDrag.maxDensityGPerCm3`; T12 `atmosphericDrag.solarActivityIndex`. All should be `{"enabled":false,"model":"JacchiaRoberts"}`; instead the model synthesized plausible-looking atmosphere/space-weather keys. |
| **wrong default** (epoch year) | 8 | T01,T02,T03,T07,T09,T10,T11,T12 emit `01 Jan 2023 12:00:00.000`, expected `01 Jan 2026 12:00:00.000` (T05,T06 correctly use 2026). The model hard-codes a stale default year instead of the schema-default 2026. |
| **missing key** | 4 | T01 `version` absent; T04 & T08 `epoch` object absent; T05 `maneuvers` key absent. |
| **wrong placement** (frame top-level) | 6 | T03,T04,T05,T07,T08,T11 put `coordinateSystem` at the top level instead of inside `initialOrbit` (→ the `unsupported:$.coordinateSystem` verdict). |
| **arithmetic error** (SMA) | 7 | T02 7674.86 vs 19080.389; T03 1855.1 vs 1797.4; T05 6602.83 vs 6501.8; T07 282119.8 vs 321492.0; T09 6378.137 vs 6448.1363; T10 6799 vs 6878.1363; T12 3714.118 vs 3576.316. |
| **wrong type** (drag boolean) | 1 | T08 `atmosphericDrag: false` (boolean) rather than an object. |
| **invalid JSON** | 0 | all 14 blocks parsed clean. |
| **format only** | 0 | fences stripped; no scoring impact. |

Sum = 9 + 8 + 4 + 6 + 7 + 1 = 35 = 168 − 133 ✓.

---

## 4. Extras — T13 (#13 `MercB2_027`, Mercury) & T14 (#14 `ParaphraseTrain033`, Earth)

No gold for orbit elements / SMA / expName / centralBody / dryMass were given in
the tasking, so those are **N/A** here. Only default-driven and
schema-conformance fields are scored.

| field (conformance) | #13 MercB2_027 | #14 ParaphraseTrain033 |
|---------------------|----------------|--------------------------|
| version == 1.0 | ✅ | ❌ (absent) |
| experimentName present | ✅ | ✅ |
| epoch == default 2026 | ❌ (`01 Jan 2024`) | ❌ (`01 Jan 2024`) |
| frame inside initialOrbit | ❌ (top-level) | ✅ (`EarthMJ2000Eq`) |
| gravity degree/order default | ✅ (0/0, Mercury) | ✅ (4/4, Earth) |
| pointMasses default | ✅ (`[Luna,Sun]`) | ✅ (`[Luna,Sun]`) |
| drag object conforms | ❌ (extra `solarWindSpeedKmS`) | ❌ (extra `solarActivityIndex:50`) |
| SRP true | ✅ | ✅ |
| maneuvers key present | ✅ (`[]`) | ✅ |
| propagation conforms | ✅ (RK89 / stopCondition / 60 s) | ✅ (RK89 / stopCondition / 60 s) |
| **total conformance** | **7/10** | **7/10** |

Both are rejected by the pipeline on the hallucinated drag/coordinateSystem keys
(see §1).

---

## 5. Comparison with attempt 1

| metric | attempt 1 | attempt 2 (this) | Δ |
|--------|-----------|------------------|---|
| overall field score | 137/168 = 81.5% | **133/168 = 79.2%** | −0.7 pp (slightly worse) |
| fully correct tests | 0 | 0 | = |
| SMA | 4/12 | **5/12** | +1 |
| maneuvers key | 5/12 | **11/12** | +6 |
| propagation block | 9/12 | **12/12** | +3 |
| drag object | 8/12 | **2/12** | −6 |
| blind accuracy | — | **0/32** | new baseline |
| realistic accuracy | — | **0/30** | new baseline |

Attempt 2 improves copy reliability (SMA, maneuvers key, propagation) but
regresses hard on the **drag object** (8/12 → 2/12) because the model now
invents plausible atmosphere/space-weather keys (`solarActivity*`,
`rateCoefficient`, `maxDensityGPerCm3`, …) inside `atmosphericDrag`. Those
invented keys are exactly what drives the accept-expected tests (T01–T08) to a
**0%** verdict pass rate, and the same hallucination pattern also zeroes the
blind (0/32) and realistic (0/30) endpoint evals.

---

## 6. Blind & realistic endpoint accuracy (model `deepseek-ai/DeepSeek-V4-Flash-0731:deepinfra` via router)

| set | cases | verdict accuracy | notes |
|-----|-------|------------------|-------|
| blind (`cases_blind.jsonl`) | 32 | **0/32 = 0%** | all rejected on `unsupported:` keys (`experiment`, `orbit`, `initial_state`, `dry_mass_kg`, `propagator`, …) |
| realistic (`cases_realistic.jsonl`) | 30 | **0/30 = 0%** | all rejected on `unsupported:` keys |

Full per-case evidence saved to `eval/blind_A2.json` + `eval/blind_A2.report.md`
and `eval/realistic_A2.json` + `eval/realistic_A2.report.md` (endpoint
`deepseek-ai/DeepSeek-V4-Flash-0731:deepinfra`, run with `run_eval.py` from
`datasets/v11_train/eval/`).

Every accept-expected endpoint case is rejected for hallucinated/alternate keys
(`$.experiment`, `$.propagator`, `$.orbit`, snake_case variants, etc.) rather
than the canonical keys. This confirms the same root cause as the pasted-output
set: the model's field/key vocabulary is misaligned with the interpreter's
canonical schema, so `_unsupported_fields` fires on nearly every generation.

---

## 7. Next change (one recommendation for attempt 3)

**Anchor the generated keys to the interpreter's exact allowed field set, and
stop inventing atmosphere/space-weather keys.**

Root cause evidence: every accept-expected test and every blind/realistic case
fails because the model emits non-canonical keys that `_unsupported_fields`
rejects first. Three specific, fixed patterns dominate:

1. **drag/forceModel hallucination (9/12 tests + both extras):** the model
   synthesizes `solarActivityIndex`, `solarActivityLevel`, `solarCycle`,
   `solarApsectRatio`, `rateCoefficient`, `spaceWeatherSensitivity`,
   `maxDensityGPerCm3`, `solarWindSpeedKmS` inside `atmosphericDrag`, plus a
   scalar `atmosphereModel` at `forceModel`. The allowed drag keys are exactly
   `{enabled, model}` with `model: "JacchiaRoberts"`.
2. **frame placed at top level (6/12):** `coordinateSystem` must live inside
   `initialOrbit` as `<Body>MJ2000Eq`.
3. **stale epoch default (8/12 + both extras):** the model emits 2023/2024
   instead of the schema default `01 Jan 2026 12:00:00.000`.

Recommended single change: **augment the training data (and/or the system
prompt contract) with explicit positive + negative example pairs for the
`atmosphericDrag` block and the `initialOrbit.coordinateSystem` placement, and
pin the canonical default epoch year so the model copies `2026` rather than a
stale hard-coded year.** This directly targets the highest-count failure class
(drag keys, 9) plus the two next-largest placement/default classes, and — because
drag-key hallucination is what zeroes the accept-expected and endpoint verdicts —
should move blind/realistic accuracy off 0% in attempt 3.

---

## Deliverables

- `TASKING_A2.md` — saved tasking (with gold values).
- `outputs_raw_A2.txt` — raw 14 pasted outputs, **unchanged**.
- `results_A2.json` — machine-readable per-cell scores, failure classes, extras.
- `report_A2.md` — this report.
- `scripts/` — reproducible scoring pipeline (`a2_parse.py`, `a2_score.py`,
  `a2_field.py`, `a2_results.py`).
- `eval/` — endpoint eval evidence (blind + realistic, `.json` + `.report.md`).
- `datasets/v11_train/ATTEMPTS.md` — updated with attempt-2 blind/realistic + field score.
