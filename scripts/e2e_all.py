"""Run every test folder and print one summary table.

Folders: tests/e2e, tests (excluding tests/e2e), orbitlab_core/tests,
simulation_engine/tests. Exits 1 if anything failed or errored.
Skips (e.g. GMAT-gated e2e when GMAT_PATH is unset) are reported, not failures.
Run from the repo root:  python scripts/e2e_all.py
"""
import re
import subprocess
import sys
import time

FOLDERS = [
    ("tests/e2e", ["-m", "pytest", "tests/e2e", "-q", "--tb=no", "-p", "no:cacheprovider"]),
    ("tests", ["-m", "pytest", "tests", "-q", "--tb=no", "-p", "no:cacheprovider",
               "--ignore=tests/e2e"]),
    ("orbitlab_core/tests", ["-m", "pytest", "orbitlab_core/tests", "-q", "--tb=no",
                             "-p", "no:cacheprovider"]),
    ("simulation_engine/tests", ["-m", "pytest", "simulation_engine/tests", "-q", "--tb=no",
                                 "-p", "no:cacheprovider"]),
]

SUMMARY_RE = re.compile(r"(?:(\d+) failed, )?(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) error)?")


def run_folder(name, args):
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    dt = time.perf_counter() - t0
    passed = failed = skipped = errors = 0
    for line in proc.stdout.splitlines():
        m = SUMMARY_RE.search(line)
        if m and "passed" in line:
            failed = int(m.group(1) or 0)
            passed = int(m.group(2))
            skipped = int(m.group(3) or 0)
            errors = int(m.group(4) or 0)
    if proc.returncode not in (0, 1, 5):
        errors += 1
    return {"folder": name, "passed": passed, "failed": failed,
            "skipped": skipped, "errors": errors, "seconds": round(dt, 1),
            "code": proc.returncode}


def main():
    rows = [run_folder(name, args) for name, args in FOLDERS]
    print("%-24s %7s %7s %7s %7s %8s" % ("folder", "passed", "failed", "skipped", "errors", "seconds"))
    for r in rows:
        print("%-24s %7d %7d %7d %7d %8.1f" % (
            r["folder"], r["passed"], r["failed"], r["skipped"], r["errors"], r["seconds"]))
    bad = sum(r["failed"] + r["errors"] for r in rows)
    print("total failed+errors: %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
