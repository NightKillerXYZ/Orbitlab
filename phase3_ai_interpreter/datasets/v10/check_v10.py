"""v10 dataset gate -- Step 3.

Gates all 400 Gemini batch rows (raw\\batch_01..batch_10) against the same
checks the front step / validators use, plus the SMA audit reused from the v9b
close-out and a v9b duplicate sweep.

What is verified here
---------------------
1.  Every row parses as JSON and keeps the canonical v9b assistant key order.
2.  Valid rows (batch_01-08, batch_10-blind) load through Pydantic, pass the
    AstrodynamicValidator *and* a deterministic GMAT compile (success == True),
    and point-mass gravity-degree>0 warnings are tallied (never failed).
3.  Reject rows (batch_09) must ALL be rejected by the AstrodynamicValidator:
    36 rows for below-minimum-altitude, 12 rows for exceeding the body SOI.
4.  SMA audit (reused from datasets\\v9\\audit_v9c_sma_all.py): every auditable
    row's semi-major axis must match what the prompt specifies, with the Sun AU
    rows handled as AU * 149597870.691 km (the AU rows' parenthetical km value
    equals the JSON SMA directly).  Zero mismatches expected.
5.  body constants (radius / mu / min-periapsis-altitude / SOI radius) must all
    match orbitlab_core/bodies.json for the bodies used (Mercury/Venus/Jupiter/Sun).
6.  Duplicates: no row duplicated within the 400 (by user text, experiment name,
    or body+element signature) and none duplicated against the 4300 v9b rows.

Output: datasets\\v10\\gate_report.json + gate_report.md

Rerun-safe: this script never edits raw\\ or any data; it is read-only.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # feature-physics-core
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parents[1]))  # phase3_ai_interpreter

from interpreter.json_interpreter import JsonExperimentInterpreter  # noqa: E402
from orbitlab_core.constants import CENTRAL_BODY_PROPERTIES  # noqa: E402

AU_KM = 149597870.691

RAW = HERE / "raw"
FIXED = HERE / "fixed"
V9B_MASTER = HERE.parent / "v9" / "orbitlab_interpreter_train_v9b_master.jsonl"

# Canonical v9b assistant JSON key order (frozen v9b storage).
CANON_TOP = ["version", "experimentName", "description", "spacecraft",
             "centralBody", "epoch", "initialOrbit", "forceModel",
             "maneuvers", "propagation"]
CANON_INITORBIT = ["type", "coordinateSystem", "elements"]
CANON_ELEMS = ["semiMajorAxisKm", "eccentricity", "inclinationDeg",
               "raanDeg", "argumentOfPeriapsisDeg", "trueAnomalyDeg"]
CANON_FORCEMODEL = ["gravityDegree", "gravityOrder", "pointMasses",
                    "atmosphericDrag", "solarRadiationPressure"]
CANON_SC = ["name", "dryMassKg", "coefficientOfDrag", "dragAreaM2",
            "coefficientOfReflectivity", "srpAreaM2"]
CANON_PROP = ["integrator", "stopCondition", "stepSizeSecs"]

# Expected file -> (kind, count, bodies).  batch_09/10 kinds are 'reject'/'blind'.
FILE_EXPECT = {
    "batch_01_mercury_valid.jsonl": ("valid", 40, ["Mercury"]),
    "batch_02_mercury_valid.jsonl": ("valid", 40, ["Mercury"]),
    "batch_03_venus_valid.jsonl": ("valid", 40, ["Venus"]),
    "batch_04_venus_valid.jsonl": ("valid", 40, ["Venus"]),
    "batch_05_jupiter_valid.jsonl": ("valid", 40, ["Jupiter"]),
    "batch_06_jupiter_valid.jsonl": ("valid", 40, ["Jupiter"]),
    "batch_07_sun_valid.jsonl": ("valid", 40, ["Sun"]),
    "batch_08_sun_valid.jsonl": ("valid", 40, ["Sun"]),
    "batch_09_all_reject.jsonl": ("reject", 48, ["Mercury", "Venus", "Jupiter", "Sun"]),
    "batch_10_all_blind.jsonl": ("blind", 32, ["Mercury", "Venus", "Jupiter", "Sun"]),
}
VALID_FILES = [k for k, v in FILE_EXPECT.items() if v[0] in ("valid", "blind")]


def load_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def check_key_order(exp: dict) -> list[str]:
    """Return list of key-order problems (empty == OK)."""
    problems = []
    top = list(exp.keys())
    expected = [k for k in CANON_TOP if not (k == "description" and "description" not in exp)]
    if top != expected:
        problems.append(f"top keys {top} != expected {expected}")
    if list(exp.get("initialOrbit", {}).keys()) != CANON_INITORBIT:
        problems.append(f"initialOrbit keys {list(exp.get('initialOrbit', {}).keys())}")
    el = exp.get("initialOrbit", {}).get("elements", {})
    if list(el.keys()) != CANON_ELEMS:
        problems.append(f"elements keys {list(el.keys())}")
    if list(exp.get("forceModel", {}).keys()) != CANON_FORCEMODEL:
        problems.append(f"forceModel keys {list(exp.get('forceModel', {}).keys())}")
    if list(exp.get("spacecraft", {}).keys()) != CANON_SC:
        problems.append(f"spacecraft keys {list(exp.get('spacecraft', {}).keys())}")
    if list(exp.get("propagation", {}).keys()) != CANON_PROP:
        problems.append(f"propagation keys {list(exp.get('propagation', {}).keys())}")
    return problems


# ---------------------------------------------------------------------------
# SMA audit -- reuse audit_v9c_sma_all
# ---------------------------------------------------------------------------
_spec = importlib.util.spec_from_file_location(
    "_audit_all", HERE.parent / "v9" / "audit_v9c_sma_all.py"
)
audall = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audall)

RADIUS = audall.RADIUS
TOLERANCE_KM = audall.TOLERANCE_KM
_RADIUS = RADIUS  # local alias for the body table below


def sma_audit_one(prompt: str, body: str, actual_sma: float, actual_e: float):
    """Return (category, expected_sma, status) for one row.

    Sun AU rows: 'SMA X AU (Y km) from the centre' -> expected = round(X*AU_KM,3).
    Otherwise reuse the v9b derivation (audit_v9c_sma_all).
    """
    m = re.search(r"SMA\s+([\d.]+)\s*AU\s*\(\s*([\d.]+)\s*km\s*\)", prompt, re.I)
    if m:
        au = float(m.group(1))
        expected = round(au * AU_KM, 3)
        status = "pass" if abs(expected - actual_sma) <= TOLERANCE_KM else "fail"
        return "sun-au", expected, status
    return audall.derive_expected_all(prompt, body, actual_sma, actual_e)


# ---------------------------------------------------------------------------
# bodies.json numbers table
# ---------------------------------------------------------------------------
_BODY_JSON = json.loads((ROOT / "orbitlab_core" / "bodies.json").read_text(encoding="utf-8"))["bodies"]


def body_number_check(body: str) -> list[str]:
    """Verify the v10-relevant bodies.json constants against chosen bodies."""
    problems = []
    if body not in ("Mercury", "Venus", "Jupiter", "Sun"):
        problems.append(f"unexpected centralBody {body!r}")
        return problems
    props = CENTRAL_BODY_PROPERTIES[body]
    bj = _BODY_JSON[body]
    checks = {
        "radiusKm": (props[0], bj["radiusKm"]),
        "muKm3S2": (props[1], bj["muKm3S2"]),
    }
    for name, (ports, bjson) in checks.items():
        if abs(float(ports) - float(bjson)) > 1e-9:
            problems.append(f"{body}.{name} mismatch ports={ports} bodies.json={bjson}")
    return problems


def body_numbers_report_rows() -> list[dict]:
    rows = []
    for body in ["Mercury", "Venus", "Jupiter", "Sun"]:
        bj = _BODY_JSON[body]
        rows.append({
            "body": body,
            "radiusKm": bj["radiusKm"],
            "muKm3S2": bj["muKm3S2"],
            "minPeriapsisAltKm": bj.get("minPeriapsisAltKm"),
            "soiRadiusKm": bj.get("soiRadiusKm"),
            "pointMassOnly": bj.get("pointMassOnly"),
            "gmatName": bj.get("gmatName"),
        })
    return rows


def main() -> int:
    interpreter = JsonExperimentInterpreter()

    report: dict[str, Any] = {
        "script": "check_v10.py",
        "step": "Step 3 gate",
        "total_rows": 0,
        "by_file": {},
        "key_order": {"checked": 0, "fail": 0, "rows_with_problems": []},
        "validation": {
            "valid_expected_pass": 0,
            "valid_actual_pass": 0,
            "valid_actual_fail": 0,
            "pointmass_gravity_warnings": 0,
            "warnings_by_file": {},
            "fail_rows": [],
        },
        "rejects": {
            "expected_total": 48,
            "expected_min_altitude": 36,
            "expected_soi": 12,
            "actual_rejected": 0,
            "actual_min_altitude": 0,
            "actual_soi": 0,
            "actual_accepted": 0,
            "unexpected": [],
        },
        "sma_audit": {
            "tolerance_km": TOLERANCE_KM,
            "rows": 0,
            "pass": 0,
            "fail": 0,
            "na": 0,
            "failures": [],
            "categories": Counter(),
        },
        "bodies": {
            "table": body_numbers_report_rows(),
            "problems": [],
        },
        "duplicates": {"within_400": [], "vs_v9b": []},
    }

    all_user_text = []
    all_expnames = []
    all_sig = []
    all_rows_meta = []  # (file, line, body, sma, ecc)

    master_rows = load_rows(V9B_MASTER)
    v9b_contents = master_rows
    v9b_user_set = set()
    v9b_sig_set = set()
    v9b_expname_set = set()
    for row in v9b_contents:
        contents = row.get("contents", row.get("messages", []))
        # find user text and assistant experiment
        user = ""
        exp = None
        for item in contents:
            role = item.get("role")
            text = (item.get("parts") or [{}])[0].get("text", "")
            if role == "user":
                user = text
            elif role == "assistant":
                try:
                    exp = json.loads(text)
                except Exception:
                    pass
        user_n = re.sub(r"\s+", " ", user).strip().lower()
        if user_n:
            v9b_user_set.add(user_n)
        if exp:
            v9b_expname_set.add(exp.get("experimentName"))
            el = exp.get("initialOrbit", {}).get("elements", {})
            sig = (exp.get("centralBody"), el.get("semiMajorAxisKm"), el.get("eccentricity"))
            if sig[0]:
                v9b_sig_set.add(sig)

    for fn in sorted(FILE_EXPECT):
        kind, exp_count, exp_bodies = FILE_EXPECT[fn]
        # All 10 batches are gated from fixed\\ -- the final deliverable dataset
        # (batch_01-08/09 are storage-normalised copies of raw; batch_10 is the
        # Step 1 corrected copy).  Gating here validates exactly what ships.
        path = FIXED / fn
        rows = load_rows(path)
        file_rec = {
            "kind": kind, "rows": len(rows), "expected_rows": exp_count,
            "expected_bodies": exp_bodies, "pass": True, "notes": [],
        }

        if len(rows) != exp_count:
            file_rec["pass"] = False
            file_rec["notes"].append(f"row count {len(rows)} != expected {exp_count}")

        # bodies used in this file
        bodies_seen = set()
        for i, row in enumerate(rows):
            line = i + 1
            report["total_rows"] += 1
            user = row["messages"][1]["content"]
            assistant = row["messages"][2]["content"]

            # --- 1. parse + key order ---
            report["key_order"]["checked"] += 1
            try:
                exp = json.loads(assistant)
            except Exception as e:
                report["key_order"]["rows_with_problems"].append(
                    {"file": fn, "line": line, "type": "parse", "detail": str(e)}
                )
                continue
            probs = check_key_order(exp)
            if probs:
                report["key_order"]["fail"] += 1
                report["key_order"]["rows_with_problems"].append(
                    {"file": fn, "line": line, "problems": probs}
                )

            body = exp.get("centralBody")
            bodies_seen.add(body)

            # store signature data for duplicate / sma
            all_user_text.append((fn, line, re.sub(r"\s+", " ", user).strip().lower()))
            all_expnames.append((fn, line, exp.get("experimentName")))
            el = exp.get("initialOrbit", {}).get("elements", {})
            all_sig.append((fn, line, (body, el.get("semiMajorAxisKm"), el.get("eccentricity"))))
            all_rows_meta.append((fn, line, body, el.get("semiMajorAxisKm"), el.get("eccentricity")))

            # body number check (each body checked once)
            bn = body_number_check(body)
            if bn:
                report["bodies"]["problems"].append({"file": fn, "line": line, "problems": bn})

            # --- SMA audit ---
            if el.get("semiMajorAxisKm") is not None and el.get("eccentricity") is not None:
                cat, expected, status = sma_audit_one(
                    user, body, float(el["semiMajorAxisKm"]), float(el["eccentricity"])
                )
                report["sma_audit"]["rows"] += 1
                report["sma_audit"]["categories"][cat] += 1
                report["sma_audit"][status] += 1
                if status == "fail":
                    report["sma_audit"]["failures"].append({
                        "file": fn, "line": line, "body": body,
                        "expected_sma_km": expected, "actual_sma_km": el["semiMajorAxisKm"],
                        "diff_km": abs((expected or 0) - float(el["semiMajorAxisKm"])),
                        "prompt": user[:160],
                    })

            # --- validation / GMAT compile ---
            res = interpreter.interpret(assistant)
            if kind in ("valid", "blind"):
                report["validation"]["valid_expected_pass"] += 1
                wcount = len(res.warnings)
                if wcount:
                    report["validation"]["pointmass_gravity_warnings"] += wcount
                    report["validation"]["warnings_by_file"][fn] = report["validation"]["warnings_by_file"].get(fn, 0) + wcount
                if res.success:
                    report["validation"]["valid_actual_pass"] += 1
                else:
                    report["validation"]["valid_actual_fail"] += 1
                    report["validation"]["fail_rows"].append(
                        {"file": fn, "line": line, "errors": res.errors[:3]}
                    )
                    file_rec["pass"] = False
            else:  # reject rows
                report["rejects"]["actual_rejected"] += 1
                err = (res.errors[0] if res.errors else "").lower()
                if "minimum safe altitude" in err:
                    report["rejects"]["actual_min_altitude"] += 1
                elif "sphere of influence" in err or "soi" in err:
                    report["rejects"]["actual_soi"] += 1
                else:
                    report["rejects"]["unexpected"].append(
                        {"file": fn, "line": line, "errors": res.errors[:3]}
                    )
                if res.success:
                    report["rejects"]["actual_accepted"] += 1
                    report["rejects"]["unexpected"].append(
                        {"file": fn, "line": line, "errors": "row was accepted (should reject)"}
                    )

        # bodies used vs expected
        actual_bodies = sorted(bodies_seen)
        if actual_bodies != sorted(exp_bodies):
            file_rec["pass"] = False
            file_rec["notes"].append(f"bodies seen {actual_bodies} != expected {sorted(exp_bodies)}")

        report["by_file"][fn] = file_rec

    # --- duplicate checks ---
    def dup_finder(seq):
        counts = Counter(seq)
        return [sig for sig, n in counts.items() if n > 1]

    dups_user = dup_finder(all_user_text)
    dups_name = dup_finder(all_expnames)
    dups_sig = dup_finder(all_sig)
    report["duplicates"]["within_400"] = {
        "by_user_text": [list(u) for u in dups_user],
        "by_experiment_name": [list(n) for n in dups_name],
        "by_body_sma_ecc": [list(s) for s in dups_sig],
    }

    # vs v9b
    vs_user = [(fn, ln, t) for (fn, ln, t) in all_user_text if t in v9b_user_set]
    vs_name = []
    for (fn, ln, name) in all_expnames:
        if name in v9b_expname_set:
            vs_name.append([fn, ln, name])
    vs_sig = []
    for (fn, ln, sig) in all_sig:
        if sig in v9b_sig_set:
            vs_sig.append([fn, ln, list(sig)])
    report["duplicates"]["vs_v9b"] = {
        "by_user_text": [list(x) for x in vs_user],  # (file,line,user)
        "by_experiment_name": vs_name,
        "by_body_sma_ecc": vs_sig,
    }

    # --- summarize / gate pass ---
    key_order_pass = report["key_order"]["fail"] == 0
    valid_pass = report["validation"]["valid_actual_fail"] == 0
    reject_ok = (
        report["rejects"]["actual_min_altitude"] == report["rejects"]["expected_min_altitude"]
        and report["rejects"]["actual_soi"] == report["rejects"]["expected_soi"]
        and report["rejects"]["actual_accepted"] == 0
        and not report["rejects"]["unexpected"]
    )
    sma_ok = report["sma_audit"]["fail"] == 0
    bodies_ok = not report["bodies"]["problems"]
    dup_ok = (
        not dups_user and not dups_name and not dups_sig
        and not vs_user and not vs_name and not vs_sig
    )

    report["gate"] = {
        "key_order_pass": key_order_pass,
        "validation_pass": valid_pass,
        "reject_rows_pass": reject_ok,
        "sma_audit_pass": sma_ok,
        "bodies_pass": bodies_ok,
        "duplicates_pass": dup_ok,
        "overall": all([
            key_order_pass, valid_pass, reject_ok,
            sma_ok, bodies_ok, dup_ok,
        ]),
    }

    # JSON output
    json_out = dict(report)
    json_out["sma_audit"]["categories"] = dict(report["sma_audit"]["categories"])
    (HERE / "gate_report.json").write_text(
        json.dumps(json_out, indent=2, default=list) + "\n", encoding="utf-8"
    )

    # Markdown output
    lines = []
    lines.append("# v10 dataset gate report")
    lines.append("")
    lines.append(f"Generated by `check_v10.py` — {len(json_out['by_file'])} batch files, {report['total_rows']} rows.")
    lines.append("")
    lines.append("## Gate summary")
    lines.append("")
    lines.append("| Check | Result |")
    lines.append("|---|---|")
    for k, v in report["gate"].items():
        lines.append(f"| {k} | {'PASS' if v else 'FAIL'} |")
    lines.append("")
    lines.append("## Per-file table")
    lines.append("")
    lines.append("| file | kind | rows | expected | pass | notes |")
    lines.append("|---|---|---|---|---|---|")
    for fn, rec in report["by_file"].items():
        lines.append(f"| {fn} | {rec['kind']} | {rec['rows']} | {rec['expected_rows']} | {'OK' if rec['pass'] else 'FAIL'} | {'; '.join(rec['notes']) if rec['notes'] else ''} |")
    lines.append("")
    lines.append("## Validation")
    lines.append("")
    v = report["validation"]
    lines.append(f"- valid rows expected to pass: {v['valid_expected_pass']}")
    lines.append(f"- valid rows actually passed (Pydantic + validator + GMAT compile): {v['valid_actual_pass']}")
    lines.append(f"- valid rows failed: {v['valid_actual_fail']}")
    lines.append(f"- point-mass gravity-degree>0 warnings: {v['pointmass_gravity_warnings']} ({dict(v['warnings_by_file'])})")
    if v["fail_rows"]:
        lines.append("\nFailing valid rows:")
        for f in v["fail_rows"]:
            lines.append(f"- {f['file']} line {f['line']}: {f['errors']}")
    lines.append("")
    lines.append("## Reject rows (batch_09)")
    lines.append("")
    rj = report["rejects"]
    lines.append(f"- expected min-altitude rejects: {rj['expected_min_altitude']}, actual: {rj['actual_min_altitude']}")
    lines.append(f"- expected SOI rejects: {rj['expected_soi']}, actual: {rj['actual_soi']}")
    lines.append(f"- actual accepted (should be none): {rj['actual_accepted']}")
    if rj["unexpected"]:
        lines.append("\nUnexpected:")
        for u in rj["unexpected"]:
            lines.append(f"- {u['file']} line {u['line']}: {u['errors']}")
    lines.append("")
    lines.append("## SMA audit")
    lines.append("")
    sa = report["sma_audit"]
    lines.append(f"- tolerance: {sa['tolerance_km']} km")
    lines.append(f"- rows audited: {sa['rows']} | pass: {sa['pass']} | fail: {sa['fail']} | na: {sa['na']}")
    lines.append(f"- categories: {dict(sa['categories'])}")
    if sa["failures"]:
        lines.append("\nFAILURES:")
        for f in sa["failures"]:
            lines.append(f"- {f['file']} line {f['line']} {f['body']}: expected {f['expected_sma_km']} got {f['actual_sma_km']} (diff {f['diff_km']})")
    lines.append("")
    lines.append("## Bodies (bodies.json)")
    lines.append("")
    lines.append("| body | radiusKm | muKm3S2 | minPeriapsisAltKm | soiRadiusKm | pointMassOnly | gmatName |")
    lines.append("|---|---|---|---|---|---|---|")
    for b in report["bodies"]["table"]:
        lines.append(f"| {b['body']} | {b['radiusKm']} | {b['muKm3S2']} | {b['minPeriapsisAltKm']} | {b['soiRadiusKm']} | {b['pointMassOnly']} | {b['gmatName']} |")
    if report["bodies"]["problems"]:
        lines.append("\nBody problems:")
        for p in report["bodies"]["problems"]:
            lines.append(f"- {p['file']} line {p['line']}: {p['problems']}")
    lines.append("")
    lines.append("## Duplicates")
    lines.append("")
    d = report["duplicates"]
    lines.append(f"- within 400 by user text: {len(d['within_400']['by_user_text'])}")
    lines.append(f"- within 400 by experiment name: {len(d['within_400']['by_experiment_name'])}")
    lines.append(f"- within 400 by body/SMA/ecc: {len(d['within_400']['by_body_sma_ecc'])}")
    lines.append(f"- vs v9b (4300) by user text: {len(d['vs_v9b']['by_user_text'])}")
    lines.append(f"- vs v9b (4300) by experiment name: {len(d['vs_v9b']['by_experiment_name'])}")
    lines.append(f"- vs v9b (4300) by body/SMA/ecc: {len(d['vs_v9b']['by_body_sma_ecc'])}")
    if d["vs_v9b"]["by_body_sma_ecc"]:
        lines.append("\nvs v9b collisions:")
        for c in d["vs_v9b"]["by_body_sma_ecc"]:
            lines.append(f"- {c}")
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    lines.append(f"**{'READY' if report['gate']['overall'] else 'NOT READY'}** — v10 dataset gate.")
    lines.append("")
    (HERE / "gate_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"gate": report["gate"], "total_rows": report["total_rows"]}, indent=2))
    print("sma categories:", dict(report["sma_audit"]["categories"]))
    print("key_order fail:", report["key_order"]["fail"])
    print("valid fail:", report["validation"]["valid_actual_fail"])
    print("reject unexpected:", report["rejects"]["unexpected"])
    print("dup within:", len(dups_user), len(dups_name), len(dups_sig))
    print("dup vs v9b:", len(vs_user), len(vs_name), len(vs_sig))
    return 0 if report["gate"]["overall"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
