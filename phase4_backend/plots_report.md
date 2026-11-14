# Plots report (`v1-plots`)

## Step 1 — what the data and tabs hold today (read only)

Telemetry (`result.trajectory.points[]`, inertial per-body frame matching
`coordinateSystem`): `elapsed_secs`, `x_km/y_km/z_km`, `vx_km_s/vy_km_s/vz_km_s`,
`altitude_km`, plus per-sample `semi_major_axis_km`, `eccentricity`,
`inclination_deg`. So altitude/speed exist directly, but sma/ecc are derived
in JS from r/v with the body mu (labelled "computed from telemetry"), per the
task — never trusting per-sample elements for the new charts.
`result.experiment.maneuvers[]` is validator-shaped (`id`, `type`
`TargetedHohmannTransfer|ImpulsiveBurn`, `trigger{condition, elapsedSecs?}`,
`burnVector{deltaVVectorKmS[3]?}`, `targetObjectives{targetOrbitRadiusKm?}`);
no executed delta-v fields exist anywhere in the result today.

Graph tab today (`liveBody`, `app.js`): heading + `chartSVG` altitude-vs-time
and speed-vs-time (static SVG, all points, no hover, fixed km/km/s units) +
point-count legend. Results tab today: header, 4 metric cells (period, shape,
mean speed, outcome), 4 more (min/max alt/speed), final state, warnings
(max 8), export button — no maneuver table.

## Steps 2–3 — implementation (done)

- New `UIUX/OrbitlabUI Main/plots.js` (classic script, no imports, no CDN):
  mu table exactly as specified; `decimateIndices` (≤1500, first+last kept,
  evenly spaced); `chooseTimeUnit` (s < 120 s, min < 2 h, h < 2 d, else d);
  `orbitalElementsKm` (vis-viva + eccentricity vector); `hohmannEstimate`
  (dv1/dv2/total/transfer time); `lineChartSVG` (title, unit ticks, CSS-var
  colours with hex fallbacks, hover readout `(t, value)` via a transparent
  overlay rect → nearest sample, `setDrawRange`-free since SVG). Colours use
  `var(--blue/--cyan/--gold/--green/--muted/--line)` with the current hex
  values as fallbacks.
- Graph tab now shows 4 charts: (1) altitude `|r|-R`, (2) speed `|v|`,
  (3) semi-major axis + (4) eccentricity computed per sample from r/v with
  the body mu, both labelled "(computed from telemetry)". Time axis uses the
  most readable unit. Hover shows exact (t, value).
- Results tab: `maneuverSummary()` renders a MANEUVERS section (omitted when
  empty) from `experiment.maneuvers` — id, type, trigger, target radius for
  Hohmann, Δv magnitude for impulsive burns (planned values as-is). Hohmann
  rows add dv1/dv2/total/transfer time labelled "analytic estimate" (r1 =
  initial sma when e < 0.05 else initial periapsis radius — decision: a
  non-circular start departs from periapsis). `simDeltaVText` scans
  trajectory points for delta-v-shaped fields and would label them "from
  simulation"; none exist in current data, so that branch is untriggered
  (stated here, not hidden).
- Also loaded `plots.js` in `index.html` before `app.js`.

## Step 4 — tests (done)

- `tests/plots.test.cjs` (7): mu table, decimation budget/first/last/
  evenness, time-unit selection, circular-orbit elements from hand-computed
  r/v (a = 7000, e ≈ 0), Hohmann Earth 6678 → 42164 km (dv1 = 2.43 ± 0.02,
  dv2 = 1.47 ± 0.02, transfer = 5.27 h ± 0.02 — hand computation in the test
  comment), chart title/units/css-vars/hover hook, hover readout write via
  stubbed DOM.
- `ui_helpers.test.cjs` (+2): `apoapsisEccentricity` (Hohmann 7000→9000 =
  0.125 hand-computed) and `telemetryInclinationDeg` (30° hand-computed
  r×v case).
- `ui_render.test.cjs`: Graph now asserts 4 SVGs + sma/ecc headings; a new
  fixture test injects a Hohmann maneuver and asserts the MANEUVERS table,
  analytic-estimate labels, and absence of "from simulation".

## Verification and anything unsure

- Node (`node --test tests/plots.test.cjs tests/ui_helpers.test.cjs tests/ui_render.test.cjs tests/view3d.test.cjs`): 37 pass.
- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 169 passed + 28 skipped.
- Core / sim (repo root): 48 (+29 subtests) / 23 passed.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell: tests/e2e 49, tests 148,
  orbitlab_core/tests 48, simulation_engine/tests 23 — 268 passed, 0 failed.
- Unchecked: hover behaviour in a real browser (fake-DOM only); whether the
  per-sample `semi_major_axis_km`/`eccentricity` fields would ever disagree
  with the recomputed values (recompute is authoritative here by design);
  Hohmann estimates assume impulsive coplanar transfer from the stated r1.
