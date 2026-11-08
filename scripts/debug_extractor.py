"""Debug the real extractor endpoint: raw reply, parsed fields, final result.

Reads EXTRACTOR_BASE_URL, EXTRACTOR_API_KEY, EXTRACTOR_MODEL from the
environment only (never prints them; missing => print the NAME and exit 2).
First call uses a 300 s timeout (cold start), later calls 60 s.
Saves extractor_debug.json with no secrets.

PowerShell:
  $env:EXTRACTOR_BASE_URL='<host-root>'; $env:EXTRACTOR_API_KEY='<key>'; $env:EXTRACTOR_MODEL='<model>'
  $env:PYTHONPATH='phase4_backend'; python scripts/debug_extractor.py [--out extractor_debug.json]

Bash:
  export EXTRACTOR_BASE_URL='<host-root>' EXTRACTOR_API_KEY='<key>' EXTRACTOR_MODEL='<model>'
  PYTHONPATH=phase4_backend python scripts/debug_extractor.py [--out extractor_debug.json]
"""
import argparse
import asyncio
import json
import os
import sys
import time

SENTENCES = [
    "Put a 500 kg satellite in a circular orbit at 400 km altitude around Earth for 1 day.",
    "Create a 1200 kg spacecraft around Mars with periapsis altitude 300 km and eccentricity 0.2 for 3 days.",
    "A 800 kg probe around Venus, semi-major axis 9000 km, eccentricity 0.05, inclination 30 degrees, for 5 orbits.",
    "Simulate a 300 kg satellite at 150 km altitude above the Earth with 4 degrees inclination for 12 hours.",
    "Moon orbit, 100 km altitude, 500 kg, 6 hours.",
    "500 kg satellite around Earth in a 7000 km circular orbit, Hohmann transfer to 9000 km at periapsis, 2 days.",
]

REQUIRED = ("EXTRACTOR_BASE_URL", "EXTRACTOR_API_KEY", "EXTRACTOR_MODEL")


def _summarize_sent(sent):
    if not sent:
        return None
    return {
        "body": sent.get("centralBody"),
        "semiMajorAxisKm": sent.get("semiMajorAxisKm"),
        "eccentricity": sent.get("eccentricity"),
        "inclinationDeg": sent.get("inclinationDeg"),
        "duration": [sent.get("stopConditionType"), sent.get("durationValue"), sent.get("durationUnit")],
    }


async def run_one(text, client, timeout_s):
    """Run one sentence through the SAME path as the pipeline: process()."""
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor

    t0 = time.perf_counter()
    entry = {"sentence": text}
    ext = FrontStepExtractor(extractor_client=client)
    try:
        res = await asyncio.wait_for(ext.process(text), timeout=timeout_s + 30)
    except Exception as e:
        entry.update({"verdict": "ERROR", "stage": "extract", "code": "extractor_error",
                      "error": "%s: %s" % (type(e).__name__, str(e)[:200]),
                      "raw_reply_first_600": getattr(client, "last_raw", None),
                      "parsed_fields": getattr(client, "last_parsed", None),
                      "elapsed_s": round(time.perf_counter() - t0, 1)})
        return entry
    entry["raw_reply_first_600"] = (getattr(client, "last_raw", "") or "")[:600]
    entry["parsed_fields"] = getattr(client, "last_parsed", None)
    if res.status == "needs_clarification":
        entry.update({"verdict": "FAIL", "missing": res.missing,
                      "sent": None, "converter": None,
                      "elapsed_s": round(time.perf_counter() - t0, 1)})
    else:
        entry.update({"verdict": "OK", "sent": _summarize_sent(res.data),
                      "converter": _summarize_sent(res.data),
                      "elapsed_s": round(time.perf_counter() - t0, 1)})
    return entry


async def amain(out_path):
    from orbitlab_backend.clients.extractor_client import OpenAIExtractor

    results = []
    for i, text in enumerate(SENTENCES):
        timeout = 300.0 if i == 0 else 60.0
        client = OpenAIExtractor(timeout_s=timeout)
        print("=" * 70)
        print("SENTENCE: %s" % text)
        entry = await run_one(text, client, timeout)
        results.append(entry)
        print("RAW (first 600 chars): %s" % (entry.get("raw_reply_first_600") or entry.get("error", "") or "")[:600])
        print("PARSED FIELDS: %s" % json.dumps(entry.get("parsed_fields"))[:600])
        if entry.get("verdict") == "OK":
            c = entry.get("converter") or {}
            print("FINAL: ok a=%s e=%s inc=%s duration=%s elapsed=%.1fs" % (c.get("semiMajorAxisKm"), c.get("eccentricity"), c.get("inclinationDeg"), c.get("duration"), entry.get("elapsed_s")))
        elif "missing" in entry:
            print("FINAL: needs_clarification missing=%s elapsed=%.1fs" % (entry["missing"], entry.get("elapsed_s")))
        else:
            print("FINAL: %s %s elapsed=%.1fs" % (entry.get("verdict"), entry.get("error"), entry.get("elapsed_s")))
    ok = sum(1 for r in results if r.get("verdict") == "OK")
    print("=" * 70)
    print("summary: %d OK, %d not-OK out of %d (timeouts: first 300 s, rest 60 s)" % (ok, len(results) - ok, len(results)))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, indent=1)
    print("saved %s (no secrets in it)" % out_path)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Debug the real extractor endpoint (no secrets printed or saved).")
    parser.add_argument("--out", default="extractor_debug.json")
    args = parser.parse_args(argv)
    missing = [n for n in REQUIRED if not os.environ.get(n)]
    if missing:
        for n in missing:
            print("Missing %s" % n)
        return 2
    try:
        return asyncio.run(amain(args.out))
    except KeyboardInterrupt:
        print("interrupted")
        return 1


if __name__ == "__main__":
    sys.exit(main())
