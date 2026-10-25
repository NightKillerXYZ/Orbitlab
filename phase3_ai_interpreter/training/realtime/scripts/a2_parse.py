# OrbitLab attempt-2 (data v12) field-level scoring + pipeline verdicts.
import io, json, re, sys, os

REPO = r"C:\Users\canit\.devswarm\repos\0\c799e6d2\feature-physics-core"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "phase3_ai_interpreter"))

from orbitlab_core.ast.models import OrbitLabExperiment
from orbitlab_core.ast.validation import AstrodynamicValidator
from interpreter.json_interpreter import JsonExperimentInterpreter

RAW = r"C:\Users\canit\.devswarm\repos\0\c799e6d2\feature-physics-core\phase3_ai_interpreter\training\realtime\outputs_raw_A2.txt"
with io.open(RAW, "r", encoding="utf-8") as f:
    raw_text = f.read()

# Each block starts with "<n>. {" (one per line before JSON). Split.
# Find the lines that are "<int>. {"
lines = raw_text.splitlines(keepends=True)
blocks = []  # list of (id_line, json_text)
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

print("parsed block count:", len(blocks))
clean_blocks = []
for idx, (num, txt) in enumerate(blocks, 1):
    # Strip the leading "<n>. " id prefix from the first line
    txt2 = re.sub(r'^\s*\d+\.\s*', '', txt, count=1)
    # Strip the trailing "--- END ---" marker / trailer (last block only)
    txt2 = re.sub(r'---\s*END\s*---.*$', '', txt2, flags=re.S)
    txt2 = txt2.rstrip() + "\n"
    clean_blocks.append((num, txt2))
    try:
        obj = json.loads(txt2)
        name = obj.get("experimentName")
    except Exception as e:
        name = f"<json error: {e}>"
    print(f"{idx}: num={num} name={name!r} len={len(txt2)}")
    with io.open(rf"C:\Users\canit\AppData\Local\Temp\opencode\a2\block_{idx:02d}.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, indent=2) if 'obj' in dir() and isinstance(obj, dict) else "")


os.makedirs(r"C:\Users\canit\AppData\Local\Temp\opencode\a2", exist_ok=True)
for idx, (num, txt) in enumerate(clean_blocks, 1):
    with io.open(rf"C:\Users\canit\AppData\Local\Temp\opencode\a2\block_{idx:02d}.txt", "w", encoding="utf-8") as f:
        f.write(txt)
