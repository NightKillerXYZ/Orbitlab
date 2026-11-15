"""Unit tests for scripts/realistic_cases.py (fake HTTP, no network, no GMAT)."""
import importlib.util
import pathlib


def _load():
    path = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "realistic_cases.py"
    spec = importlib.util.spec_from_file_location("realistic_cases", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_case_table_shape():
    mod = _load()
    assert len(mod.CASES) == 14
    ids = [c["id"] for c in mod.CASES]
    assert ids == list(range(1, 15))
    for c in mod.CASES:
        assert c["prompt"] and isinstance(c["prompt"], str)
        exp = c["expected"]
        assert exp in ("success", "needs_clarification", "info") or exp.startswith("failed_at:"), exp


def _job(status, error=None, result=None):
    j = {"status": status}
    if error is not None:
        j["error"] = error
    if result is not None:
        j["result"] = result
    return j


def test_verdict_logic():
    mod = _load()
    ok = mod.verdict_for("success", {"actual": "success"})
    assert ok == "PASS"
    assert mod.verdict_for("success", {"actual": "failed", "code": "x", "stage": "y"}) == "FAIL"
    assert mod.verdict_for("needs_clarification", {"actual": "failed", "code": "needs_clarification", "stage": "extract"}) == "PASS"
    assert mod.verdict_for("needs_clarification", {"actual": "failed", "code": "other", "stage": "extract"}) == "FAIL"
    assert mod.verdict_for("failed_at:validate", {"actual": "failed", "code": "validation_failed", "stage": "validate"}) == "PASS"
    assert mod.verdict_for("failed_at:validate", {"actual": "failed", "code": "x", "stage": "simulate"}) == "FAIL"
    assert mod.verdict_for("info", {"actual": "timeout"}) == "INFO"
    assert mod.verdict_for("info", {"actual": "success"}) == "INFO"
    assert mod.verdict_for("bogus", {"actual": "success"}) == "FAIL"


def test_parse_job_success_and_failure():
    mod = _load()
    good = _job("success", result={
        "explanationSource": "model",
        "experiment": {"initialOrbit": {"elements": {"semiMajorAxisKm": 6778.136, "eccentricity": 0}},
                       "propagation": {"stopCondition": {"type": "ElapsedDays", "value": 1}}}})
    p = mod.parse_job(good)
    assert (p["actual"], p["stage"], p["code"]) == ("success", "", "")
    assert p["explanationSource"] == "model"
    assert p["a"] == 6778.136 and p["e"] == 0
    assert p["duration"] == "1 ElapsedDays"
    bad = _job("failed", error={"stage": "validate", "code": "validation_failed",
                                "details": {"explanation": "too low"}})
    q = mod.parse_job(bad)
    assert (q["stage"], q["code"], q["explanation"]) == ("validate", "validation_failed", "too low")
    assert q["a"] is None and q["e"] is None and q["duration"] is None
    assert mod.parse_job({})["actual"] is None
    assert mod.parse_job(None)["actual"] is None


def test_observations_and_markdown():
    mod = _load()
    rows = [
        {"id": 1, "prompt": "p1", "expected": "success", "actual": "success", "stage": "",
         "code": "", "explanationSource": "model", "seconds": 12.0, "a": 1, "e": 0,
         "duration": "1 ElapsedDays", "verdict": "PASS"},
        {"id": 2, "prompt": "p2", "expected": "success", "actual": "failed", "stage": "extract",
         "code": "extraction_error", "explanationSource": "", "seconds": 3.0, "a": None,
         "e": None, "duration": None, "verdict": "FAIL"},
        {"id": 3, "prompt": "p3", "expected": "info", "actual": "timeout", "stage": "poll",
         "code": "timeout", "explanationSource": "fallback", "seconds": 400.0, "a": None,
         "e": None, "duration": None, "verdict": "INFO"},
    ]
    obs = mod.compute_observations(rows)
    assert obs["total"] == 3 and obs["non_info"] == 2 and obs["passed"] == 1
    assert obs["failed_ids"] == [2]
    assert obs["slowest_id"] == 3 and obs["slowest_seconds"] == 400.0
    assert obs["fallback_ids"] == [3]
    md = mod.render_markdown(rows, obs, {"when": "t", "mode_label": "demo", "server_mode": "demo", "timeout_s": 400})
    assert "| id | prompt | expected | actual | stage | code | explSrc | seconds | a | e | duration | verdict |" in md
    assert "fallback" in md


def test_safe_base_strips_secrets():
    mod = _load()
    assert mod.safe_base("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
    assert mod.safe_base("http://user:key@h:1/x?y=2#f") == "http://h:1"
    assert "key" not in mod.safe_base("http://user:key@h:1/x?y=2#f")


def test_run_case_with_fake_transport(monkeypatch):
    mod = _load()
    seen = {}

    def fake_post(base, path, payload, timeout_s=30.0):
        seen["post"] = (base, path, payload)
        assert set(payload) == {"text"}
        return {"id": "job-1"}

    def fake_get(base, path, timeout_s=30.0):
        seen.setdefault("gets", []).append(path)
        assert path == "/api/experiments/job-1"
        return {"status": "success",
                "result": {"explanationSource": "fallback",
                           "experiment": {"initialOrbit": {"elements": {"semiMajorAxisKm": 7000.0, "eccentricity": 0.1}},
                                         "propagation": {"stopCondition": {"type": "ElapsedHours", "value": 5}}}}}

    monkeypatch.setattr(mod, "api_post", fake_post)
    monkeypatch.setattr(mod, "api_get", fake_get)
    entry = mod.run_case("http://127.0.0.1:8000", {"id": 1, "prompt": "x", "expected": "success"}, 400.0)
    assert entry["verdict"] == "PASS"
    assert entry["a"] == 7000.0 and entry["e"] == 0.1
    assert entry["duration"] == "5 ElapsedHours"
    assert entry["explanationSource"] == "fallback"
    assert entry["seconds"] >= 0


def test_run_case_timeout_is_fail(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "api_post", lambda *a, **k: {"id": "j"})
    monkeypatch.setattr(mod, "api_get", lambda *a, **k: {"status": "running"})
    entry = mod.run_case("http://x", {"id": 2, "prompt": "x", "expected": "success"}, 0.0)
    assert entry["actual"] == "timeout"
    assert entry["verdict"] == "FAIL"
    entry2 = mod.run_case("http://x", {"id": 3, "prompt": "x", "expected": "info"}, 0.0)
    assert entry2["verdict"] == "INFO"


def test_main_exit_codes_and_only_filter(tmp_path, monkeypatch):
    mod = _load()
    calls = []

    def fake_post(base, path, payload, timeout_s=30.0):
        calls.append(payload["text"])
        return {"id": "j"}

    def fake_get(base, path, timeout_s=30.0):
        if "health" in path:
            return {"status": "ok", "mode": "demo"}
        return {"status": "success", "result": {"experiment": {
            "initialOrbit": {"elements": {"semiMajorAxisKm": 1, "eccentricity": 0}},
            "propagation": {"stopCondition": {"type": "ElapsedDays", "value": 1}}}}}

    monkeypatch.setattr(mod, "api_post", fake_post)
    monkeypatch.setattr(mod, "api_get", fake_get)
    out = str(tmp_path / "res.md")
    assert mod.main(["--only", "1,2", "--out", out, "--mode", "real"]) == 0
    assert len(calls) == 2
    text = pathlib.Path(out).read_text(encoding="utf-8")
    assert "| 1 |" in text and "| 2 |" in text
    assert "| 3 |" not in text


def test_main_fails_on_failed_case(tmp_path, monkeypatch):
    mod = _load()

    def fake_post(base, path, payload, timeout_s=30.0):
        return {"id": "j"}

    def fake_get(base, path, timeout_s=30.0):
        if "health" in path:
            return {"status": "ok"}
        return {"status": "failed", "error": {"stage": "extract", "code": "extraction_error"}}

    monkeypatch.setattr(mod, "api_post", fake_post)
    monkeypatch.setattr(mod, "api_get", fake_get)
    out = str(tmp_path / "res2.md")
    assert mod.main(["--only", "1", "--out", out]) == 1
