"""Wiring for the two knowledge bases a published repo talks to.

`craft.db` lives with godogen and carries cross-project knowledge -- engine
traps, toolchain traps, design principles. `game.db` lives in the game repo
and accumulates that game's own findings. Both are mounted; recall reads
craft first, so a new game starts with every prior game's lessons in context.

Config generation only. Nothing here touches a database.
"""

from __future__ import annotations

from pathlib import Path

from . import external

# Hooks that inject knowledge into context. Each runs once per database.
INJECTING_HOOKS = {
    "session-start.js": ("SessionStart", "startup"),
    "post-compact.js": ("SessionStart", "compact"),
    "auto-recall.js": ("UserPromptSubmit", None),
}

# search-enforcer.js is deliberately NOT wired. It is a PreToolUse hook, so
# wiring it spends a node process on every single tool call (~60ms measured)
# to do nothing at all unless the user has created
# ~/.claude/hooks/.kg-enforcer-active, which is off by default.
#
# It used to be unwirable for a worse reason: it matched hardcoded
# `mcp__knowledge-graph__*` tool-name prefixes, which never match the
# kg-craft / kg-game names below, so it denied every write until its 3-strike
# breaker fired. Fixed upstream in Multi-knowledgeGraph by
# fix/search-enforcer-tool-names -- what is left is the cost, not a defect.

HOOK_TIMEOUT_S = 10

# Both external services resolve the same way -- see external.py.
KgNotFound = external.NotFound
KG_MISSING_WARNING = external.KG.missing_message()
ACE_MISSING_WARNING = external.ACE.missing_message()


def find_kg_home(env: dict[str, str] | None = None) -> Path | None:
    """Locate the shared kg installation, or None. See external.py."""
    return external.KG.find(env)


def find_ace_home(env: dict[str, str] | None = None) -> Path | None:
    """Locate the ACE Studio installation, or None."""
    return external.ACE.find(env)


def _ace_entry(ace_home: Path) -> str:
    return str((Path(ace_home) / "mcp-server" / "index.mjs").resolve())


def mcp_config(
    kg_home: Path, craft_db: Path, game_db: Path, ace_home: Path | None = None
) -> dict:
    """One MCP server per knowledge base, plus the audio studio when present.

    ACE Studio already speaks MCP, so the agent gets typed tools -- generate,
    and crucially list_library -- instead of a script shelling out over HTTP.
    """
    main = str((kg_home / "main.js").resolve())
    servers = {
        "kg-craft": {
            "command": "node",
            "args": [main, "--db", str(Path(craft_db).resolve())],
        },
        "kg-game": {
            "command": "node",
            "args": [main, "--db", str(Path(game_db).resolve())],
        },
    }
    if ace_home is not None:
        servers["ace-studio"] = {"command": "node", "args": [_ace_entry(ace_home)]}
    return {"mcpServers": servers}


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


def codex_mcp_config(
    kg_home: Path, craft_db: Path, game_db: Path, ace_home: Path | None = None
) -> str:
    """`.codex/config.toml` -- one [mcp_servers.<name>] table per server."""
    main = str((kg_home / "main.js").resolve())
    entries: list[tuple[str, list[str]]] = [
        ("kg-craft", [main, "--db", str(Path(craft_db).resolve())]),
        ("kg-game", [main, "--db", str(Path(game_db).resolve())]),
    ]
    if ace_home is not None:
        entries.append(("ace-studio", [_ace_entry(ace_home)]))

    blocks = []
    for name, args in entries:
        rendered = ", ".join(_toml_string(a) for a in args)
        blocks.append(f"[mcp_servers.{name}]\ncommand = \"node\"\nargs = [{rendered}]\n")
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
