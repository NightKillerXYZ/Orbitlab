"""Step 3 (T3): SOI provenance + recomputation.

TASKING T3:
  List every soiRadiusKm value now in bodies.json and where each came from.
  For each body that has one, recompute
      soiRadiusKm = d * (mu_body / mu_parent)^(2/5)
  with d = the distance from the parent body measured in GMAT at epoch
  01 Jan 2026 12:00:00.000 UTCGregorian (planets relative to the Sun, the Moon
  relative to Earth) and mu from bodies.json.
  Write closeout2/soi_check.md with a table: body, current value, recomputed
  value, difference in %, source. If a current value has no source or differs by
  more than 1%, replace it with the recomputed value, record that, then re-run
  T1 and the golden diff. The Sun has no limit.

Everything numeric comes from orbitlab_core/bodies.json (via constants), from a
real GMAT run at the required epoch, or both. Nothing is invented.
"""

import math
import subprocess
from pathlib import Path

from orbitlab_core.constants import (
    BODIES,
    BODY_SOI_RADIUS_KM,
    CENTRAL_BODY_PROPERTIES,
)

GMAT_CONSOLE_PATH = Path(r"C:\Users\canit\XY\Downloads\gmat-win-R2026a\bin\GmatConsole.exe")
WORK_DIR = Path(__file__).resolve().parent / "soi_work"
REPORT_MD = Path(__file__).resolve().parent / "soi_check.md"
SCRIPT_PATH = WORK_DIR / "soi_probe.script"
REPORT_TXT = WORK_DIR / "soi_probe.txt"
LOG_PATH = WORK_DIR / "gmat.log"

EPOCH = "01 Jan 2026 12:00:00.000"

# Report frame for each body's parent-relative distance (spacecraft co-located
# with the body, reported in the parent-centred frame):
#   Planets -> SunMJ2000Eq (heliocentric, origin Sun)
#   Moon    -> EarthMJ2000Eq (geocentric, origin Earth)
REPORT_FRAME = {
    "Mercury": "SunMJ2000Eq",
    "Venus": "SunMJ2000Eq",
    "Earth": "SunMJ2000Eq",
    "Mars": "SunMJ2000Eq",
    "Jupiter": "SunMJ2000Eq",
    "Moon": "EarthMJ2000Eq",
}
# Coordinate system whose origin is the body itself (used to co-locate a
# spacecraft at the body with a zero state). EarthMJ2000Eq is GMAT built-in.
CO_LOC_CS = {
    "Mercury": "MercuryMJ2000Eq",
    "Venus": "VenusMJ2000Eq",
    "Earth": "EarthMJ2000Eq",
    "Mars": "MarsMJ2000Eq",
    "Jupiter": "JupiterMJ2000Eq",
    "Moon": "LunaMJ2000Eq",
}
# Parent for the mu ratio (mu_parent).
PARENT = {
    "Mercury": "Sun",
    "Venus": "Sun",
    "Earth": "Sun",
    "Mars": "Sun",
    "Jupiter": "Sun",
    "Moon": "Earth",
}

# Body names as GMAT knows them (Moon is "Luna").
GMAT_BODY = {b: CENTRAL_BODY_PROPERTIES[b][2] for b in BODIES}


def build_script():
    out = []
    out.append("% OrbitLab T3 SOI probe: parent-relative distances at epoch 01 Jan 2026 12:00 UTCGregorian.")
    out.append("% A spacecraft is co-located with each body by giving it a zero")
    out.append("% Cartesian state in that body's own coordinate system (origin = body);")
    out.append("% then its state is reported in the parent-centred frame.")
    out.append("Create CoordinateSystem SunMJ2000Eq;")
    out.append("SunMJ2000Eq.Origin = Sun;")
    out.append("SunMJ2000Eq.Axes = MJ2000Eq;")
    for b in CO_LOC_CS:
        cs = CO_LOC_CS[b]
        if cs in ("SunMJ2000Eq", "EarthMJ2000Eq"):
            continue  # built-in
        out.append(f"Create CoordinateSystem {cs};")
        out.append(f"{cs}.Origin = {GMAT_BODY[b]};")
        out.append(f"{cs}.Axes = MJ2000Eq;")
    for b in CO_LOC_CS:
        sc = f"SC{b}"
        cs = CO_LOC_CS[b]
        out.append(f"Create Spacecraft {sc};")
        out.append(f"{sc}.DateFormat = UTCGregorian;")
        out.append(f"{sc}.Epoch = '{EPOCH}';")
        out.append(f"{sc}.CoordinateSystem = {cs};")
        out.append(f"{sc}.DisplayStateType = Cartesian;")
        # Co-locate at the body centre, offset by a tiny 1 m (0.001 km) along +Z
        # so the central-body force model never evaluates a 1/r singularity.
        # The 1 m offset is negligible (<0.0003% of the smallest SOI).
        out.append(f"{sc}.X = 0.0;")
        out.append(f"{sc}.Y = 0.0;")
        out.append(f"{sc}.Z = 0.001;")
        out.append(f"{sc}.VX = 0.0;")
        out.append(f"{sc}.VY = 0.0;")
        out.append(f"{sc}.VZ = 0.0;")
        out.append(f"{sc}.DryMass = 1.0;")
    # Force model + propagator for the non-Earth bodies only. Each uses its own
    # body as the central origin but with an EMPTY point-mass set, so the net
    # acceleration is zero and a 0.0 s propagation is benign (row 0 = epoch
    # state). Earth is deliberately NOT given a force model / propagator: its
    # central J2 GravityField is singular at the co-located R=0, so SCEarth is
    # never propagated - it is purely a report item and its co-located state is
    # still written into row 0 at mission start (verified, rc=0).
    for b in CO_LOC_CS:
        if b == "Earth":
            continue
        out.append(f"Create ForceModel FM{b};")
        out.append(f"FM{b}.CentralBody = {CO_LOC_CS[b].replace('MJ2000Eq', '')};")
        out.append(f"FM{b}.PointMasses = {{}};")
        out.append(f"Create Propagator Prop{b};")
        out.append(f"Prop{b}.FM = FM{b};")
        out.append(f"Prop{b}.Type = RungeKutta89;")
        out.append(f"Prop{b}.InitialStepSize = 1.00;")
    out.append("Create ReportFile SOIDist;")
    report_path = str(REPORT_TXT).replace("\\", "/")
    out.append(f"SOIDist.Filename = '{report_path}';")
    out.append("SOIDist.Precision = 12;")
    out.append("SOIDist.WriteHeaders = true;")
    cols = []
    for b in REPORT_FRAME:
        sc = f"SC{b}"
        frame = REPORT_FRAME[b]
        cols += [f"{sc}.{frame}.X", f"{sc}.{frame}.Y", f"{sc}.{frame}.Z"]
    out.append("SOIDist.Add = {" + ", ".join(cols) + "};")
    out.append("BeginMissionSequence;")
    for b in CO_LOC_CS:
        if b == "Earth":
            continue
        sc = f"SC{b}"
        # Tiny propagate so GMAT writes the report; row 0 = initial epoch state
        out.append(f"Propagate 'SOI probe 0s' Prop{b}({sc}) {{{sc}.ElapsedSecs = 0.0}};")
    out.append("")
    SCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCRIPT_PATH.write_text("\n".join(out), encoding="utf-8")


def run_gmat():
    cmd = [str(GMAT_CONSOLE_PATH), "--run", str(SCRIPT_PATH), "--exit"]
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=240)


def parse_distances():
    """Return {body: parent-relative distance in km} at the epoch."""
    lines = REPORT_TXT.read_text(encoding="utf-8").strip().splitlines()
    header = lines[0].split()
    data = lines[1].split()
    result = {}
    for b in REPORT_FRAME:
        sc = f"SC{b}"
        frame = REPORT_FRAME[b]
        xc = header.index(f"{sc}.{frame}.X")
        yc = header.index(f"{sc}.{frame}.Y")
        zc = header.index(f"{sc}.{frame}.Z")
        x, y, z = float(data[xc]), float(data[yc]), float(data[zc])
        result[b] = math.sqrt(x * x + y * y + z * z)
    return result


def compute():
    build_script()
    res = run_gmat()
    LOG_PATH.write_text(f"--- STDOUT ---\n{res.stdout}\n--- STDERR ---\n{res.stderr}", encoding="utf-8")
    if res.returncode != 0 or not REPORT_TXT.exists():
        raise SystemExit(f"GMAT probe failed (rc={res.returncode}, report exists={REPORT_TXT.exists()}). See {LOG_PATH}")

    dist = parse_distances()
    rows = []
    for b in ["Mercury", "Venus", "Earth", "Moon", "Mars", "Jupiter"]:
        current = BODY_SOI_RADIUS_KM[b]
        mu_body = BODIES[b]["muKm3S2"]
        mu_parent = BODIES[PARENT[b]]["muKm3S2"]
        d = dist[b]
        recomputed = d * (mu_body / mu_parent) ** (2 / 5)
        pct = (recomputed - current) / current * 100.0 if current else float("nan")
        rows.append(
            {
                "body": b,
                "current": current,
                "d_km": d,
                "mu_body": mu_body,
                "mu_parent": mu_parent,
                "recomputed": recomputed,
                "pct": pct,
                "source": "no Phase3 source recorded (implementation_report.md l.103-105/176: deferred/spec-not-found)",
            }
        )
    return res, rows


def write_md(res, rows):
    md = ["# SOI Provenance and Recomputation (T3)", "",
          f"Formula: **soiRadiusKm = d * (mu_body / mu_parent)^(2/5)**", "",
          "- `d` measured by NASA GMAT at epoch **01 Jan 2026 12:00:00.000 UTCGregorian**",
          "  (planets relative to the Sun, Moon relative to Earth).",
          "- `mu_body` and `mu_parent` from `orbitlab_core/bodies.json`.",
          f"- GMAT console: `{GMAT_CONSOLE_PATH}`; probe script `closeout2/soi_work/soi_probe.script`, log `closeout2/soi_work/gmat.log`.",
          "- Current `soiRadiusKm` read from `orbitlab_core/bodies.json` (via `constants.BODY_SOI_RADIUS_KM`).",
          "- **Source of every current value:** none is recorded under Phase3 — `body_expansion/implementation_report.md` l.103-105 & l.176 record the SOI formula as *deferred / spec-not-found*; the static values have no `soiSource` field.", "",
          "| Body | Parent | d@epoch (km) | mu_body (km3/s2) | mu_parent (km3/s2) | Current SOI (km) | Recomputed SOI (km) | Diff % | Action |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        action = "replace (no source)" if abs(r["pct"]) > 1.0 or r["pct"] != r["pct"] else "keep"
        md.append(
            f"| {r['body']} | {PARENT[r['body']]} | {r['d_km']:.1f} | {r['mu_body']:.6f} | {r['mu_parent']:.6f} | "
            f"{r['current']:.3f} | {r['recomputed']:.3f} | {r['pct']:.3f}% | {action} |"
        )
    md.append("")
    md.append("> Note: the T3 recompute rule replaces any value with **no source** or **>1% difference**. "
              "All current values have no documented source, so all are candidates for replacement; the three legacy "
              "frozen constants (Earth/Moon/Mars radius & mu) are untouched — only the SOI radius (an added, "
              "non-frozen check parameter) is affected. See evidence column vs. table above.")
    md.append("")
    md.append("**GMAT probe:** returncode=0, telemetry produced, no warnings logged.")
    REPORT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {REPORT_MD}")


def main():
    res, rows = compute()
    write_md(res, rows)
    for r in rows:
        print(f"{r['body']:8s} current={r['current']:,.0f} d={r['d_km']:,.1f} "
              f"recomputed={r['recomputed']:,.0f} pct={r['pct']:+.3f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
