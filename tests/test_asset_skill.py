from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "asset-gen" / "SKILL.md"


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _body() -> str:
    """Frontmatter summarises everything, so ordering only means something
    below it."""
    lines = _text().splitlines()
    return "\n".join(lines[lines.index("---", 1) + 1 :])


def test_local_tools_come_before_cloud():
    """Order is the recommendation. Whatever is first is what gets used."""
    text = _body()
    assert text.index("blender_gen") < text.index("asset_gen.py")
    assert text.index("sfx_gen") < text.index("Tripo3D")
    assert text.index("comfy_gen") < text.index("Gemini")


def test_all_three_local_pipelines_are_documented():
    text = _text()
    for tool in ("blender_gen.py", "comfy_gen.py", "sfx_gen.py"):
        assert tool in text, tool


def test_cloud_fallback_survives_with_its_cost_warning():
    text = _text()
    assert "asset_gen.py" in text
    assert "resume" in text, "the double-charge trap must stay documented"


def test_skill_keeps_the_asset_manifest_rule():
    text = _text()
    assert "Size" in text
    assert "README.md" in text


def test_skill_keeps_its_tokens():
    text = _text()
    for token in ("${ASSET_GEN_SKILL_DIR}", "${RUNTIME_ASSET_DIR}"):
        assert token in text, token


def test_post_processing_is_stated_as_mandatory():
    text = _text()
    assert "後處理" in text


def test_frontmatter_has_a_name_and_description():
    lines = _text().splitlines()
    assert lines[0] == "---"
    head = "\n".join(lines[1 : lines.index("---", 1)])
    assert "name: asset-gen" in head
    assert "description:" in head
