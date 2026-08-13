import pytest

from scripts.publish_lib import layout


def test_engines_are_godot_and_babylon_only():
    assert set(layout.ENGINES) == {"godot", "babylon"}


def test_runtime_asset_dir_differs_per_engine():
    assert layout.runtime_asset_dir("godot") == "assets"
    assert layout.runtime_asset_dir("babylon") == "src/assets"


def test_manifest_tokens_carry_display_name_and_guide_file():
    tokens = layout.manifest_tokens("godot")
    assert tokens["ENGINE_NAME"] == "Godot"
    assert tokens["ENGINE_GUIDE_FILE"] == "godot.md"
    assert tokens["ASSET_SKILL_COMMAND"] == "/asset-gen"


def test_gitignore_includes_engine_specific_and_common_lines():
    lines = layout.gitignore_lines("godot")
    assert ".claude" in lines
    assert "CLAUDE.md" in lines
    assert "godot.md" in lines
    assert ".godot" in lines
    assert "bin/" in lines


def test_command_tokens_are_shared_by_manifest_and_skills():
    """A command token present in one but not the other ships as a literal
    ${TOKEN} in whichever document was missed."""
    manifest = layout.manifest_tokens("godot")
    skills = layout.skill_tokens("godot")
    for key in ("ASSET_SKILL_COMMAND", "KG_HARVEST_COMMAND"):
        assert manifest[key] == skills[key]


def test_unknown_engine_raises():
    with pytest.raises(layout.UnknownEngine):
        layout.manifest_tokens("bevy")
