# Generates results_A2.json with per-cell scores, failure classes, and #13/#14
# supplementary default-driven scoring. Pure computation, no network.
import io, json, sys, os, re

REPO = r"C:\Users\canit\.devswarm\repos\0\c799e6d2\feature-physics-core"
RAW = os.path.join(REPO, "phase3_ai_interpreter", "training", "realtime", "outputs_raw_A2.txt")
OUT = os.path.join(REPO, "phase3_ai_interpreter", "training", "realtime", "results_A2.json")

with io.open(RAW, "r", encoding="utf-8") as f:
    raw_text = f.read()
lines = raw_text.splitlines(keepends=True)
blocks = []
current_id = None; buf = []
for ln in lines:
    m = re.match(r'^\s*(\d+)\.\s*\{\s*$', ln)
    if m:
        if current_id is not None: blocks.append((current_id, "".join(buf)))
        current_id = m.group(1); buf = [ln]
    else:
        buf.append(ln)
if current_id is not None: blocks.append((current_id, "".join(buf)))

def load(txt):
    t = re.sub(r'^\s*\d+\.\s*', '', txt, count=1)
    t = re.sub(r'---\s*END\s*---.*$', '', t, flags=re.S).rstrip() + "\n"
    return json.loads(t)

payloads = [load(t) for _, t in blocks]

GOLD = {
 "T01": dict(body="Earth",sma=7178.1363,ecc=0,inc=98.6,raan=25,aop=0,ta=0,mass=850,grav=(4,4),pm=["Luna","Sun"],intg="RungeKutta89",stop=("ElapsedHours",10)),
 "T02": dict(body="Earth",sma=19080.389,ecc=0.65,inc=41,raan=200,aop=45,ta=10,mass=2200,grav=(4,4),pm=["Luna","Sun"],intg="PrinceDormand78",stop=("ElapsedHours",20)),
 "T03": dict(body="Moon",sma=1797.4,ecc=0,inc=45,raan=10,aop=0,ta=0,mass=950,grav=(4,4),pm=["Luna","Sun"],intg="RungeKutta89",stop=("ElapsedHours",6)),
 "T04": dict(body="Mars",sma=3900,ecc=0.02,inc=25,raan=80,aop=10,ta=0,mass=1200,grav=(4,4),pm=["Luna","Sun"],intg="RungeKutta89",stop=("ElapsedHours",24)),
 "T05": dict(body="Venus",sma=6501.8,ecc=0,inc=60,raan=0,aop=0,ta=0,mass=700,grav=(4,4),pm=["Luna","Sun"],intg="PrinceDormand78",stop=("ElapsedHours",8)),
 "T06": dict(body="Mercury",sma=3000,ecc=0.1,inc=88,raan=10,aop=0,ta=0,mass=350,grav=(0,0),pm=["Luna","Sun"],intg="RungeKutta89",stop=("ElapsedHours",12)),
 "T07": dict(body="Jupiter",sma=321492.0,ecc=0,inc=12,raan=0,aop=0,ta=0,mass=2600,grav=(0,0),pm=["Luna","Sun"],intg="PrinceDormand78",stop=("ElapsedDays",3)),
 "T08": dict(body="Sun",sma=74798935.346,ecc=0.1,inc=3,raan=0,aop=0,ta=0,mass=400,grav=(0,0),pm=[],intg="RungeKutta89",stop=("ElapsedDays",60)),
 "T09": dict(body="Earth",sma=6448.1363,ecc=0,inc=51.6,raan=0,aop=0,ta=0,mass=500,grav=(4,4),pm=["Luna","Sun"],intg="RungeKutta89",stop=("ElapsedHours",6)),
 "T10": dict(body="Earth",sma=6878.1363,ecc=0,inc=200,raan=0,aop=0,ta=0,mass=500,grav=(4,4),pm=["Luna","Sun"],intg="RungeKutta89",stop=("ElapsedHours",6)),
 "T11": dict(body="Moon",sma=80000,ecc=0.2,inc=30,raan=0,aop=0,ta=0,mass=800,grav=(4,4),pm=["Luna","Sun"],intg="RungeKutta89",stop=("ElapsedDays",2)),
 "T12": dict(body="Mars",sma=3576.316,ecc=0.05,inc=70,raan=0,aop=0,ta=0,mass=900,grav=(4,4),pm=["Luna","Sun"],intg="RungeKutta89",stop=("ElapsedHours",6)),
}
FRAME = {"Earth":"EarthMJ2000Eq","Moon":"LunaMJ2000Eq","Mars":"MarsMJ2000Eq",
         "Venus":"VenusMJ2000Eq","Mercury":"MercuryMJ2000Eq","Jupiter":"JupiterMJ2000Eq","Sun":"SunMJ2000Eq"}
FIELDS = ["version","experimentName","spacecraft","centralBody","epoch","frame","SMA",
          "ecc+angles","gravity","pointMasses","drag","SRP","maneuvers","propagation"]

def g(p,*path):
    cur=p
    for k in path:
        if not isinstance(cur,dict) or k not in cur: return None
        cur=cur[k]
    return cur

def elem(p): 
    e=g(p,"initialOrbit","elements") or {}
    return e

# failure class per field (T01-T12 only)
def classify(name, p, gold, field):
    # returns a class string when the field fails, else None
    if field=="version":
        if "version" not in p: return "missing key"
    if field=="epoch":
        if "epoch" not in p: return "missing key"
        return "wrong default (year 2023/2024 vs 2026)"
    if field=="frame":
        if "coordinateSystem" in p: return "wrong placement (top-level, not inside initialOrbit)"
        return "missing key"
    if field=="SMA":
        return "arithmetic (wrong orbital radius/altitude)"
    if field=="drag":
        ad=g(p,"forceModel","atmosphericDrag")
        if "atmosphereModel" in (p.get("forceModel") or {}): return "wrong schema key (forceModel.atmosphereModel scalar)"
        if not isinstance(ad,dict): return "wrong type (boolean, not object)"
        extra = set(ad or {}) - {"enabled","model"}
        return f"extra schema key: {sorted(extra)}"
    if field=="maneuvers":
        return "missing key"
    return None

score_grid = {}
failure_classes = {}
for name, gold in GOLD.items():
    p = payloads[[x["experimentName"] for x in payloads].index(name)]
    sma = g(p,"initialOrbit","elements","semiMajorAxisKm")
    sc = g(p,"spacecraft")
    el = elem(p)
    fm = p.get("forceModel") or {}
    ad = fm.get("atmosphericDrag")
    pr = p.get("propagation") or {}
    sc_ = pr.get("stopCondition") or {}
    check = {
      "version": p.get("version")=="1.0",
      "experimentName": p.get("experimentName")==name,
      "spacecraft": bool(sc and sc.get("name")=="SC_"+name and sc.get("dryMassKg")==gold["mass"] and sc.get("coefficientOfDrag")==2.2 and sc.get("dragAreaM2")==1 and sc.get("coefficientOfReflectivity")==1.8 and sc.get("srpAreaM2")==1),
      "centralBody": p.get("centralBody")==gold["body"],
      "epoch": g(p,"epoch","value")=="01 Jan 2026 12:00:00.000",
      "frame": g(p,"initialOrbit","coordinateSystem")==FRAME[gold["body"]],
      "SMA": sma is not None and abs(sma-gold["sma"])<=0.002,
      "ecc+angles": el.get("eccentricity")==gold["ecc"] and el.get("inclinationDeg")==gold["inc"] and el.get("raanDeg")==gold["raan"] and el.get("argumentOfPeriapsisDeg")==gold["aop"] and el.get("trueAnomalyDeg")==gold["ta"],
      "gravity": fm.get("gravityDegree")==gold["grav"][0] and fm.get("gravityOrder")==gold["grav"][1],
      "pointMasses": fm.get("pointMasses")==gold["pm"],
      "drag": isinstance(ad,dict) and ad.get("model")=="JacchiaRoberts" and set(ad.keys())<= {"enabled","model"},
      "SRP": fm.get("solarRadiationPressure") is True,
      "maneuvers": "maneuvers" in p,
      "propagation": pr.get("integrator")==gold["intg"] and sc_.get("type")==gold["stop"][0] and sc_.get("value")==gold["stop"][1] and pr.get("stepSizeSecs")==60,
    }
    score_grid[name] = check
    failure_classes[name] = {f: classify(name,p,gold,f) for f in FIELDS if not check[f]}

# extras #13/#14 default-driven scoring
def extra_score(p, body, default_grav, frame):
    ad = g(p,"forceModel","atmosphericDrag")
    fm = p.get("forceModel") or {}
    pr = p.get("propagation") or {}
    return {
      "version": p.get("version")=="1.0",
      "experimentName": True,
      "epoch_default": g(p,"epoch","value")=="01 Jan 2026 12:00:00.000",
      "frame_inside_initialOrbit": g(p,"initialOrbit","coordinateSystem")==frame,
      "gravity": fm.get("gravityDegree")==default_grav[0] and fm.get("gravityOrder")==default_grav[1],
      "pointMasses": fm.get("pointMasses")==(["Luna","Sun"] if body!="Sun" else []),
      "drag_conforms": isinstance(ad,dict) and ad.get("model")=="JacchiaRoberts" and set(ad.keys())<= {"enabled","model"},
      "SRP": fm.get("solarRadiationPressure") is True,
      "maneuvers_key": "maneuvers" in p,
      "propagation_conforms": pr.get("integrator")=="RungeKutta89" and pr.get("stepSizeSecs")==60 and isinstance(pr.get("stopCondition"),dict),
    }

e13 = payloads[[x["experimentName"] for x in payloads].index("MercB2_027")]
e14 = payloads[[x["experimentName"] for x in payloads].index("ParaphraseTrain033")]
extras = {
  "MercB2_027": extra_score(e13,"Mercury",(0,0),"MercuryMJ2000Eq"),
  "ParaphraseTrain033": extra_score(e14,"Earth",(4,4),"EarthMJ2000Eq"),
}

# per-field totals
ftot = {f: sum(1 for n in GOLD if score_grid[n][f]) for f in FIELDS}
per_test = {n: sum(score_grid[n].values()) for n in GOLD}
grand = sum(per_test.values())

result = {
  "attempt": 2, "data_version": "v12", "data_hash": "a0c20c4f8e106b3eb632dbaca913134a187474375594d574b44a01443b9e45f1",
  "tests_scored": list(GOLD.keys()),
  "fields": FIELDS,
  "score_grid": score_grid,
  "per_test_totals": per_test,
  "grand_total": grand, "grand_denom": len(GOLD)*len(FIELDS),
  "grand_pct": round(grand/(len(GOLD)*len(FIELDS))*100,1),
  "fully_correct_tests": sum(1 for n in GOLD if per_test[n]==len(FIELDS)),
  "field_totals": ftot,
  "failure_classes": failure_classes,
  "extras_default_scored": extras,
  "extras_orbit_gold": "none provided in tasking -> SMA/ecc+angles/sc-mass marked N/A",
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT,"w",encoding="utf-8") as f:
    json.dump(result,f,indent=2,ensure_ascii=False)

print(f"wrote {OUT}")
print("grand:", grand, "/", len(GOLD)*len(FIELDS), f"= {grand/(len(GOLD)*len(FIELDS)*100):.1f}%")
print("fully correct:", result["fully_correct_tests"])
print("field totals:", ftot)
print("per-test:", per_test)
print("extras:", json.dumps(extras,indent=1))
