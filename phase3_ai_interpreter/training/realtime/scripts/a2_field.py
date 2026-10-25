# Deterministic field-level scoring for attempt-2 (data v12) outputs.
# Scores T01-T12 (gold defined) over 14 fields; reports extra #13/#14 separately
# on default-driven/schema fields only (no gold for orbit elements).
import io, json, sys, os, re

REPO = r"C:\Users\canit\.devswarm\repos\0\c799e6d2\feature-physics-core"
RAW = os.path.join(REPO, "phase3_ai_interpreter", "training", "realtime", "outputs_raw_A2.txt")

with io.open(RAW, "r", encoding="utf-8") as f:
    raw_text = f.read()

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

def load(txt):
    t = re.sub(r'^\s*\d+\.\s*', '', txt, count=1)
    t = re.sub(r'---\s*END\s*---.*$', '', t, flags=re.S).rstrip() + "\n"
    return json.loads(t)

def g(p, *path):
    cur = p
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur

# gold: name -> dict
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

def score(p, name, gold):
    r = {}
    # version
    r["version"] = (p.get("version") == "1.0")
    # experimentName
    r["experimentName"] = (p.get("experimentName") == name)
    # spacecraft
    sc = g(p,"spacecraft")
    ok = (sc and sc.get("name")==("SC_"+name) and sc.get("dryMassKg")==gold["mass"]
          and sc.get("coefficientOfDrag")==2.2 and sc.get("dragAreaM2")==1
          and sc.get("coefficientOfReflectivity")==1.8 and sc.get("srpAreaM2")==1)
    r["spacecraft"] = ok
    # centralBody
    r["centralBody"] = (p.get("centralBody")==gold["body"])
    # epoch
    ep = g(p,"epoch","value")
    r["epoch"] = (ep=="01 Jan 2026 12:00:00.000")
    # frame (inside initialOrbit)
    r["frame"] = (g(p,"initialOrbit","coordinateSystem")==FRAME[gold["body"]])
    # SMA tol 0.002
    sma = g(p,"initialOrbit","elements","semiMajorAxisKm")
    r["SMA"] = (sma is not None and abs(sma-gold["sma"])<=0.002)
    # ecc+angles
    el = g(p,"initialOrbit","elements") or {}
    r["ecc+angles"] = (el.get("eccentricity")==gold["ecc"] and el.get("inclinationDeg")==gold["inc"]
                       and el.get("raanDeg")==gold["raan"] and el.get("argumentOfPeriapsisDeg")==gold["aop"]
                       and el.get("trueAnomalyDeg")==gold["ta"])
    # gravity
    fm = p.get("forceModel") or {}
    r["gravity"] = (fm.get("gravityDegree")==gold["grav"][0] and fm.get("gravityOrder")==gold["grav"][1])
    # pointMasses
    r["pointMasses"] = (fm.get("pointMasses")==gold["pm"])
    # drag object: present, dict, model JacchiaRoberts, only keys {enabled,model}
    ad = fm.get("atmosphericDrag")
    r["drag"] = (isinstance(ad,dict) and ad.get("model")=="JacchiaRoberts"
                 and set(ad.keys())<= {"enabled","model"})
    # SRP
    r["SRP"] = (fm.get("solarRadiationPressure") is True)
    # maneuvers key present
    r["maneuvers"] = ("maneuvers" in p)
    # propagation: integrator + stopCondition(type,value) + step 60
    pr = p.get("propagation") or {}
    sc_ = pr.get("stopCondition") or {}
    ok_prop = (pr.get("integrator")==gold["intg"]
               and sc_.get("type")==gold["stop"][0] and sc_.get("value")==gold["stop"][1]
               and pr.get("stepSizeSecs")==60)
    r["propagation"] = ok_prop
    return r

print("=== FIELD SCORES T01-T12 (rows=fields, each cell PASS/FAIL) ===")
hdr = "field".ljust(13) + "".join(f"{n:>5}" for n in GOLD)
print(hdr)
per_test_total = {}
totals = {f:0 for f in FIELDS}
# name -> payload
name2payload = {}
for num, txt in blocks:
    try:
        name2payload[load(txt)["experimentName"]] = load(txt)
    except Exception as e:
        pass
for f in FIELDS:
    row = f.ljust(13)
    for name in GOLD:
        r = score(name2payload[name], name, GOLD[name])
        row += f"{'P' if r[f] else '.' :>5}"
        if r[f]: totals[f]+=1
    print(row)
print()
print("Field totals (of 12):")
for f in FIELDS:
    print(f"  {f}: {totals[f]}/12")
print()
print("=== PER-TEST TOTALS ===")
grand=0
for name in GOLD:
    r = score(name2payload[name], name, GOLD[name])
    n = sum(r.values())
    grand += n
    print(f"  {name}: {n}/14")
print(f"  TOTAL: {grand}/168 = {grand/168*100:.1f}%")
print(f"  fully correct tests: {sum(1 for name in GOLD if sum(score(name2payload[name],name,GOLD[name]).values())==14)}")
