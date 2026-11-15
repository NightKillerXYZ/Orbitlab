# Playback speed control (`v1-playback-speed`)

## Step 1 — how replay speed is applied today (read only)

- State (`app.js:93-94`): `speed = 1`, `speedIndex = 0`,
  `speedOptions = [1, 2, 5, 10]`.
- Pacing (`app.js:108-109`): `REPLAY_TICK_MS = 100`,
  `REPLAY_SAMPLES_PER_SEC = 200`;
  `replayAdvance(spanSecs, nPts, speed) = span/(n-1) * 200 * 0.1 * speed`
  seconds per tick, i.e. ~200 samples/s of wall time at 1x.
- Timer (`app.js:269`): every 100 ms, mock mode advances
  `simDay += speed*0.12`; a live replay does
  `animT += replayAdvance(span, trajPts().length, speed)`, clamps at the end
  (`animPlaying=false`, `syncPlayBtn()`), then `drawCraft()` +
  `updateTelemetry()`. A full 86400 s / 1016-sample fixture run therefore
  finishes in ~5 s at 1x — too fast to watch, and nothing slower than 1x
  exists.
- Both views share it: `drawCraft` maps `animT` to marker position,
  `#simTime`, timeline fill/knob and the epoch overlay (2D); `driveView3D`
  (`app.js:160-166`) maps the same `animT` to `view3d.setProgress(animT/span)`
  (3D). Slider clicks set `animT` directly, so speed never causes jumps.
- The speed button (`index.html:51`, handler `app.js:621`) only cycles
  `[1,2,5,10]`, rewrites its own `innerHTML` and toasts; there is no readout
  of simulated time per second. `speed` is also (harmlessly) reused by the
  mock clock and the sample CSV exporter.
- Tests today (`tests/ui_render.test.cjs:474-483`): assert the 100 ms tick,
  the 200/s rate, linear scaling and the zero-span guard.

## Plan (Steps 2–5)

- Replace sample-rate pacing with run-relative progress:
  `REPLAY_FULL_RUN_SECONDS_AT_1X = 60`; per tick
  `span * speed * (REPLAY_TICK_MS/1000) / 60`. `REPLAY_TICK_MS` stays.
  `replayAdvance(spanSecs, speed)` keeps its name; the old
  `REPLAY_SAMPLES_PER_SEC` constant and the old Node test go away with it.
- `index.html`: the `#speedBtn` button becomes a real `<select id="speedSelect">`
  (0.05/0.1/0.2/0.5/1/2/5/10/20x + `Custom...`), a hidden number input
  (`min 0.01 max 100 step 0.01`, Enter/blur applies, invalid reverts), and a
  muted `#speedReadout` span; styled like the existing pills. JS:
  `SPEED_PRESETS`, `DEFAULT_SPEED = 0.5`, `clampSpeed`, `applySpeed` (immediate,
  no position change), `loadStoredSpeed`, per-session memory + `localStorage`
  in try/catch, `formatSimRate` (`= 48 min of simulation per second`, s/m/h/d,
  empty when the span is unknown). Default 0.5x.
- Play, pause, restart and the slider are untouched; the readout updates on
  speed change and on each new run.
- Node tests: per-tick progress per preset, valid/invalid custom, no-jump on
  mid-replay change, readout units, 0.5x default, single dropdown after 1 and
  3 renders, throwing-localStorage safety; then all suites + counts.

## Steps 2–5 — what was done

- Pacing (`app.js`): `replayAdvance(spanSecs, speed) = span*speed*(100/1000)/60`
  under `REPLAY_FULL_RUN_SECONDS_AT_1X = 60` (`REPLAY_TICK_MS` kept at 100);
  the `REPLAY_SAMPLES_PER_SEC` constant is gone with the old formula. Both
  views are driven by the same `animT` (`drawCraft` for 2D, `driveView3D`
  fraction for 3D), so both follow the new rule with no 3D-side change.
- Control (`index.html` + `styles.css` + `app.js`): the `#speedBtn` button is
  now `<select id="speedSelect">` (0.05–20x + `Custom...`, 0.5x selected),
  a hidden number input (`min 0.01 max 100 step 0.01`, Enter/blur applies,
  invalid reverts to the previous value with a toast) and a muted
  `#speedReadout` span, styled like the existing pills. `applySpeed` only
  sets `speed` (plus UI + persistence), so mid-replay changes never move
  `animT`. Choice persists per session and in `localStorage` (try/catch;
  throwing storage is a no-op). Default 0.5x unless a stored value exists.
- Readout: `= X unit of simulation per second` from
  `span/60*speed`, formatted s/min/h/d with one decimal under 10 else rounded
  (e.g. a 2-day run at 1x reads `= 48 min of simulation per second`); empty
  string when the span is unknown (mock mode, no run). Refreshed on speed
  change and on every new run.
- Play, pause, restart and the slider are byte-identical in behavior; the
  mock Venus clock keeps its old `speed*0.12` rate (now also slowable).
- Node tests (all in `tests/ui_render.test.cjs`, fake DOM): per-tick progress
  per preset vs `span*speed/600`; custom accept/revert incl. min/max bounds;
  no-jump on mid-replay change (simTime text identical); readout units incl.
  days; default 0.5x + stored-value load; throwing-localStorage safety;
  index.html option list; single dropdown/input/readout after 3 renders.
  The old 200-samples/s test was rewritten for the progress rule.

## Step 5 — suites and counts

- Node (existing invocation, all files): **74 passed, 0 fail**
  (69 pre-existing + 5 new speed tests).
- Backend from `phase4_backend` (`python -m pytest ../tests -q`):
  **243 passed, 0 failed** (no backend code changed).
- `scripts/e2e_all.py` from the repo root (`GMAT_PATH` from the shell only):
  tests/e2e **49**, tests **194**, orbitlab_core **48**,
  simulation_engine **23** — **314 passed, total failed+errors 0**.

## Anything unsure

- `toFixed(1)` rounding at unit boundaries (e.g. 0.75 s shows as `0.8 s`)
  is standard JS rounding; thresholds use strict `<` so 60 s reads
  `1.0 min`, 3600 s reads `1.0 h`, 86400 s reads `1.0 d`.
- The readout for a cached/live run uses the stored span; on failure-restore
  of a previous result it describes that result (meta is recomputed in
  `renderRealRun`), which is the truthful caption for what is drawn.
- `localStorage` may be unavailable (file://, private mode) or throw — both
  degrade to the in-memory default with no errors; the choice simply does
  not persist.
- No visual screenshot was required by this task's steps; behavior is
  covered by the DOM-level tests above.
