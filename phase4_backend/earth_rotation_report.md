# Earth rotation in the 3D view (`v1-earth-rotation`)

## Step 1 — what view3d.js and groundtrack.js contain today (read only)

### view3d.js — no rotation anywhere
- The central-body mesh is built as `new THREE.Mesh(new THREE.SphereGeometry(R,48,32),mat)`
  with no orientation or spin applied, for every body. Nothing in the file reads an
  epoch, computes GMST, or touches `mesh.rotation` on the body.
- The body is created asynchronously inside the `bodyMaterial(...).then(...)` callback
  (texture load may resolve after the rest of the scene); rotation applied only in
  `applyProgress` would therefore miss a late-arriving mesh unless it is also applied
  (or re-applied) when the mesh is added.
- The orbit track is drawn from raw telemetry `x_km/y_km/z_km`, i.e. already in the
  inertial (ECI/J2000-equatorial) frame — so only the Earth texture needs to spin
  beneath it; the track itself must not move.
- `setResult` reads `container.dataset.spacecraftName/bodyName` but no epoch; view3d
  never references `GroundTrack`, `gmstDeg`, or `parseGmatEpoch`. `groundtrack.js`
  loads after `view3d.js` in `index.html`, so only runtime (not load-time) use of the
  global is possible.

### groundtrack.js — the shared helpers (unchanged, reused as-is)
- `parseGmatEpoch("01 Jan 2026 12:00:00.000")` → Julian date (UT1 treated as UTC).
- `gmstDeg(jd)` → IAU 1982 GMST in degrees, normalized to [0,360).
- `eciToLatLon` uses `lon = atan2(y,x) − GMST`: at GMST 0, longitude λ sits on the
  inertial ray at angle λ from +X. The 3D view must use the same convention so both
  views agree: texture longitude λ must appear at inertial angle λ + GMST, i.e. the
  mesh rotates **+GMST about +Z** (counterclockwise seen from north).

### Vendored three.js r160 SphereGeometry — UV orientation verified in
`vendor/three/three.module.min.js` (not from memory)
- Vertices: `x = -r·cos(u·2π)·sinθ`, `y = r·cosθ`, `z = r·sin(u·2π)·sinθ`,
  `uv = (u, 1−v)` with defaults `phiStart=0, phiLength=2π`.
- `u = 0.5` is the image centre = longitude 0 → `phi = π` → `x = +r·sinθ`:
  **longitude 0 already faces +X at zero rotation** (equator), so the needed
  texture offset constant is `EARTH_TEX_OFFSET_DEG = 0` (kept as a named constant
  with this derivation in a comment).
- Poles come out along **±Y** (three spheres are Y-up) while the scene is Z-up
  (`camera.up = (0,0,1)`), so the Earth geometry additionally needs a baked
  `rotateX(+π/2)` (maps +Y→+Z, leaves the lon-0/+X alignment untouched:
  verified above: `(r,0,0)` is fixed by rotateX, lon 90E `(0,0,−r)` → `(0,+r,0)`,
  matching `atan2` convention). Without it, a Z-spin would tumble the texture like
  a rotisserie instead of spinning the planet. Other bodies keep their mesh
  untouched (out of scope; they do not rotate).

### Plan (Step 2)
- `app.js` sets `vis.dataset.epochValue` (the experiment's GMAT epoch string) in
  `renderRealRun`; view3d reads it in `setResult` and parses it with the same
  `GroundTrack.parseGmatEpoch` the ground track uses (via `deps.GroundTrack` or the
  `globalThis.GroundTrack` global at runtime; absent/unparseable → no rotation).
- New pure helper `earthSpinDeg(jd, gmstDegFn)` = normalized `gmstDeg(jd) + offset`,
  plus `earthTexAngleDeg(lon)` = normalized `lon + offset`; closure `spinBody(t)`
  sets `bodyMesh.rotation.z` for `body === 'Earth'` only, called from
  `applyProgress` and after the async body mesh is added. Public API unchanged.

## Step 2 — what changed (public API unchanged)

- `UIUX/OrbitlabUI Main/view3d.js`:
  - `EARTH_TEX_OFFSET_DEG = 0` plus pure helpers `earthTexAngleDeg(lon)` and
    `earthSpinDeg(jd, gmstDegFn)` (normalized GMST + offset; both exported).
  - Earth-only pole fix: the body geometry gets a baked `rotateX(+PI/2)`
    (guarded; three spheres are Y-up, the scene is Z-up). Verified: lon 0 stays
    on +X and lon 90E maps to +Y. Other bodies keep their mesh untouched.
  - `setResult` reads `container.dataset.epochValue` (GMAT epoch string) and
    resolves `parseGmatEpoch`/`gmstDeg` from `deps.GroundTrack` or the
    `globalThis.GroundTrack` global (the same helper the ground track uses, so
    both views agree). Absent/unparseable epoch or helper → no rotation.
  - New `spinBody(t)` closure sets `bodyMesh.rotation.z` for `body === 'Earth'`
    only; called from `applyProgress` every replay step and re-applied when the
    async body mesh arrives. Non-Earth bodies never spin.
- `UIUX/OrbitlabUI Main/app.js`: `renderRealRun` sets `vis.dataset.epochValue`
  from `experiment.epoch.value` (one guarded line; no other app changes).
- No backend/physics/validator/compiler/schema/HTTP-client/conversion changes
  (`groundtrack.js` untouched).

## Step 3 — Node tests (same `node --test` invocation, stub WebGL/DOM)

- `tests/view3d.test.cjs` (+4 tests, 18 total): spin angle equals
  `GT.gmstDeg` at t = 0/1/3600/21600/43200/86399 s; null-safe without helper or
  jd; one mean sidereal day (86164.0905 s) later the angle returns within
  0.01 deg; `EARTH_TEX_OFFSET_DEG === 0`, lon 0/90/-180 map to 0/90/180 deg
  (prime meridian on +X at GMST 0, computed from the offset logic, no GPU);
  Earth mesh `rotation.z` matches `earthSpinDeg` at progress 0/0.25/0.5/1 with
  baked `rotateX(PI/2)`; Moon with an epoch stays at `rotation.z === 0`, no
  pole fix, true radius kept.
- `tests/ui_render.test.cjs` (+1 test, 19 total): render wires
  `dataset.epochValue` (`01 Jan 2026 12:00:00.000`) plus names for the 3D view.
- Full Node run, all files: **64 passed, 0 fail**.

## Visual check (screenshots taken, continents moved)

Playwright/Chromium was not installed, so as on the previous branch
`playwright-core` (temp dir outside the repo) drove the installed system Chrome
headless (SwiftShader) against a local uvicorn server. `assets/textures/` ships
no `earth.jpg` by design (not committed), so a temporary procedural
equirectangular texture (green blobs, graticule, red lon-0 meridian) was
generated for the run and **deleted afterwards** — never committed.
- `phase4_backend/earth_spin_p0.png` (progress 0, T+00:00:00): red meridian
  vertical near disc centre, graticule/equator upright (poles up).
- `phase4_backend/earth_spin_p05.png` (progress 0.5, T+11:57:53): meridian gone
  to the far side (~180.5 deg of GMST advance), a different set of blobs/graticule
  visible; the red orbit track is unchanged in inertial space.
- **Continents moved between the two shots** while the orbit stayed fixed;
  zero page errors in both runs. GMST at epoch 281.15 deg, +12 h 101.65 deg
  (same helper as the ground track).

## Step 4 — suites and counts

- Node (existing invocation, all files): **64 passed, 0 failed**.
- Backend from `phase4_backend` (`python -m pytest ../tests -q`): **225 passed**.
- `scripts/e2e_all.py` from the repo root (`GMAT_PATH` from the shell only,
  never logged or committed): tests/e2e **49**, tests **176**,
  orbitlab_core **48**, simulation_engine **23** — **296 passed, 0 failed,
  total failed+errors 0**.

## Unsure / conservative readings

- Other bodies keep the Y-up sphere orientation and never rotate (explicit
  requirement; out of scope to fix their pole orientation).
- The temporary texture was removed after the run; `git status` confirms no
  `assets/textures/earth.jpg` and no other stray files from this task.
- Branch base confirmed: `v1-gmat-look` existed and is the ancestor of this
  branch (`git merge-base --is-ancestor`, exit 0).
