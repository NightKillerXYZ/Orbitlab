# OrbitLab V2 Specification

## 0. Architecture (unchanged)

Natural language → extractor → interpreter → verify → validator →
deterministic compiler → real GMAT. The model never writes raw GMAT script:
it only fills the experiment JSON; the compiler renders the script from fixed
templates and the validator rejects unsafe physics before anything compiles.
v2 extends the schema, the compiler, and the UI — never this division of labor.

## 1. v1.x fixes first (prerequisites, already in flight)

- Burn without delta-V asks the user instead of crashing or inventing a vector
  (`needs_clarification`, burn-size wording).
- Per-body point-mass perturber defaults with central-body stripping
  (Earth → Luna, Sun; Moon → Earth, Sun; Mars → Sun).
- Guided (schema-constrained) JSON decoding trial behind `ORBITLAB_GUIDED_JSON`.

## 2. v2a — mostly compiler/backend, light model data

### 2.1 What-if and compare with multi-turn follow-ups

- Schema additions: `session {parentRunId, revisedFields[]}`, no new physics fields.
- Compiler work: none (recompile edited experiment).
- Validator rules: re-validate full experiment on every follow-up; verify scopes
  comparison to `revisedFields`.
- UI work: follow-up input on the result card; side-by-side compare of two runs
  (telemetry overlay + delta table).
- Tests: follow-up changes only targeted fields; compare renders two runs;
  20-prompt multi-turn eval set passes.
- Size: **M**.

### 2.2 All planets and the Sun as central bodies

- Schema additions: extend `centralBody` enum with Saturn, Uranus, Neptune (others already supported).
- Compiler work: none beyond `bodies.json` entries (frames, potential files, point-mass-only flags flow through existing paths).
- Validator rules: per-body minimum periapsis altitude, drag refusal (gas/ice giants: no drag), SOI containment where bounded.
- UI work: body picker entries; texture/provenance credits per new body.
- Tests: per-body boundary tests (min-alt ±, SOI), compiler emission tests, texture presence.
- Size: **S**.

### 2.3 Higher-fidelity force models

- Schema additions: `forceModel {gravityDegree, gravityOrder, dragModel enum
  [JacchiaRoberts, MSISE90, HarrisPriester], srpModel, pointMasses[]}` with per-body allowed sets.
- Compiler work: emit drag-model selection, SRP shape parameters, third-body list; degree/order caps per body.
- Validator rules: policy table — allowed drag models per body (Earth only for now), degree/order ≤ body maximum, unknown third body rejected.
- UI work: force-model section in Details; warnings surfaced as notes.
- Tests: policy-table unit tests; compiler lines per model; eval prompts requesting specific models.
- Size: **M**.

### 2.4 More frames, state types, time scales

- Schema additions: `coordinateSystem` extended (e.g. ICRF/J2000 variants, body-fixed);
  state types beyond Keplerian/Cartesian (e.g. equinoctial, spherical);
  `epoch {format, value}` extended with TDB/TT scales.
- Compiler work: frame/epoch rendering per GMAT syntax; conversions reuse front-step converters.
- Validator rules: frame valid for central body; epoch parseable in stated scale; converted state sane (energy/angular momentum).
- UI work: frame/state-type display in Details; epoch shown with scale.
- Tests: conversion round-trips; compiler output per frame; invalid-frame rejection.
- Size: **M**.

### 2.5 Eclipse and ground-station contact events

- Schema additions: `events[] {type: eclipse | contact, station {name, latDeg, lonDeg, altKm, minElevationDeg} | shadowModel}`.
- Compiler work: GMAT eclipse/contact locators + event reports; report-file fields for event spans.
- Validator rules: station coordinates in range; elevation mask 0–90°; event requests need a propagation span that can contain them.
- UI work: event markers on timeline and ground track; event list tab.
- Tests: compiler emits locators; validator rejects bad stations; eval with/without stations (ask case).
- Size: **M**.

### 2.6 Report and ephemeris export (CCSDS / SPICE / STK)

- Schema additions: `outputs {ephemerisFormat enum, reportFields[], stepSecs}`.
- Compiler work: GMAT `ReportFile`/ephemeris writers (CCSDS OEM, SPK via export, STK `.e`); file paths under the run folder.
- Validator rules: step size positive and ≤ duration; format supported.
- UI work: download buttons per format; Details tab lists generated files.
- Tests: route returns file bytes for a canned run; 404 for unknown runs; no path traversal.
- Size: **S**.

### 2.7 Parameter sweeps

- Schema additions: `sweep {parameter, from, to, steps}` (one parameter, bounded steps).
- Compiler work: none per-run (N experiments through the existing pipeline).
- Validator rules: swept parameter must be a sweepable field; steps cap (e.g. ≤ 11); total estimated wall time within timeout.
- UI work: sweep setup (parameter + range), results grid/mini-plots, per-run drill-down.
- Tests: N runs dispatched; cap enforced; aggregation correct on canned runs.
- Size: **L**.

### 2.8 Fuel and delta-V budget

- Schema additions: none (derived); optional `budget {dryMassKg, ispSecs}` override for reporting.
- Compiler work: none (impulsive burns already compile).
- Validator rules: total delta-V summed from maneuvers; warn when budget exceeded if fuel data present.
- UI work: budget table in Results (per-burn and total delta-V, remaining estimate).
- Tests: budget math unit tests; table renders on runs with burns.
- Size: **M**.

## 3. v2b — heavy

### 3.1 Fuel tank, thruster, finite burns

- Schema additions: `hardware {tanks[] {fuelKg, ispSecs}, thrusters[] {name, thrustN, tank}}`;
  `maneuvers[]` gains finite-burn type with duration/thrust profile.
- Compiler work: GMAT `FuelTank`/`Thruster` resources + finite-burn sequence; mass depletion across burns.
- Validator rules: thrust > 0, fuel sufficient for planned delta-V, tank referenced by thruster exists.
- UI work: hardware section in setup/results; fuel-remaining readout.
- Tests: compiler hardware block; insufficient-fuel refusal; eval prompts with/without hardware (ask cases).
- Size: **L**.

### 3.2 Target (differential corrector)

- Schema additions: `target {goals[] {variable, targetValue, tolerance}, maxIterations}`.
- Compiler work: GMAT `Target` loop with `Vary`/`Achieve` around propagation; iteration cap; convergence report parsing.
- Validator rules: goals reference solved variables; tolerances positive; iteration cap bounded.
- UI work: target status (converged/iterations) in Results; goal table.
- Tests: canned converged/diverged runs; cap enforcement; non-convergence is a clean failure, not a crash.
- Size: **L**.

### 3.3 Mission templates

Earth→Moon, GTO→GEO, Earth→Mars Hohmann, sun-synchronous, Molniya, geostationary.
- Schema additions: `template {name, params{}}` resolved to a full experiment before verify.
- Compiler work: none (templates lower to existing schema; analytic Hohmann needs no Target).
- Validator rules: template params in range; resolved experiment passes standard validation.
- UI work: template gallery with parameter forms; one-click run.
- Tests: each template resolves + validates + compiles; ~20–30 prompt variations per template in training/eval.
- Size: **M** (analytic ones **S** each).

### 3.4 Walker constellations (multi-spacecraft)

- Schema additions: `spacecraft[]` (array), `constellation {planes, satsPerPlane, phasing}` expanding to spacecraft entries.
- Compiler work: N spacecraft + per-spacecraft propagators/sequences from templates.
- Validator rules: spacecraft names unique; count cap; each member validates.
- UI work: multi-spacecraft viewer support (select/focus craft, combined tracks).
- Tests: expansion count correct; viewer handles N tracks; cap enforced.
- Size: **L**.

### 3.5 Two-body view for transfers

- Schema additions: none (view-only; uses Hohmann/transfer runs).
- Compiler work: none.
- Validator rules: none (requires a transfer maneuver present to activate).
- UI work: Sun-centered two-body transfer arc view (departure/target body positions, transfer ellipse).
- Tests: view renders on Hohmann runs, hidden otherwise.
- Size: **M**.

## 4. Dependencies

- Target (§3.2) unlocks the Earth→Moon template (§3.3): lunar transfer needs a corrector; ship other templates first.
- Hohmann-type templates (GTO→GEO, Earth→Mars, GEO circularization) are analytic and need no Target.
- Constellations (§3.4) need multi-spacecraft viewer support before the schema expansion is usable.

## 5. Schema evolution

Modular sections — `environment` (body, frame, forces), `hardware` (tanks, thrusters),
`maneuvers`, `events`, `outputs` — with a `schemaVersion` field. Additive-only
changes stay v1.0-compatible: existing v1.0 experiments validate unchanged;
new sections are optional with documented defaults.

## 6. Cut line

If time is short: ship v2a plus the analytic templates (§3.3 minus Earth→Moon)
and move Target (§3.2) and finite burns (§3.1) to v3. Constellations and the
two-body view follow the viewer work, not the physics work.

## 7. v3 and beyond

Control-flow scripting (loops/branches over mission phases), Optimize/CSALT
trajectory optimization. Orbit determination is out of scope for now.

## 8. Dataset policy

One data version per phase (v2a-train, v2b-train, …). Mission templates need
about 20–30 prompt variations each. Every new feature gets an eval set written
BEFORE training (see `evals/v2/`); a feature trains only after its eval exists.
