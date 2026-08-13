#!/usr/bin/env python3
"""Decide which knowledge survives context compaction.

The post-compact hook injects `ORDER BY access_count DESC LIMIT 10`. With a
fresh import every count is 0, so the order collapses to insertion order and
the selection is effectively arbitrary -- on a 20-entry corpus that silently
dropped every single principle, leaving the agent with a pile of technical
traps and no method.

This seeds access_count so the slots go somewhere deliberate:

    principles > patterns > pitfalls

Principles and patterns are always relevant -- how to verify, how to change
balance, where to look first. Pitfalls are situational: they matter when you
touch Blender, or a web export, or a sort comparator, and recall surfaces
them then. Post-compact is the only always-on channel, so it carries the
always-relevant half.

This is a workaround, not a fix. access_count means "how often was this
recalled", and overloading it with priority is a lie the database tells --
the real fix is a priority column, or a larger budget, in the kg repo. Until
then this beats an arbitrary cut.

    python scripts/seed_priority.py --db craft.db

Re-run after every import; import-skills.js resets counts to 0.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Higher wins a slot. Gaps leave room for per-entry overrides either way.
CATEGORY_PRIORITY = {
    "principles": 300,
    "patterns": 200,
    "pitfalls": 100,
}

# The corpus writing guide. Useful when adding knowledge, noise the rest of
# the time, and it is not knowledge itself.
EXCLUDED_STEMS = {"README"}
EXCLUDED_PRIORITY = 0


def priority_of(path: Path, corpus: Path) -> int:
    """Category order, unless the entry declares `priority:` in frontmatter."""
    if path.stem in EXCLUDED_STEMS:
        return EXCLUDED_PRIORITY

    for line in path.read_text(encoding="utf-8").splitlines()[:10]:
        if line.startswith("priority:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                break

    category = path.relative_to(corpus).parts[0]
    return CATEGORY_PRIORITY.get(category, EXCLUDED_PRIORITY)


def node_key(name: str) -> str:
    """import-skills.js names nodes by relative path with the suffix dropped,
    joined with ' > '. Normalise both separators to compare against a file."""
    return name.replace(" > ", "/").replace("\\", "/")


def seed(db_path: Path, corpus: Path) -> dict[str, int]:
    """Write priorities into access_count. Returns {node name: priority}."""
    wanted = {
        str(p.relative_to(corpus).with_suffix("")).replace("\\", "/"): priority_of(p, corpus)
        for p in sorted(corpus.rglob("*.md"))
    }

    conn = sqlite3.connect(str(db_path))
    applied: dict[str, int] = {}
    try:
        with conn:
            for node_id, name in conn.execute("SELECT id, name FROM nodes"):
                priority = wanted.get(node_key(name))
                if priority is None:
                    continue
                conn.execute(
                    "UPDATE nodes SET access_count = ? WHERE id = ?", (priority, node_id)
                )
                applied[name] = priority
    finally:
        conn.close()
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="seed_priority.py")
    parser.add_argument("--db", default=str(REPO_ROOT / "craft.db"))
    parser.add_argument("--knowledge", default=str(REPO_ROOT / "knowledge"))
    parser.add_argument("--limit", type=int, default=10, help="post-compact budget")
    args = parser.parse_args(argv)

    db, corpus = Path(args.db), Path(args.knowledge)
    if not db.exists():
        print(f"error: {db} not found -- import the corpus first", file=sys.stderr)
        return 1

    applied = seed(db, corpus)
    if not applied:
        print(f"error: no nodes in {db} matched {corpus}", file=sys.stderr)
        return 1

    ranked = sorted(applied.items(), key=lambda kv: (-kv[1], kv[0]))
    print(f"Seeded {len(applied)} nodes. Top {args.limit} survive compaction:")
    for name, priority in ranked[: args.limit]:
        print(f"  {priority:>4}  {name}")
    if len(ranked) > args.limit:
        print(f"  ---- below the cut ({len(ranked) - args.limit}) ----")
        for name, priority in ranked[args.limit :]:
            print(f"  {priority:>4}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
