# Ground track report (`v1-ground-track`)

## Step 1 — frame, epoch, time base (read only)

- Telemetry frame: body-centred inertial matching `experiment.initialOrbit.coordinateSystem`
  (`EarthMJ2000Eq` for Earth runs — J2000 mean equator/equinox, ECI-like). No
  rotation is applied anywhere in the UI path today.
- Epoch: `experiment.epoch = {"format": "UTCGregorian", "value": "01 Jan 2026 12:00:00.000"}`.
- Time base: `elapsed_secs` per sample, seconds since the epoch (fixture: 0.0 → 86400.0 over 1016 points).
- Nothing missing: JD follows from epoch + elapsed/86400, GMST from JD, lat/lon from a Z-rotation.

## Steps 2–3 — implementation (done)

- New `UIUX/OrbitlabUI Main/groundtrack.js` (classic script, no imports, no
  CDN): `parseGmatEpoch` ("DD Mon YYYY HH:MM:SS.mmm" UTCGregorian → JD,
  verified 01 Jan 2026 12:00:00.000 → 2461042.0), `gmstDeg` (IAU 1982:
  280.46061837 + 360.98564736629 d⁻¹, normalized), `eciToLatLon` (Z-rotation
  by GMST, lon in [-180, 180]), `decimateIndices` (≤3000, first+last kept),
  `splitAtWrap` (segments split at ±180 crossings), `drawGroundTrack`
  (equirectangular canvas: lat/lon grid, or `assets/textures/earth.jpg` when
  it loads; track line with wrap breaks; start/end markers; degree axis
  labels; empty input → "No track points"; anything unexpected → false, never
  throws). Spherical Earth, no precession/nutation/polar motion (~0.2° error);
  the chart is labelled "GROUND TRACK (APPROXIMATE)".
- `index.html` loads `groundtrack.js` before `app.js`. Graph tab: new section
  with `<canvas id="groundTrack">` for Earth runs only (other bodies get
  "Ground track is available for Earth runs"); `renderTab` paints after the
  HTML lands (`paintGroundTrack`, fully guarded). Image loading is async with
  an onload redraw; a missing file or missing `Image` keeps the grid.
- `app.js` changes only: loader tag is a one-line `index.html` edit; new pure
  helpers + `paintGroundTrack` + Graph branch + `renderTab` hook + test
  exports. No backend code touched at all.

## Step 3 — tests (done)

- `tests/groundtrack.test.cjs` (8): epoch→JD, GMST at J2000 = 280.4606°,
  +X@J2000 → lon 79.539°/lat 0, +Z → lat 90, wrap split, decimation
  budget/endpoints, draw calls (grid/track/markers/degree labels) with a
  stub canvas, missing texture/bad canvas/empty input never throwing.
- `ui_render.test.cjs` (+2): Graph tab renders the ground-track canvas for
  the Earth fixture and paints grid+track+markers through the fake DOM;
  Mars fixture shows the non-Earth message and no canvas.

## Step 4 — verification

- Node (`node --test` on all five files — groundtrack, ui_helpers,
  ui_render, view3d, plots): 47 pass.
- Backend (`phase4_backend/`, `python -m pytest ../tests -q`): 169 passed + 28 skipped.
- Core / sim (repo root): 48 (+29 subtests) / 23 passed.
- `scripts/e2e_all.py` with `GMAT_PATH` in the shell: tests/e2e 49, tests 148,
  orbitlab_core/tests 48, simulation_engine/tests 23 — 268 passed, 0 failed.
- Unsure: on-screen look of the canvas (no browser here — fake-DOM only);
  `drawImage` path (no texture file or `Image` in the test env, so only the
  grid fallback is exercised); behaviour when a run's epoch format deviates
  from `UTCGregorian` (paint is skipped, tab keeps its message).
