#!/usr/bin/env python3
"""Backup collector for the write path: lessons left in commit messages.

This is a net, not the main entrance. Measured against 80 real commits from
the project this corpus came from, it catches about 4% -- and the corpus's
most valuable entries were never written at commit time at all. They appeared
when their author had to explain a finished piece of work to a person, which
is the only moment that forces the question "so what next time?". A commit
message is written for the diff.

So the primary harvest happens at delivery, through the kg-harvest skill.
This runs anyway because it is free: it asks nothing of anyone, and whatever
it catches is material that skill can work from later.

Wired as a PostToolUse hook. Every failure is silent: a broken harvest must
never block a commit.

Standalone use, to replay history into a fresh database:

    python hooks/harvest_commit.py --replay HEAD~50..HEAD --db .kg/game.db
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

# Section headings that mark harvestable content. A heading only counts at the
# start of a paragraph, followed by a colon somewhere on that line -- prose
# that merely mentions one is not a section.
#
# Deliberately loose. These are prefixes drawn from headings that actually
# appeared in real commit bodies ("平衡（探針，零指令）：" missed an exact
# "平衡回歸" match by two characters). A false positive costs one cheap
# episode row; a miss loses the lesson entirely.
HARVEST_HEADINGS: tuple[str, ...] = (
    "踩到的坑",
    "平衡",
    "難度",
    "呈現",
    "根因",
    "實測",
    "使用者實測",
    "教訓",
    "Pitfall",
    "Regression",
    "Lesson",
)

_COLONS = ("：", ":")

# Copied verbatim from kg/lib/db.js so a fresh game.db works before kg has
# ever opened it. Both sides use CREATE TABLE IF NOT EXISTS, so whichever
# runs first wins and the other is a no-op. Keep in sync with that file.
_EPISODES_DDL = """
CREATE TABLE IF NOT EXISTS episodes (
  id         TEXT PRIMARY KEY,
  type       TEXT NOT NULL CHECK(type IN ('success','failure','lesson')),
  context    TEXT,
  summary    TEXT NOT NULL,
  outcome    TEXT,
  session_id TEXT,
  created_at TEXT NOT NULL
);
"""


def _heading_of(line: str) -> str | None:
    stripped = line.lstrip()
    for heading in HARVEST_HEADINGS:
        if not stripped.startswith(heading):
            continue
        rest = stripped[len(heading) :]
        if any(colon in rest for colon in _COLONS):
            return heading
    return None


def parse_sections(body: str) -> dict[str, str]:
    """Return {heading: text} for every harvestable paragraph in a commit body.

    A section is the paragraph whose first line opens with a known heading;
    it ends at the next blank line.
    """
    sections: dict[str, str] = {}
    for block in body.split("\n\n"):
        lines = block.strip().splitlines()
        if not lines:
            continue
        heading = _heading_of(lines[0])
        if heading is not None:
            sections[heading] = "\n".join(line.strip() for line in lines).strip()
    return sections


def to_episodes(
    subject: str,
    body: str,
    commit: str = "",
    when: str = "",
    session_id: str = "",
) -> list[dict]:
    """Turn one commit into zero or more episode rows.

    `type` is always 'lesson' -- kg's schema only allows success/failure/lesson,
    and which of those a pitfall note represents cannot be read off the text.
    The section heading goes in `context` so the distinction stays searchable.
    """
    episodes = []
    for heading, text in parse_sections(body).items():
        digest = hashlib.sha1(f"{commit}:{heading}".encode("utf-8")).hexdigest()[:16]
        episodes.append(
            {
                "id": f"harvest-{digest}",
                "type": "lesson",
                "context": heading,
                "summary": f"{subject} | {text}",
                "outcome": commit,
                "session_id": session_id,
                "created_at": when,
            }
        )
    return episodes


def write_episodes(db_path: Path | str, episodes: list[dict]) -> int:
    """Insert episodes, skipping ones already present. Returns rows written.

    Returns 0 rather than raising on any failure -- see the module docstring.
    """
    if not episodes:
        return 0
    try:
        conn = sqlite3.connect(str(db_path))
    except sqlite3.Error:
        return 0
    try:
        with conn:
            conn.execute(_EPISODES_DDL)
            before = conn.total_changes
            conn.executemany(
                "INSERT OR IGNORE INTO episodes "
                "(id, type, context, summary, outcome, session_id, created_at) "
                "VALUES (:id, :type, :context, :summary, :outcome, :session_id, :created_at)",
                episodes,
            )
            return conn.total_changes - before
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def _git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout if result.returncode == 0 else ""


def harvest_commit(ref: str = "HEAD", cwd: Path | None = None, session_id: str = "") -> list[dict]:
    """Read one commit and turn it into episodes."""
    raw = _git(["log", "-1", "--format=%H%n%aI%n%s%n%b", ref], cwd)
    if not raw:
        return []
    commit, when, subject, body = (raw.split("\n", 3) + ["", "", "", ""])[:4]
    return to_episodes(subject, body, commit[:7], when, session_id)


def _replay(rng: str, db: Path, cwd: Path | None = None) -> int:
    """Rebuild a knowledge database from git history."""
    revs = _git(["rev-list", "--reverse", rng], cwd).split()
    written = 0
    for rev in revs:
        written += write_episodes(db, harvest_commit(rev, cwd))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harvest_commit.py")
    parser.add_argument("--db", default=".kg/game.db")
    parser.add_argument("--replay", metavar="RANGE", help="e.g. HEAD~50..HEAD")
    args = parser.parse_args(argv)

    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)

    if args.replay:
        written = _replay(args.replay, db)
        print(f"harvested {written} episodes from {args.replay}")
        return 0

    # Hook mode: only act on a Bash tool call that committed something.
    payload = {}
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return 0

    command = str((payload.get("tool_input") or {}).get("command", ""))
    if "git commit" not in command:
        return 0

    write_episodes(db, harvest_commit(session_id=payload.get("session_id", "")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # a broken harvest must never block a commit
        raise SystemExit(0)
