"""Constraints that are easy to violate and produce no local symptom."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# These reach the Windows console, which encodes as cp950 by default. A single
# em-dash there prints as mojibake and the user cannot tell what broke.
CLI_SOURCES = [
    ROOT / "publish.py",
    ROOT / "scripts" / "publish_lib" / "layout.py",
    ROOT / "scripts" / "publish_lib" / "kgwire.py",
]


@pytest.mark.parametrize("path", CLI_SOURCES, ids=lambda p: p.name)
def test_cli_source_is_ascii(path: Path):
    text = path.read_text(encoding="utf-8")
    offenders = sorted({c for c in text if ord(c) > 127})
    assert not offenders, f"{path.name} has non-ASCII: {offenders}"


@pytest.mark.parametrize("path", CLI_SOURCES, ids=lambda p: p.name)
def test_cli_source_has_no_crlf(path: Path):
    assert b"\r\n" not in path.read_bytes(), path.name


def test_no_powershell_scripts_in_repo():
    """Cross-platform execution logic is Python. PowerShell 5.1 pipelines fail
    halfway and still write their output -- see knowledge/pitfalls/."""
    scripts = [
        p for p in ROOT.rglob("*.ps1") if ".git" not in p.parts
    ]
    assert not scripts, f"unexpected PowerShell scripts: {scripts}"
