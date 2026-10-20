import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import importlib.util
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("audit_mod", HERE / "audit_v9c_sma.py")
aud = importlib.util.module_from_spec(spec)
sys.argv = ["audit_v9c_sma.py"]
spec.loader.exec_module(aud)
from orbitlab_core.constants import CENTRAL_BODY_PROPERTIES
RAD = {b: p[0] for b, p in CENTRAL_BODY_PROPERTIES.items()}

rows = [json.loads(x) for x in (HERE / "orbitlab_interpreter_train_v9b_master.jsonl").read_text(encoding="utf-8-sig").splitlines() if x.strip()]

def num(pat, t):
    m = re.search(pat, t, re.I)
    if not m: return None
    mm = re.match(r"\d+(?:\.\d+)?", m.group(1))
    return float(mm.group(0)) if mm else None

def first(patterns, t):
    for p in patterns:
        v = num(p, t)
        if v is not None: return v
    return None

PERI = [
    r"periapsis\s+altitude\s+(?:of\s+)?([\d.]+)\s*km",
    r"periapsis\s+(?:of\s+)?([\d.]+)\s*km",
    r"periapsis\s+sits\s+([\d.]+)\s*km",
    r"periapsis\s+([\d.]+)\s*km\s+above",
    r"perigee\s+altitude\s+(?:of\s+)?([\d.]+)\s*km",
    r"perigee\s+(?:of\s+)?([\d.]+)\s*km",
    r"perigee\s+sits\s+([\d.]+)\s*km",
    r"perigee/periapsis\s+([\d.]+)\s*km",
    r"periapsis/perigee\s+([\d.]+)\s*km",
    r"perigee\s*/\s*periapsis\s+([\d.]+)\s*km",
    r"pericenter\s+altitude\s+(?:of\s+)?([\d.]+)\s*km",
    r"nearest\s+point\s+(?:is|sits)?\s+([\d.]+)\s*km",
    r"lowest[- ]altitude\s+(?:point\s+)?(?:is|sits)?\s+([\d.]+)\s*km",
    r"starting\s+(?:from\s+)?a\s+periapsis\s+altitude\s+of\s+([\d.]+)\s*km",
    r"with\s+a\s+periapsis\s+altitude\s+of\s+([\d.]+)\s*km",
]
APO = [
    r"apoapsis\s+altitude\s+(?:of\s+)?([\d.]+)\s*km",
    r"apoapsis\s+(?:of\s+)?([\d.]+)\s*km",
    r"apoapsis\s+sits\s+([\d.]+)\s*km",
    r"apogee\s+altitude\s+(?:of\s+)?([\d.]+)\s*km",
    r"apogee\s+(?:of\s+)?([\d.]+)\s*km",
]
ABOVE = [
    r"([\d.]+)\s*km\s+above\s+(?:the\s+)?(?:surface|Earth|(?:the\s+)?(?:Moon|Mars)(?:'s\s+surface)?)",
    r"(?:perigee|periapsis|pericenter|nearest point|lowest point)\s+([\d.]+)\s*km\s+above",
    r"(?:periapsis|perigee|nearest point)\s+is\s+([\d.]+)\s*km",
    r"([\d.]+)\s*km\s+off\s+(?:the\s+)?(?:surface|ground)",
    r"sits\s+([\d.]+)\s*km\s+(?:above|up)",
    r"altitude\s+of\s+([\d.]+)\s*km",
]

def classify_na(prompt, body):
    low = prompt
    circular = bool(re.search(r"circular", low, re.I)) or bool(re.search(r"zero eccentricity", low, re.I))
    cartesian = bool(re.search(r"position\s*\[", low, re.I))
    v9adda = bool(re.match(r"^[Ss]et up an orbit for the (Moon|Mars) named V9AddA", low))
    ecc = num(r"eccentricit\w*\s*(?:of\s+)?([\d.]+)", low)
    if ecc is None: ecc = num(r"(?:^|[;\s,])e\s*=\s*([\d.]+)", low)
    if ecc is None: ecc = num(r"(?:^|[;\s,])e\s+([\d.]+)", low)
    if ecc is None: ecc = num(r"eccentricity\s+([\d.]+)", low)
    if circular and ecc is None: ecc = 0.0
    sma = None
    if not v9adda:
        sma = first([
            r"with\s+SMA\s+([\d.]+)\s*km", r"SMA\s+([\d.]+)\s*km",
            r"semi[- ]?major\s+axis\s+(?:of\s+)?([\d.]+)\s*km", r"(?:at\s+)?a\s*=\s*([\d.]+)\s*km",
            r"(?:^|[^=a-zA-Z])([\d.]+)\s*km\s+SMA", r"elements\s*\[\s*([\d.]+)\s*km",
            r"(?:^|[^a-zA-Z])a\s+([\d.]+)\s*km",
        ], low)
    peri = first(PERI, low)
    apo = first(APO, low)
    above = first(ABOVE, low)
    period = num(r"period\s+(?:of\s+)?([\d.]+)\s*(?:hours?|hr|h)\b", low) or num(r"period\s+(?:of\s+)?([\d.]+)\s*s(?:ec)?\b", low)
    if cartesian: return "na-cartesian"
    if sma is not None and ecc is not None: return "direct-sma"
    if sma is not None: return "na-sma-no-ecc"
    if peri is not None and ecc is not None: return "periapsis"
    if apo is not None and ecc is not None: return "apoapsis"
    if above is not None and ecc is not None: return "above"
    if peri is not None and ecc is None: return "na-periapsis-no-ecc"
    if apo is not None and ecc is None: return "na-apoapsis-no-ecc"
    if above is not None and ecc is None: return "na-above-no-ecc"
    if circular:
        alt = first([r"(?:circular\s+)?(?:orbit|altitude)\s+(?:at|of)?\s+([\d.]+)\s*km",
            r"(?:at|of)\s+([\d.]+)\s*km\s+altitude", r"altitude\s+([\d.]+)\s*km",
            r"alt\s+([\d.]+)\s*km", r"([\d.]+)\s*km\s+altitude", r"([\d.]+)\s*km\s+high",
            r"([\d.]+)\s*km\s+(?:circular|above)", r"satellite\s+at\s+([\d.]+)\s*km",
            r"(?:at|of)\s+([\d.]+)\s*km"], low)
        if alt is not None: return "circular-alt"
        return "na-circular-other"
    if period is not None: return "period"
    return "na-other"

buckets = {}
samples = {}
for i, row in enumerate(rows):
    prompt = row["contents"][0]["parts"][0]["text"]
    exp = json.loads(row["contents"][1]["parts"][0]["text"])
    body = exp.get("centralBody"); st = exp.get("initialOrbit", {}).get("type")
    if st != "Keplerian":
        buckets.setdefault("output-Cartesian", []).append(i+1); continue
    asma = exp["initialOrbit"]["elements"]["semiMajorAxisKm"]; ae = exp["initialOrbit"]["elements"]["eccentricity"]
    cat, expv, status = aud.derive_expected(prompt, body, asma, ae)
    if status != "na": continue
    b = classify_na(prompt, body)
    buckets.setdefault(b, []).append(i+1)
    samples.setdefault(b, []).append((i+1, body, asma, ae, prompt))

for bucket in ["na-other", "na-circular-other", "na-periapsis-no-ecc", "na-above-no-ecc", "direct-sma", "periapsis", "above", "circular-alt", "period"]:
    print("#"*70)
    print(bucket, len(samples.get(bucket, [])))
    for it in samples.get(bucket, [])[:8]:
        print(f"line {it[0]} {it[1]} sma={it[2]} e={it[3]}")
        print("   ", it[4][:200])
