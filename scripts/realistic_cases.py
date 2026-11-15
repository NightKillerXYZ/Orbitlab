"""Realistic free-text cases through the running backend API.

Sends each prompt with POST /api/experiments {"text": ...} and polls
GET /api/experiments/{id} like the UI does (2 s interval), then writes a
results table. No keys, tokens or headers are ever sent, printed or saved;
only the plain base URL host is recorded.

Usage (server already running):
    python scripts/realistic_cases.py [--base-url URL] [--mode demo|real]
        [--timeout-s SECS] [--only 1,3,5] [--out results.md]

Exit code is non-zero only if a non-"info" case fails its expectation.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


CASES = [
    {"id": 1, "prompt": "500 kg satellite around Earth, circular orbit at 400 km altitude, 1 day",
     "expected": "success"},
    {"id": 2, "prompt": "260 kg satellite around Earth at 550 km altitude, inclination 53 degrees, 2 days",
     "expected": "success"},
    {"id": 3, "prompt": "500 kg satellite around the Moon, 100 km altitude, 6 hours",
     "expected": "success"},
    {"id": 4, "prompt": "800 kg satellite around Mars, periapsis altitude 300 km, eccentricity 0.2, 2 days",
     "expected": "success"},
    {"id": 5, "prompt": "Spacecraft around Venus, semi-major axis 9000 km, 5 orbits",
     "expected": "success"},
    {"id": 6, "prompt": "500 kg satellite around Earth in a 7000 km circular orbit, Hohmann transfer to 9000 km at periapsis, 2 days",
     "expected": "success"},
    {"id": 7, "prompt": "500 kg satellite around Earth, 500 km altitude, burn at apoapsis to 800 km, 1 day",
     "expected": "success"},
    {"id": 8, "prompt": "400 kg satellite around Mercury, circular 300 km altitude, 2 days",
     "expected": "success"},
    {"id": 9, "prompt": "Earth, 90 minutes",
     "expected": "needs_clarification"},
    {"id": 10, "prompt": "400 km circular",
     "expected": "needs_clarification"},
    {"id": 11, "prompt": "500 kg satellite around Earth, periapsis altitude 50 km, 1 day",
     "expected": "failed_at:validate"},
    {"id": 12, "prompt": "500 kg satellite around Earth, circular 400 km, 400 days",
     "expected": "info"},
    {"id": 13, "prompt": "500 kg satellite around Earth, circular 400 km, 2 days, sun-synchronous",
     "expected": "info"},
    {"id": 14, "prompt": "Spacecraft around Jupiter, 80000 km altitude circular, 3 days",
     "expected": "info"},
]


def safe_base(url: str) -> str:
    """scheme://host[:port] only — never userinfo, query, fragment or keys."""
    try:
        p = urllib.parse.urlparse(url if "://" in url else "http://" + url)
        host = (p.hostname or "").strip()
        if not host:
            return "http://127.0.0.1:8000"
        port = ":%d" % p.port if p.port else ""
        scheme = (p.scheme or "http").lower()
        if scheme not in ("http", "https"):
            scheme = "http"
        return "%s://%s%s" % (scheme, host, port)
    except Exception:
        return "http://127.0.0.1:8000"


def api_post(base_url: str, path: str, payload: dict, timeout_s: float = 30.0):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base_url.rstrip("/") + path, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_get(base_url: str, path: str, timeout_s: float = 30.0):
    req = urllib.request.Request(base_url.rstrip("/") + path, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_job(job: dict) -> dict:
    """Pull report fields out of a GET /api/experiments/{id} payload."""
    out = {"actual": None, "stage": "", "code": "",
           "explanation": "", "explanationSource": "",
           "a": None, "e": None, "duration": None}
    if not isinstance(job, dict):
        return out
    out["actual"] = job.get("status")
    if not isinstance(job, dict):
        return out
    err = job.get("error") or {}
    if isinstance(err, dict):
        out["stage"] = err.get("stage") or ""
        out["code"] = err.get("code") or ""
        det = err.get("details") or {}
        if isinstance(det, dict) and det.get("explanation"):
            out["explanation"] = str(det.get("explanation"))[:300]
        elif err.get("explanation"):
            out["explanation"] = str(err.get("explanation"))[:300]
    res = job.get("result") or {}
    if isinstance(res, dict):
        if res.get("explanationSource"):
            out["explanationSource"] = str(res.get("explanationSource"))
        exp = res.get("experiment") or {}
        if isinstance(exp, dict):
            els = ((exp.get("initialOrbit") or {}).get("elements")) or {}
            if isinstance(els, dict):
                if els.get("semiMajorAxisKm") is not None:
                    out["a"] = els.get("semiMajorAxisKm")
                if els.get("eccentricity") is not None:
                    out["e"] = els.get("eccentricity")
            stop = ((exp.get("propagation") or {}).get("stopCondition")) or {}
            if isinstance(stop, dict) and stop.get("value") is not None:
                out["duration"] = "%s %s" % (stop.get("value"), stop.get("type"))
    return out


def verdict_for(expected: str, parsed: dict) -> str:
    """Verdict for one case. 'info' expectations are always INFO."""
    if expected == "info":
        return "INFO"
    actual = parsed.get("actual")
    if expected == "success":
        return "PASS" if actual == "success" else "FAIL"
    if expected == "needs_clarification":
        return "PASS" if (actual == "failed" and parsed.get("code") == "needs_clarification") else "FAIL"
    if expected.startswith("failed_at:"):
        stage = expected.split(":", 1)[1]
        return "PASS" if (actual == "failed" and parsed.get("stage") == stage) else "FAIL"
    return "FAIL"


def compute_observations(results: list) -> dict:
    non_info = [r for r in results if r.get("expected") != "info"]
    passed = sum(1 for r in non_info if r.get("verdict") == "PASS")
    failed = [r for r in non_info if r.get("verdict") != "PASS"]
    slowest = max(results, key=lambda r: r.get("seconds") or 0.0) if results else None
    fallback = [r["id"] for r in results if r.get("explanationSource") == "fallback"]
    return {"total": len(results),
            "non_info": len(non_info), "passed": passed,
            "failed_ids": [r["id"] for r in failed],
            "slowest_id": slowest["id"] if slowest else None,
            "slowest_seconds": (slowest.get("seconds") if slowest else None),
            "fallback_ids": fallback}


def _cell(v):
    if v is None or v == "":
        return "n/a"
    return str(v)


def render_markdown(results: list, obs: dict, meta: dict) -> str:
    lines = []
    lines.append("# Realistic cases results")
    lines.append("")
    lines.append("Run: %s | mode label: %s | server mode: %s | timeout per case: %ss" % (
        meta.get("when", ""), meta.get("mode_label", ""), meta.get("server_mode", ""),
        meta.get("timeout_s", "")))
    lines.append("Base URL host recorded only (no keys, tokens or headers anywhere).")
    lines.append("")
    lines.append("| id | prompt | expected | actual | stage | code | explSrc | seconds | a | e | duration | verdict |")
    lines.append("|----|--------|----------|--------|-------|------|---------|---------|---|---|----------|---------|")
    for r in results:
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r.get("id"), (r.get("prompt") or "").replace("|", "/"),
            r.get("expected"), _cell(r.get("actual")), _cell(r.get("stage")),
            _cell(r.get("code")), _cell(r.get("explanationSource")),
            ("%.1f" % r["seconds"]) if isinstance(r.get("seconds"), (int, float)) else "n/a",
            _cell(r.get("a")), _cell(r.get("e")), _cell(r.get("duration")),
            r.get("verdict")))
    lines.append("")
    lines.append("## Observations (generated)")
    lines.append("")
    lines.append("- cases: %(total)d total, %(non_info)d non-info, %(passed)d passed; failed ids: %(failed)s" % {
        "total": obs.get("total"), "non_info": obs.get("non_info"),
        "passed": obs.get("passed"), "failed": obs.get("failed_ids") or "none"})
    lines.append("- slowest case: %s (%.1f s)" % (obs.get("slowest_id"), obs.get("slowest_seconds") or 0.0))
    if obs.get("fallback_ids"):
        lines.append("- automatic (fallback) explanations on cases: %s" % ", ".join(str(i) for i in obs["fallback_ids"]))
    else:
        lines.append("- no automatic (fallback) explanations observed.")
    lines.append("")
    return "\n".join(lines) + "\n"


def run_case(base_url: str, case: dict, timeout_s: float, poll_s: float = 2.0) -> dict:
    t0 = time.perf_counter()
    entry = {"id": case["id"], "prompt": case["prompt"], "expected": case["expected"],
             "actual": None, "stage": "", "code": "", "explanation": "",
             "explanationSource": "", "a": None, "e": None, "duration": None,
             "seconds": 0.0, "verdict": "FAIL"}
    try:
        created = api_post(base_url, "/api/experiments", {"text": case["prompt"]}, timeout_s=30.0)
        jid = (created or {}).get("id")
        if not jid:
            raise ValueError("no job id returned")
        deadline = t0 + timeout_s
        job = None
        while time.perf_counter() < deadline:
            job = api_get(base_url, "/api/experiments/%s" % jid, timeout_s=30.0)
            if isinstance(job, dict) and job.get("status") in ("success", "failed"):
                break
            time.sleep(poll_s)
        else:
            job = {"status": "timeout", "error": {"stage": "poll", "code": "timeout"}}
        if not isinstance(job, dict) or job.get("status") not in ("success", "failed"):
            job = {"status": "timeout", "error": {"stage": "poll", "code": "timeout"}}
        parsed = parse_job(job)
        entry.update(parsed)
        entry["seconds"] = round(time.perf_counter() - t0, 1)
        entry["verdict"] = verdict_for(case["expected"], parsed)
    except Exception as e:
        entry["seconds"] = round(time.perf_counter() - t0, 1)
        entry["actual"] = "error"
        entry["code"] = "harness_error"
        entry["explanation"] = "%s: %s" % (type(e).__name__, str(e)[:200])
        entry["verdict"] = "INFO" if case["expected"] == "info" else "FAIL"
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Realistic free-text cases through the backend API.")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--mode", default="demo", choices=["demo", "real"],
                    help="label only; the real mode is read from /api/health")
    ap.add_argument("--timeout-s", type=float, default=400.0)
    ap.add_argument("--only", default="", help="comma-separated case ids to run")
    ap.add_argument("--out", default="",
                    help="where to write the results table (default: phase4_backend/realistic_cases_results.md)")
    args = ap.parse_args(argv)

    only = set()
    if args.only:
        for bit in str(args.only).split(","):
            bit = bit.strip()
            if bit:
                try:
                    only.add(int(bit))
                except ValueError:
                    print("ignoring bad --only value: %s" % bit)

    base = safe_base(args.base_url)
    try:
        health = api_get(base, "/api/health", timeout_s=10.0)
        server_mode = (health or {}).get("mode", "live") if isinstance(health, dict) else "live"
    except Exception as e:
        server_mode = "unknown"
        print("warning: /api/health unreachable (%s: %s)" % (type(e).__name__, str(e)[:120]))
    print("mode label: %s; server mode: %s" % (args.mode, server_mode))

    cases = [c for c in CASES if not only or c["id"] in only]
    results = []
    for c in cases:
        entry = run_case(base, c, args.timeout_s)
        results.append(entry)
        print("[%s] #%d %s (%.1fs) stage=%s code=%s" % (
            entry["verdict"], entry["id"], entry["prompt"][:60], entry["seconds"],
            entry["stage"] or "-", entry["code"] or "-"))

    obs = compute_observations(results)
    meta = {"when": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "mode_label": args.mode, "server_mode": server_mode,
            "timeout_s": args.timeout_s}
    text = render_markdown(results, obs, meta)
    import pathlib
    out = args.out or str(pathlib.Path(__file__).resolve().parent.parent
                          / "phase4_backend" / "realistic_cases_results.md")
    pathlib.Path(out).write_text(text, encoding="utf-8")
    print("wrote %s" % out)
    print("counts: %d total, %d non-info, %d passed, failed=%s" % (
        obs["total"], obs["non_info"], obs["passed"], obs["failed_ids"] or "none"))
    if obs["failed_ids"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
