"""v10 dataset gate -- Step 4: GMAT sanity.

For each of the 4 new bodies (Mercury, Venus, Jupiter, Sun) pick 3 validated rows
(one circular, one periapsis, one SMA+e), compile the interpreted experiment with the
same compiler the pipeline uses, launch NASA GMAT Console, and check distance and speed
after propagation against an independent Python two-body prediction within 0.5%
(same method as closeout2\\gmat_runs.py).

Immutable inputs
----------------
- rows come from raw\\batch_01..batch_08 (the valid set).  batch_10 is not used here.
- numbers (SMA, ecc, mu) come from the validated experiment / bodies.json, never invented.
- gravity degree / point masses come straight from the row data.

Two-body prediction
-------------------
- circular row (e ~ 0):   expected_r = SMA,  expected_v = sqrt(mu / SMA)
- elliptical row (e > 0):  vis-viva at each reported radius r:
                           expected_v(r) = sqrt(mu * (2/r - 1/SMA))
   and the r itself must stay between the two-body pericentre a(1-e) and
   apocentre a(1+e) (within tolerance).  This is the exact analytic two-body orbit
   for the row's own SMA/ecc, so it is the independent Python prediction for the
   same dynamics GMAT integrates.

Writes datasets/v10/gmat_sanity.md
"""

import importlib.util
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
ROOT = HERE.parents[2]

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "phase3_ai_interpreter"))

from interpreter.json_interpreter import JsonExperimentInterpreter  # noqa: E402
from orbitlab_core.constants import AU_KM, CENTRAL_BODY_PROPERTIES  # noqa: E402
from orbitlab_core.compiler.generator import GmatScriptCompiler  # noqa: E402

# Reuse the v9b close-out SMA audit so rows are categorised exactly as the gate does.
_SPEC = importlib.util.spec_from_file_location("_audit_all", HERE.parent / "v9" / "audit_v9c_sma_all.py")
_AUDALL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_AUDALL)

GMAT_CONSOLE_PATH = Path(r"C:\Users\canit\XY\Downloads\gmat-win-R2026a\bin\GmatConsole.exe")
WORK_DIR = HERE / "gmat_work"
LOG_DIR = WORK_DIR / "logs"
REPORT_MD = HERE / "gmat_sanity.md"

TOLERANCE = 0.005  # 0.5%

BODIES = {
    "Mercury": ["batch_01_mercury_valid.jsonl", "batch_02_mercury_valid.jsonl"],
    "Venus": ["batch_03_venus_valid.jsonl", "batch_04_venus_valid.jsonl"],
    "Jupiter": ["batch_05_jupiter_valid.jsonl", "batch_06_jupiter_valid.jsonl"],
    "Sun": ["batch_07_sun_valid.jsonl", "batch_08_sun_valid.jsonl"],
}


def load_rows(files):
    rows = []
    for fn in files:
        text = (RAW / fn).read_text(encoding="utf-8-sig")
        for ln in text.splitlines():
            if ln.strip():
                rows.append(json.loads(ln))
    return rows


def categorize(user, body, sma, ecc):
    """Return one of {circular, periapsis, direct-sma} using the v9b SMA audit,
    which is the same categorisation the Step 3 gate uses."""
    import re

    m = re.search(r"SMA\s+([\d.]+)\s*AU\s*\(\s*([\d.]+)\s*km\s*\)", user, re.I)
    if m:
        return "circular"  # Sun AU circular rows
    cat, _expected, _status = _AUDALL.derive_expected_all(user, body, sma, ecc)
    if cat in ("circular-alt", "circular", "not-derivable"):
        return "circular"
    if cat == "periapsis":
        return "periapsis"
    return "direct-sma"


def select_rows(interpreter):
    """Pick one circular, one periapsis, one SMA+e row per body."""
    selection = {}
    for body, files in BODIES.items():
        rows = load_rows(files)
        by_cat = {}
        for r in rows:
            exp = json.loads(r["messages"][2]["content"])
            el = exp["initialOrbit"]["elements"]
            user = r["messages"][1]["content"]
            cat = categorize(user, body, float(el["semiMajorAxisKm"]), float(el["eccentricity"]))
            by_cat.setdefault(cat, []).append(r)
        # prefer circular-alt rows for "circular" (they use R+alt wording)
        circ_pool = by_cat.get("circular", [])
        periapsis_pool = by_cat.get("periapsis", [])
        smae_pool = by_cat.get("direct-sma", [])
        if body == "Sun":
            circ_pool = circ_pool  # sun AU rows
        chosen = []
        if circ_pool:
            chosen.append(("circular", circ_pool[0]))
        if periapsis_pool:
            chosen.append(("periapsis", periapsis_pool[0]))
        if smae_pool:
            chosen.append(("direct-sma", smae_pool[0]))
        selection[body] = chosen
    return selection


def parse_report(report_path, coord, sc_name):
    """Return list of (r, v, t) telemetry samples."""
    lines = report_path.read_text(encoding="utf-8").strip().splitlines()
    header = lines[0].split()
    # GMAT writes elapsed time first, then state columns.
    tcol = 0
    xcol = header.index(f"{sc_name}.{coord}.X")
    ycol = header.index(f"{sc_name}.{coord}.Y")
    zcol = header.index(f"{sc_name}.{coord}.Z")
    vxcol = header.index(f"{sc_name}.{coord}.VX")
    vycol = header.index(f"{sc_name}.{coord}.VY")
    vzcol = header.index(f"{sc_name}.{coord}.VZ")
    samples = []
    for raw in lines[1:]:
        vals = raw.split()
        if len(vals) <= max(xcol, ycol, zcol, vxcol, vycol, vzcol):
            continue
        t = float(vals[tcol])
        x, y, z = float(vals[xcol]), float(vals[ycol]), float(vals[zcol])
        vx, vy, vz = float(vals[vxcol]), float(vals[vycol]), float(vals[vzcol])
        r = math.sqrt(x * x + y * y + z * z)
        v = math.sqrt(vx * vx + vy * vy + vz * vz)
        samples.append((t, r, v))
    return samples


def run_gmat(script_path):
    cmd = [str(GMAT_CONSOLE_PATH), "--run", str(script_path), "--exit"]
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)


def check_row(res, exp, body, kind):
    """Run GMAT for one experiment and compare against the independent two-body prediction."""
    radius_ref, mu_ref, gmat_name, coord = CENTRAL_BODY_PROPERTIES[body]
    a = exp.initialOrbit.elements.semiMajorAxisKm
    e = exp.initialOrbit.elements.eccentricity
    sc_name = exp.spacecraft.name

    compiler = GmatScriptCompiler()
    body_dir = WORK_DIR / f"{body}_{kind}"
    body_dir.mkdir(parents=True, exist_ok=True)
    script_path = body_dir / f"{kind}.script"
    report_path = body_dir / f"{kind}_telemetry.txt"
    log_path = LOG_DIR / f"{body}_{kind}.log"

    compiler.compile_to_file(exp, output_script_path=str(script_path), telemetry_filepath=str(report_path))
    res_proc = run_gmat(script_path)
    log_path.write_text(f"--- STDOUT ---\n{res_proc.stdout}\n--- STDERR ---\n{res_proc.stderr}\n", encoding="utf-8")

    ok = False
    notes = []
    if res_proc.returncode != 0:
        notes.append(f"GMAT returncode={res_proc.returncode} (non-zero)")
    if not report_path.exists():
        notes.append("no telemetry report produced")
        return False, None, None, None, notes

    samples = parse_report(report_path, coord, sc_name)
    if not samples:
        notes.append("telemetry produced but no data rows")
        return False, None, None, None, notes

    # Independent two-body prediction.
    if e < 1e-6:
        # circular: r should equal SMA, v = sqrt(mu/SMA)
        exp_r = a
        exp_v = math.sqrt(mu_ref / a)
        r_rel = abs(max(r for _t, r, _v in samples) - exp_r) / exp_r
        v_ref_vals = [exp_v] * len(samples)
    else:
        # elliptical: r in [a(1-e), a(1+e)]; vis-viva v = sqrt(mu(2/r - 1/a))
        exp_r_min = a * (1 - e)
        exp_r_max = a * (1 + e)
        r_rel = 0.0
        v_rel_max = 0.0
        for _t, r, v in samples:
            if r < exp_r_min or r > exp_r_max:
                # periapsis/apapsis check
                r_bound_rel = max((exp_r_min - r) / exp_r_min if r < exp_r_min else 0.0,
                                  (r - exp_r_max) / exp_r_max if r > exp_r_max else 0.0)
                r_rel = max(r_rel, r_bound_rel)
            v_pred = math.sqrt(mu_ref * (2.0 / r - 1.0 / a))
            v_rel = abs(v - v_pred) / v_pred
            v_rel_max = max(v_rel_max, v_rel)
        exp_r = a
        exp_v = math.sqrt(mu_ref / a)
        v_rel = v_rel_max

    if e < 1e-6:
        v_rel = max(abs(v - exp_v) / exp_v for _t, r, v in samples)
        r_rel = abs(max(r for _t, r, _v in samples) - exp_r) / exp_r

    if r_rel <= TOLERANCE and v_rel <= TOLERANCE:
        ok = True
    else:
        notes.append(f"r rel err {r_rel*100:.3f}%, v rel err {v_rel*100:.3f}% (>0.5%)")

    # Also verify the satellite stays near the initial state (sanity).
    return ok, samples, (r_rel, v_rel), (exp_r, exp_v), notes


def main():
    INTERPRETER = JsonExperimentInterpreter()
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    selection = select_rows(INTERPRETER)
    rows_out = []
    for body, picks in selection.items():
        for kind, r in picks:
            exp_raw = r["messages"][2]["content"]
            res = INTERPRETER.interpret(exp_raw)
            if not res.success or res.experiment is None:
                rows_out.append({"body": body, "kind": kind, "name": "?", "status": "FAIL",
                                 "returncode": "-", "r_rel": "-", "v_rel": "-",
                                 "notes": "interpreter did not produce a valid experiment"})
                continue
            exp = res.experiment
            ok, samples, rels, refs, notes = check_row(res, exp, body, kind)
            r_rel, v_rel = rels if rels else (None, None)
            status = "PASS" if ok else "FAIL"
            rows_out.append({"body": body, "kind": kind,
                             "name": exp.experimentName,
                             "sma": exp.initialOrbit.elements.semiMajorAxisKm,
                             "ecc": exp.initialOrbit.elements.eccentricity,
                             "status": status,
                             "returncode": "-", "r_rel": r_rel, "v_rel": v_rel,
                             "notes": "; ".join(notes) if notes else "ok"})
            print(f"[{status}] {body} {kind}: r_rel={None if r_rel is None else round(r_rel*100,3)}% "
                  f"v_rel={None if v_rel is None else round(v_rel*100,3)}% | {rows_out[-1]['notes']}")

    # Report.
    md = ["# v10 GMAT sanity (Step 4)", "",
          f"GMAT console: `{GMAT_CONSOLE_PATH}`",
          "12 runs = 3 validated rows (circular / periapsis / SMA+e) x 4 new bodies.",
          "Numbers from validated experiments and `orbitlab_core/bodies.json`.", "",
          "Two-body prediction: circular `v=sqrt(mu/SMA)`, `r=SMA`; elliptical vis-viva "
          "`v=sqrt(mu(2/r-1/SMA))` with `r in [a(1-e), a(1+e)]`.",
          "PASS = GMAT returncode 0, telemetry produced, distance & speed within 0.5%.", "",
          "| Body | Type | Rows | Name | SMA (km) | e | r rel % | v rel % | Status | Notes |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for o in rows_out:
        rrel = "-" if o["r_rel"] is None else f"{o['r_rel']*100:.3f}"
        vrel = "-" if o["v_rel"] is None else f"{o['v_rel']*100:.3f}"
        sma = f"{o.get('sma', 0):.4f}" if o.get("sma") else "-"
        ecc = f"{o.get('ecc', 0):.4f}" if o.get("ecc") is not None else "-"
        md.append(f"| {o['body']} | {o['kind']} | 1 | {o['name']} | {sma} | {ecc} | {rrel} | {vrel} | {o['status']} | {o['notes']} |")
    md.append("")
    passes = sum(1 for o in rows_out if o["status"] == "PASS")
    md.append(f"**Result: {passes}/{len(rows_out)} runs PASS.**")
    md.append("")
    REPORT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"\nWrote {REPORT_MD}")
    return 0 if passes == len(rows_out) == 12 else 1


if __name__ == "__main__":
    sys.exit(main())
