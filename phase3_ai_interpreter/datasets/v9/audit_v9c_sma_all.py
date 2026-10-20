"""Extended semi-major-axis (SMA) audit for all 4,300 v9b master rows.

Task T5 (close-out part 2): datasets\\v9\\audit_v9c_sma.py audits the SMA the
prompt specifies against the SMA in the reference answer for 2,589 rows and
reports 1,711 rows as N/A ("not auditable -> report only").  This NEW script
extends the coverage: it applies the original derivation unchanged (so the
rows it already handles keep identical results) and then, for the rows the
original left N/A, applies a broader, keyword-anchored parser that recovers
the SMA from the *row's own* stated values combined with the body radius R
from orbitlab_core/bodies.json.

The prompt can specify the orbit in several recoverable forms:

  * a direct SMA ("a 9900 km", "semimajor axis 7073 km", "7000 km, e=0.004")
                                                              -> a = SMA
  * a periapsis altitude + eccentricity  (incl. "periapsis sits X km up",
    "perigee/periapsis X km", "periapsis altitude of X km")    -> a=(R+rp)/(1-e)
  * an apoapsis altitude + eccentricity                        -> a=(R+ra)/(1+e)
  * "above the surface" / lowest/nearest point + eccentricity  -> a=(R+h)/(1-e)
  * a circular altitude (incl. "circular orbit at X km",
    "X km high", "circular X km alt")                          -> a=R+alt

Eccentricity itself is recovered from many spellings ("eccentricity X",
"eccentricity is/reads X", "0.15 (eccentricity)", "e X", "X e").

Rows whose prompt still carries no recoverable SMA (notably the
full-Cartesian-state rows, where the SMA appears only in the reference
answer and never in the request) remain N/A and are reported by count only,
exactly as in the original audit.

Output: datasets\\v9\\audit_v9c_sma_all.json   (the existing audit files are
left untouched).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

# Load the original audit as a plain module so we can reuse its derivation
# (identical on the 2,589 rows it already handles), plus RADIUS / tolerance /
# helpers.  The module's own `main()` is guarded, so importing is side-effect
# free.  sys.path insert mirrors the original so orbitlab_core resolves.
sys.path.insert(0, str(HERE.parents[2]))  # feature-physics-core on sys.path
_spec = importlib.util.spec_from_file_location("_audit_v9c", HERE / "audit_v9c_sma.py")
aud = importlib.util.module_from_spec(_spec)
sys.argv = ["audit_v9c_sma.py"]
_spec.loader.exec_module(aud)

RADIUS = aud.RADIUS
TOLERANCE_KM = aud.TOLERANCE_KM
MASTER = aud.MASTER
OUT_REPORT = HERE / "audit_v9c_sma_all.json"

_num = aud._num
_first_num = aud._first_num


# ---------------------------------------------------------------------------
# Extended, keyword-anchored patterns (only applied to rows the original N/A'd)
# ---------------------------------------------------------------------------

SMA_PATS_ALL = (
    r"with\s+SMA\s+([\d.]+)\s*km",
    r"SMA\s+([\d.]+)\s*km",
    r"semi[- ]?major\s+axis\s+(?:of\s+)?([\d.]+)\s*km",        # incl. "semimajor"
    r"(?:at\s+)?a\s*=\s*([\d.]+)\s*km",
    r"(?:^|[^=a-zA-Z])([\d.]+)\s*km\s+SMA",
    r"(?:^|[^=a-zA-Z])([\d.]+)\s*km\s+semi[- ]?major",
    r"elements\s*\[\s*([\d.]+)\s*km",
    r"(?:^|[^a-zA-Z=])a\s+([\d.]+)\s*km\b(?!\s+target\b)(?=[\s,;.)]|$)",      # "a 9900 km" (not "a X km target")
)

PERI_PATS = (
    r"periapsis\s+altitude\s+(?:above\s+the\s+surface\s+)?(?:is|of|:|=)?\s*([\d.]+)\s*km",
    r"periapsis\s+altitude\s+(?:sits|is at|is)\s+([\d.]+)\s*km\s+above\b",
    r"periapsis\s+(?:is|of|:|=)?\s*([\d.]+)\s*km\b",
    r"periapsis\s+sits\s+([\d.]+)\s*km",
    r"periapsis\s+([\d.]+)\s*km\s+(?:above|high|up)",
    r"perigee\s+altitude\s+(?:is|of|:|=)?\s*([\d.]+)\s*km",
    r"perigee\s+height\s+(?:is|of|:|=)?\s*([\d.]+)\s*km",
    r"perigee\s+(?:is|of|:|=)?\s*([\d.]+)\s*km\b",
    r"perigee\s*/\s*periapsis\s*(?:is|of)?\s*([\d.]+)\s*km",
    r"periapsis\s*/\s*perigee\s*(?:is|of)?\s*([\d.]+)\s*km",
    r"(?:starting from|with)\s+a\s+periapsis\s+altitude\s+of\s*([\d.]+)\s*km",
    r"pericenter\s+altitude\s+(?:is|of|:|=)?\s*([\d.]+)\s*km",
    r"perigee/periapsis\s+([\d.]+)\s*km",
    r"periapsis/perigee\s+([\d.]+)\s*km",
)

APO_PATS = (
    r"apoapsis\s+altitude\s+(?:is|of|:|=)?\s*([\d.]+)\s*km",
    r"apoapsis\s+(?:is|of|:|=)?\s*([\d.]+)\s*km\b",
    r"apoapsis\s+sits\s+([\d.]+)\s*km",
    r"apoapsis\s+([\d.]+)\s*km\s+(?:above|high)",
    r"apogee\s+altitude\s+(?:is|of|:|=)?\s*([\d.]+)\s*km",
    r"apogee\s+(?:is|of|:|=)?\s*([\d.]+)\s*km\b",
)

ABOVE_PATS = (
    r"lowest point above the surface\s+(?:is|sits)?\s*([\d.]+)\s*km",
    r"nearest point above the surface\s+(?:is|sits)?\s*([\d.]+)\s*km",
    r"(?:nearest point|lowest point|lowest-altitude point|lowest altitude)\s+(?:is|sits)?\s*([\d.]+)\s*km\s+above\b",
    r"sits\s+([\d.]+)\s*km\s+above\s+(?:the\s+)?(?:surface|ground)",
    r"([\d.]+)\s*km\s+above\s+(?:the\s+)?(?:surface|ground)",
    r"(?:above the surface|above the ground)\s+at\s+periapsis\s+is\s+([\d.]+)\s*km",
    r"(?:perigee|periapsis|pericenter|nearest point)\s+(?:is|sits)\s*([\d.]+)\s*km\s+above",
)

ECC_PATS = (
    r"eccentricit\w*\s+(?:is|reads|is read as|is given as|of|:|=)?\s*([\d.]+)",
    r"([\d.]+)\s*\(\s*eccentricity\s*\)",
    r"eccentricity\s*=\s*([\d.]+)",
    r"(?:^|[\s,;])e\s*=\s*([\d.]+)",
    r"(?:^|[\s,;])e\s+([\d.]+)(?=\s|,|;|$|\))",
    r"([\d.]+)\s*e\b(?![\w.])(?=[\s,;)]|$)",
)

CIRC_PATS = (
    r"circular\s+([\d.]+)\s*km\s+(?:alt|altitude|orbit|high)",
    r"circular\s+orbit\s+(?:at|of)?\s*([\d.]+)\s*km\s+altitude",
    r"(?:at|of)\s+([\d.]+)\s*km\s+altitude\b",
    r"altitude\s+(?:of\s+)?([\d.]+)\s*km\b",
    r"([\d.]+)\s*km\s+(?:alt|altitude)\b",
    r"([\d.]+)\s*km\s+high\b",
)


def _ecc_all(prompt: str) -> float | None:
    for p in ECC_PATS:
        v = _num(p, prompt)
        if v is not None and 0.0 <= v < 1.0:
            return v
    return None


def _status(expected: float, actual_sma: float) -> str:
    return "pass" if abs(expected - actual_sma) <= TOLERANCE_KM else "fail"


def derive_expected_all(
    prompt: str, body: str, actual_sma: float, actual_e: float
) -> tuple[str, float | None, str]:
    """Return (category, expected_sma_or_None, status) using the original
    derivation first, then the extended recovery for rows the original N/A'd.

    status: "pass" | "fail" | "na".
    """
    cat, exp, status = aud.derive_expected(prompt, body, actual_sma, actual_e)
    if status != "na":
        return cat, exp, status

    radius = RADIUS[body]
    circular = bool(re.search(r"circular", prompt, re.I)) or bool(
        re.search(r"zero eccentricity", prompt, re.I)
    )
    cartesian = bool(re.search(r"position\s*\[", prompt, re.I))
    v9adda = bool(re.match(r"^[Ss]et up an orbit for the (Moon|Mars) named V9AddA", prompt))

    if cartesian:
        return "cartesian", None, "na"  # SMA only in the answer, not the request

    ecc = _ecc_all(prompt)
    if circular and ecc is None:
        ecc = 0.0

    sma = None if v9adda else _first_num(SMA_PATS_ALL, prompt)
    if sma is not None:
        if ecc is not None:
            return "direct-sma", float(sma), _status(float(sma), actual_sma)
        return "direct-sma-ecc-not-stated", None, "na"

    apo = _first_num(APO_PATS, prompt)
    if apo is not None:
        if ecc is not None:
            return "apoapsis", (radius + apo) / (1 + ecc), _status((radius + apo) / (1 + ecc), actual_sma)
        return "apoapsis-ecc-not-stated", None, "na"

    peri = _first_num(PERI_PATS, prompt)
    if peri is not None:
        if ecc is not None:
            return "periapsis", (radius + peri) / (1 - ecc), _status((radius + peri) / (1 - ecc), actual_sma)
        return "periapsis-ecc-not-stated", None, "na"

    above = _first_num(ABOVE_PATS, prompt)
    if above is not None:
        if ecc is not None:
            return "periapsis", (radius + above) / (1 - ecc), _status((radius + above) / (1 - ecc), actual_sma)
        return "above-ecc-not-stated", None, "na"

    if circular:
        alt = _first_num(CIRC_PATS, prompt)
        if alt is not None:
            return "circular-alt", radius + alt, _status(radius + alt, actual_sma)
        return "circular-other", None, "na"

    return "not-derivable", None, "na"


def main() -> int:
    rows = aud._load(MASTER)
    if len(rows) != 4300:
        raise ValueError(f"expected 4300 master rows, got {len(rows)}")

    counts: dict[str, dict[str, int]] = {}
    failures: list[dict[str, Any]] = []
    passed_rows = 0
    for index, row in enumerate(rows):
        prompt = row["contents"][0]["parts"][0]["text"]
        exp = json.loads(row["contents"][1]["parts"][0]["text"])
        body = exp.get("centralBody")
        if body not in RADIUS:
            raise ValueError(f"row {index + 1}: unknown centralBody {body!r}")
        st = exp.get("initialOrbit", {}).get("type")
        if st != "Keplerian":
            category = f"output-{st}"
            counts.setdefault(category, {"rows": 0, "pass": 0, "fail": 0, "na": 0})
            counts[category]["rows"] += 1
            counts[category]["na"] += 1
            continue
        actual_sma = exp["initialOrbit"]["elements"]["semiMajorAxisKm"]
        actual_e = exp["initialOrbit"]["elements"]["eccentricity"]
        category, expected, status = derive_expected_all(prompt, body, actual_sma, actual_e)

        counts.setdefault(category, {"rows": 0, "pass": 0, "fail": 0, "na": 0})
        counts[category]["rows"] += 1
        counts[category][status] += 1
        if status == "fail":
            failures.append(
                {
                    "line": index + 1,
                    "experimentName": exp.get("experimentName"),
                    "body": body,
                    "expected_sma_km": expected,
                    "actual_sma_km": actual_sma,
                    "diff_km": abs(expected - actual_sma),
                    "prompt": prompt[:200],
                }
            )
        elif status == "pass":
            passed_rows += 1

    total_rows = sum(v["rows"] for v in counts.values())
    total_pass = sum(v["pass"] for v in counts.values())
    total_fail = sum(v["fail"] for v in counts.values())
    total_na = sum(v["na"] for v in counts.values())

    report = {
        "file": str(MASTER),
        "rows_total": total_rows,
        "tolerance_km": TOLERANCE_KM,
        "radii_km": RADIUS,
        "extended_from": "audit_v9c_sma.py",
        "audited_pass": total_pass,
        "audited_fail": total_fail,
        "not_auditable_report_only": total_na,
        "categories": counts,
        "failures": failures,
    }
    OUT_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, indent=2))
    print("failure_count:", total_fail)
    if total_fail:
        print("FAILURES:", json.dumps(failures, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
