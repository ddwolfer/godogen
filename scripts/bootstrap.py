#!/usr/bin/env python3
"""Make a fresh clone remember things.

craft.db is not versioned -- knowledge/*.md is the reviewable source of truth
and the database is its search index -- so a clone starts amnesic, and nothing
says so. publish still succeeds, the agent still runs, it just knows nothing.

This builds the index and, more importantly, refuses to report success it
cannot verify. Both steps it wraps fail by quietly doing less:

  import-skills.js  gates embedding on isReady(), which only turns true after
                    embed() has been called -- a fresh process writes zero
                    vectors and prints success
  post-compact      injects ORDER BY access_count DESC with a fixed LIMIT,
                    which on a fresh import is every count at 0 and an
                    arbitrary cut

    python scripts/bootstrap.py

Re-run after editing knowledge/. Safe to repeat.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts import seed_priority  # noqa: E402
from scripts.publish_lib import kgwire  # noqa: E402


class BootstrapFailed(Exception):
    """Something did not work, and pretending otherwise helps nobody."""


def _run(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise BootstrapFailed(
            f"{' '.join(args[:2])} exited {result.returncode}\n{result.stderr[-800:]}"
        )
    return result.stdout


def count_vectors(kg_home: Path, db: Path) -> tuple[int, int]:
    """Ask Node, not Python. sqlite-vec binds to better-sqlite3; a Python
    connection reports 'no such module: vec0' and looks like a broken install."""
    probe = (
        "const D=require('better-sqlite3'),V=require('sqlite-vec');"
        f"const db=new D({json.dumps(str(db))},{{readonly:true}});V.load(db);"
        "console.log(JSON.stringify({"
        "nodes:db.prepare('SELECT count(*) c FROM nodes').get().c,"
        "vec:db.prepare('SELECT count(*) c FROM vec_nodes').get().c}));"
    )
    out = _run(["node", "-e", probe], cwd=kg_home)
    payload = json.loads(out.strip().splitlines()[-1])
    return payload["nodes"], payload["vec"]


def bootstrap(kg_home: Path, db: Path, corpus: Path, rebuild: bool = True) -> dict:
    if rebuild:
        for suffix in ("", "-shm", "-wal"):
            Path(str(db) + suffix).unlink(missing_ok=True)

    print(f"kg:        {kg_home}")
    print(f"corpus:    {corpus}")
    print(f"database:  {db}")
    print()

    print("[1/3] importing corpus...")
    _run(["node", str(kg_home / "scripts" / "import-skills.js"), str(corpus),
          "--db", str(db)], cwd=kg_home)

    print("[2/3] generating embeddings (first run downloads ~560MB)...")
    _run(["node", str(kg_home / "scripts" / "backfill-embeddings.js"),
          "--db", str(db)], cwd=kg_home)

    print("[3/3] seeding injection priority...")
    applied = seed_priority.seed(db, corpus)
    if not applied:
        raise BootstrapFailed(f"no nodes in {db} matched {corpus}")

    nodes, vec = count_vectors(kg_home, db)
    if nodes == 0:
        raise BootstrapFailed("imported zero nodes")
    if vec < nodes:
        raise BootstrapFailed(
            f"{nodes} nodes but only {vec} vectors -- semantic recall would be "
            f"silently dead. Re-run; the embedding model may still be downloading."
        )

    principles = sum(1 for v in applied.values() if v >= seed_priority.CATEGORY_PRIORITY["principles"])
    return {"nodes": nodes, "vectors": vec, "principles": principles}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bootstrap.py")
    parser.add_argument("--kg", help="path to the Multi-knowledgeGraph checkout")
    parser.add_argument("--db", default=str(REPO_ROOT / "craft.db"))
    parser.add_argument("--knowledge", default=str(REPO_ROOT / "knowledge"))
    parser.add_argument(
        "--keep", action="store_true",
        help="import without wiping first. The importer does not de-duplicate, "
             "so re-running this over the same corpus doubles every entry. It "
             "is for adding a second corpus, or for when the database is "
             "locked and cannot be deleted.")
    args = parser.parse_args(argv)

    kg_home = Path(args.kg) if args.kg else kgwire.find_kg_home()
    if not args.kg:
        shadowed = kgwire.external.KG.shadow_warning()
        if shadowed:
            print(shadowed, file=sys.stderr)
    if kg_home is None:
        print(kgwire.KG_MISSING_WARNING.replace("warning:", "error:"), file=sys.stderr)
        return 1
    if shutil.which("node") is None:
        print("error: node is not on PATH", file=sys.stderr)
        return 1

    try:
        stats = bootstrap(kg_home, Path(args.db), Path(args.knowledge), rebuild=not args.keep)
    except (BootstrapFailed, sqlite3.Error, json.JSONDecodeError, OSError) as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"Ready. {stats['nodes']} entries indexed, {stats['vectors']} vectorized, "
          f"{stats['principles']} principles prioritized for post-compaction recall.")
    print("Publish a game repo with:  python publish.py --engine godot --name <game>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
