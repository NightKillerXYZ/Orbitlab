# OrbitLab demo video script (4 minutes)

Record with the demo backend (no keys, deterministic, fast). Start it first:

```powershell
$env:ORBITLAB_DEMO_MODE='true'; $env:PYTHONPATH='phase4_backend'
python -m uvicorn orbitlab_backend.api.app --port 8000
```

Open http://127.0.0.1:8000/main. Each prompt below goes in the Chat box.
Timings assume demo mode; in real-model mode every first call can take
~90 s (cold start), so either demo the recording in demo mode or wait out
the first call before rolling. Pre-demo tip only: keep model containers warm
with `min_containers=1` on Modal, and remove it after the demo.

## 0:00 — Setup shot (15 s)

- **Viewer sees:** terminal with the server starting, then the Main UI
  ("SIMULATION COMPLETE" is not shown yet; the Venus sample card is visible).
- **Say:** "This is OrbitLab: plain English in, real orbital mechanics out.
  Everything you are about to see runs against a real GMAT simulation."
- **Fallback:** if the page shows "Cannot reach the server", the backend is
  not up — start it with the command above and recheck
  http://127.0.0.1:8000/api/health first.

## 0:20 — Prompt 1: simple Earth orbit (40 s)

- **Exact text:** `Put a 500 kg satellite in a circular orbit at 400 km altitude around Earth for 1 day.`
- **Viewer sees:** stage chips run through all eight stages, then the card
  redraws around Earth: 1.54-hour period, periapsis/apoapsis ~400 km,
  e = 0.000, and a near-perfect circle on the 2D view.
- **Say:** "A plain request becomes a validated experiment and a GMAT run in
  a few seconds. The numbers in the stat cards come from the trajectory,
  not from the model."
- **Fallback:** none needed in demo mode; in real-model mode, allow up to
  90 s for the first call.

## 1:00 — Prompt 2: Mars elliptical orbit (40 s)

- **Exact text:** `Create a 1200 kg spacecraft around Mars with periapsis altitude 300 km and eccentricity 0.2 for 2 days.`
- **Viewer sees:** an elliptical Mars orbit (a = 4611.875 km, e = 0.2),
  min/max altitude cards differ, trajectory closes on itself.
- **Say:** "Same flow, different planet and a genuinely elliptical orbit —
  the pipeline converts periapsis altitude to a semi-major axis and the
  validator checks it before anything is compiled."
- **Fallback:** none in demo mode.

## 1:40 — Prompt 3: Hohmann transfer (40 s)

- **Exact text:** `500 kg satellite around Earth in a 7000 km circular orbit, Hohmann transfer to 9000 km at periapsis, 2 days`
- **Viewer sees:** Results tab gains a MANEUVERS section with analytic
  Δv1/Δv2/total estimates labelled as estimates; the orbit draws the
  transfer ellipse.
- **Say:** "Maneuvers are part of the experiment JSON, and the UI shows what
  the transfer should cost — labelled as an analytic estimate, not measured
  data."
- **Fallback:** none in demo mode.

## 2:20 — Bad prompt: validator catches it (30 s)

- **Exact text:** `500 kg satellite around Earth, periapsis altitude 50 km, 1 day`
- **Viewer sees:** a red failure banner at the validate stage explaining the
  50 km periapsis is below the 100 km Earth minimum — a clear explanation,
  not a stack trace.
- **Say:** "This is the safety chain working: an unsafe orbit never reaches
  the compiler, and you always get a reason you can act on."
- **Fallback:** none; deterministic.

## 2:50 — Incomplete prompt: clarification (25 s)

- **Exact text:** `Earth, 90 minutes`
- **Viewer sees:** a "More information needed" banner naming the missing
  fields (mass, orbit, duration) instead of a guessed run.
- **Say:** "When the request is underspecified, OrbitLab asks — it never
  invents the missing numbers."
- **Fallback:** none; deterministic.

## 3:15 — Details tab and Open in GMAT (30 s)

- **Viewer sees:** re-run prompt 1, open the Details tab: the full
  experiment JSON and the generated GMAT script, each with a Copy button
  and the research-use notice.
- **Say:** "Everything the AI produced is inspectable — the exact JSON and
  the exact script GMAT ran. And if the desktop app is installed and the
  local flag is on, one click opens that same script in full GMAT."
- **Note for recording:** the Open in GMAT button only appears when the
  backend runs with `ORBITLAB_ALLOW_OPEN_GMAT=true` and a local GMAT build;
  either enable it for this shot or skip the click and just point at the
  Details tab.
- **Fallback:** with no stored script the tab says "No script available for
  this run" — re-run prompt 1 if you see that.

## 3:45 — Closing with the architecture diagram (15 s)

- **Viewer sees:** the pipeline diagram (README): extract → interpret →
  verify → validate → compile → simulate → parse → explain.
- **Say:** "Models only read and write text. Verify, the validator and the
  compiler are deterministic — and a human reviews the script before
  anything matters. OrbitLab is a research and education tool, not for
  flight operations."

## Pre-recording checklist

- [ ] Backend running in demo mode on port 8000, health endpoint returns
  `{"status":"ok","mode":"demo"}`.
- [ ] `GMAT_PATH` set in the shell if you want real trajectories (else the
  runs use the synthetic fallback and the stat cards still fill in).
- [ ] prompt text for prompts 1–5 pasted somewhere copyable (exact wording
  matters).
- [ ] Browser zoom at 100%, panel scrolled to top, previous run cleared
  (submit an empty prompt once to reset, or reload the page).
- [ ] Screen recorder captures the whole browser window including the
  terminal for the setup shot.
- [ ] (Optional, Open in GMAT shot only) backend restarted with
  `ORBITLAB_ALLOW_OPEN_GMAT=true` and a local `GMAT.exe` present.
- [ ] (Real-model recording only) first call already warmed up; keep
  `min_containers=1` in mind as a pre-demo tip, removed afterwards.
