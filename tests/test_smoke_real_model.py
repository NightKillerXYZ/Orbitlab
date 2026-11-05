import importlib.util
import pathlib


def _load():
    path = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "smoke_real_model.py"
    spec = importlib.util.spec_from_file_location("smoke_real_model", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
