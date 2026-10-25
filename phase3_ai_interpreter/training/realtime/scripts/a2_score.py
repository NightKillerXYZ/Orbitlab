# OrbitLab attempt-2 (data v12) field-level scoring + pipeline verdicts.
import io, json, sys, os

REPO = r"C:\Users\canit\.devswarm\repos\0\c799e6d2\feature-physics-core"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "phase3_ai_interpreter"))

from interpreter.json_interpreter import JsonExperimentInterpreter

RAW = os.path.join(REPO, "phase3_ai_interpreter", "training", "realtime", "outputs_raw_A2.txt")
with io.open(RAW, "r", encoding="utf-8") as f:
    raw_text = f.read()

import re
lines = raw_text.splitlines(keepends=True)
blocks = []
current_id = None
buf = []
for ln in lines:
    m = re.match(r'^\s*(\d+)\.\s*\{\s*$', ln)
    if m:
        if current_id is not None:
            blocks.append((current_id, "".join(buf)))
        current_id = m.group(1)
        buf = [ln]
    else:
        buf.append(ln)
if current_id is not None:
    blocks.append((current_id, "".join(buf)))

interp = JsonExperimentInterpreter()

results = []
for idx, (num, txt) in enumerate(blocks, 1):
    txt2 = re.sub(r'^\s*\d+\.\s*', '', txt, count=1)
    txt2 = re.sub(r'---\s*END\s*---.*$', '', txt2, flags=re.S).rstrip() + "\n"
    payload = json.loads(txt2)
    res = interp.interpret(txt2)
    results.append((idx, num, payload, res))

print("==== PIPELINE VERDICTS ====")
for idx, num, payload, res in results:
    name = payload.get("experimentName")
    print(f"[{idx:02d}] {name}: success={res.success}")
    for e in res.errors:
        print(f"      - {e}")
