"""
Phase 3 v12_gen generator for OrbitLab.

Reads spec rows from ../../datasets/v12/*.jsonl, builds one ChatML training row
per spec (system prompt reused verbatim from v11; user text using exact v10
wording; assistant JSON with canonical v9b key order), then classifies,
validates, verifies rejects, dedups, and writes outputs + report into
datasets/v12_gen/.

Run from: phase3_ai_interpreter/  (project root of this repo)
"""

import json
import glob
import os
import sys
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# __file__ = <repo>/phase3_ai_interpreter/datasets/v12_gen/build_v12_gen.py
GEN = os.path.dirname(os.path.abspath(__file__))          # .../datasets/v12_gen
DATASETS = os.path.dirname(GEN)                            # .../datasets
PHASE = os.path.dirname(DATASETS)                          # .../phase3_ai_interpreter
ROOT = os.path.dirname(PHASE)                              # <repo root>
V12 = os.path.join(PHASE, "datasets", "v12")
V12GEN = os.path.join(PHASE, "datasets", "v12_gen")
V11 = os.path.join(PHASE, "datasets", "v11_train")
V10F = os.path.join(PHASE, "datasets", "v10", "fixed")
BODIES_JSON = os.path.join(ROOT, "orbitlab_core", "bodies.json")

OUT_JSONL = os.path.join(V12GEN, "orbitlab_v12_gen.jsonl")
REPORT_MD = os.path.join(V12GEN, "report.md")

# ---------------------------------------------------------------------------
# Load constants
# ---------------------------------------------------------------------------
with open(BODIES_JSON, encoding="utf-8") as f:
    bodies_cfg = json.load(f)["bodies"]

# Coordinate systems (confirmed from v11 train rows)
COORD_SYSTEM = {
    "Earth": "EarthMJ2000Eq",
    "Sun": "SunMJ2000Eq",
    "Moon": "LunaMJ2000Eq",
    "Mars": "MarsMJ2000Eq",
    "Mercury": "MercuryMJ2000Eq",
    "Jupiter": "JupiterMJ2000Eq",
    "Venus": "VenusMJ2000Eq",
}

# Default force model per body (tasking requirements)
DEFAULT_GRAV_DEG = 4
DEFAULT_PM = ["Luna", "Sun"]
MERCURY_JUPITER_GRAV = 0
SUN_GRAV = 0
SUN_PM = []

AU_KM = 149597870.691

# ---------------------------------------------------------------------------
# System prompt: reuse verbatim from v11 train rows
# ---------------------------------------------------------------------------
def load_system_prompt():
    fn = os.path.join(V11, "orbitlab_v11_tinker_train.jsonl")
    prompts = set()
    with open(fn, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            prompts.add(d["messages"][0]["content"])
    assert len(prompts) == 1, f"expected 1 distinct system prompt, got {len(prompts)}"
    return prompts.pop()

SYSTEM_PROMPT = load_system_prompt()

# ---------------------------------------------------------------------------
# User-text number rendering (natural str, no trailing .0)
# ---------------------------------------------------------------------------
def nstr(v):
    """Render a number the way v10 did: natural str, whole values without .0."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)

def fmt_orbital_e(e_str):
    """eccentricity text: used as provided."""
    return e_str

# ---------------------------------------------------------------------------
# Build user text (exact v10 wording)
# ---------------------------------------------------------------------------
def build_user(spec):
    run = spec["id"]
    body = spec["body"]
    form = spec["form"]
    mass = spec["mass"]
    inc = spec["inc"]
    raan = spec["raan"]
    aop = spec["aop"]
    ta = spec["ta"]
    dur = spec["dur"]
    unit = spec["unit"]
    integ = spec["integ"]

    if form == "circ":
        orbit_clause = f"around {body} a circular orbit at an altitude of {nstr(spec['h'])} km,"
    elif form == "peri":
        orbit_clause = (
            f"around {body} a periapsis altitude of {nstr(spec['h'])} km, "
            f"eccentricity {spec['e']:.4f},"
        )
    elif form == "sma":
        orbit_clause = f"around {body} with SMA {nstr(spec['a'])} km, eccentricity {spec['e']},"
    elif form == "au":
        x = spec["x"]
        k = round(x * AU_KM, 3)
        e_text = "0" if spec["e"] == 0 else str(spec["e"])
        orbit_clause = (
            f"around {body} with SMA {nstr(x)} AU ({nstr(k)} km) from the centre, "
            f"eccentricity {e_text},"
        )
    else:
        raise ValueError(f"unknown form {form}")

    force = spec.get("force")
    if force:
        pm = force.get("pm", [])
        srp = force.get("srp")
        srp_word = "enable" if srp else "disable"
        pm_clause = f" with point masses {', '.join(pm)}" if pm else ""
        force_clause = (
            f"use a degree-{force['deg']} and order-{force['deg']} gravity field"
            f"{pm_clause} and {srp_word} solar radiation pressure."
        )
    else:
        force_clause = "use the model's default force settings; I'm not asking for extra options."

    user = (
        f"I'd like an experiment call the run \"{run}\" with spacecraft \"SC{run}\"; "
        f"use {nstr(mass)} kg for the dry mass; {orbit_clause} "
        f"inclination {nstr(inc)} degrees, RAAN {nstr(raan)} degrees, "
        f"argument of periapsis {nstr(aop)} degrees, true anomaly {nstr(ta)} degrees; "
        f"propagate for {nstr(dur)} {unit}; integrate with {integ}; {force_clause}"
    )
    return user

# ---------------------------------------------------------------------------
# Build assistant JSON (canonical v9b key order)
# ---------------------------------------------------------------------------
def body_radius(spec):
    return bodies_cfg[spec["body"]]["radiusKm"]

def compute_sma(spec):
    form = spec["form"]
    r = body_radius(spec)
    if form == "circ":
        return r + spec["h"]
    if form == "peri":
        return round((r + spec["h"]) / (1.0 - spec["e"]), 3)
    if form == "sma":
        return spec["a"]
    if form == "au":
        return round(spec["x"] * AU_KM, 3)
    raise ValueError(form)

def force_model(spec):
    body = spec["body"]
    if spec.get("force"):
        deg = spec["force"]["deg"]
        pm = list(spec["force"]["pm"])
        srp = bool(spec["force"]["srp"])
    else:
        if body in ("Mercury", "Jupiter", "Sun"):
            deg = 0
        else:
            deg = DEFAULT_GRAV_DEG
        pm = [] if body == "Sun" else list(DEFAULT_PM)
        srp = True
    return {
        "gravityDegree": deg,
        "gravityOrder": deg,
        "pointMasses": pm,
        "atmosphericDrag": {"enabled": False, "model": "JacchiaRoberts"},
        "solarRadiationPressure": srp,
    }

def stop_condition(spec):
    """Propagation stop condition per TASKING: unit hours -> ElapsedHours,
    unit days -> ElapsedDays, value = dur as float."""
    return {
        "type": "ElapsedHours" if spec["unit"] == "hours" else "ElapsedDays",
        "value": float(spec["dur"]),
    }

def build_assistant(spec):
    run = spec["id"]
    body = spec["body"]
    sma = compute_sma(spec)
    stop = stop_condition(spec)
    return {
        "version": "1.0",
        "experimentName": run,
        "spacecraft": {
            "name": "SC" + run,
            "dryMassKg": float(spec["mass"]),
            "coefficientOfDrag": 2.2,
            "dragAreaM2": 1.0,
            "coefficientOfReflectivity": 1.8,
            "srpAreaM2": 1.0,
        },
        "centralBody": body,
        "epoch": {"format": "UTCGregorian", "value": "01 Jan 2026 12:00:00.000"},
        "initialOrbit": {
            "type": "Keplerian",
            "coordinateSystem": COORD_SYSTEM[body],
            "elements": {
                "semiMajorAxisKm": float(sma),
                "eccentricity": float(spec["e"]),
                "inclinationDeg": float(spec["inc"]),
                "raanDeg": float(spec["raan"]),
                "argumentOfPeriapsisDeg": float(spec["aop"]),
                "trueAnomalyDeg": float(spec["ta"]),
            },
        },
        "forceModel": force_model(spec),
        "maneuvers": [],
        "propagation": {
            "integrator": spec["integ"],
            "stopCondition": stop,
            "stepSizeSecs": 60.0,
        },
    }

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def self_classify(spec):
    body = spec["body"]
    sma = compute_sma(spec)
    e = spec["e"]
    if spec["inc"] > 180:
        return "bad_incl"
    soi = bodies_cfg[body].get("soiRadiusKm")
    apogee = sma * (1.0 + e)
    if soi and apogee > soi:
        return "beyond_soi"
    r = body_radius(spec)
    periapsis_alt = sma * (1.0 - e) - r
    if periapsis_alt < bodies_cfg[body]["minPeriapsisAltKm"]:
        return "below_min"
    return "valid"

# ---------------------------------------------------------------------------
# Validation using the real interpreter chain
# ---------------------------------------------------------------------------
def load_interpreter():
    sys.path.insert(0, PHASE)
    sys.path.insert(0, ROOT)   # orbitlab_core lives at repo root
    sys.path.insert(0, os.path.join(ROOT, "phase3_ai_interpreter"))
    from interpreter.json_interpreter import JsonExperimentInterpreter
    return JsonExperimentInterpreter()

def validate_assistant(interp, assistant_str):
    """Returns (ok, errors list)."""
    res = interp.interpret(assistant_str)
    return res.success, list(res.errors)

# ---------------------------------------------------------------------------
# Read JSONL files -> list of parsed messages dicts
# ---------------------------------------------------------------------------
def read_messages(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            out.append(json.loads(line))
    return out

def extract_ref_user_text(d):
    """Extract the dedup user-text from a ref row dict across formats."""
    msgs = d.get("messages")
    if isinstance(msgs, list):
        for m in msgs:
            if isinstance(m, dict) and m.get("role") == "user" and \
                    isinstance(m.get("content"), str):
                return m["content"]
    if "user_text" in d:
        return d["user_text"]
    return None

def extract_ref_triple(d):
    """Extract (body, sma, ecc) from a ref row's assistant JSON across formats."""
    msgs = d.get("messages")
    asst_str = None
    if isinstance(msgs, list):
        for m in msgs:
            if isinstance(m, dict) and m.get("role") == "assistant" and \
                    isinstance(m.get("content"), str):
                asst_str = m["content"]
                break
        else:
            asst_str = None
    if asst_str is None and d.get("expect_json"):
        asst_str = d["expect_json"]
    if not asst_str:
        return None
    try:
        a = json.loads(asst_str) if isinstance(asst_str, str) else asst_str
    except Exception:
        return None
    elems = a.get("initialOrbit", {}).get("elements", {})
    return (
        a.get("centralBody"),
        round(float(elems.get("semiMajorAxisKm", -1)), 3),
        round(float(elems.get("eccentricity", -1)), 3),
    )

# ---------------------------------------------------------------------------
def main():
    os.makedirs(V12GEN, exist_ok=True)

    # 1. Load specs
    specs = []
    for fn in sorted(glob.glob(os.path.join(V12, "*.jsonl"))):
        with open(fn, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                specs.append(json.loads(line))
    assert len(specs) == 480, f"expected 480 specs, got {len(specs)}"
    print(f"loaded {len(specs)} specs")

    # 2. Build all rows
    rows = {}   # id -> dict(messages, spec)
    user_text_by_id = {}
    for spec in specs:
        user = build_user(spec)
        asst = build_assistant(spec)
        asst_str = json.dumps(asst, separators=(",", ":"), ensure_ascii=False)
        # No BOM: write later with utf-8 (no utf-8-sig)
        msg = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
                {"role": "assistant", "content": asst_str},
            ]
        }
        rows[spec["id"]] = {"messages": msg, "spec": spec, "asst_str": asst_str}
        user_text_by_id[spec["id"]] = user

    # 3. Classification check: self vs Gemini spec class
    class_drops = []
    for sid, r in rows.items():
        sc = self_classify(r["spec"])
        if sc != r["spec"]["class"]:
            class_drops.append((sid, r["spec"]["class"], sc, compute_sma(r["spec"])))
    for sid, g, s, sma in class_drops:
        print(f"  CLASS MISMATCH {sid}: gemini={g} self={s} sma={sma}")
    if class_drops:
        print(f"WARNING: {len(class_drops)} class mismatches (tasking expects 0)")
    for sid, *_ in class_drops:
        del rows[sid]

    # 4. Validation
    interp = load_interpreter()
    valid_drops = []      # (id, errors)
    unrepresentable = []  # (id, errors) valid but duration > 365-day schema cap
    reject_bad_reason = []  # (id, expected_reason, actual_errors)
    for sid, r in rows.items():
        cls = r["spec"]["class"]
        # Physically-valid but schema-unrepresentable: stopCondition types are all
        # capped at 365 elapsed days (models.py StopCondition), so a valid row with
        # unit=days and dur > 365.0 cannot be expressed. Report it distinctly,
        # do not clamp or rewrite the user's requested duration (TASKING rule).
        if cls == "valid" and r["spec"]["unit"] == "days" and float(r["spec"]["dur"]) > 365.0:
            ok, errs = validate_assistant(interp, r["asst_str"])
            unrepresentable.append((sid, errs))
            continue
        ok, errs = validate_assistant(interp, r["asst_str"])
        if cls == "valid":
            if not ok:
                valid_drops.append((sid, errs))
        else:
            # verify it fails with the CORRECT reason
            if ok:
                # does NOT fail at all -> bad reject
                reject_bad_reason.append((sid, cls, ["PASSED (should fail)"]))
                continue
            if cls == "bad_incl":
                good = any("pydantic" in e and "inclination" in e for e in errs)
            elif cls in ("below_min", "beyond_soi"):
                key = ("safe periapsis" if cls == "below_min"
                       else "sphere of influence")
                good = any("physical" in e and key in e for e in errs)
            else:
                good = False
            if not good:
                reject_bad_reason.append((sid, cls, errs))
    for sid, errs in valid_drops:
        print(f"  VALID ROW FAILED: {sid} -> {errs}")
    for sid, errs in unrepresentable:
        print(f"  UNREPRESENTABLE (valid, dur>365d): {sid} -> {errs}")
    for sid, cls, errs in reject_bad_reason:
        print(f"  REJECT WRONG REASON: {sid} ({cls}) -> {errs}")
    for sid, *_ in valid_drops + unrepresentable + reject_bad_reason:
        rows.pop(sid, None)

    # 5. Dedup
    dedup_drops = []
    # 5a. build ref sets from v11 train/val + blind + eval
    ref_user = set()
    ref_triple = set()   # (body, round(sma,3), round(ecc,3))
    ref_files = [
        os.path.join(V11, "orbitlab_v11_tinker_train.jsonl"),
        os.path.join(V11, "orbitlab_v11_tinker_val.jsonl"),
        os.path.join(V11, "blind", "batch_10_all_blind.jsonl"),
        os.path.join(V11, "blind", "v9b_blind_eval.jsonl"),
        os.path.join(V11, "eval", "cases_blind.jsonl"),
        os.path.join(V11, "eval", "cases_realistic.jsonl"),
    ]
    for path in ref_files:
        for d in read_messages(path):
            u = extract_ref_user_text(d)
            if u:
                ref_user.add(u)
            t = extract_ref_triple(d)
            if t:
                ref_triple.add(t)
    print(f"dedup refs: {len(ref_user)} user texts, {len(ref_triple)} (body,sma,ecc) triples")

    # 5b. self-dedup by user text or (body,sma,ecc)
    seen_user = set()
    seen_triple = set()
    for sid in list(rows.keys()):
        r = rows[sid]
        spec = r["spec"]
        sma = round(compute_sma(spec), 3)
        triple = (spec["body"], sma, round(spec["e"], 3))
        user = user_text_by_id[sid]
        dupe_self = (user in seen_user) or (triple in seen_triple)
        dupe_ref = (user in ref_user) or (triple in ref_triple)
        if dupe_self:
            dedup_drops.append((sid, "duplicate within v12_gen (user or triple)"))
            del rows[sid]
        elif dupe_ref:
            dedup_drops.append((sid, "duplicate vs v11/blind/eval (user or triple)"))
            del rows[sid]
        else:
            seen_user.add(user)
            seen_triple.add(triple)

    for sid, reason in dedup_drops:
        print(f"  DEDUP DROP {sid}: {reason}")

    # 6. Write outputs
    kept = sorted(rows.keys(), key=lambda sid: (sid,))
    out_lines = []
    for sid in kept:
        out_lines.append(json.dumps(rows[sid]["messages"], separators=(",", ":"), ensure_ascii=False))
    with open(OUT_JSONL, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out_lines) + ("\n" if out_lines else ""))
    print(f"wrote {len(out_lines)} rows to {OUT_JSONL}")

    # Counts
    body_form = Counter()
    body_class = Counter()
    for sid in kept:
        spec = rows[sid]["spec"]
        body_form[(spec["body"], spec["form"])] += 1
        body_class[(spec["body"], spec["class"])] += 1

    short_cells = []
    all_body_forms = sorted({(s["body"], s["form"]) for s in specs})
    for (b, fm) in all_body_forms:
        target = sum(1 for s in specs if s["body"] == b and s["form"] == fm)
        got = body_form.get((b, fm), 0)
        if got < target:
            short_cells.append((b, fm, got, target))

    # 7. Report
    report(OUT_JSONL, REPORT_MD, body_form, body_class, class_drops,
           valid_drops, unrepresentable, reject_bad_reason, dedup_drops, short_cells,
           len(kept), len(out_lines))

    print("DONE")


def report(out_jsonl, report_md, body_form, body_class, class_drops,
           valid_drops, unrepresentable, reject_bad_reason, dedup_drops, short_cells,
           kept_count, out_lines_count):
    lines = []
    lines.append("# v12_gen report — generated training dataset (OrbitLab)")
    lines.append("")
    lines.append(f"Input specs: 480 rows from `datasets/v12/*.jsonl`. Output: "
                 f"{out_lines_count} rows in `orbitlab_v12_gen.jsonl`.")
    lines.append("")
    lines.append("## Verdict")
    ct = Counter()
    for (b, c) in body_class:
        ct[c] += body_class[(b, c)]
    ready = kept_count >= 420 and not class_drops and not valid_drops and not reject_bad_reason
    lines.append(f"**{'READY' if ready else 'NOT READY'}** — kept {kept_count} rows")
    lines.append("")
    lines.append(f"Classification mismatches (self vs Gemini): {len(class_drops)}")
    lines.append(f"Valid rows that failed validation: {len(valid_drops)}")
    lines.append(f"Valid rows unrepresentable (duration > 365-day schema cap): {len(unrepresentable)}")
    lines.append(f"Reject rows failing with wrong reason: {len(reject_bad_reason)}")
    lines.append(f"Dedup drops: {len(dedup_drops)}")
    lines.append("")
    lines.append("## Class counts (kept)")
    for c in ["valid", "below_min", "beyond_soi", "bad_incl"]:
        lines.append(f"- {c}: {ct.get(c, 0)}")
    lines.append("")
    lines.append("## Per-body / form counts (kept)")
    lines.append("| body | form | count |")
    lines.append("|------|------|-------|")
    for (b, fm) in sorted(body_form):
        lines.append(f"| {b} | {fm} | {body_form[(b, fm)]} |")
    lines.append("")

    if class_drops:
        lines.append("## Classification mismatches (dropped)")
        lines.append("| id | gemini | self | sma |")
        lines.append("|----|--------|------|-----|")
        for sid, g, s, sma in class_drops:
            lines.append(f"| {sid} | {g} | {s} | {sma} |")
        lines.append("")
    if valid_drops:
        lines.append("## Valid rows that failed validation (dropped)")
        for sid, errs in valid_drops:
            lines.append(f"- {sid}: {errs}")
        lines.append("")
    if unrepresentable:
        lines.append("## Valid rows unrepresentable (dropped)")
        lines.append("These physically-valid rows exceed the 365-day schema cap for all ")
        lines.append("stop-condition types (ElapsedDays max 365.0 / ElapsedHours max 8760 / ")
        lines.append("ElapsedSeconds max 31536000), so no schema-legal representation exists.")
        lines.append("Per TASKING, the user-requested duration is never clamped/rewritten.")
        for sid, errs in unrepresentable:
            lines.append(f"- {sid}: {errs}")
        lines.append("")
    if reject_bad_reason:
        lines.append("## Reject rows failing with wrong reason (dropped)")
        for sid, cls, errs in reject_bad_reason:
            lines.append(f"- {sid} ({cls}): {errs}")
        lines.append("")
    if dedup_drops:
        lines.append("## Dedup drops")
        lines.append("| id | reason |")
        lines.append("|----|--------|")
        for sid, reason in dedup_drops:
            lines.append(f"| {sid} | {reason} |")
        lines.append("")
    if short_cells:
        lines.append("## Short cells (below spec target) — top-up candidates")
        lines.append("| body | form | got | target |")
        lines.append("|------|------|-----|--------|")
        for b, fm, got, tgt in short_cells:
            lines.append(f"| {b} | {fm} | {got} | {tgt} |")
        lines.append("")
    lines.append("## Notes")
    lines.append("- System prompt reused verbatim from v11 train rows (1 distinct value across all v11 rows).")
    lines.append("- User text uses exact v10 sentence templates; reject rows use the same templates with failing values.")
    lines.append("- `eval/cases_realistic.jsonl` is empty (0 rows) — no-op dedup source.")
    lines.append("- T01–T12 test-prompt files were not found anywhere in the repo — treated as no-op dedup source.")
    lines.append("- Reject assistant JSON computed with the same SMA formulas as valid rows (not copied from v10 batch_09).")
    lines.append("")

    with open(report_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"wrote report to {report_md}")


if __name__ == "__main__":
    main()
