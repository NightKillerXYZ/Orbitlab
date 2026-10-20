"""T4 — Golden diff for per-row warnings between the OLD and CURRENT orbitlab_core.

Runs the same v9b master rows through the OLD core (extracted at commit 4d5d3e8
into closeout2/old_core) and through the CURRENT core, recording per-row
is_valid, the error list and the warning list, then compares row by row.

Because both versions share the module name ``orbitlab_core`` (they cannot be
imported together in one process), this script runs in two modes:

  * ``--worker old``      run every row through the OLD core ONCE (a separate
                          process, launched with closeout2/old_core first on
                          sys.path), writing a per-row result file.
  * ``--worker current``  run every row through the CURRENT core (the repo's own
                          orbitlab_core), writing a per-row result file.
  * no args               orchestrate: launch the two workers as separate
                          subprocesses with the right PYTHONPATH, then load both
                          per-row files, compare them, write closeout2/
                          warnings_diff.json and print a summary. Exit code 0
                          iff the per-row diff count is 0.

Required result: 0 differences across all 4,300 rows.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../phase3_ai_interpreter/closeout2
PHASE = HERE.parent                              # .../phase3_ai_interpreter
ROOT = PHASE.parent                              # repo root
OLD_CORE = HERE / "old_core"                     # .../closeout2/old_core  (contains orbitlab_core/)
DATASET = PHASE / "datasets" / "v9" / "orbitlab_interpreter_train_v9b_master.jsonl"
OUT_OLD = HERE / "_rows_old.json"
OUT_CURRENT = HERE / "_rows_current.json"
RESULT = HERE / "warnings_diff.json"


def sys_path_insert(path: str) -> None:
    if path not in sys.path:
        sys.path.insert(0, path)


def worker(mode: str) -> int:
    """Validate every dataset row with one specific core and write its result file."""
    if mode == "old":
        # old_core must be FIRST on sys.path so `import orbitlab_core` resolves
        # to the archived copy, not the repo's current one.
        sys_path_insert(str(OLD_CORE))
    else:
        sys_path_insert(str(ROOT))
        sys_path_insert(str(PHASE))

    from orbitlab_core.ast.models import OrbitLabExperiment  # noqa: E402
    from orbitlab_core.ast.validation import AstrodynamicValidator  # noqa: E402

    rows = []
    with open(DATASET, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            body = None
            try:
                row = json.loads(line)
                for part in row.get("contents", []):
                    if part.get("role") == "model":
                        text = part["parts"][0]["text"]
                        obj = json.loads(text)
                        break
                exp = OrbitLabExperiment.model_validate(obj)
                body = exp.centralBody
                vr = AstrodynamicValidator.validate(exp)
                rows.append({
                    "line": line_no,
                    "centralBody": body,
                    "ok": True,
                    "is_valid": bool(vr.is_valid),
                    "errors": list(vr.errors),
                    "warnings": list(vr.warnings),
                })
            except Exception as exc:  # noqa: BLE001 - record any per-row failure
                rows.append({
                    "line": line_no,
                    "centralBody": body,
                    "ok": False,
                    "is_valid": None,
                    "error": f"{type(exc).__name__}: {exc}",
                    "errors": [],
                    "warnings": [],
                })

    out = OUT_OLD if mode == "old" else OUT_CURRENT
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"[{mode}] wrote {out} ({len(rows)} rows)")
    return 0


def _launch(worker_args):  # noqa: ANN001
    env = dict(os.environ)
    return subprocess.run(
        [sys.executable, str(__file__), *worker_args],
        cwd=str(HERE),
        env=env,
        capture_output=True,
        text=True,
    )


def compare() -> int:
    """Orchestrate: run both workers in separate processes, then diff."""
    # Ensure a clean worker output before orchestrating.
    for p in (OUT_OLD, OUT_CURRENT):
        if p.exists():
            p.unlink()

    # OLD worker: old_core must shadow the repo's current orbitlab_core. We
    # prepend OLD_CORE to PYTHONPATH for that subprocess so its import of
    # orbitlab_core resolves to the archived copy.
    env_old = dict(os.environ)
    sep = ";" if os.name == "nt" else ":"
    old_pp = [str(OLD_CORE)] + [p for p in env_old.get("PYTHONPATH", "").split(sep) if p]
    env_old["PYTHONPATH"] = sep.join(old_pp)

    r_old = subprocess.run(
        [sys.executable, str(__file__), "--worker", "old"],
        cwd=str(HERE), env=env_old, capture_output=True, text=True,
    )
    r_cur = subprocess.run(
        [sys.executable, str(__file__), "--worker", "current"],
        cwd=str(HERE), env=dict(os.environ), capture_output=True, text=True,
    )
    for name, r in (("old", r_old), ("current", r_cur)):
        if r.returncode != 0:
            print(f"[{name}] worker failed rc={r.returncode}")
            print(r.stdout)
            print(r.stderr)
            sys.exit(1)

    old_rows = json.loads(OUT_OLD.read_text(encoding="utf-8"))
    cur_rows = json.loads(OUT_CURRENT.read_text(encoding="utf-8"))

    n = min(len(old_rows), len(cur_rows))
    mismatches = 0
    examples = []
    per_body = {}
    for i in range(n):
        o, c = old_rows[i], cur_rows[i]
        o_key = (o.get("ok"), o.get("is_valid"), o.get("errors"), o.get("warnings"))
        c_key = (c.get("ok"), c.get("is_valid"), c.get("errors"), c.get("warnings"))
        same = o_key == c_key and o.get("centralBody") == c.get("centralBody")
        b = c.get("centralBody")
        d = per_body.setdefault(b, {"same": 0, "diff": 0})
        d["same" if same else "diff"] += 1
        if not same:
            mismatches += 1
            if len(examples) < 10:
                examples.append({
                    "line": c.get("line"),
                    "centralBody": b,
                    "old": o_key,
                    "current": c_key,
                })

    result = {
        "row_count": (len(old_rows), len(cur_rows)),
        "mismatches": mismatches,
        "examples": examples,
        "per_body": per_body,
    }
    RESULT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Wrote {RESULT}")
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        sys.exit(worker(sys.argv[2]))
    sys.exit(compare())
