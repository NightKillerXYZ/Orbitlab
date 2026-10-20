"""Throwaway: count v9b master rows whose apoapsis would newly fail the SOI
containment check if bodies.json soiRadiusKm were replaced with the T3
recomputed values. Only Keplerian, bounded rows with a real apoapsis are
considered (the validator only applies SOI to contained orbits)."""
import json
from pathlib import Path

MASTER = Path(r"C:\Users\canit\.devswarm\repos\0\c799e6d2\feature-physics-core\phase3_ai_interpreter\datasets\v9\orbitlab_interpreter_train_v9b_master.jsonl")

OLD = {"Earth": 925000.0, "Moon": 66200.0, "Mars": 577000.0, "Mercury": 112000.0, "Venus": 616000.0, "Jupiter": 48200000.0}
NEW = {"Mercury": 134530.210, "Venus": 619750.031, "Earth": 909222.284, "Moon": 62065.619, "Mars": 541047.733, "Jupiter": 48294715.423}

rows = [json.loads(x) for x in MASTER.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
print("total rows:", len(rows))

from collections import defaultdict
impact = defaultdict(lambda: {"newly_fail": 0, "examples": []})
per_body_rows = defaultdict(int)
for idx, row in enumerate(rows):
    exp = json.loads(row["contents"][1]["parts"][0]["text"])
    body = exp.get("centralBody")
    if body not in OLD:
        continue
    per_body_rows[body] += 1
    st = exp.get("initialOrbit", {}).get("type")
    if st != "Keplerian":
        continue
    el = exp["initialOrbit"]["elements"]
    sma = el.get("semiMajorAxisKm")
    e = el.get("eccentricity")
    if sma is None or e is None:
        continue
    if e >= 1.0:
        continue  # unbound; validator would warn but not SOI-fail
    apo = sma * (1.0 + e)
    old_soi = OLD[body]
    new_soi = NEW[body]
    # newly fail = passes under old but fails under new
    if new_soi < old_soi and apo <= old_soi and apo > new_soi:
        impact[body]["newly_fail"] += 1
        if len(impact[body]["examples"]) < 3:
            impact[body]["examples"].append({"line": idx + 1, "apoapsis_km": round(apo, 2), "sma": round(sma, 2), "e": e})

for body, old in OLD.items():
    new = NEW[body]
    print(f"{body:8s} old={old:14.2f} new={new:14.2f} newly_fail={impact[body]['newly_fail']} rows_total={per_body_rows[body]}")
    for ex in impact[body]["examples"]:
        print("      example:", ex)
