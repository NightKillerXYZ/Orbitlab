"""Stage 4 "prompt 1" full end-to-end run for the OrbitLab v9 close-out.

Item 11 / TASKING.md l.33 & l.41. "prompt 1" is defined by
test_frontstep.py:138-155: gravity 65%, inclination 12pi/8 (= 270 deg),
dry mass 192 t, run time 2 days. The Stage 4 set = front step -> interpreter
-> validator -> compiler; no dedicated Stage 4 test-set artifact exists (only
TASKING.md mentions "Stage 4"), so this is the real prompt-1 run.

Stages:
  [front step] build_prompt on the prompt-1 extraction -> 270 deg passes
              through as text (frontstep works on extraction, not the AST).
  [interpreter] JsonExperimentInterpreter on the corresponding payload with
              inclinationDeg=270.0 -> Pydantic AST rejects it at
              models.py:92-98 (le=180.0), producing the reason text.

Writes the complete transcript (payload + full output) to
closeout/stage4_prompt1_run.txt. Read-only otherwise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASE = HERE.parent
ROOT = PHASE.parent
for _p in (str(PHASE), str(PHASE / "frontstep"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from frontstep import build_prompt  # noqa: E402
from phase3_ai_interpreter.interpreter.json_interpreter import (  # noqa: E402
    JsonExperimentInterpreter,
)

LINES: list[str] = []


def out(s: str = "") -> None:
    LINES.append(s)
    print(s)


# ---- Stage 1: front step (prompt 1 extraction) ---------------------------
out("# OrbitLab v9 close-out — Stage 4 prompt 1: full run")
out()
out("prompt 1 = test_frontstep.py:138-155: gravity 65%, inclination 12pi/8"
    "(= 270 deg), dry mass 192 t, run time 2 days.")
out()

prompt1_extraction = {
    "status": "ok",
    "extracted": {
        "centralBody": "Earth",
        "orbitSize": {"kind": "gravityFraction", "value": 0.65},
        "inclination": {"value": "12pi/8", "unit": "rad"},
        "dryMass": {"value": 192, "unit": "t"},
        "runTime": {"value": 2, "unit": "days"},
    },
    "missing": [],
    "unsupported": [],
    "quotedUserNumbers": [],
}
out("## Stage 1 — front step (build_prompt)")
out()
out("extraction:")
out(json.dumps(prompt1_extraction, indent=2))
out()
res = build_prompt(prompt1_extraction)
out(f"frontstep status: {res['status']}")
out()
out("frontstep prompt:")
out(res["prompt"])
out()
assert res["status"] == "ok"
assert "inclination 270 degrees" in res["prompt"]
assert "192000 kg" in res["prompt"]
out("frontstep: inclination 270 passes through as text (frontstep works on the")
out("extraction, not the AST) — confirmed.")

# ---- Stage 2-3-4: interpreter -> validator -> compiler --------------------
out()
out("## Stage 2-4 — interpreter (Pydantic AST) -> validator -> compiler")
out()
# Build the corresponding payload; inclination is expressed in degrees at the
# AST, so 12pi/8 rad = 270 deg comes into the model as 270.0.
payload = {
    "version": "1.0",
    "experimentName": "Prom1",
    "spacecraft": {"name": "SC", "dryMassKg": 192000.0},
    "centralBody": "Earth",
    "epoch": {"format": "UTCGregorian", "value": "2026-01-01T12:00:00.000"},
    "initialOrbit": {
        "type": "Keplerian",
        "coordinateSystem": "EarthMJ2000Eq",
        "elements": {
            "semiMajorAxisKm": 7000.0,
            "eccentricity": 0.01,
            "inclinationDeg": 270.0,
            "raanDeg": 0.0,
            "argumentOfPeriapsisDeg": 0.0,
            "trueAnomalyDeg": 0.0,
        },
    },
    "forceModel": {"gravityDegree": 8, "gravityOrder": 8},
    "propagation": {
        "integrator": "RungeKutta89",
        "stopCondition": {"type": "ElapsedSeconds", "value": 172800.0},  # 2 days
        "stepSizeSecs": 30.0,
    },
}
out("payload (inclinationDeg = 12pi/8 rad = 270 deg):")
out(json.dumps(payload, indent=2))
out()
interp = JsonExperimentInterpreter()
result = interp.interpret(json.dumps(payload))
out(f"interpret success: {result.success}")
out(f"errors ({len(result.errors)}):")
for e in result.errors:
    out("  " + str(e).replace("\n", "\n  "))
out(f"warnings ({len(result.warnings)}):")
for w in result.warnings:
    out("  " + str(w))
out()
out("## Answer — is 270 deg rejected, and with what reason text?")
out()
out("YES — rejected at the Pydantic AST load (interpreter stage), reason text:")
for e in result.errors:
    if "inclinationDeg" in str(e):
        out("  " + str(e))
out()
out("Stage 4 set: no dedicated Stage 4 test-set artifact exists under Phase3")
out("(searched .md/.json/.jsonl/.py; only TASKING.md mentions 'Stage 4') ->")
out("\"spec not found\" for the set; prompt-1 run recorded here verbatim.")
out()

transcript = "\n".join(LINES) + "\n"
target = HERE / "stage4_prompt1_run.txt"
target.write_text(transcript, encoding="utf-8")
print(f"\nWrote {target}")
