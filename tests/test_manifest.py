from pathlib import Path

MANIFEST = Path(__file__).resolve().parent.parent / "prompts" / "runtime.md"


def _text() -> str:
    return MANIFEST.read_text(encoding="utf-8")


def test_manifest_is_engine_neutral():
    """It renders for every engine, so it cannot name one."""
    text = _text()
    for banned in ("GDScript", ".tscn", "C#", "TypeScript", "godot.md", "babylon.md"):
        assert banned not in text, banned


def test_manifest_has_no_absolute_paths():
    text = _text()
    for banned in ("C:\\", "D:\\", "/usr/", "~/"):
        assert banned not in text, banned


def test_manifest_covers_the_four_methods():
    text = _text()
    for topic in ("決定論", "呈現層", "旋鈕", "驗收"):
        assert topic in text, topic


def test_manifest_keeps_its_tokens():
    text = _text()
    for token in ("${ENGINE_NAME}", "${ENGINE_GUIDE_FILE}", "${ASSET_SKILL_COMMAND}"):
        assert token in text, token


def test_manifest_still_fixes_durable_state_and_proof():
    text = _text()
    assert "README.md" in text
    assert "${KG_HARVEST_COMMAND}" in text


def test_the_screenshot_layer_is_delegated_to_fresh_eyes():
    """The builder cannot see "made it but you cannot see it": knowing the
    fireball is there is enough to see it. Layer 2 only catches anything if
    the reader does not know what was intended."""
    text = _text()
    assert "subagent" in text
    assert "不要告訴它你做了什麼" in text


def test_the_reviewer_is_told_to_carry_its_own_yardstick():
    """A subagent gets no knowledge-base injection -- SessionStart and
    UserPromptSubmit fire for the session, and SubagentStart cannot add
    context. So whatever the reviewer needs has to be in the prompt."""
    assert "判準要你寫進 prompt" in _text()


def test_the_ladder_does_not_also_say_look_at_it_yourself():
    """Delegating layer 2 and doing it yourself are contradictory orders about
    the same layer, and a manifest holding both gets obeyed in whichever
    direction is cheaper that minute."""
    assert "是你看,不是等使用者看" not in _text()


def test_manifest_stays_short():
    """A manifest nobody reads to the end fixes nothing. Upstream ran 11 lines;
    the methodology earns more, but not unboundedly more."""
    lines = [ln for ln in _text().splitlines() if ln.strip()]
    assert len(lines) <= 60, f"{len(lines)} non-blank lines"
