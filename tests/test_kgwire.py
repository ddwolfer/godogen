import json
from pathlib import Path

from scripts.publish_lib import kgwire


def _fake_kg(root: Path) -> Path:
    kg = root / "kg"
    (kg / "hooks").mkdir(parents=True)
    (kg / "main.js").touch()
    for hook in ("session-start.js", "post-compact.js", "auto-recall.js"):
        (kg / "hooks" / hook).touch()
    return kg


def test_env_override_wins(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    assert kgwire.find_kg_home({"GODOGEN_KG_HOME": str(kg)}) == kg


def test_missing_kg_returns_none(tmp_path: Path):
    assert kgwire.find_kg_home({"GODOGEN_KG_HOME": str(tmp_path / "nope")}) is None


def test_directory_without_main_js_is_not_kg(tmp_path: Path):
    bare = tmp_path / "kg"
    bare.mkdir()
    assert kgwire.find_kg_home({"GODOGEN_KG_HOME": str(bare)}) is None


def test_mcp_config_declares_two_servers(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    cfg = kgwire.mcp_config(kg, tmp_path / "craft.db", tmp_path / "game.db")
    assert set(cfg["mcpServers"]) == {"kg-craft", "kg-game"}


def test_mcp_servers_point_at_their_own_db(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    cfg = kgwire.mcp_config(kg, tmp_path / "craft.db", tmp_path / "game.db")
    craft = " ".join(cfg["mcpServers"]["kg-craft"]["args"])
    game = " ".join(cfg["mcpServers"]["kg-game"]["args"])
    assert "craft.db" in craft and "game.db" not in craft
    assert "game.db" in game and "craft.db" not in game


def test_mcp_config_is_json_serialisable(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    cfg = kgwire.mcp_config(kg, tmp_path / "craft.db", tmp_path / "game.db")
    assert json.loads(json.dumps(cfg)) == cfg


def test_injecting_hooks_run_against_both_dbs(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    settings = kgwire.hook_settings(kg, tmp_path / "craft.db", tmp_path / "game.db")
    compact = [
        g for g in settings["hooks"]["SessionStart"] if g["matcher"] == "compact"
    ][0]
    assert len(compact["hooks"]) == 2
    commands = " ".join(h["command"] for h in compact["hooks"])
    assert "craft.db" in commands and "game.db" in commands


def test_craft_is_injected_before_game(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    settings = kgwire.hook_settings(kg, tmp_path / "craft.db", tmp_path / "game.db")
    prompt = settings["hooks"]["UserPromptSubmit"][0]["hooks"]
    assert "craft.db" in prompt[0]["command"]
    assert "game.db" in prompt[1]["command"]


def test_all_three_injecting_hooks_are_wired(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    settings = kgwire.hook_settings(kg, tmp_path / "craft.db", tmp_path / "game.db")
    matchers = {g["matcher"] for g in settings["hooks"]["SessionStart"]}
    assert matchers == {"startup", "compact"}
    assert "UserPromptSubmit" in settings["hooks"]


def test_search_enforcer_is_not_wired(tmp_path: Path):
    """Its read-tool prefixes are hardcoded to mcp__knowledge-graph__, which
    never matches the kg-craft / kg-game server names — it would block every
    write until the circuit breaker fires. See Task 18."""
    kg = _fake_kg(tmp_path)
    settings = kgwire.hook_settings(kg, tmp_path / "craft.db", tmp_path / "game.db")
    assert "PreToolUse" not in settings["hooks"]
    rendered = json.dumps(settings)
    assert "search-enforcer" not in rendered


def test_harvest_hook_absent_when_no_script_given(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    settings = kgwire.hook_settings(kg, tmp_path / "craft.db", tmp_path / "game.db")
    assert "PostToolUse" not in settings["hooks"]


def test_harvest_hook_targets_bash_and_the_game_db(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    script = tmp_path / "harvest_commit.py"
    script.touch()
    settings = kgwire.hook_settings(
        kg, tmp_path / "craft.db", tmp_path / "game.db", harvest_script=script
    )
    group = settings["hooks"]["PostToolUse"][0]
    assert group["matcher"] == "Bash"
    command = group["hooks"][0]["command"]
    assert "game.db" in command
    assert "craft.db" not in command, "a game's lessons belong to that game"


def test_hook_commands_use_absolute_paths(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    settings = kgwire.hook_settings(kg, tmp_path / "craft.db", tmp_path / "game.db")
    for group in settings["hooks"]["SessionStart"]:
        for hook in group["hooks"]:
            assert str(kg) in hook["command"]
