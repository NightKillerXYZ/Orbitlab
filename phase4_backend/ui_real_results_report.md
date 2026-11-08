# UI real-results report (`ui-real-results`)

## Step 1 — what shows sample content today (read-only)

Sample/static Venus content in `UIUX/OrbitlabUI Main` (before any run, and —
the bug — also after a real run):

- Mission/title area (`index.html`): breadcrumbs `My missions / Venus in Motion`;
  `welcome-row h1` "Venus in Motion" + lead "Explore how gravity shapes the path
  of a planet around the Sun."; sidebar `mission-link[data-mission=venus]`
  "Venus in Motion".
- Main simulation card (`index.html`): `card-subtitle` "Observe Venus as it
  travels around the Sun"; `#orbitVisual` decorations — `.orbit-path`
  (`.path-outer`/`.path-main`/`.path-inner`, fixed 350/260/175 px ellipses),
  `.orbit-label.label-venus` "VENUS", `.label-sun` "THE SUN", `.sun-glow` +
  `.sun-core`, `.planet.venus-planet` (12 px, CSS-orbiting demo), static
  `.earth-planet` / `.mars-planet` dots, `.orbit-axis`, `.distance-line` +
  `.distance-label` "0.72 AU", `.scale-label` "NOT TO SCALE",
  `.visual-caption` "VENUS" + `#captionSpeed` "35.0 km/s"; `.telemetry-row`
  stat cards ORBITAL PERIOD 224.7 days / AVG. DISTANCE 108.2 million km /
  ORBITAL SPEED 35.0 km/s (`#speedMetric`) / ECCENTRICITY 0.007;
  `#simTime` "DAY 0.00", timeline knob maps 0–224.7 d, play button drives the
  demo Venus loop (`renderTime`, `#venusPlanet`).
- Assistant tabs (`app.js content.*` + `liveBody`): Chat welcome message +
  three quick-start chips (all "Venus…/…the Sun", `data-prompt`s);
  Understanding ("Falling around the Sun", Inertia/Gravity fact blocks);
  Results (baseline "Venus is following a stable, nearly circular orbit…",
  224.7/35.0/Near circular); Graph (hard-coded "Distance from the Sun (AU)"
  SVG + "0.72 AU avg." legend); Physics (Sun's mass / 108.2M km / 35.0 km/s).
  `liveBody` after a run only appends: Chat banner (body, a, e, mean speed,
  telemetry span), Results "Run complete/OUTCOME" block, Graph raw trajectory
  polyline + experiment JSON dump, Physics integrator/stop/sma + explanation
  text, Understanding body/sma/e/mass + explanation. The card, drawing, stat
  cards, titles and chips keep showing Venus.
- `?mock=1` (or missing adapter) renders `content.*` untouched and never calls
  the network (`runScenarioMock`).

Real result JSON (`tests/fixtures/real_result_earth.json`, copied from the
repo-root run, `events` dropped): `status`, `result.status`,
`result.experiment` (version, experimentName, spacecraft{name, dryMassKg,
Cd, areas}, centralBody, epoch, initialOrbit{type, coordinateSystem,
elements{semiMajorAxisKm, eccentricity, inclinationDeg, raanDeg,
argumentOfPeriapsisDeg, trueAnomalyDeg}} — Cartesian runs carry
`elements{xKm,yKm,zKm,vxKmS,vyKmS,vzKmS}` instead, forceModel{gravityDegree,
gravityOrder, pointMasses[], atmosphericDrag{enabled,model},
solarRadiationPressure}, maneuvers[] ({id,type,trigger{condition,elapsedSecs},
burnVector{deltaVVectorKmS[3]},targetObjectives{targetOrbitRadiusKm}}),
propagation{integrator, stopCondition{type,value}, stepSizeSecs}),
`result.warnings[]` (strings), `result.trajectory{full_count,
visualization_count, points[]}` with points
`{elapsed_secs,x_km,y_km,z_km,vx_km_s,vy_km_s,vz_km_s,semi_major_axis_km,eccentricity,inclination_deg,altitude_km}`
(km, km/s, s; thinned to ≤2000 for the card), `result.telemetry{points}`
(count only), `result.explanation` (string, may be ""), `result.explanationSource`
(`"model"`/`"fallback"`), `result.prompt`.

Already read after a run: Chat (body/a/e/mean speed/telemetry span),
Results (shape/mean speed/warning count), Graph (raw x/y polyline, no axes),
Physics + Understanding (integrator/stop/sma + explanation text).

## Steps 2–5 — what changed

All rendering lives in `UIUX/OrbitlabUI Main/app.js` (single JS file, existing
CSS only, no new libraries, dark theme kept); one read-only route in
`phase4_backend/orbitlab_backend/api/app.py`.

- Pure helpers at the top of `app.js` (no DOM): `BODY_TABLE` (radii + mu mirror
  `orbitlab_core/bodies.json`; colours UI-only), `fitOrbit` (body-centred fit
  with margin; null when nothing drawable), `trajectoryStats` (n/min/max/final
  alt/speed, span), `pointAltKm` (prefers `altitude_km`, else radius minus body
  radius), `keplerPeriodSecs` + `periodText` + `smaForDisplay` (the result
  carries no period, so the UI computes `T = 2*pi*sqrt(a^3/mu)` from the echo
  semi-major axis — or the telemetry mean for Cartesian echoes — and the
  body's mu), `fmtKm` (thousands separators, 1–3 decimals, `n/a` when missing),
  `fmtSecs`, `chartSVG` (labelled axes with units), `stopText`/`manText`/
  `forceText`.
- Success (`renderRealRun`, also used by `?fixture=1`): body disc with true
  radius ratio (clamped to 5–30 px so LEO discs stay visible), orbit polyline
  from x/y telemetry scaled to fit, spacecraft marker with Play/Pause (existing
  `#playBtn`), reset (`#resetBtn`) and timeline-slider (`#timelineKnob`) reused
  for the replay, live altitude/speed/elapsed in `#captionSpeed`/`#simTime`.
  Stat cards rebuilt to 5 cells: period, periapsis/apoapsis altitude,
  eccentricity, inclination. Titles/chips updated to the real body; SAMPLE
  badge (injected on load) flips to LIVE DATA.
- Tabs: Understanding gains duration/maneuvers/forces rows from the experiment
  echo; Results gains min/max alt, min/max speed, final state, point count and
  the warnings list (max 8 + count); Graph draws altitude-vs-time and
  speed-vs-time SVGs with unit-labelled axes (single point → dot; empty →
  "no trajectory returned", everything else `n/a`).
- Failed runs restore the previous result (or keep the labelled sample) and
  show only the failure banner, as before; a new run clears the previous SVG
  overlay before drawing. `?mock=1` path untouched.

## Step 6 — tests and visual verification

- `node --test tests/ui_helpers.test.cjs tests/ui_render.test.cjs`: 15 pass
  (helpers incl. the 1.54 h Earth period; render tests drive
  `renderRealRun`/`drawCraft`/`liveBody` against
  `tests/fixtures/real_result_earth.json` in a minimal fake DOM: 1016-point
  polyline, marker, badge, titles, stat cells, labelled charts, warnings).
- Backend: `test_sample_result.py` — `GET /` and `/main` still 200,
  `GET /sample-result` returns the fixture JSON (fixed file only).
- NOT visually verified: no Playwright and no jsdom are available offline, so
  no real browser pixels were checked — layout/overlap judged from CSS rules
  only. Check manually:
  `http://127.0.0.1:8000/main?fixture=1` (renders the Earth fixture exactly as
  a live run would, no models needed) and
  `http://127.0.0.1:8000/main` in normal mode.

## Step 7 — verification

- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 146 passed + 16 skipped.
- Core / sim (repo root): 48 (+29 subtests) / 23 passed.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell: tests/e2e 32, tests 130,
  orbitlab_core/tests 48, simulation_engine/tests 23 — 233 passed, 0 failed.
- Changed files: `UIUX/OrbitlabUI Main/app.js`,
  `phase4_backend/orbitlab_backend/api/app.py` (`/sample-result` only),
  `tests/fixtures/real_result_earth.json`, `tests/ui_helpers.test.cjs`,
  `tests/ui_render.test.cjs`, `tests/test_sample_result.py`.
