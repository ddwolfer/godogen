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

_GODOGEN_ROOT = Path(__file__).resolve().parents[2]

# Searched in order when GODOGEN_KG_HOME is unset. All relative to the godogen
# checkout or the home directory -- an absolute path here would only work on
# the machine it was written on. Kept as one constant so a test can empty it;
# otherwise "no kg installed" tests pass only on machines that happen not to
# have one, which is not a test.
DEFAULT_KG_PATHS = (
    _GODOGEN_ROOT / "kg",           # inside the checkout (gitignored)
    _GODOGEN_ROOT.parent / "kg",    # beside the checkout
    Path.home() / ".godogen" / "kg",
)

KG_MISSING_WARNING = (
    "warning: no kg installation found -- publishing without knowledge wiring.\n"
    "         The game repo will work, but it starts and stays amnesic.\n"
    "         Fix with:\n"
    "           git clone https://github.com/ddwolfer/Multi-knowledgeGraph kg\n"
    "           cd kg && npm install\n"
    "         from the godogen checkout, or set GODOGEN_KG_HOME to an existing one."
)


class KgNotFound(Exception):
    """GODOGEN_KG_HOME was set but does not point at a kg installation."""


def _is_kg(path: Path) -> bool:
    try:
        return (path / "main.js").is_file() and (path / "hooks").is_dir()
    except OSError:
        return False


def find_kg_home(env: dict[str, str] | None = None) -> Path | None:
    """Locate the shared kg installation, or None.

    GODOGEN_KG_HOME is authoritative: if it is set and wrong, that is an
    error, not a reason to quietly use a different installation somewhere
    else. Silently ignoring an explicit choice is how you end up wiring a
    game repo to a knowledge base you did not mean.
    """
    env = os.environ if env is None else env

    override = env.get("GODOGEN_KG_HOME")
    if override:
        path = Path(override)
        if not _is_kg(path):
            raise KgNotFound(
                f"GODOGEN_KG_HOME={override} is not a kg installation "
                "(expected main.js and hooks/ inside it)"
            )
        return path

    for candidate in DEFAULT_KG_PATHS:
        if _is_kg(candidate):
            return candidate
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


def hook_settings(
    kg_home: Path,
    craft_db: Path,
    game_db: Path,
    harvest_script: Path | None = None,
) -> dict:
    """Claude Code hook config. Craft is injected before game, so
    cross-project knowledge frames whatever this game has learned.

    `harvest_script` wires tier 1 of the write path: lessons already being
    written into commit bodies get filed as episodes in the game database.
    Referenced by absolute path rather than copied, so improvements to the
    harvester reach every game repo without a re-publish.
    """
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

    if harvest_script is not None:
        script = str(Path(harvest_script).resolve())
        hooks["PostToolUse"] = [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'python "{script}" --db "{game}"',
                        "timeout": HOOK_TIMEOUT_S,
                    }
                ],
            }
        ]

    return {"hooks": hooks}


# --- Codex ----------------------------------------------------------------

# Codex has SessionStart, UserPromptSubmit and PostToolUse, but no event that
# fires after context compaction -- and compaction is exactly when re-injection
# matters, because a generation run compacts several times over hours. On Codex
# the only always-available channel is UserPromptSubmit, so auto-recall carries
# the load alone. Verified against the Codex docs on 2026-08-14; hooks there are
# still marked experimental, so re-check before trusting this.
CODEX_NO_COMPACT_HOOK = (
    "note: Codex has no post-compaction hook. Knowledge is injected at session "
    "start and on each prompt, but is not re-injected after a compaction."
)


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def codex_mcp_config(kg_home: Path, craft_db: Path, game_db: Path) -> str:
    """`.codex/config.toml` -- one [mcp_servers.<name>] table per database."""
    main = str((kg_home / "main.js").resolve())
    blocks = []
    for name, db in (("kg-craft", craft_db), ("kg-game", game_db)):
        args = ", ".join(
            _toml_string(a) for a in (main, "--db", str(Path(db).resolve()))
        )
        blocks.append(f"[mcp_servers.{name}]\ncommand = \"node\"\nargs = [{args}]\n")
    return "\n".join(blocks)


def codex_hook_settings(
    kg_home: Path,
    craft_db: Path,
    game_db: Path,
    harvest_script: Path | None = None,
) -> dict:
    """`.codex/hooks.json`. Same three injecting scripts, minus the one Codex
    has no event for. Codex spells the timeout field `timeoutSec`."""
    craft = str(Path(craft_db).resolve())
    game = str(Path(game_db).resolve())

    def commands(script: str) -> list[dict]:
        hook = str((kg_home / "hooks" / script).resolve())
        return [
            {
                "type": "command",
                "command": f'node "{hook}" "{db}"',
                "timeoutSec": HOOK_TIMEOUT_S,
            }
            for db in (craft, game)
        ]

    hooks: dict[str, list[dict]] = {
        "SessionStart": [{"hooks": commands("session-start.js")}],
        "UserPromptSubmit": [{"hooks": commands("auto-recall.js")}],
    }

    if harvest_script is not None:
        script = str(Path(harvest_script).resolve())
        hooks["PostToolUse"] = [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'python "{script}" --db "{game}"',
                        "timeoutSec": HOOK_TIMEOUT_S,
                    }
                ],
            }
        ]

    return {"hooks": hooks}
