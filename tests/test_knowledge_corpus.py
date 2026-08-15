import re
from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parent.parent / "knowledge"
CATEGORIES = ("pitfalls", "principles", "patterns")

LINK = re.compile(r"\[\[([^\]]+)\]\]")
QUOTE = re.compile(r"「([^」]+)」")

VERIFIED_VALUES = {"true", "partial", "false"}


def _entries() -> list[Path]:
    return sorted(p for c in CATEGORIES for p in (CORPUS / c).glob("*.md"))


def _slugs() -> set[str]:
    return {p.stem for p in _entries()}


def _split(path: Path) -> tuple[dict[str, str], list[str]]:
    """Return (frontmatter, body lines)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", f"{path.name} has no frontmatter"
    end = lines.index("---", 1)
    meta = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, lines[end + 1 :]


def test_corpus_has_all_three_categories():
    for category in CATEGORIES:
        assert (CORPUS / category).is_dir(), category


def test_corpus_is_not_empty():
    assert len(_entries()) >= 15


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_declares_its_source(path: Path):
    """Where a lesson came from decides how much weight it carries."""
    meta, _ = _split(path)
    assert meta.get("source"), f"{path.name} needs a source"


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_declares_whether_it_was_verified(path: Path):
    """'partial' exists because an entry can mix a measured finding with an
    inferred one -- which is exactly how a rumour ended up ranked first."""
    meta, _ = _split(path)
    assert meta.get("verified") in VERIFIED_VALUES, (
        f"{path.name}: verified must be one of {sorted(VERIFIED_VALUES)}"
    )


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_unverified_entries_flag_themselves_in_the_body(path: Path):
    """A frontmatter flag nobody renders is not a warning. Anything less than
    fully verified must say so where it is read."""
    meta, body = _split(path)
    if meta["verified"] != "true":
        assert "未實測" in "\n".join(body), (
            f"{path.name} is {meta['verified']} but the body never says which part"
        )


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_starts_with_h1(path: Path):
    _, body = _split(path)
    assert body[0].startswith("# "), f"{path.name} must open with an H1 title"


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_has_a_summary_quote(path: Path):
    """The importer sets trust='principle' only when it finds a 「」 quote, and
    post-compact re-injects only principles. Without this line an entry imports
    as a pattern and silently vanishes from the most important hook."""
    _, body = _split(path)
    assert body[2].startswith("> 「") and body[2].rstrip().endswith("」"), (
        f"{path.name} needs a > 「...」 one-line summary under the title"
    )


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_the_summary_is_the_first_quote_in_the_file(path: Path):
    """The importer stores quotes[0] as the node's quote, scanning in document
    order -- so nothing quoted may appear above the summary."""
    text = path.read_text(encoding="utf-8")
    _, body = _split(path)
    first = QUOTE.search(text)
    assert first is not None, path.name
    assert f"「{first.group(1)}」" == body[2].strip().removeprefix("> "), (
        f"{path.name}: an earlier 「」 wins -- found {first.group(1)!r}.\n"
        "Almost always the H1: a title like # 「要保守」是方向 steals the slot "
        "and the entry imports with the wrong quote. Rephrase the title "
        "without brackets; the summary line is where quoting belongs."
    )


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_has_a_case_section(path: Path):
    text = path.read_text(encoding="utf-8")
    assert "案例" in text or "實例" in text, f"{path.name} needs a concrete case"


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_has_no_bom(path: Path):
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_cross_links_resolve(path: Path):
    """A [[link]] typo has no symptom -- it just silently breaks the graph."""
    known = _slugs()
    for target in LINK.findall(path.read_text(encoding="utf-8")):
        assert target in known, f"{path.name} links to unknown entry [[{target}]]"
