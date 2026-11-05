"""First real-model smoke: front step -> interpreter -> verify -> validate.

No compile, no GMAT. Reads ORBITLAB_MODEL_URL, ORBITLAB_MODEL_KEY and
ORBITLAB_MODEL_TIMEOUT_S from the process environment only. Secret values
are never printed, logged or saved.

Usage (PowerShell first, then bash):
    $env:ORBITLAB_MODEL_URL='<base-url>'; $env:ORBITLAB_MODEL_KEY='<key>'
    python scripts/smoke_real_model.py [--out smoke_results.json]

    export ORBITLAB_MODEL_URL='<base-url>' ORBITLAB_MODEL_KEY='<key>'
    python scripts/smoke_real_model.py [--out smoke_results.json]
"""

import argparse
import asyncio
import json
import os
import sys
import time

PROMPTS = [
    "500 kg satellite, circular orbit at 400 km altitude around Earth, 1 day",
    "1200 kg spacecraft around Mars, periapsis altitude 300 km, eccentricity 0.2, 3 days",
    "a Hohmann transfer from a 7000 km circular Earth orbit to 9000 km, 2 days",
    "a Cartesian start around the Moon with position 2000 0 0 km and velocity 0 1.2 0 km/s, 6 hours",
    "800 kg satellite around Venus, semi-major axis 9000 km, eccentricity 0.05, inclination 30 degrees, 5 orbit periods",
    "300 kg satellite around Earth at 150 km altitude with 4 degree inclination for 12 hours",
]

REQUIRED_VARS = ("ORBITLAB_MODEL_URL", "ORBITLAB_MODEL_KEY")


def missing_vars():
    return [name for name in REQUIRED_VARS if not os.environ.get(name)]


def _summarize_sent(sent):
    return {
        "body": sent.get("centralBody"),
        "semiMajorAxisKm": sent.get("semiMajorAxisKm"),
        "stop": [sent.get("stopConditionType"), sent.get("durationValue"), sent.get("durationUnit")],
    }


async def run_one(prompt, client, explainer_note="explainer not called in smoke"):
    from orbitlab_backend.frontstep.extractor import FrontStepExtractor
    from orbitlab_backend.frontstep.verify import verify_experiment, apply_frontstep_names
    from orbitlab_core.ast.models import OrbitLabExperiment
    from orbitlab_core.ast.validation import AstrodynamicValidator

    t0 = time.perf_counter()
    try:
        extractor = FrontStepExtractor()
        if hasattr(extractor, "process"):
            res = await extractor.process(prompt)
        else:
            res = extractor.process_sync(prompt)
        if res.status == "needs_clarification":
            return {
                "prompt": prompt,
                "verdict": "FAIL",
                "stage": "extract",
                "code": "needs_clarification",
                "error": "Missing required fields: %s" % (res.missing,),
                "elapsed_s": round(time.perf_counter() - t0, 1),
                "sent": None,
                "warnings": [],
            }
        sent, canon_prompt = res.data, res.prompt
        try:
            returned = await client.interpret_prompt(canon_prompt)
        except Exception as e:
            code = "interpreter_unavailable" if ("timeout" in str(e).lower() or "503" in str(e) or "502" in str(e) or "504" in str(e)) else "interpreter_error"
            return {
                "prompt": prompt,
                "verdict": "FAIL",
                "stage": "interpret",
                "code": code,
                "error": "%s: %s" % (type(e).__name__, str(e)[:300]),
                "elapsed_s": round(time.perf_counter() - t0, 1),
                "sent": _summarize_sent(sent),
                "warnings": [],
            }
        returned, _ = apply_frontstep_names(sent, returned)
        mismatches = verify_experiment(sent, returned)
        if mismatches:
            return {
                "prompt": prompt,
                "verdict": "FAIL",
                "stage": "verify",
                "code": "interpreter_mismatch",
                "error": "Interpreter mismatch: %s" % (mismatches[:5],),
                "elapsed_s": round(time.perf_counter() - t0, 1),
                "sent": _summarize_sent(sent),
                "warnings": [],
            }
        try:
            experiment = OrbitLabExperiment.model_validate(returned)
        except Exception as e:
            return {
                "prompt": prompt,
                "verdict": "FAIL",
                "stage": "validate",
                "code": "schema_error",
                "error": "%s: %s" % (type(e).__name__, str(e)[:300]),
                "elapsed_s": round(time.perf_counter() - t0, 1),
                "sent": _summarize_sent(sent),
                "warnings": [],
            }
        outcome = AstrodynamicValidator.validate(experiment)
        verdict = "PASS" if (outcome.is_valid and not outcome.warnings) else ("WARN" if outcome.is_valid else "FAIL")
        entry = {
            "prompt": prompt,
            "verdict": verdict,
            "elapsed_s": round(time.perf_counter() - t0, 1),
            "sent": _summarize_sent(sent),
            "warnings": list(outcome.warnings or []),
        }
        if not outcome.is_valid:
            entry.update({
                "stage": "validate",
                "code": "validation_failed",
                "error": "; ".join(outcome.errors or [])[:500],
            })
        return entry
    except Exception as e:  # never crash the harness on one prompt
        return {
            "prompt": prompt,
            "verdict": "FAIL",
            "stage": "harness",
            "code": "harness_error",
            "error": "%s: %s" % (type(e).__name__, str(e)[:300]),
            "elapsed_s": round(time.perf_counter() - t0, 1),
            "sent": None,
            "warnings": [],
        }


async def amain(out_path, timeout_s):
    from orbitlab_backend.clients.interpreter_client import HttpInterpreterClient

    first_timeout = max(180.0, float(timeout_s))
    print("timeouts: first call %.0fs, later calls 60s (cold start allowance)" % first_timeout)
    results = []
    for i, prompt in enumerate(PROMPTS):
        timeout = first_timeout if i == 0 else 60.0
        client = HttpInterpreterClient(timeout_s=timeout)
        entry = await run_one(prompt, client)
        results.append(entry)
        sent = entry.get("sent") or {}
        stop = sent.get("stop") or ["?", "?", "?"]
        print("[%s] %s (%.1fs) body=%s sma=%s stop=%s/%s %s" % (
            entry["verdict"], prompt[:60], entry["elapsed_s"],
            sent.get("body"), sent.get("semiMajorAxisKm"),
            stop[0], stop[1],
            ("errors=%s" % entry.get("error", ""))[:120] if entry["verdict"] == "FAIL" else "",
        ))
    counts = {v: sum(1 for r in results if r["verdict"] == v) for v in ("PASS", "WARN", "FAIL")}
    print("summary: %d PASS, %d WARN, %d FAIL out of %d" % (counts["PASS"], counts["WARN"], counts["FAIL"], len(results)))
    payload = {"results": results, "summary": counts, "note": "no secrets stored; model key/URL never written here"}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
    print("saved %s" % out_path)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Real-model smoke test (frontstep/interpret/verify/validate only).")
    parser.add_argument("--out", default="smoke_results.json", help="Where to save the JSON results (no secrets).")
    args = parser.parse_args(argv)
    missing = missing_vars()
    if missing:
        for name in missing:
            print("Missing %s" % name)
        return 2
    try:
        timeout_s = float(os.environ.get("ORBITLAB_MODEL_TIMEOUT_S", "180") or 180)
    except ValueError:
        timeout_s = 180.0
    try:
        return asyncio.run(amain(args.out, timeout_s))
    except KeyboardInterrupt:
        print("interrupted")
        return 1


if __name__ == "__main__":
    sys.exit(main())
