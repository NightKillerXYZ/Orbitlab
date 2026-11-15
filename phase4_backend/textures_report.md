# Real planet textures (`v1-textures`)

## Step 1 — where the textures come from (read only)

- GMAT location: the `GMAT_PATH` environment variable (a `GmatConsole`
  executable inside `<gmat>/bin`) is set and the file exists. Going up from
  the executable folder gives `<gmat>/data/graphics/texture`, which exists
  and contains `ModifiedBlueMarble.jpg` plus all six other required sources
  (list verified present; no `C:\\`/profile search needed, 60 s budget
  untouched). Absolute paths are deliberately not recorded here or in the
  repo (task rule: never print environment variables).
- Player contract (`UIUX/OrbitlabUI Main/view3d.js`, `textureFileFor`):
  `assets/textures/` + lowercase body name + `.jpg`, i.e. exactly
  `earth/moon/mars/mercury/venus/jupiter/sun.jpg`, loaded relative to
  `UIUX/OrbitlabUI Main/`. The existing `assets/textures/README.md` lists the
  same seven names as optional equirectangular (2:1) JPGs with plain-colour
  fallback and already suggests GMAT's texture set as the source.
- Base-branch note (decision recorded, then continued): `git checkout main`
  is impossible here (that ref is checked out in another worktree) and this
  repo's `main` ref is a 3-file stub (`.gitignore`, `ARCHITECTURE.md`,
  `schemas/`) with no backend/UI/tests, so it cannot host this task despite
  the brief's "launcher is merged there" premise. `v1-textures` was instead
  created from the launcher-branch tip (which contains the launcher, the
  backend, the UI and the suites) after verifying `v1-textures` did not exist.

## Plan (Steps 2–5)

- Copy byte for byte, no resize/recompress, only the seven mapped files;
  verify `.gitignore` exclusion first (fix only for this folder if needed).
- `CREDITS.md` per file: new name, original name, author from the original
  file name, GMAT `data/graphics/texture` provenance (Apache 2.0,
  `https://github.com/nasa/GMAT`), size in KB; licence quoted by title only
  and only if a licence/readme sits next to the textures.
- Update `assets/textures/README.md` (files now included) + one line in the
  root README "Credits" section pointing to `CREDITS.md`.
- Verification test (header bytes + non-empty + name coverage), screenshots
  at progress 0/0.5 with the Hohmann prompt if a browser is drivable, full
  suites, counts, commits.

## Steps 2–3 — what was copied and credited

- Seven files copied byte for byte (no resize, no recompress; JPEG SOI
  headers verified on read) from the installed GMAT's
  `data/graphics/texture` folder into
  `UIUX/OrbitlabUI Main/assets/textures/`, exactly the names the player
  requests (`view3d.js textureFileFor`: lowercase body + `.jpg`):
  `ModifiedBlueMarble.jpg` → `earth.jpg` (2319.9 KB),
  `Moon_HermesCelestiaMotherlode.jpg` → `moon.jpg` (234.1 KB),
  `Mars_JPLCaltechUSGS.jpg` → `mars.jpg` (794.8 KB),
  `Mercury_JPLCaltech.jpg` → `mercury.jpg` (405.5 KB),
  `Venus_BjornJonsson.jpg` → `venus.jpg` (57.9 KB),
  `Jupiter_HermesCelestiaMotherlode.jpg` → `jupiter.jpg` (406.8 KB),
  `Sun.jpg` → `sun.jpg` (26.3 KB). Total textures: 4347251 bytes (~4.1 MB).
  All seven are exactly 2:1 equirectangular as the player requires.
  No other GMAT file was copied. `.gitignore` does not exclude them
  (`git check-ignore` exit 1), so no ignore rule was touched.
- `assets/textures/CREDITS.md` lists new name, original name, author credit
  from the original file name, GMAT `data/graphics/texture` provenance
  (Apache 2.0, https://github.com/nasa/GMAT) and size in KB. No licence or
  readme file sits next to the textures in the GMAT folder, so no further
  licence terms are claimed. `assets/textures/README.md` now says the files
  are included (with a pointer to `CREDITS.md`); the root README "Credits"
  section gained one line pointing at `CREDITS.md`.
- No backend logic, physics, validator, compiler, schema, clients or JS/UI
  code was changed (textures + docs + one pytest file only).

## Step 4 — verification

- `tests/test_textures.py` (2 tests, pass): every name the player requests
  exists, is non-empty, starts with the JPEG SOI bytes and ends with the EOI
  trailer; the `textureFileFor` rule in `view3d.js` is asserted literally.
- Screenshots (system Chrome headless + SwiftShader via `playwright-core`,
  temp dir outside the repo; server in demo mode on :8000 with `GMAT_PATH`
  from the shell only; Hohmann prompt
  "500 kg satellite around Earth in a 7000 km circular orbit, Hohmann
  transfer to 9000 km at periapsis, 2 days"; 3D view; device scale factor 1):
  `phase4_backend/textures_earth_p0.png` (T+00:00:00) and
  `phase4_backend/textures_earth_p05.png` (T+24:49:30), zero page errors.
  **The Earth shows continents in both** (Africa/Europe/Middle East clearly
  visible; textured sphere, graticule upright, poles up).
- Texture motion between the two shots: pixel-diff over the globe disc shows
  only track/marker/label pixels changed (~1.4% raw, 0.7% excluding overlay
  colours — antialiasing at the track edge). The texture itself is static,
  which is the correct behaviour here: this demo run carries no parseable
  epoch (overlay reads `Epoch: n/a`), so per the Earth-rotation rules the
  mesh correctly does not spin. Spin with epoch was already verified visually
  on the previous branch (`earth_spin_p0/p05.png`: red meridian rotated
  ~180 deg). No new screenshot of spin was needed for this task.

## Step 5 — suites and counts

- Backend from `phase4_backend` (`python -m pytest ../tests -q`):
  **240 passed, 0 failed** (238 pre-existing + 2 texture tests).
- Node (existing invocation, all files): **64 passed, 0 fail**.
- `scripts/e2e_all.py` from the repo root (`GMAT_PATH` from the shell only):
  tests/e2e **49**, tests **191**, orbitlab_core **48**,
  simulation_engine **23** — **311 passed, total failed+errors 0**.
- Total added to the repo by this task: 12 files, 5185868 bytes (~4.9 MB),
  of which textures 4347251 bytes (~4.1 MB).

## Anything unsure

- Author credits are taken strictly from the original file-name tokens;
  `ModifiedBlueMarble.jpg` and `Sun.jpg` name no author, recorded as such.
- The `Epoch: n/a` overlay on the demo Hohmann run is pre-existing app
  behaviour for runs without an epoch (out of scope: no UI changes allowed).
- Window check for the 3D view is the two screenshots above (rendered, no
  page errors); no separate window test was applicable.
