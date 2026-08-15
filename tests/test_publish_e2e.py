from pathlib import Path

import pytest

import publish


def test_publish_godot_creates_expected_files(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out)

    assert (out / "CLAUDE.md").is_file()
    assert (out / "godot.md").is_file()
    assert (out / ".claude" / "skills" / "asset-gen" / "SKILL.md").is_file()
    assert (out / ".gitignore").is_file()


def test_manifest_tokens_are_substituted(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out)
    text = (out / "CLAUDE.md").read_text(encoding="utf-8")
    assert "${" not in text
    assert "Godot" in text


def test_skill_tokens_are_substituted(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("babylon", out)
    text = (out / ".claude" / "skills" / "asset-gen" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "${" not in text
    assert "src/assets" in text


def test_engine_guide_matches_requested_engine(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("babylon", out)
    assert (out / "babylon.md").is_file()
    assert not (out / "godot.md").exists()


def test_force_wipes_existing_target(tmp_path: Path):
    out = tmp_path / "game"
    out.mkdir()
    stale = out / "stale.txt"
    stale.write_text("old", encoding="utf-8")

    publish.publish("godot", out, force=True)
    assert not stale.exists()


def test_without_force_existing_files_survive(tmp_path: Path):
    out = tmp_path / "game"
    out.mkdir()
    keep = out / "keep.txt"
    keep.write_text("mine", encoding="utf-8")

    publish.publish("godot", out)
    assert keep.read_text(encoding="utf-8") == "mine"


def test_existing_gitignore_is_not_overwritten(tmp_path: Path):
    out = tmp_path / "game"
    out.mkdir()
    (out / ".gitignore").write_text("mine\n", encoding="utf-8")

    publish.publish("godot", out)
    assert (out / ".gitignore").read_text(encoding="utf-8") == "mine\n"


def test_unknown_engine_is_rejected(tmp_path: Path):
    with pytest.raises(publish.layout.UnknownEngine):
        publish.publish("bevy", tmp_path / "game")


def test_refuses_to_force_wipe_the_source_repo(tmp_path: Path):
    with pytest.raises(publish.UnsafeTarget):
        publish.publish("godot", publish.REPO_ROOT, force=True)


def test_no_bom_in_any_written_file(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out)
    for path in out.rglob("*"):
        if path.is_file():
            assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), path


def test_pycache_is_not_published(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out)
    assert not list(out.rglob("__pycache__"))


@pytest.mark.parametrize("agent", ["claude", "codex"])
def test_no_unsubstituted_tokens_anywhere_in_the_output(tmp_path: Path, agent: str):
    """Checking only the manifest missed that a token can reach any rendered
    file. .git is git's own boilerplate, not ours."""
    out = tmp_path / "game"
    publish.publish("godot", out, agent=agent, wire_knowledge=False)

    offenders = []
    for path in out.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            if "${" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(out))
        except UnicodeDecodeError:
            continue
    assert not offenders, f"unsubstituted tokens in: {offenders}"


def test_publish_installs_kg_harvest_skill(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out, wire_knowledge=False)
    assert (out / ".claude" / "skills" / "kg-harvest" / "SKILL.md").is_file()


def test_kg_harvest_skill_knows_where_godogen_is(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out, wire_knowledge=False)
    text = (out / ".claude" / "skills" / "kg-harvest" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "${" not in text
    assert str(publish.REPO_ROOT) in text


def _fake_kg(root: Path, name: str = "kg") -> Path:
    kg = root / name
    (kg / "hooks").mkdir(parents=True)
    (kg / "main.js").touch()
    for hook in ("session-start.js", "post-compact.js", "auto-recall.js"):
        (kg / "hooks" / hook).touch()
    return kg


def test_kg_present_writes_wiring(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    out = tmp_path / "game"
    publish.publish("godot", out, kg_home=kg)

    assert (out / ".mcp.json").is_file()
    assert (out / ".claude" / "settings.json").is_file()
    assert (out / ".kg").is_dir()


def test_kg_wiring_references_both_databases(tmp_path: Path):
    kg = _fake_kg(tmp_path)
    out = tmp_path / "game"
    publish.publish("godot", out, kg_home=kg)

    mcp = (out / ".mcp.json").read_text(encoding="utf-8")
    assert "craft.db" in mcp and "game.db" in mcp


def test_kg_absent_still_publishes(tmp_path: Path, capsys, monkeypatch):
    """kg_home=None means 'discover', so the discovery itself has to be
    neutralised -- otherwise this passes only on a machine without kg."""
    monkeypatch.setattr(publish.kgwire.external, "ANCHORS", ())
    monkeypatch.delenv("GODOGEN_KG_HOME", raising=False)

    out = tmp_path / "game"
    publish.publish("godot", out, wire_knowledge=True, kg_home=None)

    assert (out / "CLAUDE.md").is_file()
    assert not (out / ".mcp.json").exists()
    assert "no kg installation found" in capsys.readouterr().err


def test_two_kg_installations_are_named_when_publishing(
    tmp_path: Path, capsys, monkeypatch
):
    """Publishing is where a shadowed install does the most damage: the chosen
    path is baked into .mcp.json and every hook command, and this runs once per
    game rather than once per machine like bootstrap."""
    anchor = tmp_path / "anchor"
    first = _fake_kg(anchor, "kg")
    second = _fake_kg(anchor, "Multi-knowledgeGraph")
    monkeypatch.setattr(publish.kgwire.external, "ANCHORS", (anchor,))
    monkeypatch.delenv("GODOGEN_KG_HOME", raising=False)

    publish.publish("godot", tmp_path / "game", kg_home=None)

    err = capsys.readouterr().err
    assert str(first) in err
    assert str(second) in err
    assert "GODOGEN_KG_HOME" in err


def test_an_explicit_kg_home_is_never_reported_as_ambiguous(
    tmp_path: Path, capsys, monkeypatch
):
    """Naming the install is a choice, so there is nothing to disambiguate."""
    anchor = tmp_path / "anchor"
    _fake_kg(anchor, "kg")
    chosen = _fake_kg(anchor, "Multi-knowledgeGraph")
    monkeypatch.setattr(publish.kgwire.external, "ANCHORS", (anchor,))
    monkeypatch.delenv("GODOGEN_KG_HOME", raising=False)

    publish.publish("godot", tmp_path / "game", kg_home=chosen)

    assert "installations found" not in capsys.readouterr().err


def test_gitignore_covers_the_knowledge_cache(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out, wire_knowledge=False)
    ignored = (out / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".kg/" in ignored
    assert ".mcp.json" in ignored


def test_name_creates_the_game_under_the_games_root(tmp_path: Path, monkeypatch):
    """Having a default at all is the point: without one each game lands
    wherever was convenient that day."""
    monkeypatch.setattr(publish.config, "games_root", lambda *a: tmp_path / "games")
    assert publish.main(["--engine", "godot", "--name", "tower"]) == 0
    assert (tmp_path / "games" / "tower" / "CLAUDE.md").is_file()


def test_name_and_out_together_are_rejected(tmp_path: Path):
    with pytest.raises(SystemExit):
        publish.main(["--engine", "godot", "--name", "a", "--out", str(tmp_path)])


def test_neither_name_nor_out_is_rejected():
    with pytest.raises(SystemExit):
        publish.main(["--engine", "godot"])


def test_out_still_works_for_a_one_off_location(tmp_path: Path):
    out = tmp_path / "somewhere"
    assert publish.main(["--engine", "godot", "--out", str(out)]) == 0
    assert (out / "CLAUDE.md").is_file()
