# UI audit: provenance, duplicates, overlay, epoch (`v1-ui-audit`)

## Can pre-made data appear in a real run? NO — with the listed exceptions

A real run (no `?mock=1`, adapter present, no `?fixture=1`) can only show what
its own job computed: chat submit (`#chatForm`, `app.js:602`) → `runScenario`
(`app.js:583`) → `adapter.runExperiment` (`ui_adapter.js:203`) →
`POST /api/experiments` → background `run_job` with a **fresh `Pipeline()`**
(`api/app.py:246-247`, cache starts `{}`) → GMAT/simulate → stored in the
module-level `JobStore`, streamed back over `WS /ws/experiments/{id}` (2 s
`GET /api/experiments/{jid}` poll fallback, `ui_adapter.js:225-266`) and
rendered from that job's own `result`. No pre-made file is on this path:
`run_job` constructs a new `Pipeline` per job, so the `self.cache`
(`orchestrator/pipeline.py:42,87-92,379-383`, keyed by sha256 of the canonical
prompt, max 500 entries) **can never hit across jobs in production** (and a
single `run()` pass cannot hit its own fresh cache). The store only ever
returns the requesting job's own result/events (`api/app.py:102-112`, replay
of the same job's events on WS subscribe). No `localStorage`/`sessionStorage`
anywhere in the UI; `tests/fixtures/` holds exactly one file
(`real_result_earth.json`), served verbatim only by `GET /sample-result`
(`api/app.py:222-229`, fixed file, nothing else exposed).

Where pre-made/sample data CAN appear instead of a real run:

1. **Mock mode** — `useMock()` (`app.js:100`) is true when the adapter script
   is absent, `window.ORBITLAB_USE_MOCK`, `?mock=1`, or the
   `ORBITLAB_USE_MOCK`/`VITE_USE_MOCK` env says so (`ui_adapter.js:66-81`).
   Then: `runScenarioMock` (`app.js:571`) shows hard-coded velocities/periods/
   shapes ("70.0 km/s", "Wider orbit", …); the adapter returns `{mock:true}`;
   CSV export is fabricated (`exportSampleCSV`, `app.js:609`). Instant and
   synthetic by design.
2. **Fixture mode** — `?fixture=1` **and** not mock (`app.js:649`, runs at
   boot): `GET /sample-result` → `tests/fixtures/real_result_earth.json`,
   rendered with a "Sample run" toast. Only trigger: the query string.
3. **Failure fallback (stale but real, not synthetic)** — on run error with a
   previous result present, `runScenario` restores `prevResult/prevJobId` and
   re-renders the *previous* successful run's visualization with a "Run
   failed" toast (`app.js:599`). A failed fresh run therefore redisplays old
   data, never invented data.
4. **Job-store retention** — module-singleton `JobStore`
   (`api/store.py`, `MAX_JOBS=1000`, oldest terminal job evicted); `GET`
   returns only the requested job's own stored result. No cross-job leakage
   (the failing-test pinning in `test_extractor_timeout.py` aside, each poll
   addresses its own `jid`).

`?mock=1` handling lives in `detectMockMode` (`ui_adapter.js:66-81`);
`?fixture=1` handling is the boot IIFE (`app.js:649`, requires `!useMock()`).

## Duplicates: census results (read-only probes, then Step 3)

Static files are clean: `index.html` contains exactly one `.app-footer`,
one `.profile`, one `.simulation-controls`/`#simTime`, one `#orbitVisual`;
single `<script>` tags (no double boot). All `renderTab`/`liveBody` bodies are
single strings assigned via `panel.innerHTML=` (replace, never append);
`renderStatCards` uses `innerHTML=`; toasts/`#demoBadge`/`#runBadge`/
`#epochOverlay`/`#view3dUI` creation paths all check existence first;
`renderRealRun` clears (`clearRunDrawing`) before appending one svg.
Live DOM census (system Chrome + SwiftShader via `playwright-core`, local
server; fixture load, 3D toggle, back to 2D, real Hohmann demo run, second
run, all alt pages): **exactly 1** footer / profile / sim-controls /
`#simTime` / `#runOrbit` / stat row (5 cells) in every state — structural
duplication does **not** reproduce.

Two real defects found instead (both fixed in Steps 3–4):

- **`#view3dUI` (Show full path + Reset view) stays `display:flex`-visible
  after toggling back to 2D** (canvas hides, box does not) — i.e. exactly the
  "both the 2D and 3D control rows shown" case. Proven: `back2d:
  #view3dUI:rect=782,274,170,29 display=flex` vs `#view3dCanvas:display=none`.
- **The yellow epoch overlay overlaps the HUD in 2D**: `#epochOverlay`
  (overlay y 672–698) vs `.visual-caption` (y 687–696) inside `#orbitVisual`
  (y 265–705) — `updateEpochOverlay` runs from `drawCraft` in every mode.
  The overlay also exists in 2D at all (`epoch:1` in the 2D census).

The remaining "twice" reports could not be reproduced structurally; the
counting tests added in Step 3 lock the singleton invariant after 1 and 3
renders so any future append-without-clear regresses loudly.

## Overlay and epoch today

- `ensureEpochOverlay` (`app.js:476`) pins `#epochOverlay` at
  `left:8px;bottom:6px` of `#orbitVisual` in all modes; text is
  `frameName + Epoch: <date>` advancing with replay.
- Missing/unparseable epoch → `epochTextAt` returns `'Epoch: ' + (raw||'n/a')`
  (`app.js:474`); container `dataset.epochValue` is `''`, so view3d skips the
  spin and the ground-track painter returns early — no crash anywhere.
- Schema default: `EpochConfig.value` defaults to `"01 Jan 2026 12:00:00.000"`
  (`orbitlab_core/ast/models.py:65-74`), the value Step 5 adopts for the
  overlay, the Earth spin and the ground track (with a `(default epoch)` tag
  in the overlay only).

## Plan (Steps 2–5)

- Provenance: `fromCache`/`elapsedSeconds`/`jobId` added to the pipeline
  result (cache hits marked on a copy; fresh runs marked false with measured
  wall time; `run_job` stamps the job id); muted `#runProvenance` caption
  under the Orbital view (`Live GMAT run - 3.2 s` / `Result from cache (same
  input as an earlier run)` / `Sample data (not a run)`); tests for each.
- Idempotent renders + counting tests (1 and 3 renders); `#view3dUI`
  hidden with the canvas in 2D.
- Epoch overlay 3D-only, repositioned clear of the HUD; default epoch from
  `EpochConfig` with `(default epoch)` tag; same default for spin + ground
  track.

## Steps 2–5 — what was done (all additive, no logic changes)

- **Provenance (Step 2).** `pipeline.run` stamps `fromCache: False` plus
  wall-time `elapsedSeconds` on every fresh result; cache hits return a copy
  marked `fromCache: True` (original timing preserved). `run_job` stamps the
  result's `jobId`. UI: `metaFromResult` derives
  `{origin:'live'|'cache'|'sample'|'mock',elapsedSecs,jobId}` from those
  fields; a small muted `#runProvenance` caption under the Orbital view
  shows `Live GMAT run - 3.2 s` / `Result from cache (same input as an
  earlier run)` / `Sample data (not a run)` (mock maps to the sample text).
  Mock and `?fixture=1` paths set the meta explicitly (the fixture JSON
  carries no flags); the failure fallback re-renders the previous result and
  the caption follows it, so it stays truthful.
- **Duplicates (Step 3).** Census proved structural singletons everywhere, so
  the code change is the one real leak found: `#view3dUI` stayed visible
  after toggling back to 2D — `hideView3D` now hides it, `showView3D`
  re-shows it, `dispose` already removed it. Render paths already
  clear-before-append; counting tests pin one footer / user card /
  sim-controls bar / `#simTime` / `#runOrbit` / `#epochOverlay` /
  `#runProvenance` and 5 stat cells after 1 and 3 consecutive renders.
- **Overlay (Step 4).** `#epochOverlay` moved to `top:8px;left:8px` (clear of
  the caption + stat rows, verified non-overlapping) and is shown in 3D only
  (`display:none` in 2D, including the mock 2D view).
- **Epoch default (Step 5).** `DEFAULT_EPOCH_STR = "01 Jan 2026 12:00:00.000"`
  (mirrors `EpochConfig.value`); missing/unparseable epochs use it for the
  overlay (with a ` (default epoch)` tag on the epoch line only), the Earth
  spin, and the ground track. Existing epoch behavior is byte-identical when
  an epoch is present.

## Step 6 — suites and counts

- Backend from `phase4_backend` (`python -m pytest ../tests -q`):
  **243 passed, 0 failed** (incl. 3 new provenance tests: live marks +
  wall time, second identical run served from cache with original timing,
  `run_job` stamps `jobId`).
- Node (existing invocation, all files): **69 passed, 0 fail** (incl. 4
  caption cases, idempotency after 1 and 3 renders, overlay 3D-only,
  default-epoch overlay + ground track, view3d default-epoch spin).
- `scripts/e2e_all.py` from the repo root (`GMAT_PATH` from the shell only,
  never logged or committed): tests/e2e **49**, tests **194**,
  orbitlab_core **48**, simulation_engine **23** — **314 passed, total
  failed+errors 0**.

## Anything unsure

- The "instant result" complaint is fully explained without pre-made data:
  mock mode renders instantly by design; `?fixture=1` renders the sample
  fixture instantly; the pipeline cache cannot hit across jobs (fresh
  `Pipeline` per `run_job`); the WS/event replay only replays the same job's
  own events. A same-text repeat run still re-simulates today (cache lives
  and dies inside one `Pipeline` instance) — hence the caption for a second
  identical run currently says "Live GMAT run", truthfully.
- The duplicated-footer/cards/bars reports could not be reproduced as DOM
  duplication in any flow (fixture, real Hohmann run ×2, all alt pages,
  3D toggle both ways: exactly 1 each). The shipped fixes cover the two
  confirmed look-alikes (3D controls persisting in 2D; epoch overlay HUD
  overlap) plus regression tests for all of them.
- `Epoch: n/a` seen on demo Hohmann runs is pre-existing backend content
  (no epoch in those experiments), not a UI bug; with this change the overlay
  now shows the schema default instead, tagged as default.
