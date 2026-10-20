import json, re, importlib.util, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
_spec = importlib.util.spec_from_file_location("_audit_v9c", HERE / "audit_v9c_sma.py")
aud = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aud)
import importlib
A = importlib.import_module("audit_v9c_sma_all")
rows = aud._load(aud.MASTER)

def show(cat):
    cc = 0
    for i, row in enumerate(rows):
        prompt = row["contents"][0]["parts"][0]["text"]
        exp = json.loads(row["contents"][1]["parts"][0]["text"])
        body = exp.get("centralBody"); st = exp.get("initialOrbit", {}).get("type")
        if st != "Keplerian":
            continue
        asma = exp["initialOrbit"]["elements"]["semiMajorAxisKm"]; ae = exp["initialOrbit"]["elements"]["eccentricity"]
        c, x, s = A.derive_expected_all(prompt, body, asma, ae)
        if c == cat:
            cc += 1
            print(f"{i+1:5d} {body:8s} sma={asma} e={ae} :: {prompt[:170]}")
    print("count", cc)

show("not-derivable")
print("====circular-other====")
show("circular-other")
