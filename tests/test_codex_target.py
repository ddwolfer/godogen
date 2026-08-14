"""Codex is a second publish target with a smaller knowledge story.

It has SessionStart, UserPromptSubmit and PostToolUse, but no event that fires
after context compaction -- and a generation run compacts several times over
hours. These tests pin the difference so it cannot quietly drift into looking
like parity.
"""

import json
import tomllib
from pathlib import Path

import pytest

import publish
from scripts.publish_lib import kgwire, layout


def _fake_kg(root: Path) -> Path:
    kg = root / "kg"
    (kg / "hooks").mkdir(parents=True)
    (kg / "main.js").touch()
    for hook in ("session-start.js", "post-compact.js", "auto-recall.js"):
        (kg / "hooks" / hook).touch()
    return kg


# --- layout ---------------------------------------------------------------


def test_both_agents_are_publish_targets():
    assert set(layout.AGENTS) == {"claude", "codex"}


def test_each_agent_has_its_own_manifest_and_skills_dir():
    assert layout.manifest_file("claude") == "CLAUDE.md"
    assert layout.manifest_file("codex") == "AGENTS.md"
    assert layout.skills_dir("claude") == ".claude/skills"
    assert layout.skills_dir("codex") == ".agents/skills"


def test_skill_commands_use_each_agents_prefix():
    assert layout.manifest_tokens("godot", "claude")["ASSET_SKILL_COMMAND"] == "/asset-gen"
    assert layout.manifest_tokens("godot", "codex")["ASSET_SKILL_COMMAND"] == "$asset-gen"


def test_skill_dir_token_follows_the_agent():
    assert ".agents/skills" in layout.skill_tokens("godot", "codex")["ASSET_GEN_SKILL_DIR"]


def test_gitignore_covers_the_right_agents_files():
    codex = layout.gitignore_lines("godot", "codex")
    assert "AGENTS.md" in codex and ".agents" in codex and ".codex" in codex
    assert "CLAUDE.md" not in codex


def test_unknown_agent_raises():
    with pytest.raises(layout.UnknownAgent):
        layout.manifest_tokens("godot", "gemini")


# --- wiring ---------------------------------------------------------------


def test_codex_mcp_config_is_valid_toml_with_both_databases(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    text = kgwire.codex_mcp_config(kg, tmp_path / "craft.db", tmp_path / "game.db")
    parsed = tomllib.loads(text)
    assert set(parsed["mcp_servers"]) == {"kg-craft", "kg-game"}
    assert "craft.db" in " ".join(parsed["mcp_servers"]["kg-craft"]["args"])


def test_codex_toml_escapes_windows_backslashes(tmp_path: Path):
    """A raw C:\\path in TOML is an invalid escape; tomllib would reject it."""
    kg = _fake_kg(tmp_path)
    text = kgwire.codex_mcp_config(kg, tmp_path / "craft.db", tmp_path / "game.db")
    tomllib.loads(text)  # would raise on a bad escape


def test_codex_has_no_post_compaction_hook(tmp_path: Path):
    """The gap worth remembering: Codex offers no compaction event, so nothing
    re-injects knowledge after a run compacts."""
    kg = _fake_kg(tmp_path)
    settings = kgwire.codex_hook_settings(kg, tmp_path / "craft.db", tmp_path / "game.db")
    rendered = json.dumps(settings)
    assert "post-compact" not in rendered
    assert set(settings["hooks"]) <= {"SessionStart", "UserPromptSubmit", "PostToolUse"}


def test_codex_wires_the_events_it_does_have(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    settings = kgwire.codex_hook_settings(
        kg, tmp_path / "craft.db", tmp_path / "game.db", harvest_script=tmp_path / "h.py"
    )
    assert "session-start" in json.dumps(settings["hooks"]["SessionStart"])
    assert "auto-recall" in json.dumps(settings["hooks"]["UserPromptSubmit"])
    assert settings["hooks"]["PostToolUse"][0]["matcher"] == "Bash"


def test_codex_uses_its_own_timeout_field(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    settings = kgwire.codex_hook_settings(kg, tmp_path / "craft.db", tmp_path / "game.db")
    hook = settings["hooks"]["SessionStart"][0]["hooks"][0]
    assert "timeoutSec" in hook and "timeout" not in hook


def test_codex_injects_both_databases(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    settings = kgwire.codex_hook_settings(kg, tmp_path / "craft.db", tmp_path / "game.db")
    commands = json.dumps(settings["hooks"]["SessionStart"])
    assert "craft.db" in commands and "game.db" in commands


# --- end to end -----------------------------------------------------------


def test_publish_codex_writes_agents_md_not_claude_md(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out, agent="codex", wire_knowledge=False)
    assert (out / "AGENTS.md").is_file()
    assert not (out / "CLAUDE.md").exists()
    assert (out / ".agents" / "skills" / "asset-gen" / "SKILL.md").is_file()
    assert not (out / ".claude").exists()


def test_publish_codex_generates_skill_metadata(tmp_path: Path):
    """Codex discovers skills through agents/openai.yaml, not frontmatter."""
    out = tmp_path / "game"
    publish.publish("godot", out, agent="codex", wire_knowledge=False)
    for skill in ("asset-gen", "game-design", "game-ui", "kg-harvest"):
        assert (out / ".agents" / "skills" / skill / "agents" / "openai.yaml").is_file()


def test_publish_codex_substitutes_dollar_prefixed_commands(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out, agent="codex", wire_knowledge=False)
    text = (out / "AGENTS.md").read_text(encoding="utf-8")
    assert "${" not in text
    assert "$game-design" in text


def test_publish_codex_writes_codex_config(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    out = tmp_path / "game"
    publish.publish("godot", out, agent="codex", kg_home=kg)
    assert (out / ".codex" / "config.toml").is_file()
    assert (out / ".codex" / "hooks.json").is_file()
    assert not (out / ".mcp.json").exists()


def test_publish_codex_warns_about_the_compaction_gap(tmp_path: Path, capsys):
    kg = _fake_kg(tmp_path)
    publish.publish("godot", tmp_path / "game", agent="codex", kg_home=kg)
    err = capsys.readouterr().err
    assert "no post-compaction hook" in err
    assert "codex_hooks = true" in err


def test_claude_remains_the_default(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out, wire_knowledge=False)
    assert (out / "CLAUDE.md").is_file()
