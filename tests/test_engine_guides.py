from pathlib import Path

import pytest

ENGINES = Path(__file__).resolve().parent.parent / "engines"
GUIDES = sorted(ENGINES.glob("*.md"))


def test_only_supported_engines_have_guides():
    assert {p.stem for p in GUIDES} == {"godot", "babylon"}


@pytest.mark.parametrize("path", GUIDES, ids=lambda p: p.name)
def test_no_xvfb(path: Path):
    """Windows-first: there is no virtual X display to run under."""
    assert "xvfb" not in path.read_text(encoding="utf-8").lower(), path.name


@pytest.mark.parametrize("path", GUIDES, ids=lambda p: p.name)
def test_no_codex_leftovers(path: Path):
    text = path.read_text(encoding="utf-8")
    for banned in (".agents/", "openai.yaml", "Codex"):
        assert banned not in text, f"{path.name}: {banned}"


def _godot() -> str:
    return (ENGINES / "godot.md").read_text(encoding="utf-8")


def test_godot_guide_has_no_csharp_leftovers():
    text = _godot()
    for banned in (
        "partial",
        ".csproj",
        "dotnet build",
        "SetScript()",
        "EnableDynamicLoading",
        "PackedScene",
        "assembly_name",
    ):
        assert banned not in text, banned


def test_godot_guide_covers_the_silent_failures():
    text = _godot()
    for topic in ("sort_custom", "SCRIPT ERROR", "BOM", "Variant"):
        assert topic in text, topic


def test_godot_runners_are_python_with_a_timeout():
    """Their PowerShell equivalents had no timeout, which is how a parse error
    hung a screenshot batch -- a GUI-subsystem exe never exits on its own."""
    text = _godot()
    assert "subprocess" in text
    assert "timeout" in text
    assert "Start-Process" not in text


def test_godot_guide_keeps_upstream_3d_traps():
    text = _godot()
    for topic in ("GenerateNormals", "AABB", "trimesh"):
        assert topic in text, topic
