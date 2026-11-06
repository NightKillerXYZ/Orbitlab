import importlib.util
import pathlib


def _load():
    path = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "debug_extractor.py"
    spec = importlib.util.spec_from_file_location("debug_extractor", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_missing_vars_exit_2(monkeypatch):
    mod = _load()
    for name in ("EXTRACTOR_BASE_URL", "EXTRACTOR_API_KEY", "EXTRACTOR_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert mod.main([]) == 2


def test_missing_key_only_exit_2(monkeypatch):
    mod = _load()
    monkeypatch.setenv("EXTRACTOR_BASE_URL", "http://example.invalid")
    monkeypatch.delenv("EXTRACTOR_API_KEY", raising=False)
    monkeypatch.setenv("EXTRACTOR_MODEL", "m")
    assert mod.main([]) == 2
