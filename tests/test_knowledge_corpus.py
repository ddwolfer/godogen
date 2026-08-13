import re
from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parent.parent / "knowledge"
CATEGORIES = ("pitfalls", "principles", "patterns")

LINK = re.compile(r"\[\[([^\]]+)\]\]")


def _entries() -> list[Path]:
    return sorted(p for c in CATEGORIES for p in (CORPUS / c).glob("*.md"))


def _slugs() -> set[str]:
    return {p.stem for p in _entries()}


def test_corpus_has_all_three_categories():
    for category in CATEGORIES:
        assert (CORPUS / category).is_dir(), category


def test_corpus_is_not_empty():
    assert len(_entries()) >= 15


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_starts_with_h1(path: Path):
    first = path.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("# "), f"{path.name} must start with an H1 title"


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_has_a_case_section(path: Path):
    text = path.read_text(encoding="utf-8")
    assert "案例" in text or "實例" in text, f"{path.name} needs a concrete case"


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_has_no_bom(path: Path):
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_cross_links_resolve(path: Path):
    """A [[link]] typo has no symptom — it just silently breaks the graph."""
    known = _slugs()
    for target in LINK.findall(path.read_text(encoding="utf-8")):
        assert target in known, f"{path.name} links to unknown entry [[{target}]]"
