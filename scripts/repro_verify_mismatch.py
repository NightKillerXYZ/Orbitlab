"""Reproduce a verify-stage unit mismatch (investigation only - read-only probe).

Sends prompts through the REAL extractor and interpreter (endpoints and key
come from the environment only and are NEVER printed) and prints the
extractor output next to the interpreter output, highlighting any
km-vs-m scale mismatch (e.g. 400 vs 400000).

Usage (repo root):  PYTHONPATH=phase4_backend python scripts/repro_verify_mismatch.py
"""
import asyncio
import json
import os
import sys

PROMPTS = [
    "500 kg satellite around Earth, circular 400 km, 2 days, sun-synchronous",
    "500 kg satellite around Earth, circular 400 km, 1 day",
    "500 kg satellite around Earth, 500 km altitude, burn at apoapsis to 800 km, 1 day",
    "500 kg satellite around Venus, semi-major axis 9000 km, 1 day",
]

NEED = ["EXTRACTOR_BASE_URL", "EXTRACTOR_API_KEY", "EXTRACTOR_MODEL",
        "ORBITLAB_MODEL_URL", "ORBITLAB_MODEL_KEY"]


def check_env():
    missing = [k for k in NEED if not os.environ.get(k)]
    if missing:
        print("missing environment (names only, values never shown): "
              + ", ".join(sorted(missing)))
        print("Set them in your shell and retry; nothing was called.")
        return False
    print("environment ok (presence only): " + ", ".join(sorted(NEED)))
    return True


def pick_numbers(obj, keys):
    out = {}
    try:
        els = (obj.get("initialOrbit") or {}).get("elements") or {}
        for k in keys:
            if k in els:
                out[k] = els[k]
    except Exception:
        pass
    return out


async def one(extractor, interpreter, text):
    print("=" * 78)
    print("PROMPT: " + text)
    try:
        ex = await extractor.process(text)
    except Exception as e:
        print("extractor raised: %s: %s" % (type(e).__name__, e))
        return
    status = getattr(ex, "status", "?")
    data = getattr(ex, "data", None) or {}
    prompt = getattr(ex, "prompt", "")
    print("extractor status: %s" % status)
    try:
        missing = getattr(ex, "missing", None)
        if missing:
            print("extractor missing: %s" % sorted(str(m) for m in missing))
    except Exception:
        pass
    print("extractor data: %s" % json.dumps(data, sort_keys=True))
    try:
        print("canonical prompt: %s" % prompt[:400])
    except Exception:
        pass
    if status != "ok":
        print("note: extraction did not succeed; interpreter skipped")
        return
    try:
        interp = await interpreter.interpret_prompt(prompt)
    except Exception as e:
        print("interpreter raised: %s: %s" % (type(e).__name__, e))
        return
    got = interp.get("semiMajorAxisKm") if isinstance(interp, dict) else None
    print("interpreter elements: %s" % json.dumps(pick_numbers(
        interp, ["semiMajorAxisKm", "eccentricity", "inclinationDeg",
                 "raanDeg", "argumentOfPeriapsisDeg", "trueAnomalyDeg"]), sort_keys=True))
    try:
        a = float(data.get("semiMajorAxisKm"))
        b = float((interp.get("initialOrbit") or {}).get("elements", {}).get("semiMajorAxisKm"))
        ratio = (a / b) if b else None
        flag = ""
        if ratio and (abs(ratio - 1000.0) < 1.0 or abs(ratio - 0.001) < 0.00001):
            flag = "  <-- 1000x UNIT MISMATCH?"
        print("sma extractor=%.6g interpreter=%.6g ratio=%s%s" % (a, b, ratio, flag))
    except Exception as e:
        print("sma compare skipped: %s" % e)


async def amain():
    if not check_env():
        return 2
    # Local imports so --help-style import never needs the backend env.
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "phase4_backend"))
    try:
        from orbitlab_backend.frontstep.extractor import FrontStepExtractor
        from orbitlab_backend.clients.extractor_client import get_extractor, MockExtractor
        from orbitlab_backend.clients.interpreter_client import get_interpreter_client
    except Exception as e:
        print("import failed: %s: %s" % (type(e).__name__, e))
        return 2
    try:
        interpreter = get_interpreter_client()
    except Exception as e:
        print("interpreter client unavailable: %s: %s" % (type(e).__name__, e))
        return 2
    try:
        name = type(interpreter).__name__
    except Exception:
        name = "?"
    print("interpreter client: %s (mock would mean demo/misconfig - aborting)" % name)
    if "Mock" in name:
        print("refusing to probe a mock interpreter")
        return 2
    # Mirror Pipeline: real endpoint client when configured, never mock.
    try:
        _cli = get_extractor()
    except Exception as e:
        print("extractor client unavailable: %s" % type(e).__name__)
        return 2
    print("extractor client: %s (mock would mean demo/misconfig - aborting)" % type(_cli).__name__)
    if isinstance(_cli, MockExtractor):
        print("refusing to probe a mock extractor")
        return 2
    extractor = FrontStepExtractor(extractor_client=_cli)
    print("note: sync probe skipped (async context); the async path below exercises the live endpoint")
    for text in PROMPTS:
        await one(extractor, interpreter, text)
    return 0


def main(argv=None):
    try:
        return asyncio.run(amain())
    except KeyboardInterrupt:
        print("interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
