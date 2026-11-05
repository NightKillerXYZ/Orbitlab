import importlib.util
import pathlib


def _load():
    path = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "smoke_real_model.py"
    spec = importlib.util.spec_from_file_location("smoke_real_model", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_skip_extract_uses_prebuilt_sent_without_extractor(monkeypatch):
    import asyncio
    import orbitlab_backend.frontstep.extractor as extmod

    mod = _load()

    def _boom(*a, **k):
        raise AssertionError("extractor must not be called with --skip-extract")

    monkeypatch.setattr(extmod.FrontStepExtractor, "process", _boom)
    monkeypatch.setattr(extmod.FrontStepExtractor, "process_sync", _boom)

    sent = dict(mod.SKIP_PROMPTS[3][1])
    canned = {
        "version": "1.0",
        "experimentName": sent["experimentName"],
        "spacecraft": {"name": "SC_" + sent["spacecraftName"], "dryMassKg": sent["dryMassKg"]},
        "centralBody": sent["centralBody"],
        "initialOrbit": {"type": "Keplerian", "coordinateSystem": "EarthMJ2000Eq", "elements": {
            "semiMajorAxisKm": sent["semiMajorAxisKm"], "eccentricity": sent["eccentricity"],
            "inclinationDeg": sent["inclinationDeg"], "raanDeg": 0,
            "argumentOfPeriapsisDeg": 0, "trueAnomalyDeg": 0}},
        "propagation": {"integrator": "RungeKutta89", "stopCondition": {
            "type": sent["stopConditionType"], "value": sent["durationValue"]}, "stepSizeSecs": 60},
        "maneuvers": [],
    }

    class FakeClient:
        async def interpret_prompt(self, prompt, warming_callback=None):
            assert prompt == mod.SKIP_PROMPTS[3][0]
            return canned

    entry = asyncio.run(mod.run_one(mod.SKIP_PROMPTS[3][0], FakeClient(), sent=sent))
    assert entry["verdict"] == "PASS"
    assert entry["sent"]["semiMajorAxisKm"] == 6528.136


def test_missing_both_vars_exit_2(monkeypatch):
    mod = _load()
    monkeypatch.delenv("ORBITLAB_MODEL_URL", raising=False)
    monkeypatch.delenv("ORBITLAB_MODEL_KEY", raising=False)
    assert mod.main([]) == 2


def test_missing_key_only_exit_2(monkeypatch):
    mod = _load()
    monkeypatch.setenv("ORBITLAB_MODEL_URL", "http://example.invalid")
    monkeypatch.delenv("ORBITLAB_MODEL_KEY", raising=False)
    assert mod.main([]) == 2


def test_missing_url_only_exit_2(monkeypatch):
    mod = _load()
    monkeypatch.delenv("ORBITLAB_MODEL_URL", raising=False)
    monkeypatch.setenv("ORBITLAB_MODEL_KEY", "dummy")
    assert mod.main([]) == 2
