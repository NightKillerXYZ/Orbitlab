"""v11 OrbitLab evaluation harness.

Runs a model endpoint against a JSONL of cases and scores each one through the
same chain the dataset gate uses: strict JSON parse -> Pydantic AST load ->
AstrodynamicValidator -> deterministic GMAT compile (all via
:class:`JsonExperimentInterpreter`).

Case schema (see README.md):
    {id, user_text, expect: "accept"|"reject",
     expect_reason (substring, optional, for rejects),
     expect_json (optional, for accepts: element comparison target)}

Endpoints
---------
The endpoint is pluggable so the harness works with any backend:
  * OpenAI-compatible HTTP ("works with hosted untuned baseline, Kaggle-served
    tuned model, or local") -- configured via env vars:
        EVAL_BASE_URL     OpenAI-compatible base URL (must end in /v1)
        EVAL_API_KEY      API key
        EVAL_MODEL        model name
  * Mock endpoints for testing (no network):
        --mock gold      returns each case's expect_json serialised (=> ~100%)
        --mock garbage   returns random garbage text (=> ~0%, no crash)

Scoring (per case)
------------------
  * JSON valid
  * schema / physics valid (interpreter succeeds)
  * validator verdict (accept/reject) equals `expect`
  * accepts: elements compared to `expect_json` with tolerances
    (SMA 0.1%, angles 0.01 deg, ecc 1e-4)
  * rejects: the rejection reason contains `expect_reason` (substring)

Output
------
  * results JSON (full per-case detail) + report.md, each with a timestamp so
    attempts can be compared.

Usage
-----
    python run_eval.py cases.jsonl --out results
    python run_eval.py cases_blind.jsonl --mock gold
    python run_eval.py cases_blind.jsonl --mock garbage
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # feature-physics-core
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "phase3_ai_interpreter"))

from interpreter.json_interpreter import JsonExperimentInterpreter  # noqa: E402

# --- tolerances (per tasking) ---
SMA_TOL = 0.001          # 0.1%
ANGLE_TOL_DEG = 0.01
ECC_TOL = 1e-4

ANGLE_FIELDS = ("inclinationDeg", "raanDeg", "argumentOfPeriapsisDeg", "trueAnomalyDeg")
NUM_FIELDS = ("semiMajorAxisKm", "eccentricity") + ANGLE_FIELDS


# ---------------------------------------------------------------------------
# Standard system prompt (copied verbatim from the v10 fixed blind rows).
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "The model is an OrbitLab Experiment Interpreter.\n\n"
    "It converts natural-language orbital-simulation requests into the exact "
    "OrbitLab Experiment JSON structure.\n\n"
    "Rules:\n"
    "- Output only the Experiment JSON when the request contains enough information for a valid experiment.\n"
    "- Never output raw GMAT script.\n"
    "- Never invent unsupported fields.\n"
    "- Never silently change user-specified physical parameters.\n"
    "- Use only fields supported by the actual OrbitLab schema.\n"
    "- Do not decide physical validity independently of OrbitLab validation.\n"
    "- Preserve the user's requested values and units after converting them to the schema's required units.\n"
    "- If required information is genuinely missing, the production system should request clarification rather than inventing a value.\n"
    "- The deterministic OrbitLab compiler, not the AI, is responsible for producing GMAT syntax."
)


# ---------------------------------------------------------------------------
# Case loading
# ---------------------------------------------------------------------------
def load_cases(path: Path) -> list[dict]:
    cases = []
    for ln, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path} line {ln}: bad JSON: {exc}")
        if not isinstance(case, dict) or "id" not in case or "user_text" not in case:
            raise SystemExit(f"{path} line {ln}: case must have id and user_text")
        if case.get("expect", "accept") not in ("accept", "reject"):
            raise SystemExit(f"{path} line {ln}: expect must be accept|reject")
        cases.append(case)
    return cases


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
class BaseEndpoint:
    """Callable: endpoint(user_text, case) -> raw model output string."""

    def __call__(self, user_text: str, case: dict) -> str:  # pragma: no cover
        raise NotImplementedError


class OpenAICompatibleEndpoint(BaseEndpoint):
    """OpenAI-compatible chat completions endpoint (hosted / local)."""

    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float = 0.0, timeout: int = 120) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def __call__(self, user_text: str, case: dict) -> str:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


class MockGoldEndpoint(BaseEndpoint):
    """Returns the case's gold expect_json (serialised) -> ~100%."""

    def __call__(self, user_text: str, case: dict) -> str:
        if "expect_json" not in case:
            raise RuntimeError("mock gold requires expect_json on every case")
        return json.dumps(case["expect_json"], ensure_ascii=False)


class MockGarbageEndpoint(BaseEndpoint):
    """Returns deterministic garbage text -> ~0% (no crash)."""

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def __call__(self, user_text: str, case: dict) -> str:
        junk = ("lorem ipsum dolor sit amet", "NOT JSON AT ALL", "```", "12345",
                "yeah sure the orbit goes fast and far", "{ invalid")
        return self._rng.choice(junk) + f" {self._rng.randint(0, 1000)}"


def make_endpoint(mock: str | None, temperature: float) -> BaseEndpoint:
    if mock == "gold":
        return MockGoldEndpoint()
    if mock == "garbage":
        return MockGarbageEndpoint()
    base = os.environ.get("EVAL_BASE_URL", "").strip()
    key = os.environ.get("EVAL_API_KEY", "").strip()
    model = os.environ.get("EVAL_MODEL", "").strip()
    if not (base and model):
        raise SystemExit(
            "Set EVAL_BASE_URL, EVAL_API_KEY and EVAL_MODEL (or pass --mock gold|garbage)."
        )
    return OpenAICompatibleEndpoint(base, key, model, temperature=temperature)


# ---------------------------------------------------------------------------
# Interpretation / scoring
# ---------------------------------------------------------------------------
def elements_of(exp) -> dict | None:
    """Return a plain-dict of orbital elements from a parsed payload (or None)."""
    if not isinstance(exp, dict):
        return None
    init = exp.get("initialOrbit")
    if not isinstance(init, dict):
        return None
    el = init.get("elements")
    return el if isinstance(el, dict) else None


def field_diff(field: str, got: float, expected: float) -> float | None:
    """Signed tolerance check. Returns None when within tolerance, else diff."""
    if field == "semiMajorAxisKm":
        tol = abs(expected) * SMA_TOL
    elif field == "eccentricity":
        tol = ECC_TOL
    else:  # angles
        tol = ANGLE_TOL_DEG
    diff = abs(got - expected)
    return diff if diff > tol else None


def check_elements(case: dict, payload: dict) -> list[str]:
    """Compare accepted payload elements vs case['expect_json']. Returns problems."""
    problems: list[str] = []
    target = case.get("expect_json")
    if not isinstance(target, dict):
        return problems  # nothing to compare against
    got = elements_of(payload)
    want = elements_of(target)
    body = payload.get("centralBody")
    tbody = target.get("centralBody")
    if body != tbody:
        problems.append(f"centralBody got={body!r} want={tbody!r}")
    if "type" in target.get("initialOrbit", {}) and "type" in payload.get("initialOrbit", {}):
        if payload["initialOrbit"]["type"] != target["initialOrbit"]["type"]:
            problems.append(
                f"initialOrbit.type got={payload['initialOrbit']['type']!r} "
                f"want={target['initialOrbit']['type']!r}"
            )
    if got is None or want is None:
        problems.append("elements missing (got or want)")
        return problems
    for f in NUM_FIELDS:
        g = got.get(f)
        w = want.get(f)
        if g is None or w is None:
            if g is None and w is not None or (w is None and g is not None):
                problems.append(f"element {f} missing in {'got' if g is None else 'want'}")
            continue
        try:
            diff = field_diff(f, float(g), float(w))
        except (TypeError, ValueError):
            problems.append(f"element {f} non-numeric got={g!r} want={w!r}")
            continue
        if diff is not None:
            problems.append(f"element {f} got={g} want={w} diff={diff:.6g} (>tol)")
    return problems


def reason_matches(errors: list[str], expect_reason: str) -> bool:
    needle = str(expect_reason).lower()
    return any(needle in e.lower() for e in errors)


def score_case(interpreter, case: dict, output: str) -> dict:
    """Score a single case given the raw model output. Returns a result dict."""
    res = {
        "id": case["id"],
        "expect": case["expect"],
        "expect_reason": case.get("expect_reason"),
        "raw_output": output,
    }

    # 1. JSON valid
    try:
        payload = json.loads(output)
    except (json.JSONDecodeError, TypeError) as exc:
        res.update({
            "json_valid": False, "schema_valid": False, "validated": False,
            "verdict": "reject", "verdict_correct": False,
            "problems": [f"json: {exc}"], "pass": False,
        })
        return res

    res["json_valid"] = True
    if not isinstance(payload, dict):
        res.update({
            "schema_valid": False, "validated": False, "verdict": "reject",
            "verdict_correct": False, "problems": ["payload is not an object"], "pass": False,
        })
        return res

    # 2. schema + physics + compile via the shared interpreter
    it = interpreter.interpret(output)
    errors = list(it.errors)
    res["_errors_full"] = " | ".join(str(e) for e in errors)
    # schema_valid: parsed into AST with no schema/parse errors (physical-only
    # failures are reported separately and drive the accept/reject verdict).
    res["schema_valid"] = all(str(e).startswith("physical:") for e in errors)
    res["validated"] = it.success
    res["warnings"] = list(it.warnings)

    # 3. validator verdict
    #   An "accept" case passes iff the interpreter succeeds. A "reject" case is
    #   correct iff the interpreter did NOT succeed (physical reject).
    verdict = "accept" if it.success else "reject"
    res["verdict"] = verdict
    res["verdict_correct"] = verdict == case["expect"]

    # 4. per-expectation checks
    problems: list[str] = []
    if case["expect"] == "accept":
        if not it.success:
            problems.append("expected accept but validator rejected: " + " | ".join(errors[:4]))
        else:
            problems.extend(check_elements(case, payload))
            res["elements"] = elements_of(payload)
    else:  # reject
        if it.success:
            problems.append("expected reject but validator accepted")
        else:
            reason = case.get("expect_reason")
            if reason:
                if reason_matches(errors, reason):
                    res["reason_match"] = True
                else:
                    problems.append(f"reject reason missing {reason!r}; got errors: {errors[:4]}")

    res["problems"] = problems
    res["pass"] = res.get("verdict_correct", False) and not problems
    return res


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def summarize(results: list[dict], cases: list[dict]) -> dict:
    n = len(results)
    passed = sum(1 for r in results if r["pass"])
    accuracy = (passed / n) if n else 0.0

    by_body: dict[str, list[dict]] = defaultdict(list)
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for case, res in zip(cases, results):
        body = None
        cat = None
        exp = case.get("expect_json") or (res.get("raw_output") and _try_body(res["raw_output"]))
        if isinstance(exp, dict):
            body = exp.get("centralBody")
            init = exp.get("initialOrbit", {})
            cat = init.get("type") or (PATH_DEFAULT_CAT.get(res["id"], "unknown"))
        by_body[body or "unknown"].append(res)
        by_cat[cat or "unknown"].append(res)

    def acc(rs):
        return (sum(1 for r in rs if r["pass"]) / len(rs)) if rs else 0.0

    return {
        "total": n,
        "passed": passed,
        "accuracy": accuracy,
        "per_body": {b: {"n": len(rs), "acc": acc(rs)} for b, rs in sorted(by_body.items())},
        "per_category": {c: {"n": len(rs), "acc": acc(rs)} for c, rs in sorted(by_cat.items())},
    }


def _try_body(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


# Fallback category for blind ids -> used only when expect_json lacks type.
PATH_DEFAULT_CAT: dict[str, str] = {}


def write_report(summ: dict, results: list[dict], out_prefix: str,
                 cases_file: str, endpoint_desc: str, timestamp: str) -> None:
    lines = []
    lines.append(f"# v11 eval run — {timestamp}")
    lines.append("")
    lines.append(f"- cases: `{cases_file}` ({summ['total']})")
    lines.append(f"- endpoint: {endpoint_desc}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- passed: {summ['passed']} / {summ['total']}")
    lines.append(f"- accuracy: {summ['accuracy']:.4f}")
    lines.append("")
    lines.append("### Per body")
    lines.append("")
    lines.append("| body | n | accuracy |")
    lines.append("|---|---|---|")
    for b, d in summ["per_body"].items():
        lines.append(f"| {b} | {d['n']} | {d['acc']:.4f} |")
    lines.append("")
    lines.append("### Per category")
    lines.append("")
    lines.append("| category | n | accuracy |")
    lines.append("|---|---|---|")
    for c, d in summ["per_category"].items():
        lines.append(f"| {c} | {d['n']} | {d['acc']:.4f} |")
    lines.append("")
    lines.append("## Failing cases")
    lines.append("")
    fails = [r for r in results if not r["pass"]]
    if not fails:
        lines.append("_(none)_")
    for r in fails:
        lines.append(f"### {r['id']} (expect {r['expect']})")
        lines.append("")
        lines.append("- verdict: " + ("accept" if r["verdict"] == "accept" else "reject")
                     + f" (correct={r['verdict_correct']})")
        lines.append("- json_valid: " + str(r.get("json_valid")))
        lines.append("- schema/validated: " + str(r.get("validated")))
        if r.get("problems"):
            for p in r["problems"]:
                lines.append(f"- problem: {p}")
        lines.append("- raw output:")
        lines.append("")
        lines.append("```")
        lines.append(r["raw_output"][:2000])
        lines.append("```")
        lines.append("")
    (Path(out_prefix + ".report.md")).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="OrbitLab v11 evaluation harness")
    ap.add_argument("cases", help="JSONL of cases to score")
    ap.add_argument("--out", default=str(HERE / "results"), help="output prefix (timestamp appended)")
    ap.add_argument("--mock", choices=["gold", "garbage"], default=None,
                    help="use a mock endpoint instead of the OpenAI-compatible one")
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    cases_path = Path(args.cases)
    if not cases_path.exists():
        raise SystemExit(f"cases file not found: {cases_path}")
    cases = load_cases(cases_path)
    if not cases:
        raise SystemExit(f"no cases in {cases_path}")

    endpoint = make_endpoint(args.mock, args.temperature)
    interpreter = JsonExperimentInterpreter()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_prefix = f"{args.out}.{timestamp}"

    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']} ...", flush=True)
        try:
            output = endpoint(case["user_text"], case)
        except Exception as exc:  # noqa: BLE001 - endpoint failure -> mark fail
            results.append({
                "id": case["id"], "expect": case["expect"],
                "verdict": "error", "verdict_correct": False, "pass": False,
                "endpoint_error": str(exc), "problems": [f"endpoint error: {exc}"],
                "raw_output": "",
            })
            continue
        results.append(score_case(interpreter, case, output))
        if case["expect"] == "reject" or results[-1]["verdict"] == "reject":
            _full = results[-1].get("_errors_full")
            print(f"       reject detail: {_full if _full is not None else 'n/a'}", flush=True)

    summ = summarize(results, cases)
    endpoint_desc = f"mock={args.mock}" if args.mock else \
        f"model={os.environ.get('EVAL_MODEL','')} url={os.environ.get('EVAL_BASE_URL','')}"
    write_report(summ, results, out_prefix, str(cases_path), endpoint_desc, timestamp)

    with open(out_prefix + ".json", "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp, "cases": str(cases_path),
            "endpoint": endpoint_desc, "summary": summ, "results": results,
        }, f, indent=2, ensure_ascii=False)

    print("\n=== SUMMARY ===")
    print(f"accuracy: {summ['accuracy']:.4f} ({summ['passed']}/{summ['total']})")
    print(f"per body: {summ['per_body']}")
    print(f"per category: {summ['per_category']}")
    print(f"wrote {out_prefix}.json and {out_prefix}.report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
