# GMAT-like 3D view report (`v1-gmat-look`)

## Step 1 — what view3d.js does today vs the GMAT facts (read only)

Checked against a shallow clone of `github.com/nasa/GMAT`
(`src/gui/subscriber/OrbitViewCanvas.cpp`, temp folder only, never
committed; behaviour noted, no code copied). Relevant GMAT facts used:
black clear colour; epoch status line at the bottom in yellow; zero-magnitude
segments skipped; axes drawn with red +X / green +Y / blue +Z labels.

| GMAT behaviour wanted | view3d.js today | Verdict |
|---|---|---|
| Reveal: only travelled part drawn; faint full path only via "Show full path" checkbox (default off) | Draws full dim line (`0x3a5a8c`) always + bright travelled part (`0x6faaff`, `setDrawRange`) | MISSING — needs rework |
| Track = line segments, skip segments with either endpoint at the origin | One continuous polyline, no zero check | MISSING |
| Spacecraft track red (#FF0000), thicker than hairline where allowed | Blue tones, `LineBasicMaterial` width 1 | MISSING (colour) |
| Draw order: black bg, fixed stars (no move/scale with camera), axes, textured body, track, marker | Black bg yes; stars are world-locked (`sizeAttenuation:true`, radius `maxR*10`); axes yes; body yes; track yes; marker yes | PARTIAL — stars must be screen-fixed |
| Bottom-left yellow monospace overlay: frame name line + `Epoch: <date>` line advancing with replay | No overlay exists | MISSING |
| Spacecraft name (red) by the marker; body name (green) by its centre; screen-facing text | No name labels | MISSING |
| X/Y/Z axes with arrowheads + labels | Plain lines + X/Y/Z sprite labels, no arrowheads | PARTIAL — arrowheads missing |
| Default camera: ~3x max orbit radius, Z-up, small tilt above equatorial plane | `dist=maxR*3.0` yes; but default Y-up camera at (0.62,0.42,0.62) (~26° tilt) | PARTIAL — needs Z-up + smaller tilt |
| Mouse orbit + wheel zoom | OrbitControls with damping already | PRESENT |
| Double-click or Reset button restores the default view | Neither exists | MISSING |
| Explicit frame-increment / update-interval constants (~200 samples/s at 1x); full trail + rested marker at end | Inline magic numbers (`setInterval 100`, `animT += span/600*speed`); end behaviour already correct | PARTIAL — constants missing, rate differs |
| Optional `assets/models/spacecraft.3ds` via TDSLoader, fallback marker | No model loading (`TDSLoader.js` not vendored) | MISSING |

`createView3D/setResult/setProgress/dispose` stay as the public API; the
checkbox, epoch/formatting helpers and model loader are new internals.

## Step 2 — what changed (public API unchanged)

- `UIUX/OrbitlabUI Main/view3d.js` (rewritten in place): travelled-only red
  (`0xFF0000`, width 2) per-run tracks via `setDrawRange`; zero-magnitude
  samples split runs (`splitRuns`, exact `== 0` like GMAT); screen-fixed stars
  (`sizeAttenuation:false`, follow camera); `ArrowHelper` X/Y/Z axes at
  1.5x max radius with letter labels; Z-up camera at 3x max radius with a
  small tilt; in-view "Show full path" checkbox (default off, faint copies at
  0.22 opacity) + "Reset view" button + double-click reset; name sprites for
  spacecraft (red) and body (green) plus axis letters, rescaled every frame
  to a constant fraction of camera distance (screen-facing text, GMAT-like);
  optional `assets/models/spacecraft.3ds` via vendored `TDSLoader.js`, centred
  and scaled to ~3% of camera distance, with validation (empty parse results
  keep the marker) and silent fallback to the white marker; larger fallback
  marker (2% of max radius). `createView3D/setResult/setProgress/dispose`
  signatures unchanged.
- `UIUX/OrbitlabUI Main/app.js`: `REPLAY_TICK_MS=100`,
  `REPLAY_SAMPLES_PER_SEC=200`, `replayAdvance()` (replaces the old
  `span/600` pacing); `frameName()` (coordinate system, e.g.
  `EarthMJ2000Eq`), `formatGmatEpoch()` (inverse of
  `GroundTrack.parseGmatEpoch`), `epochTextAt()`, bottom-left yellow monospace
  `#epochOverlay` updated in `drawCraft`; container `dataset.spacecraftName /
  bodyName` set in `renderRealRun` (read by view3d for its labels); new
  exports and `__test__` hooks (`replay/epoch/frame/epochText/fmtEpoch/
  craftName`). No backend/physics/validator/compiler/schema/HTTP/conversion
  code touched (`groundtrack.js` unchanged).
- `vendor/three/TDSLoader.js` vendored from three r160 examples with
  `from 'three'` rewritten to the local `three.module.min.js`; existing
  `vendor/three/LICENSE` (same three.js licence) kept.
- `assets/models/README.md`: copy `data/graphics/models/*.3ds` from GMAT here
  as `spacecraft.3ds` under GMAT's Apache 2.0 licence with licence kept; no
  model file committed.

## Step 3 — Node tests (stub WebGL, `node --test tests/<file>.cjs`)

- `tests/view3d.test.cjs` (14 tests): zero-position split (endpoints never at
  origin; near-zero kept); travelled-only draw ranges at progress 0 / 0.5 / 1
  (0 / 6 / 11 of 11 samples) with red width-2 material and end rest at the
  last point; X/Y/Z arrowheads (red/green/blue) at 1.5x max radius, Z-up
  camera at 3x max radius with tilt, true-radius body sphere, screen-fixed
  stars, >=5 labels; checkbox toggles faint copies, Reset button and
  double-click restore the camera; missing `.3ds` and garbage parse results
  fall back to the marker without throwing; dataset-supplied label names;
  label sprites rescale with camera distance (screen-fixed).
- `tests/ui_render.test.cjs` (+2 tests, 18 total): `REPLAY_TICK_MS=100`,
  20 samples/tick at 1x (~200/s), speed scaling, zero-span guard; overlay
  shows `EarthMJ2000Eq` + `Epoch: 01 Jan 2026 12:00:00.000` at t=0 and
  `Epoch: 02 Jan 2026 00:00:00.000` at t=43200, epoch round-trips through
  `parseGmatEpoch`, dataset names `SC_Put`/`Earth`.
- Also run the same way: `groundtrack` (8), `plots` (7), `ui_helpers` (12)
  — all pass; total **59 Node tests, 0 fail**.

## Visual check (Playwright was NOT installed; Chrome was)

Playwright/Chromium was not available (no `playwright` module, no
`ms-playwright` browsers), so `playwright-core` (npm, temp dir outside the
repo, no browser download) drove the installed system Chrome headless with
SwiftShader against a local uvicorn server. Screenshot
`phase4_backend/gmat_look_screenshot.png` (`/OrbitlabUI Main/?fixture=1`,
3D mode, replay paused at ~50%): **rendered** — black background, fixed
stars, red progressive half-track, white marker with red `SC_Put` label,
red X + green Y axes with arrowheads and letter labels, green `Earth`
label, blue Z axis, yellow monospace `EarthMJ2000Eq` /
`Epoch: 01 Jan 2026 23:57:53.293` overlay, `Show full path` (off) + `Reset
view` controls, zero page errors. Note: `/main?fixture=1` redirects to
`/OrbitlabUI Main/` and drops the query string (pre-existing backend
behaviour, unchanged), so the shot used the direct UI URL with `?fixture=1`.

## Step 4 — suites and counts

- Node (existing invocation): **59 passed, 0 failed**.
- Backend from `phase4_backend` (`python -m pytest ../tests -q`): **225 passed**.
- `scripts/e2e_all.py` from the repo root (`GMAT_PATH` from the shell only,
  `C:\XY\Downloads\gmat-win-R2026a\bin\GmatConsole.exe`, never logged or
  committed): tests/e2e **49**, tests **176**, orbitlab_core **48**,
  simulation_engine **23** — **296 passed, 0 failed, total failed+errors 0**.

## Unsure / conservative readings

- GMAT facts came from the brief plus a read-only shallow clone
  (`C:\Users\canit\AppData\Local\Temp\gmat-src`, outside the repo);
  axis label colours differ from GMAT by design (kept red/green/blue mapping
  to X/Y/Z); no GMAT code copied or committed.
- Name-sprite sizes are a per-frame fraction of camera distance (4% width):
  legible at default zoom and constant on zoom; axis-end labels can sit near
  the canvas edge at default framing (drag/Reset reveals them).
- Pre-existing working-tree clutter (phase3 datasets, logs, html) predates
  this branch and is intentionally untouched; this branch commits only the
  files listed below. Branch base confirmed: `v1-docs` is an ancestor of `v1-gmat-look`
  (`git merge-base --is-ancestor`, exit 0).
