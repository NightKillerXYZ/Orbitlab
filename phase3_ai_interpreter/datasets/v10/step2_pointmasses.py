"""STEP 2 - pointMasses question.

a) Frontstep (frontstep.py) default pointMasses per body when the user says
   "use the model's default force settings".
b) pointMasses used by frozen v9b rows for Moon and Mars.
c) pointMasses pattern counts per body across the 400 v10 rows.
d) State whether the v10 pattern equals the front-step default; if not, list
   the mismatching rows (the user decides whether to STOP).

Data is read only; no data is modified.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"

# ---- (a) Frontstep default pointMasses ----
# Load the actual SCHEMA_DEFAULTS from frontstep.py so we do not hard-code it.
sys.path.insert(0, str(HERE.parents[1]))  # phase3_ai_interpreter on path
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "frontstep_mod", HERE.parents[1] / "frontstep" / "frontstep.py"
)
fs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fs)

BODIES = ["Earth", "Moon", "Mars", "Mercury", "Venus", "Jupiter", "Sun"]

print("=" * 70)
print("(a) frontstep default pointMasses (SCHEMA_DEFAULTS)")
print("=" * 70)
print("SCHEMA_DEFAULTS['pointMasses'] =", fs.SCHEMA_DEFAULTS["pointMasses"])
print("This default is body-INDEPENDENT (frontstep never overrides it by body")
print("when force settings are not customized):")
for b in BODIES:
    print(f"  {b:8s} -> {fs.SCHEMA_DEFAULTS['pointMasses']}")

# ---- (b) v9b Moon / Mars pointMasses ----
print()
print("=" * 70)
print("(b) v9b Moon / Mars pointMasses")
print("=" * 70)
V9B = HERE.parent / "v9" / "orbitlab_interpreter_train_v9b_master.jsonl"
v9b_counts: dict[tuple, int] = {}
v9b_by_body: dict[str, dict] = {}
with open(V9B, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        exp = json.loads(row["contents"][1]["parts"][0]["text"])
        body = exp.get("centralBody")
        pm = tuple(exp.get("forceModel", {}).get("pointMasses", []))
        v9b_counts[(body, pm)] = v9b_counts.get((body, pm), 0) + 1
        d = v9b_by_body.setdefault(body, {})
        d[pm] = d.get(pm, 0) + 1
for body in ["Moon", "Mars"]:
    print(f"  {body}: {v9b_by_body.get(body, {})}")

# ---- (c) v10 pointMasses patterns per body ----
print()
print("=" * 70)
print("(c) v10 pointMasses pattern counts per body (400 rows)")
print("=" * 70)
v10_counts: dict[tuple, int] = {}
v10_by_body: dict[str, dict] = {}
mismatch_rows: list[tuple] = []  # (file, line, body, pm)
for p in sorted(glob.glob(str(RAW / "*.jsonl"))):
    fname = Path(p).name
    text = open(p, encoding="utf-8-sig").read()
    for ln, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        exp = json.loads(row["messages"][2]["content"])
        body = exp.get("centralBody")
        pm = tuple(exp.get("forceModel", {}).get("pointMasses", []))
        v10_counts[(body, pm)] = v10_counts.get((body, pm), 0) + 1
        d = v10_by_body.setdefault(body, {})
        d[pm] = d.get(pm, 0) + 1
        if pm != tuple(fs.SCHEMA_DEFAULTS["pointMasses"]):
            mismatch_rows.append((fname, ln, body, pm))
for body in BODIES:
    print(f"  {body:8s} {v10_by_body.get(body, {})}")

# ---- (d) comparison ----
print()
print("=" * 70)
print("(d) v10 pattern vs frontstep default")
print("=" * 70)
default = tuple(fs.SCHEMA_DEFAULTS["pointMasses"])
print(f"frontstep default pointMasses = {list(default)}")
for body in BODIES:
    pats = v10_by_body.get(body, {})
    if not pats:
        print(f"  {body}: no rows")
        continue
    if set(pats) == {default}:
        print(f"  {body}: ALL rows use {list(default)}  -> consistent with default")
    else:
        print(f"  {body}: patterns {pats}  -> MISMATCH vs default {list(default)}")
print()
print(f"Total rows NOT equal to frontstep default [{list(default)}]: {len(mismatch_rows)}")
for fname, ln, body, pm in mismatch_rows:
    print(f"  {fname} line {ln}: body={body} pointMasses={list(pm)}")
