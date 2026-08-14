from pathlib import Path

import pytest

from scripts.publish_lib import external


def _install(root: Path, tool: external.Tool, name: str | None = None) -> Path:
    home = root / (name or tool.dir_names[0])
    for marker in tool.markers:
        target = home / marker
        if "." in marker:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        else:
            target.mkdir(parents=True, exist_ok=True)
    return home


@pytest.fixture
def anchored(tmp_path, monkeypatch):
    monkeypatch.setattr(external, "ANCHORS", (tmp_path,))
    return tmp_path


def test_both_tools_are_declared():
    assert {t.name for t in external.TOOLS} == {"kg", "ACE Studio"}


def test_every_tool_searches_the_default_clone_name():
    """`git clone <url>` names the directory after the repo, and most people
    do not rename it -- searching only the short name missed a real install."""
    for tool in external.TOOLS:
        assert len(tool.dir_names) >= 2, tool.name


def test_finds_an_installation_under_either_name(anchored):
    for name in external.KG.dir_names:
        home = _install(anchored, external.KG, name)
        assert external.KG.find({}) is not None
        for marker in external.KG.markers:
            path = home / marker
            (path.rmdir() if path.is_dir() else path.unlink())
        home.rmdir()


def test_a_directory_missing_a_marker_is_not_an_installation(anchored):
    (anchored / "kg").mkdir()
    assert external.KG.find({}) is None


def test_env_var_wins_over_a_found_installation(anchored, tmp_path):
    _install(anchored, external.KG)
    elsewhere = _install(tmp_path / "other", external.KG)
    assert external.KG.find({external.KG.env_var: str(elsewhere)}) == elsewhere


def test_a_wrong_env_var_raises_rather_than_falling_back(anchored):
    """Falling back would wire a knowledge base the user did not choose."""
    _install(anchored, external.KG)
    with pytest.raises(external.NotFound):
        external.KG.find({external.KG.env_var: str(anchored / "nope")})


def test_one_installation_needs_no_warning(anchored):
    _install(anchored, external.KG)
    assert external.KG.shadow_warning({}) is None


def test_no_installation_needs_no_warning(anchored):
    assert external.KG.shadow_warning({}) is None


def test_two_installations_warn_and_name_both(anchored):
    """The checkout sorts first, so cloning a second copy into it shadows the
    one the user already had -- along with its model cache. Nothing else
    surfaces that: the index builds fine against the new empty one."""
    first = _install(anchored, external.KG, "kg")
    second = _install(anchored, external.KG, "Multi-knowledgeGraph")

    warning = external.KG.shadow_warning({})
    assert warning is not None
    assert str(first) in warning and str(second) in warning
    assert external.KG.env_var in warning


def test_an_explicit_choice_is_never_reported_as_ambiguous(anchored):
    _install(anchored, external.KG, "kg")
    chosen = _install(anchored, external.KG, "Multi-knowledgeGraph")
    assert external.KG.shadow_warning({external.KG.env_var: str(chosen)}) is None


def test_find_agrees_with_the_first_of_find_all(anchored):
    _install(anchored, external.KG, "kg")
    _install(anchored, external.KG, "Multi-knowledgeGraph")
    assert external.KG.find({}) == external.KG.find_all({})[0]


def test_missing_message_names_the_env_var_and_the_repo():
    for tool in external.TOOLS:
        message = tool.missing_message()
        assert tool.env_var in message
        assert "git clone" in message
