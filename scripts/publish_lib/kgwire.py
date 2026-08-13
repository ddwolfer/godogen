"""Wiring for the two knowledge bases a published repo talks to.

`craft.db` lives with godogen and carries cross-project knowledge -- engine
traps, toolchain traps, design principles. `game.db` lives in the game repo
and accumulates that game's own findings. Both are mounted; recall reads
craft first, so a new game starts with every prior game's lessons in context.

Config generation only. Nothing here touches a database.
"""

from __future__ import annotations

import os
from pathlib import Path

# Hooks that inject knowledge into context. Each runs once per database.
INJECTING_HOOKS = {
    "session-start.js": ("SessionStart", "startup"),
    "post-compact.js": ("SessionStart", "compact"),
    "auto-recall.js": ("UserPromptSubmit", None),
}

# search-enforcer.js is deliberately NOT wired. It decides whether memory was
# searched by matching hardcoded `mcp__knowledge-graph__*` tool-name prefixes,
# which never match the kg-craft / kg-game server names below -- so it would
# deny every write until its 3-strike circuit breaker fires, on every session.
# Wiring it needs a fix in the kg repo first.

HOOK_TIMEOUT_S = 10

DEFAULT_KG_PATHS = (Path("D:/AI/kg"),)

KG_MISSING_WARNING = (
    "warning: no kg installation found -- publishing without knowledge wiring.\n"
    "         The game repo will work, but it starts and stays amnesic.\n"
    "         Install https://github.com/ddwolfer/Multi-knowledgeGraph and set\n"
    "         GODOGEN_KG_HOME, or place it at D:/AI/kg."
)


def _looks_like_kg(path: Path) -> bool:
    return (path / "main.js").is_file() and (path / "hooks").is_dir()


def find_kg_home(env: dict[str, str] | None = None) -> Path | None:
    """Locate the shared kg installation, or None.

    Order: GODOGEN_KG_HOME, then the conventional locations, then a sibling
    `kg/` next to the godogen checkout.
    """
    env = os.environ if env is None else env

    candidates: list[Path] = []
    override = env.get("GODOGEN_KG_HOME")
    if override:
        candidates.append(Path(override))
    candidates.extend(DEFAULT_KG_PATHS)
    candidates.append(Path(__file__).resolve().parents[2].parent / "kg")

    for candidate in candidates:
        try:
            if candidate.is_dir() and _looks_like_kg(candidate):
                return candidate
        except OSError:
            continue
    return None


def mcp_config(kg_home: Path, craft_db: Path, game_db: Path) -> dict:
    """Two MCP server instances, one per knowledge base."""
    main = str((kg_home / "main.js").resolve())
    return {
        "mcpServers": {
            "kg-craft": {
                "command": "node",
                "args": [main, "--db", str(Path(craft_db).resolve())],
            },
            "kg-game": {
                "command": "node",
                "args": [main, "--db", str(Path(game_db).resolve())],
            },
        }
    }


def hook_settings(kg_home: Path, craft_db: Path, game_db: Path) -> dict:
    """Claude Code hook config. Craft is injected before game, so
    cross-project knowledge frames whatever this game has learned."""
    craft = str(Path(craft_db).resolve())
    game = str(Path(game_db).resolve())

    def commands(script: str) -> list[dict]:
        hook = str((kg_home / "hooks" / script).resolve())
        return [
            {
                "type": "command",
                "command": f'node "{hook}" "{db}"',
                "timeout": HOOK_TIMEOUT_S,
            }
            for db in (craft, game)
        ]

    session_start: list[dict] = []
    hooks: dict[str, list[dict]] = {}

    for script, (event, matcher) in INJECTING_HOOKS.items():
        group: dict = {"hooks": commands(script)}
        if matcher is not None:
            group["matcher"] = matcher
        if event == "SessionStart":
            session_start.append(group)
        else:
            hooks.setdefault(event, []).append(group)

    hooks["SessionStart"] = session_start
    return {"hooks": hooks}
