"""STEP 2 golden-diff capture for the OrbitLab v9 close-out.

Mirrors body_expansion/golden_snapshot.py's methodology exactly (same suite
runners, same dataset parse/validate/compile/SHA-256 loop, same metric names)
but writes the CURRENT ("after") state to NEW files so the FROZEN baseline
(golden_before.json / golden_scripts_before.json) is never overwritten, then
diffs "after" vs "before".

Item 6 gate (TASKING.md l.28): all 4300 v9b rows give the same success, errors,
warnings and compiled-script SHA-256 as the before-files. The strict ZERO-diff
gate applies to the DATASET rows (success/errors/warnings + Earth/Moon/Mars
compiled-script SHA-256). The frontstep suite PASS string legitimately changed
from "ALL 10" to "ALL 11 ASSERTIONS PASSED." because item 5 added case #11; that
is an accepted, intended difference and is reported separately from the dataset
golden gate.

Read-only w.r.t. the FROZEN dataset trees and the before-baseline files.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent               # .../closeout
PHASE = HERE.parent                                  # .../phase3_ai_interpreter
ROOT = PHASE.parent                                  # repo root
BODY_EXP = PHASE / "body_expansion"

DATASET = PHASE / "datasets" / "v9" / "orbitlab_interpreter_train_v9b_master.jsonl"
BEFORE_META = BODY_EXP / "golden_before.json"
BEFORE_ROWS = BODY_EXP / "golden_scripts_before.json"
AFTER_META = HERE / "golden_after.json"
AFTER_ROWS = HERE / "golden_scripts_after.json"

for _p in (str(PHASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FRONTSTEP_PASS = "ALL 11 ASSERTIONS PASSED."


def run_interpreter_suite() -> dict:
    module = importlib.util.spec_from_file_location(
        "test_json_interpreter_after",
        PHASE / "interpreter" / "tests" / "test_json_interpreter.py",
    )
    assert module and module.loader
    mod = importlib.util.module_from_spec(module)
    module.loader.exec_module(mod)
    suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
    result = unittest.TestResult()
    suite.run(result)
    return {
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "ok": result.wasSuccessful(),
        "skipped": len(result.skipped),
    }


def run_frontstep_suite() -> dict:
    for _p in (str(PHASE), str(PHASE / "frontstep")):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            exec(
                compile(
                    (PHASE / "frontstep" / "test_frontstep.py").read_text(encoding="utf-8"),
                    "test_frontstep.py",
                    "exec",
                ),
                {"__name__": "__test_frontstep_after__"},
            )
    except Exception as exc:  # noqa: BLE001 - assertion or import failure
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "stdout": buf.getvalue()}
    out = buf.getvalue()
    return {
        "ok": (FRONTSTEP_PASS in out and "PI PARSING TESTS PASSED." in out),
        "has_11_assertions": FRONTSTEP_PASS in out,
        "has_pi_parsing": "PI PARSING TESTS PASSED." in out,
        "stdout": out,
    }


def run_orbitlab_core_suite() -> dict:
    suite = unittest.TestSuite()
    for name in ("test_models", "test_validation", "test_compiler"):
        mod = importlib.import_module(f"orbitlab_core.tests.{name}")
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(mod))
    result = unittest.TestResult()
    suite.run(result)
    return {
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "ok": result.wasSuccessful(),
        "skipped": len(result.skipped),
    }


def snapshot_dataset() -> dict:
    from orbitlab_core.ast.models import OrbitLabExperiment
    from orbitlab_core.ast.validation import AstrodynamicValidator
    from orbitlab_core.compiler.generator import GmatScriptCompiler

    comp = GmatScriptCompiler()
    summary = {
        "rows": 0,
        "parse_ok": 0,
        "parse_err": 0,
        "validate_pass": {},
        "validate_reject": {},
        "compile_ok": {},
        "compile_err": 0,
    }
    rows = []
    with open(DATASET, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            summary["rows"] += 1
            row = json.loads(line)
            body = None
            try:
                for part in row.get("contents", []):
                    if part.get("role") == "model":
                        obj = json.loads(part["parts"][0]["text"])
                        break
                exp = OrbitLabExperiment.model_validate(obj)
                body = exp.centralBody
                summary["parse_ok"] += 1
                vr = AstrodynamicValidator.validate(exp)
                if vr.is_valid:
                    summary["validate_pass"][body] = summary["validate_pass"].get(body, 0) + 1
                else:
                    summary["validate_reject"][body] = summary["validate_reject"].get(body, 0) + 1
                script = comp.compile_to_string(exp)
                h = hashlib.sha256(script.encode("utf-8")).hexdigest()
                summary["compile_ok"][body] = summary["compile_ok"].get(body, 0) + 1
                rows.append({"centralBody": body, "sha256": h, "script": script})
            except Exception as exc:  # noqa: BLE001
                summary["parse_err"] += 1
                summary.setdefault("compile_err", summary.get("compile_err", 0))
                rows.append({"centralBody": body, "error": f"{type(exc).__name__}: {exc}"})
    return {"summary": summary, "rows": rows}


def diff_dataset(before: dict, after: dict) -> dict:
    bsum, asum = before["summary"], after["summary"]
    keys = ["rows", "parse_ok", "parse_err", "compile_err"]
    summary_diff = {k: (bsum.get(k), asum.get(k)) for k in keys}
    summary_diff["validate_pass"] = (bsum.get("validate_pass", {}), asum.get("validate_pass", {}))
    summary_diff["validate_reject"] = (bsum.get("validate_reject", {}), asum.get("validate_reject", {}))
    summary_diff["compile_ok"] = (bsum.get("compile_ok", {}), asum.get("compile_ok", {}))

    b_rows = before["rows"]
    a_rows = after["rows"]
    per_body = {}
    errors_before = {}
    errors_after = {}
    for r in b_rows:
        b = r.get("centralBody")
        if "error" in r:
            errors_before[b] = errors_before.get(b, 0) + 1
        else:
            d = per_body.setdefault(b, {"same": 0, "diff": 0, "examples": []})
            d["same"] += 1
    for r in a_rows:
        b = r.get("centralBody")
        if "error" in r:
            errors_after[b] = errors_after.get(b, 0) + 1
        else:
            pass  # counted below
    # pair rows by index (same order, same row count expected)
    mismatches = 0
    examples = []
    if len(b_rows) == len(a_rows):
        for i, (br, ar) in enumerate(zip(b_rows, a_rows)):
            if ("error" in br) != ("error" in ar) or br.get("sha256") != ar.get("sha256"):
                mismatches += 1
                if len(examples) < 10:
                    examples.append({
                        "idx": i,
                        "centralBody": ar.get("centralBody"),
                        "before_sha": br.get("sha256"),
                        "after_sha": ar.get("sha256"),
                        "before_error": br.get("error"),
                        "after_error": ar.get("error"),
                    })
    else:
        mismatches = -1  # row count differed; flag loudly

    return {
        "row_count": (len(b_rows), len(a_rows)),
        "mismatches": mismatches,
        "examples": examples,
        "per_body": per_body,
        "errors_before": errors_before,
        "errors_after": errors_after,
        "summary_diff": summary_diff,
    }


def main() -> int:
    suites = {
        "interpreter": run_interpreter_suite(),
        "frontstep": run_frontstep_suite(),
        "orbitlab_core": run_orbitlab_core_suite(),
    }
    dataset = snapshot_dataset()

    meta = {
        "artifact": "golden_after",
        "note": (
            "Captured AFTER the body-expansion close-out code edits. Dataset "
            "success/errors/warnings + Earth/Moon/Mars compiled-script SHA-256 "
            "are the item 6 ZERO-diff gate vs golden_before.json."
        ),
        "python": sys.version.split()[0],
        "suites": suites,
        "dataset": dataset["summary"],
    }

    before_meta = json.loads(BEFORE_META.read_text(encoding="utf-8"))
    before_rows = json.loads(BEFORE_ROWS.read_text(encoding="utf-8"))
    before = {"summary": before_meta["dataset"], "rows": before_rows}
    diff = diff_dataset(before, dataset)

    report = {
        "after_meta": meta,
        "before_meta": before_meta,
        "golden_diff_dataset": diff,
    }

    AFTER_META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    AFTER_ROWS.write_text(json.dumps(dataset["rows"], indent=2), encoding="utf-8")
    (HERE / "step2_golden_diff.json").write_text(json.dumps(diff, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nWrote {AFTER_META}")
    print(f"Wrote {AFTER_ROWS} ({len(dataset['rows'])} rows)")
    print(f"Wrote {HERE / 'step2_golden_diff.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
