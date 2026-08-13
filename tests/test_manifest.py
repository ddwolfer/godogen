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


def test_manifest_stays_short():
    """A manifest nobody reads to the end fixes nothing. Upstream ran 11 lines;
    the methodology earns more, but not unboundedly more."""
    lines = [ln for ln in _text().splitlines() if ln.strip()]
    assert len(lines) <= 60, f"{len(lines)} non-blank lines"
