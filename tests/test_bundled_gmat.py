"""Bundled GMAT discovery: resolution order with temp folders, no network."""
from pathlib import Path

from orbitlab_backend.config import (
    find_bundled_gmat_console,
    resolve_gmat_console_path,
    resolve_gmat_gui_path,
)


def _tree(root: Path, name: str, nested: str = "R2024a"):
    console = root / "tools" / "gmat" / nested / "bin" / name
    console.parent.mkdir(parents=True, exist_ok=True)
    console.write_text("x", encoding="utf-8")
    return console


def test_explicit_console_always_wins(tmp_path):
    assert resolve_gmat_console_path(str(tmp_path / "x" / "GmatConsole.exe"), [tmp_path]) == str(tmp_path / "x" / "GmatConsole.exe")
    assert resolve_gmat_console_path("", [tmp_path]) is None


def test_bundled_exe_found(tmp_path):
    console = _tree(tmp_path, "GmatConsole.exe")
    assert find_bundled_gmat_console([tmp_path]) == str(console)
    assert resolve_gmat_console_path(None, [tmp_path]) == str(console)


def test_bundled_noext_found(tmp_path):
    console = _tree(tmp_path, "GmatConsole")
    assert find_bundled_gmat_console([tmp_path]) == str(console)


def test_console_outside_bin_ignored(tmp_path):
    loose = tmp_path / "tools" / "gmat" / "GmatConsole.exe"
    loose.parent.mkdir(parents=True, exist_ok=True)
    loose.write_text("x", encoding="utf-8")
    assert find_bundled_gmat_console([tmp_path]) is None


def test_none_when_empty(tmp_path):
    (tmp_path / "tools" / "gmat").mkdir(parents=True, exist_ok=True)
    assert find_bundled_gmat_console([tmp_path]) is None
    assert resolve_gmat_console_path(None, [tmp_path]) is None


def test_gui_explicit_wins(tmp_path):
    gui = tmp_path / "custom" / "GMAT.exe"
    assert resolve_gmat_gui_path(str(gui), None, [tmp_path]) == str(gui)


def test_gui_next_to_bundled_console(tmp_path):
    bindir = tmp_path / "tools" / "gmat" / "R2024a" / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    (bindir / "GmatConsole.exe").write_text("x", encoding="utf-8")
    (bindir / "GMAT.exe").write_text("x", encoding="utf-8")
    assert resolve_gmat_gui_path(None, None, [tmp_path]) == str(bindir / "GMAT.exe")


def test_gui_missing_returns_none(tmp_path):
    assert resolve_gmat_gui_path(None, None, [tmp_path]) is None
    assert resolve_gmat_gui_path(None, str(tmp_path / "nowhere" / "GmatConsole.exe"), [tmp_path]) is None
