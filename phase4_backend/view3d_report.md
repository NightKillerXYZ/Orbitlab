# 3D orbit view report (`v1-3d-view`)

## Step 1 — current rendering (read-only)

- Telemetry source: `trajPts()` (`app.js:78`) reads
  `lastResult.trajectory.points`, an array of samples with
  `elapsed_secs, x_km, y_km, z_km, vx_km_s, vy_km_s, vz_km_s,
  semi_major_axis_km, eccentricity, inclination_deg, altitude_km`
  (km, km/s, s). Frame: body-centred inertial matching the experiment's
  `coordinateSystem` (`EarthMJ2000Eq`, `LunaMJ2000Eq`, …) — same frame as the
  telemetry. Central body: `lastResult.experiment.centralBody`.
- 2D rendering (`renderRealRun`, `app.js:217`): SVG overlay `#runOrbit` in
  `#orbitVisual` — body disc at projected origin, x/y polyline via `fitOrbit`
  (body-centred fit, `app.js:28`), spacecraft marker `#runCraft` moved by
  `drawCraft` (`app.js:262`).
- Playback state: `animT` (elapsed seconds into `trajSpan()`), `animPlaying`,
  `speed` (1/2/5/10). 100 ms tick: `animT += span/600*speed`, wraps to pause
  at end. Controls: `#playBtn` toggles, `#resetBtn` zeroes, `#speedBtn`
  cycles, `#timelineKnob` parent click sets `animT = f*span`; `drawCraft` moves
  the marker + timeline fill/knob + `#captionSpeed`/`#simTime`.
- 2D/3D toggle (`app.js:319`): buttons `data-view="2D"/"3D"` toggle the
  `active` class and `view-3d` on `#orbitVisual` (CSS-only tilted look today);
  no telemetry re-read, no JS branch. HUD (`#captionSpeed`, `#simTime`,
  stat cards) is updated by the same `drawCraft`/`updateTelemetry` path.
- `ui_adapter.js` only transports jobs (`runExperiment` → `{result|error}`);
  `index.html:48-51` holds the static panel skeleton (`.view-toggle`,
  `#orbitVisual`, `.telemetry-row`, controls).
- x/y/z samples exist, so no stop needed.

## Steps 2–4 — implementation (done)

- three.js r160 vendored at `UIUX/OrbitlabUI Main/vendor/three/`
  (`three.module.min.js`, `OrbitControls.js` with `from 'three'` rewritten to
  `./three.module.min.js`, `LICENSE`); installed via npm in `%TEMP%`
  (outside the repo), no `node_modules` committed, no CDN at run time.
- `UIUX/OrbitlabUI Main/view3d.js` (classic script, dynamic `import()`):
  `createView3D(container)` → `{setResult(telemetry, centralBody),
  setProgress(0..1), dispose(), ready}`. Black scene, a few hundred static
  random stars, central-body sphere at the true table radius
  (Earth 6378.137, Moon 1737.4, Mars 3396.2, Mercury 2439.7, Venus 6051.8,
  Jupiter 71492, Sun 695700 km) textured from
  `assets/textures/<body>.jpg` when present else a plain shaded sphere in a
  per-body colour (missing texture resolves to the fallback, never throws);
  trajectory decimated evenly to ≤5000 points keeping first+last, dim full
  line + bright travelled part via `setDrawRange`; white spacecraft marker;
  X/Y/Z axis lines at ±1.5× max orbit radius with sprite labels; auto-framing
  camera; OrbitControls with damping; resize handling; render-on-demand
  (no rAF loop). Same frame as telemetry, no coordinate transform, no planet
  rotation.
- Wiring (`app.js`, 2D untouched): the existing toggle flips `view-3d` and
  now calls `showView3D`/`hideView3D` — with telemetry, the 3D canvas shows
  and the 2D SVG hides (and vice versa); without telemetry the old CSS look
  remains. Play/pause/speed/slider all funnel through `animT`/`drawCraft`,
  which now also calls `view3d.setProgress(fraction)`; HUD untouched. New runs
  dispose the old scene via `clearRunDrawing`; failures restore as before.
- `assets/textures/README.md` lists the 7 files, equirectangular rule and
  credits (JPL/Caltech, Bjorn Jonsson, Celestia Motherlode). No image files
  were downloaded or generated. `index.html` loads `view3d.js` before `app.js`.

## Step 5 — stats fix (done)

- Eccentricity card: `e=(ra-rp)/(ra+rp)` from stats min/max altitude +
  body radius (`apoapsisEccentricity`), 3 decimals, falling back to the
  initial elements value only when stats are missing. A Hohmann 7000→9000 km
  run now shows 0.125 instead of 0.
- Inclination card: mean angle between r×v and +Z over samples
  (`telemetryInclinationDeg`); when samples lack position/velocity it shows
  the initial value labelled `initial`. Both helpers are pure, exported, and
  Node-tested with hand-computed comments.

## Step 6 — tests (done)

- `tests/view3d.test.cjs` (6): radius table, texture names, decimation
  budget/first/last/evenness, progress interpolation, full
  `createView3D` build/drive/dispose with stubbed THREE+DOM (missing texture
  → fallback colour, no throw; unknown body likewise).
- `ui_helpers.test.cjs` (+2): Hohmann e=0.125 and 30° r×v hand calculations.
- `ui_render.test.cjs`: stat cells updated to the new specified values
  (e=0.001, i=0.01° on the Earth fixture).
- Playwright is NOT installed here, so no screenshot was taken and nothing
  was visually verified in a browser: **not checked visually**. Manual check:
  `http://127.0.0.1:8000/main?fixture=1`, toggle to 3D (software WebGL,
  deviceScaleFactor 1). `phase4_backend/view3d_screenshot.png` was not
  created for the same reason.

## Step 7 — verification

- Node (`node --test tests/view3d.test.cjs tests/ui_helpers.test.cjs tests/ui_render.test.cjs`): 25 pass.
- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 166 passed + 28 skipped.
- Core / sim (repo root): 48 (+29 subtests) / 23 passed.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell: tests/e2e 49, tests 145,
  orbitlab_core/tests 48, simulation_engine/tests 23 — 265 passed, 0 failed.
- Unsure: real-GPU/WebGL rendering path (headless stubs only); exact on-screen
  layout of the 3D canvas vs HUD at small viewport sizes; texture appearance
  (no texture files exist yet — fallback path is the live one).
