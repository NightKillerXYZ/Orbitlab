# Demo mode report (`v1-hardening`)

## Step 1 — defaults a complete experiment needs (read-only)

Source of truth is code, not this file. A complete experiment JSON
(`tests/fixtures/real_result_earth.json :: result.experiment`, same shape as
the canonical `test_pipeline.py` fixture) needs:

- `version`: `"1.0"` (`OrbitLabExperiment.version`, models.py).
- `experimentName` / `spacecraft.name`: owned by Python, never the model —
  `frontstep.verify.frontstep_expected_names` derives them from the converted
  sentence (`sanitize_identifier`, `SC_` prefix); `apply_frontstep_names`
  overwrites whatever the interpreter returned, `normalize_maneuver_ids`
  assigns `M1, M2, ...`.
- `spacecraft`: `dryMassKg` from the sentence; the rest are schema defaults
  (`SpacecraftConfig`, models.py): `coefficientOfDrag 2.2`, `dragAreaM2 1.0`,
  `coefficientOfReflectivity 1.8`, `srpAreaM2 1.0`.
- `centralBody`: one of the 7 literals (models.py).
- `epoch`: schema default (`EpochConfig`): `UTCGregorian`,
  `01 Jan 2026 12:00:00.000`.
- `initialOrbit`: `type Keplerian` (+ `coordinatesystem` auto-filled from
  `CENTRAL_BODY_PROPERTIES` index 3: Earth→`EarthMJ2000Eq`, Moon→`LunaMJ2000Eq`,
  Mars→`MarsMJ2000Eq`, Mercury→`MercuryMJ2000Eq`, Venus→`VenusMJ2000Eq`,
  Jupiter→`JupiterMJ2000Eq`, Sun→`SunMJ2000Eq`; mismatch is a schema error);
  Keplerian elements come from the converted sentence (sma, e, i, raan, aop,
  ta; converter defaults i/raan/aop/ta to 0, e to 0 for circular).
- `forceModel`: schema defaults (`ForceModelConfig`): degree/order 4/4,
  `pointMasses ["Luna","Sun"]`, drag disabled (`JacchiaRoberts`), SRP on.
  Validator rules (validation.py): drag enabled is an *error* unless
  `BODY_ALLOWS_DRAG[body]` (only Earth allows it); degree/order > 0 on a
  `POINT_MASS_ONLY_BODIES` member (Mercury, Jupiter, Sun) is only a warning;
  periapsis must clear `MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY`
  (Earth 100, Moon/Mars/Mercury 20, Venus 100, Jupiter 1000, Sun 6261300 km).
- `propagation`: `integrator` from the sentence (`RungeKutta89` default, or
  `PrinceDormand78`; anything else → `RungeKutta89`); `stopCondition`
  `{type,value}` from converted duration (ElapsedDays/ElapsedHours/
  ElapsedSeconds/OrbitPeriods, schema caps 365 d / 8760 h / 31536000 s /
  365 periods); `stepSizeSecs` schema default 60.0.
- `maneuvers`: validator-form configs. `verify_experiment` compares count,
  `targetObjectives.targetOrbitRadiusKm`, and `burnVector.deltaVVectorKmS[3]`
  against the front-step `sent` shapes (`{"type":"Hohmann",...,
  "targetOrbitRadiusKm","apsis"}` → `TargetedHohmannTransfer` with
  `trigger AtPeriapsis/AtApoapsis`; `{"type":"ImpulsiveBurn",...,"deltaV"}`
  → `ImpulsiveBurn` with `burnVector LocalVNB`).
- `verify_experiment` (verify.py) compares: centralBody, dryMassKg (rel 1e-9),
  sma (abs 0.001 km), e/i/raan/aop/ta (rel 1e-9), integrator, stop type+value,
  explicit forces, maneuver count/target/Δv. Names are overridden, never
  compared.

## Steps 2–3 — implementation (done)

- `config.py` + `.env.example`: `ORBITLAB_DEMO_MODE` (default false).
- New `frontstep/demo.py` (no network, no model calls): `demo_enabled()`;
  `DemoExtractor` parses free text into the exact strict schema (mass in kg;
  Earth/Moon/Mars/Mercury/Venus/Jupiter/Sun + lunar/martian; the listed orbit
  phrasings incl. "7000 km circular orbit" as radius; ecc/inc/raan/AoP/TA;
  seconds/hours/days/orbits incl. singulars; Hohmann "to 9000 km" with
  at-periapsis/at-apoapsis triggers, and "burn at apoapsis to N km" as a
  Hohmann — a bare burn with no target is omitted since a valid
  `ImpulsiveBurn` needs a Δv vector no sentence provides; unknowns stay
  null so the real flow clarifies honestly). Real `normalize_extracted` +
  `deterministic_convert` run unchanged.
- `DemoInterpreter` parses the canonical prompt our own `prompt_builder`
  emits (sma/ecc/inc/raan/aop/ta, stop value+unit, integrator, Hohmann and
  both ImpulsiveBurn sentence forms) and builds the full experiment JSON from
  schema defaults (Cd 2.2 etc., epoch, per-body `*MJ2000Eq`, forceModel
  4x4/Luna+Sun/drag-off/SRP-on, step 60 s); verify passes, validator/compiler/
  real GMAT run unchanged.
- Factories only branch on the flag (`get_extractor` → `DemoExtractor`,
  `get_interpreter_client` → `DemoInterpreter`, `get_explainer` → existing
  `MockExplainer` → `explanationSource "fallback"`); real clients untouched.
  `Pipeline` forwards any non-mock extractor (was: only `OpenAIExtractor`).
- Result carries `"mode":"demo"` only in demo mode; `/api/health` returns
  `mode: demo` only in demo mode (unchanged otherwise). UI shows a
  "DEMO MODE" badge in the header when health or the result says so
  (existing badge style; covered by a Node test).

## Step 4 — tests (done)

- `tests/test_demo_mode.py` (7, offline): parser shapes incl. all quantity
  kinds, lunar/martian, angles, seconds; convert→build→verify roundtrip incl.
  Hohmann; full pipeline with `socket.socket` blocked (no network);
  4 incomplete prompts → exact missing fields; 50 km Earth periapsis → validate
  failure with explanation; health with/without flag; factories.
- `tests/e2e/test_e2e_demo.py`: 12 prompts × real GMAT (all ≤ 2 d or 5 orbits)
  → success + `mode: demo` + fallback; 4 clarification + 1 validator case via
  API (no GMAT needed).

12 GMAT prompts and outcomes (all success, `e2e_all` run):
earth-circular-1d, moon-6h, mars-periapsis-2d, venus-sma-5orbits,
mercury-circular-2d, jupiter-circular-2d, sun-sma-2d, earth-hohmann-2d,
mars-burn-apoapsis-2d, earth-seconds, moon-exact-6h, lunar-12h.

Unsure / notes: a bare "burn at apoapsis" with no target and no Δv is
deliberately dropped (no validator-valid maneuver exists for it); "400 km
circular" without the word "orbit"/"altitude" is not read as an orbit (regex
fallback behaves the same); Sun demo runs propagate 2 simulated days only —
5 orbit periods of a 7e7 km orbit would exceed the estimator timeout guard.
No browser pixels were checked (no Playwright/jsdom); the badge was asserted
in the fake-DOM Node test only.

## Verification

- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 166 passed + 28 skipped.
- Node: `node --test tests/ui_helpers.test.cjs tests/ui_render.test.cjs`: 17 pass.
- Core / sim (repo root): 48 (+29 subtests) / 23 passed.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell: tests/e2e 49, tests 145,
  orbitlab_core/tests 48, simulation_engine/tests 23 — 265 passed, 0 failed.
