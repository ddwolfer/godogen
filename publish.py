#!/usr/bin/env python3
"""Publish godogen runtime files into a target game repo.

Usage:
    python publish.py --engine godot|babylon [--agent claude|codex] --out <dir> [--force]
    python publish.py --engine godot <dir> [--force]

A published repo carries only docs: the runtime manifest (CLAUDE.md for Claude
Code, AGENTS.md for Codex), a per-engine guide (<engine>.md), and the skills.
The agent scaffolds the game itself from the guide -- no project scaffold ships.

Pure Python on purpose: it runs identically on Windows and POSIX, and avoids
the rsync/mktemp dependency of the shell version it replaces.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts import generate_codex_metadata
from scripts.publish_lib import config, kgwire, layout

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


def _write_json(path: Path, data: dict) -> None:
    _write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _ace_home_for(settings: dict[str, str]) -> Path | None:
    """ACE Studio is wired only when it is the chosen audio backend."""
    if config.backend("ASSET_AUDIO", settings) != "ace":
        return None
    home = kgwire.find_ace_home()
    shadowed = kgwire.external.ACE.shadow_warning()
    if shadowed:
        print(shadowed, file=sys.stderr)
    if home is None:
        print(kgwire.ACE_MISSING_WARNING, file=sys.stderr)
    return home


def _kg_home_for(kg_home: Path | None) -> Path | None:
    """The kg install to wire, naming any it had to pass over.

    Worth saying here and not only in bootstrap: this path is baked into
    .mcp.json and every hook command, and publishing happens once per game
    rather than once per machine. Naming an install is a choice, so only a
    search can be ambiguous.
    """
    if kg_home is not None:
        return kg_home
    home = kgwire.find_kg_home()
    shadowed = kgwire.external.KG.shadow_warning()
    if shadowed:
        print(shadowed, file=sys.stderr)
    return home


def _wire_knowledge(
    target: Path, kg_home: Path | None, agent: str, ace_home: Path | None = None
) -> None:
    """Point the game repo at the shared kg install and both knowledge bases.

    craft.db lives with godogen so every game reads the same accumulated
    craft knowledge; game.db is local and starts empty.
    """
    if kg_home is None:
        print(kgwire.KG_MISSING_WARNING, file=sys.stderr)
        return

    craft_db = REPO_ROOT / layout.CRAFT_DB_NAME
    game_db = target / ".kg" / layout.GAME_DB_NAME
    game_db.parent.mkdir(parents=True, exist_ok=True)
    harvest = REPO_ROOT / "hooks" / "harvest_commit.py"

    if agent == "codex":
        _write(
            target / ".codex" / "config.toml",
            kgwire.codex_mcp_config(kg_home, craft_db, game_db, ace_home),
        )
        _write_json(
            target / ".codex" / "hooks.json",
            kgwire.codex_hook_settings(kg_home, craft_db, game_db, harvest_script=harvest),
        )
        print(f"Wired knowledge: kg at {kg_home}")
        print(kgwire.CODEX_NO_COMPACT_HOOK, file=sys.stderr)
        print(
            "note: Codex hooks are opt-in -- set [features].codex_hooks = true in "
            "~/.codex/config.toml, and trust this project's .codex/ layer.",
            file=sys.stderr,
        )
    else:
        _write_json(
            target / ".mcp.json",
            kgwire.mcp_config(kg_home, craft_db, game_db, ace_home),
        )
        _write_json(
            target / ".claude" / "settings.json",
            kgwire.hook_settings(kg_home, craft_db, game_db, harvest_script=harvest),
        )
        print(f"Wired knowledge: kg at {kg_home}")

    if not craft_db.exists():
        print(
            f"note: {craft_db} does not exist yet -- import the seed corpus with\n"
            f"      node \"{kg_home / 'scripts' / 'import-skills.js'}\" "
            f"--db \"{craft_db}\" {REPO_ROOT / 'knowledge'}",
            file=sys.stderr,
        )


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
        raise UnsafeTarget(f"refusing to wipe {resolved} -- it contains the godogen source")
    if resolved.parent == resolved:
        raise UnsafeTarget(f"refusing to wipe a filesystem root: {resolved}")


def publish(
    engine: str,
    out: Path | str,
    agent: str = "claude",
    force: bool = False,
    kg_home: Path | None = None,
    wire_knowledge: bool = True,
) -> Path:
    """Render the runtime layout for `engine` into `out`. Returns the target path."""
    settings = config.load()
    tokens_manifest = layout.manifest_tokens(engine, agent)  # raises on unknown
    tokens_skill = layout.skill_tokens(
        engine, agent, godogen_root=str(REPO_ROOT), asset_backends=config.describe(settings)
    )
    manifest_name = layout.manifest_file(agent)
    skills_rel = layout.skills_dir(agent)

    target = Path(out)
    if force:
        _guard_target(target)
        if target.exists():
            print(f"Force: cleaning {target}")
            shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    target = target.resolve()

    print(f"Publishing {engine}/{agent} to: {target}")

    # --- Skills: rendered in a scratch copy, then installed ---
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "skills"
        staged.mkdir()
        shutil.copytree(REPO_ROOT / "asset-gen", staged / "asset-gen", ignore=_IGNORE)
        for skill in sorted((REPO_ROOT / "skills").iterdir()):
            if skill.is_dir():
                shutil.copytree(skill, staged / skill.name, ignore=_IGNORE)
        _render_tree(staged, tokens_skill)
        if agent == "codex":
            # Codex discovers skills through agents/openai.yaml, not frontmatter.
            generate_codex_metadata.main(["generate_codex_metadata.py", str(staged)])
        shutil.copytree(staged, target / skills_rel, dirs_exist_ok=True)
    print(f"Installed skills into {skills_rel}")

    # --- Manifest: the runtime process doc ---
    manifest = (REPO_ROOT / "prompts" / "runtime.md").read_text(encoding="utf-8")
    _write(target / manifest_name, render_text(manifest, tokens_manifest))
    print(f"Created {manifest_name}")

    # --- Per-engine guide (literal markdown) ---
    guide_name = tokens_manifest["ENGINE_GUIDE_FILE"]
    guide = (REPO_ROOT / "engines" / guide_name).read_text(encoding="utf-8")
    _write(target / guide_name, guide)
    print(f"Created {guide_name}")

    # --- Knowledge: the shared kg install and both databases ---
    if wire_knowledge:
        _wire_knowledge(
            target,
            _kg_home_for(kg_home),
            agent,
            ace_home=_ace_home_for(settings),
        )

    # --- .gitignore (published instruction files are regenerated) ---
    gitignore = target / ".gitignore"
    if not gitignore.exists():
        _write(gitignore, "\n".join(layout.gitignore_lines(engine, agent)) + "\n")
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
    parser.add_argument("--agent", default="claude", choices=sorted(layout.AGENTS))
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
        publish(args.engine, out, agent=args.agent, force=args.force)
    except (layout.UnknownEngine, layout.UnknownAgent, UnsafeTarget) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
