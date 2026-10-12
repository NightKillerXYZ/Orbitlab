"""Reproduce the V9 dataset artifacts from scratch and verify deterministic hashes.

Runs the full V9 pipeline in order:
  1. build_v9.py          -> corrections / master / annotations / failures
  2. validate_v9.py       -> statistics + full validation pass
  3. audit_v9.py          -> audit report
  4. build_v9_blind.py    -> blind eval set / results / report

Then recomputes the SHA-256 of every registered output artifact and compares it
against v9_sha256.json.  A mismatch means the pipeline is not bit-reproducible
and the committed artifacts cannot be trusted as the canonical V9 emit.

NOTE: this deliberately does NOT start or submit any training job.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

STEPS = ["build_v9.py", "validate_v9.py", "audit_v9.py", "build_v9_blind.py"]

# Predictions set in STEPS are validated first; recompute their hashes here.
FILES = {
    "corrections": "orbitlab_interpreter_train_v9_corrections.jsonl",
    "master": "orbitlab_interpreter_train_v9_master.jsonl",
    "tinker": "orbitlab_v9_tinker.jsonl",
    "blind_eval": "v9_blind_eval.jsonl",
    "blind_eval_results": "v9_blind_eval_results.jsonl",
    "blind_eval_report": "v9_blind_eval_report.md",
    "statistics": "v9_statistics.json",
    "audit": "v9_audit.json",
    "quality_report": "v9_quality_report.md",
    "semantic_findings": "v9_semantic_findings.json",
    "category_distribution": "v9_category_distribution.json",
    "v8_audit": "v9_v8_audit.md",
}

MISSING_EAT = {"tinker", "quality_report", "semantic_findings",
               "category_distribution", "v8_audit"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    # 1. Reconstitute the Tinker export so its hash can be compared as well.
    subprocess.run([sys.executable, "convert_v9_for_tinker.py"], cwd=str(HERE), check=True)

    # 2. Run the deterministic pipeline stages.
    for step in STEPS:
        print(f"== {step} ==", flush=True)
        subprocess.run([sys.executable, step], cwd=str(HERE), check=True)

    # 3. Compare hashes against the committed manifest.
    manifest_path = HERE / "v9_sha256.json"
    expected = json.loads(manifest_path.read_text(encoding="utf-8"))

    results: dict[str, str] = {}
    for key, fname in FILES.items():
        p = HERE / fname
        if p.exists():
            results[key] = {"sha256": sha256(p), "exists": True}
        else:
            results[key] = {"sha256": None, "exists": False}

    failed: list[str] = []
    for key in FILES:
        if key not in expected:
            continue
        if not results[key]["exists"]:
            failed.append(f"{key} (missing)")
            continue
        if results[key]["sha256"] != expected[key]:
            failed.append(f"{key} ({expected[key][:12]} != {results[key]['sha256'][:12]})")

    summary = {
        "steps": STEPS,
        "manifest_matched": len(FILES) - len(failed),
        "manifest_total": len(FILES),
        "failures": failed,
        "reproducible": not failed,
    }
    (HERE / "v9_reproduce_result.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(json.dumps(summary, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
