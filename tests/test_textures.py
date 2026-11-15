"""Planet texture assets the 3D player requests (JPEG header + non-empty)."""
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
TEXDIR = REPO / "UIUX" / "OrbitlabUI Main" / "assets" / "textures"

# Mirrors view3d.js textureFileFor(): 'assets/textures/' + lower(body) + '.jpg'.
BODIES = ["Earth", "Moon", "Mars", "Mercury", "Venus", "Jupiter", "Sun"]


def _expected_names():
    return ["assets/textures/" + b.lower() + ".jpg" for b in BODIES]


def test_every_requested_texture_exists_and_is_jpeg():
    assert TEXDIR.is_dir(), TEXDIR
    for body, rel in zip(BODIES, _expected_names()):
        assert rel == "assets/textures/" + body.lower() + ".jpg"
        path = TEXDIR / (body.lower() + ".jpg")
        assert path.is_file(), "missing player texture: %s" % rel
        data = path.read_bytes()
        assert len(data) > 0, "empty texture: %s" % rel
        assert data[:2] == b"\xff\xd8", "not a JPEG (SOI header): %s" % rel
        assert data[-2:] == b"\xff\xd9", "truncated JPEG (EOI trailer): %s" % rel


def test_texture_player_rule_matches_view3d():
    src = (REPO / "UIUX" / "OrbitlabUI Main" / "view3d.js").read_text(encoding="utf-8")
    assert "function textureFileFor(body)" in src
    assert "'assets/textures/'" in src and ".toLowerCase()" in src
