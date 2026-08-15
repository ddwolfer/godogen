from pathlib import Path

import pytest

from scripts.publish_lib import config


def test_parses_key_value_lines():
    parsed = config.parse_env("A=1\nB=two\n")
    assert parsed == {"A": "1", "B": "two"}


def test_ignores_comments_and_blanks():
    assert config.parse_env("# note\n\nA=1\n  # indented\n") == {"A": "1"}


def test_keeps_urls_and_windows_paths_intact():
    """Values are paths and URLs. A config format with quoting surprises in it
    is a bug source, so there is no unquoting to get wrong."""
    parsed = config.parse_env("U=http://127.0.0.1:8188\nP=C:\\Program Files\\b.exe\n")
    assert parsed["U"] == "http://127.0.0.1:8188"
    assert parsed["P"] == "C:\\Program Files\\b.exe"


def test_environment_overrides_the_file(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("ASSET_2D=comfyui\n", encoding="utf-8")
    loaded = config.load(env_file, environ={"ASSET_2D": "grok"})
    assert loaded["ASSET_2D"] == "grok"


def test_blank_environment_does_not_override(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("ASSET_2D=comfyui\n", encoding="utf-8")
    assert config.load(env_file, environ={"ASSET_2D": ""})["ASSET_2D"] == "comfyui"


def test_a_missing_file_is_not_an_error(tmp_path: Path):
    assert config.load(tmp_path / "nope", environ={}) == {}


def test_each_kind_defaults_to_its_first_backend():
    assert config.backend("ASSET_3D", {}) == "blender"
    assert config.backend("ASSET_2D", {}) == "comfyui"
    assert config.backend("ASSET_AUDIO", {}) == "ace"


def test_kinds_are_independent():
    """Cloud images alongside local modelling is a normal setup, which is why
    this is three axes and not one local-or-cloud switch."""
    chosen = {"ASSET_3D": "blender", "ASSET_2D": "gemini"}
    assert config.backend("ASSET_3D", chosen) == "blender"
    assert config.backend("ASSET_2D", chosen) == "gemini"


def test_an_invalid_backend_is_rejected():
    with pytest.raises(config.UnknownBackend):
        config.backend("ASSET_2D", {"ASSET_2D": "dalle"})


def test_an_unknown_kind_is_rejected():
    with pytest.raises(config.UnknownBackend):
        config.backend("ASSET_SMELL", {})


def test_missing_requirements_names_what_each_backend_needs():
    gaps = config.missing_requirements({"ASSET_3D": "tripo3d", "ASSET_2D": "none",
                                        "ASSET_AUDIO": "none"})
    assert gaps == {"tripo3d": ["TRIPO3D_API_KEY"]}


def test_nothing_missing_when_requirements_are_present():
    chosen = {"ASSET_3D": "none", "ASSET_2D": "grok", "ASSET_AUDIO": "none",
              "XAI_API_KEY": "k"}
    assert config.missing_requirements(chosen) == {}


def test_none_requires_nothing():
    allnone = {"ASSET_3D": "none", "ASSET_2D": "none", "ASSET_AUDIO": "none"}
    assert config.missing_requirements(allnone) == {}


def test_describe_names_all_three_kinds():
    text = config.describe({"ASSET_3D": "blender", "ASSET_2D": "gemini",
                            "ASSET_AUDIO": "none"})
    assert "3D" in text and "2D" in text and "audio" in text
    assert "Blender" in text and "Gemini" in text


def test_describe_marks_cost():
    """The agent should be able to tell from one line whether generating
    costs money."""
    text = config.describe({"ASSET_2D": "grok", "ASSET_3D": "none",
                            "ASSET_AUDIO": "none"})
    assert "paid" in text


def test_uses_cloud_detects_any_paid_backend():
    assert config.uses_cloud({"ASSET_3D": "tripo3d", "ASSET_2D": "comfyui",
                              "ASSET_AUDIO": "ace"})
    assert not config.uses_cloud({"ASSET_3D": "blender", "ASSET_2D": "comfyui",
                                  "ASSET_AUDIO": "ace"})


def test_uses_cloud_checks_every_axis_not_just_the_first():
    """any() short-circuits, so a paid backend on the last axis has to be
    found too -- and an invalid value on a later axis has to still raise."""
    assert config.uses_cloud({"ASSET_3D": "blender", "ASSET_2D": "grok",
                              "ASSET_AUDIO": "ace"})
    with pytest.raises(config.UnknownBackend):
        config.uses_cloud({"ASSET_3D": "blender", "ASSET_2D": "comfyui",
                           "ASSET_AUDIO": "local"})


def test_example_file_documents_every_setting():
    """.env.example is the only discoverable list of what can be configured."""
    text = (config.REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for key in list(config.BACKENDS) + ["GODOGEN_KG_HOME", "GODOT_PATH"]:
        assert key in text, key
    for reqs in config.REQUIREMENTS.values():
        for key in reqs:
            assert key in text, key


def test_example_file_lists_every_valid_backend():
    text = (config.REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for choices in config.BACKENDS.values():
        for choice in choices:
            assert choice in text, choice


def test_games_root_defaults_beside_the_generator():
    """A game is its own repo with its own remote -- the same kind of thing as
    the knowledge engine, and kept beside godogen rather than inside it."""
    assert config.games_root({}) == config.REPO_ROOT.parent / "games"


def test_games_root_is_configurable():
    assert config.games_root({"GAMES_ROOT": "E:/elsewhere"}) == Path("E:/elsewhere")


def test_games_root_is_documented():
    text = (config.REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "GAMES_ROOT" in text
