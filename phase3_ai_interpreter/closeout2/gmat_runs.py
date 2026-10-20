"""Step 2 (T2): REAL GMAT runs for all 7 central bodies.

Compiles one circular orbit per body (altitude per tasking), launches NASA GMAT
Console R2026a with the same method as orbitlab_core/tests/test_gmat_execution.py,
parses the telemetry report, and compares the propagated distance-from-centre and
speed against the analytic circular orbit (radius, v = sqrt(mu/radius)) within 0.5%.

All reference values are read from orbitlab_core/bodies.json via constants; nothing
is invented.

Writes closeout2/gmat_runs.md.
"""

import math
import subprocess
import sys
from pathlib import Path

from orbitlab_core.ast.models import (
    ForceModelConfig,
    InitialOrbitConfig,
    KeplerianElements,
    OrbitLabExperiment,
    PropagationConfig,
    SpacecraftConfig,
    StopCondition,
)
from orbitlab_core.compiler.generator import GmatScriptCompiler
from orbitlab_core.constants import (
    AU_KM,
    CENTRAL_BODY_PROPERTIES,
    MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY,
)

GMAT_CONSOLE_PATH = Path(r"C:\Users\canit\XY\Downloads\gmat-win-R2026a\bin\GmatConsole.exe")
WORK_DIR = Path(__file__).resolve().parent / "gmat_work"
LOG_DIR = WORK_DIR / "logs"
REPORT_MD = Path(__file__).resolve().parent / "gmat_runs.md"

# Per-body run profile: altitude (km) above surface and stop duration.
# Sun uses a heliocentric distance of 0.5 AU directly (no "altitude" concept).
RUNS = [
    {"body": "Mercury", "altitude": 500.0, "stop_days": 1.0},
    {"body": "Venus", "altitude": 400.0, "stop_days": 1.0},
    {"body": "Earth", "altitude": 400.0, "stop_days": 1.0},
    {"body": "Moon", "altitude": 100.0, "stop_days": 1.0},
    {"body": "Mars", "altitude": 300.0, "stop_days": 1.0},
    {"body": "Jupiter", "altitude": 5000.0, "stop_days": 1.0},
    {"body": "Sun", "altitude": None, "au": 0.5, "stop_days": 10.0},
]

REF = {}  # body -> (radius_km, mu, gmat_name)
for b in ["Earth", "Moon", "Mars", "Mercury", "Venus", "Jupiter", "Sun"]:
    REF[b] = CENTRAL_BODY_PROPERTIES[b]  # (radius, mu, gmatName, coordSystem)


def expected_target(cfg, run):
    """Return (expected_radius_km, expected_speed_kms) for the circular orbit."""
    radius, mu, _gmat, _coord = REF[run["body"]]
    if run["altitude"] is not None:
        r = radius + run["altitude"]
    else:  # Sun heliocentric
        r = run["au"] * AU_KM
    v = math.sqrt(mu / r)
    return r, v


def build_experiment(cfg, run):
    body = run["body"]
    radius = REF[body][0]
    if run["altitude"] is not None:
        sma = radius + run["altitude"]
    else:
        sma = run["au"] * AU_KM  # 0.5 AU
    min_alt = MIN_PERIAPSIS_ALTITUDE_KM_BY_BODY[body]
    # Point-mass-only bodies get gravity degree 0 (they have no gravity file).
    degree = 0 if body in ("Sun", "Mercury", "Jupiter") else 4
    return OrbitLabExperiment(
        experimentName=f"GMAT_NewBody_{body}",
        centralBody=body,
        spacecraft=SpacecraftConfig(name=f"S{body[:2]}", dryMassKg=500.0),
        initialOrbit=InitialOrbitConfig(
            type="Keplerian",
            elements=KeplerianElements(
                semiMajorAxisKm=sma,
                eccentricity=0.0,
                inclinationDeg=0.0,
            ),
        ),
        forceModel=ForceModelConfig(gravityDegree=degree, gravityOrder=degree, pointMasses=[]),
        propagation=PropagationConfig(
            stopCondition=StopCondition(type="ElapsedDays", value=run["stop_days"]),
            stepSizeSecs=60.0,
        ),
    )


def parse_report(report_path, coord, sc_name):
    """Return (min_dist, max_dist, first_speed) from the telemetry report."""
    # GMAT ReportFile default delimiter is whitespace, so tokenize on any run
    # of whitespace rather than a fixed separator.
    lines = report_path.read_text(encoding="utf-8").strip().splitlines()
    header = lines[0].split()
    xcol = header.index(f"{sc_name}.{coord}.X")
    ycol = header.index(f"{sc_name}.{coord}.Y")
    zcol = header.index(f"{sc_name}.{coord}.Z")
    vxcol = header.index(f"{sc_name}.{coord}.VX")
    vycol = header.index(f"{sc_name}.{coord}.VY")
    vzcol = header.index(f"{sc_name}.{coord}.VZ")
    min_d = math.inf
    max_d = 0.0
    first_speed = None
    for raw in lines[1:]:
        vals = raw.split()
        x, y, z = float(vals[xcol]), float(vals[ycol]), float(vals[zcol])
        vx, vy, vz = float(vals[vxcol]), float(vals[vycol]), float(vals[vzcol])
        d = math.sqrt(x * x + y * y + z * z)
        s = math.sqrt(vx * vx + vy * vy + vz * vz)
        min_d = min(min_d, d)
        max_d = max(max_d, d)
        if first_speed is None:
            first_speed = s
    return min_d, max_d, first_speed


def run_gmat(script_path):
    cmd = [str(GMAT_CONSOLE_PATH), "--run", str(script_path), "--exit"]
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=240)


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    compiler = GmatScriptCompiler()
    rows = []
    for run in RUNS:
        body = run["body"]
        expected_r, expected_v = expected_target(REF, run)
        exp = build_experiment(REF, run)
        gmat_name, coord = REF[body][2], REF[body][3]
        sc_name = exp.spacecraft.name

        body_dir = WORK_DIR / body
        body_dir.mkdir(parents=True, exist_ok=True)
        script_path = body_dir / f"{body}.script"
        report_path = body_dir / f"{body}_telemetry.txt"
        log_path = LOG_DIR / f"{body}.log"

        compiler.compile_to_file(exp, output_script_path=str(script_path), telemetry_filepath=str(report_path))
        res = run_gmat(script_path)
        log_path.write_text(f"--- STDOUT ---\n{res.stdout}\n--- STDERR ---\n{res.stderr}", encoding="utf-8")

        ok = False
        notes = []
        min_d = max_d = first_speed = None
        if res.returncode != 0:
            notes.append(f"GMAT returncode={res.returncode} (non-zero)")
        if not report_path.exists():
            notes.append("no telemetry report produced")
        else:
            min_d, max_d, first_speed = parse_report(report_path, coord, sc_name)
            # Distance and speed within 0.5% of analytic circular expectation.
            d_rel = abs(max_d - expected_r) / expected_r
            v_rel = abs(first_speed - expected_v) / expected_v
            if d_rel <= 0.005 and v_rel <= 0.005:
                ok = True
            else:
                notes.append(f"distance rel err {d_rel*100:.3f}% (>0.5%); speed rel err {v_rel*100:.3f}% (>0.5%)")

        status = "PASS" if ok else "FAIL"
        rows.append(
            {
                "body": body,
                "status": status,
                "expected_r": expected_r,
                "min_d": min_d,
                "max_d": max_d,
                "expected_v": expected_v,
                "first_speed": first_speed,
                "returncode": res.returncode,
                "notes": "; ".join(notes) if notes else "ok",
            }
        )
        print(f"[{status}] {body}: max_d={None if max_d is None else round(max_d,1)} km "
              f"(exp {expected_r:.1f}), v0={None if first_speed is None else round(first_speed,5)} km/s "
              f"(exp {expected_v:.5f}) | {rows[-1]['notes']}")

    # Write markdown report.
    md = ["# GMAT Real-Run Results for the 7 Central Bodies (T2)", "",
          f"GMAT console: `{GMAT_CONSOLE_PATH}`",
          f"All reference values from `orbitlab_core/bodies.json` / `AU_KM = {AU_KM}`.",
          "PASS = returncode 0, telemetry produced, distance & speed within 0.5% of analytic circular value.", "",
          "| Body | Alts/Radius (km) | Exp R (km) | Min d (km) | Max d (km) | Exp v (km/s) | v0 (km/s) | Return | Status | Notes |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        body = r["body"]
        cfg = [x for x in RUNS if x["body"] == body][0]
        alts = f"alt {cfg['altitude']:.0f}" if cfg["altitude"] is not None else f"{cfg['au']} AU"
        md.append(
            f"| {r['body']} | {alts} | {r['expected_r']:.1f} | "
            f"{'-' if r['min_d'] is None else f'{r['min_d']:.1f}'} | "
            f"{'-' if r['max_d'] is None else f'{r['max_d']:.1f}'} | {r['expected_v']:.5f} | "
            f"{'-' if r['first_speed'] is None else f'{r['first_speed']:.5f}'} | {r['returncode']} | "
            f"{r['status']} | {r['notes']} |"
        )
    md.append("")
    passes = sum(1 for r in rows if r["status"] == "PASS")
    md.append(f"**Result: {passes}/{len(rows)} bodies PASS.**")
    md.append("")
    REPORT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"\nWrote {REPORT_MD}")
    return 0 if passes == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
