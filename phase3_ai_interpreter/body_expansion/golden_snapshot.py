"""Golden snapshot capture for the OrbitLab body-expansion (Phase 1).

Runs entirely read-only against the frozen/unmodified codebase and records:

  1. Test-suite pass counts for the three suites that must remain stable for
     Earth/Moon/Mars behavior after the body expansion:
       - interpreter  : phase3_ai_interpreter/interpreter/tests/run_tests.py
       - frontstep    : phase3_ai_interpreter/frontstep/test_frontstep.py
       - orbitlab_core: orbitlab_core.tests (test_models, test_validation,
                        test_compiler; GMAT-execution suite excluded here)
  2. Parse / validate / compile results for every row of the frozen v9b master
     dataset, including the SHA-256 of each generated GMAT script. After the
     body expansion, the same script hash comparison must be byte-identical for
     every Earth/Moon/Mars row (Task G gate).

Output: golden_before.json (metadata + counts) and (optionally) a full per-row
record written to golden_scripts_before.json.

Read-only: opens the dataset and test modules with open()/exec, never writes
inside the repo except the output artifacts named via OUTPUT.
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

HERE = Path(__file__).resolve().parent                 # .../body_expansion
PHASE = HERE.parent                                    # .../phase3_ai_interpreter
ROOT = PHASE.parent                                    # repo root

DATASET = PHASE / "datasets" / "v9" / "orbitlab_interpreter_train_v9b_master.jsonl"
OUTPUT_META = HERE / "golden_before.json"
OUTPUT_ROWS = HERE / "golden_scripts_before.json"

for _p in (str(PHASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# --------------------------------------------------------------------------
# 1. Test suite counts
# --------------------------------------------------------------------------
def run_interpreter_suite() -> dict:
    """Run interpreter/tests/run_tests.py's suite loader and count."""

    module = importlib.util.spec_from_file_location(
        "test_json_interpreter",
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
    """Run frontstep/test_frontstep.py by executing it and capturing output."""
    # frontstep must be importable: it lives under phase3_ai_interpreter
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
                {"__name__": "__test_frontstep__"},
            )
    except Exception as exc:  # assertion or import failure
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "stdout": buf.getvalue()}
    out = buf.getvalue()
    return {
        "ok": ("ALL 10 ASSERTIONS PASSED." in out and "PI PARSING TESTS PASSED." in out),
        "has_10_assertions": "ALL 10 ASSERTIONS PASSED." in out,
        "has_pi_parsing": "PI PARSING TESTS PASSED." in out,
        "stdout": out,
    }


def run_orbitlab_core_suite() -> dict:
    """Run orbitlab_core tests (excluding GMAT-execution integration)."""
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


# --------------------------------------------------------------------------
# 2. Dataset parse/validate/compile golden
# --------------------------------------------------------------------------
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
                rows.append({
                    "centralBody": body,
                    "sha256": h,
                    "script": script,
                })
            except Exception as exc:  # noqa: BLE001 - record the row failure
                summary["parse_err"] += 1
                summary.setdefault("compile_err", summary.get("compile_err", 0))
                rows.append({
                    "centralBody": body,
                    "error": f"{type(exc).__name__}: {exc}",
                })

    return {"summary": summary, "rows": rows}


def main() -> int:
    suites = {
        "interpreter": run_interpreter_suite(),
        "frontstep": run_frontstep_suite(),
        "orbitlab_core": run_orbitlab_core_suite(),
    }
    dataset = snapshot_dataset()

    meta = {
        "artifact": "golden_before",
        "note": (
            "Captured BEFORE any body-expansion code edits. Earth/Moon/Mars "
            "test counts and per-row GMAT script hashes are the Task G gate."
        ),
        "python": sys.version.split()[0],
        "suites": suites,
        "dataset": dataset["summary"],
    }
    OUTPUT_META.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Full per-row record kept separately (large); hash-only view is in meta.
    OUTPUT_ROWS.write_text(json.dumps(dataset["rows"], indent=2), encoding="utf-8")

    print(json.dumps(meta, indent=2))
    print(f"\nWrote {OUTPUT_META}")
    print(f"Wrote {OUTPUT_ROWS} ({len(dataset['rows'])} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
