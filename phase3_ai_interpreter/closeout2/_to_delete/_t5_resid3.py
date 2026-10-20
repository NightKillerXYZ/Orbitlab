import json, importlib.util, sys, importlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
_spec = importlib.util.spec_from_file_location("_audit_v9c", HERE / "audit_v9c_sma.py")
aud = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aud)
A = importlib.import_module("audit_v9c_sma_all")
rows = aud._load(aud.MASTER)
for i, row in enumerate(rows):
    prompt = row["contents"][0]["parts"][0]["text"]
    exp = json.loads(row["contents"][1]["parts"][0]["text"])
    body = exp.get("centralBody"); st = exp.get("initialOrbit", {}).get("type")
    if st != "Keplerian":
        continue
    asma = exp["initialOrbit"]["elements"]["semiMajorAxisKm"]; ae = exp["initialOrbit"]["elements"]["eccentricity"]
    c, x, s = A.derive_expected_all(prompt, body, asma, ae)
    if c in ("not-derivable", "circular-other"):
        print("line", i + 1, body, "sma=", asma, "e=", ae, "->", c)
        print("   ", prompt[:220])
