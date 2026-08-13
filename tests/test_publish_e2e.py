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
