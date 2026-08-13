#!/usr/bin/env python3
"""Publish godogen runtime files into a target game repo.

Usage:
    python publish.py --engine godot|babylon --out <dir> [--force]
    python publish.py --engine godot <dir> [--force]

A published repo carries only docs: the runtime manifest (CLAUDE.md), a
per-engine guide (<engine>.md), and the skills. The agent scaffolds the game
itself from the engine guide — no project scaffold is shipped.

Pure Python on purpose: it runs identically on Windows and POSIX, and avoids
the rsync/mktemp dependency of the shell version it replaces.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.publish_lib import layout

REPO_ROOT = Path(__file__).resolve().parent

_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


class UnsafeTarget(Exception):
    """Raised when --force would wipe something it must not."""


def render_text(text: str, tokens: dict[str, str]) -> str:
    """Substitute ${KEY} tokens."""
    for key, value in tokens.items():
        text = text.replace(f"${{{key}}}", value)
    return text


def _write(path: Path, text: str) -> None:
    """Write UTF-8 with LF endings and no BOM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _render_tree(root: Path, tokens: dict[str, str]) -> None:
    """Substitute tokens in every text file under root, in place."""
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary asset, leave it alone
        rendered = render_text(original, tokens)
        if rendered != original:
            _write(path, rendered)


def _guard_target(target: Path) -> None:
    """--force deletes the target; make sure it is not something precious."""
    resolved = target.resolve()
    if resolved == REPO_ROOT or REPO_ROOT.is_relative_to(resolved):
        raise UnsafeTarget(f"refusing to wipe {resolved} — it contains the godogen source")
    if resolved.parent == resolved:
        raise UnsafeTarget(f"refusing to wipe a filesystem root: {resolved}")


def publish(engine: str, out: Path | str, force: bool = False) -> Path:
    """Render the runtime layout for `engine` into `out`. Returns the target path."""
    tokens_manifest = layout.manifest_tokens(engine)  # raises UnknownEngine
    tokens_skill = layout.skill_tokens(engine)

    target = Path(out)
    if force:
        _guard_target(target)
        if target.exists():
            print(f"Force: cleaning {target}")
            shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    target = target.resolve()

    print(f"Publishing {engine} to: {target}")

    # --- Skills: rendered in a scratch copy, then installed ---
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "skills"
        staged.mkdir()
        shutil.copytree(REPO_ROOT / "asset-gen", staged / "asset-gen", ignore=_IGNORE)
        _render_tree(staged, tokens_skill)
        shutil.copytree(staged, target / ".claude" / "skills", dirs_exist_ok=True)
    print("Installed skills")

    # --- Manifest: the runtime process doc ---
    manifest = (REPO_ROOT / "prompts" / "runtime.md").read_text(encoding="utf-8")
    _write(target / "CLAUDE.md", render_text(manifest, tokens_manifest))
    print("Created CLAUDE.md")

    # --- Per-engine guide (literal markdown) ---
    guide_name = tokens_manifest["ENGINE_GUIDE_FILE"]
    guide = (REPO_ROOT / "engines" / guide_name).read_text(encoding="utf-8")
    _write(target / guide_name, guide)
    print(f"Created {guide_name}")

    # --- .gitignore (published instruction files are regenerated) ---
    gitignore = target / ".gitignore"
    if not gitignore.exists():
        _write(gitignore, "\n".join(layout.gitignore_lines(engine)) + "\n")
        print("Created .gitignore")

    subprocess.run(
        ["git", "init", "-q"], cwd=target, check=False, capture_output=True
    )

    print("Done.")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="publish.py", description="Publish godogen runtime files into a game repo."
    )
    parser.add_argument("--engine", required=True, choices=sorted(layout.ENGINES))
    parser.add_argument("--out", help="target directory")
    parser.add_argument("target", nargs="?", help="target directory (positional form)")
    parser.add_argument(
        "--force", action="store_true", help="wipe the target before publishing"
    )
    args = parser.parse_args(argv)

    out = args.out or args.target
    if not out:
        parser.error("a target directory is required (--out <dir>)")
    if args.out and args.target:
        parser.error("target specified more than once")

    try:
        publish(args.engine, out, force=args.force)
    except (layout.UnknownEngine, UnsafeTarget) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
