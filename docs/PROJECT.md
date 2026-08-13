# Godogen — From Prompt to Playable Game

Godogen turns a natural-language game brief into a playable Godot or Babylon.js project. The agent builds the game, generates assets, runs the engine, and proves the result from the running game.

It is not a game engine, a code generator, or an asset marketplace. It is a source repo that publishes a thin runtime — a manifest, an engine guide, skills, and a seeded knowledge base — into a fresh game repo that Claude Code then builds in.

## Source Model

- `prompts/runtime.md` — the runtime manifest
- `engines/godot.md`, `engines/babylon.md` — per-engine guides
- `knowledge/` — the cross-project corpus, seeded into every published repo
- `asset-gen/`, `skills/` — the skills a published repo carries
- `hooks/harvest_commit.py` — tier 1 of the write path

Engine is selected at render time:

```bash
python publish.py --engine godot   --out ~/game
python publish.py --engine babylon --out ~/game
```

Publishing writes `CLAUDE.md`, `.claude/skills/`, the `<engine>.md` guide, and — when a knowledge base is installed — `.mcp.json` and the hook configuration in `.claude/settings.json`.

## Knowledge That Outlives the Game

A game repo is finite; this repo is not. Lessons born in a game must flow back here to survive, and that loop is the reason the fork exists.

**Reading** is automatic. Three hooks inject knowledge — at session start, after context compaction, and on every user message — each running against both databases, craft before game. The compaction hook matters most: a generation run lasts hours and will compact, and a guide read once at the start is gone by then. An agent does not look up what it does not know it needs.

**Writing** has three tiers, ascending in friction:

1. A `PostToolUse` hook parses `git commit` bodies for the sections a developer already writes and files them as episodes. Zero effort, so it does not lapse. IDs are derived from `sha1(commit:heading)`, which makes it idempotent and lets `--replay` rebuild a database from git history.
2. `/kg-harvest` reviews a session's commits and episodes and proposes at most three entries for promotion. Batched, so it is one decision per session.
3. Approved entries become markdown in `knowledge/` and are committed here.

The corpus rule is that a lesson without a concrete case is a guess. Density is the whole value: general advice in the corpus becomes noise in every future injection.

## How a run works

The manifest fixes four things and leaves the rest to the model: where durable state lives (`README.md`, so a run survives compaction), that simulation stays separate from rendering, how the result is verified, and that it is proven rather than claimed.

The engine guide carries only what the model can't infer or discover quickly: the project sketch, the capture recipe, and the silent-failure traps that pass a compile and break at runtime.

## Verification

Five layers, ordered by what actually catches problems:

1. The user's playthrough plus a plain-text run log — catches a wrong specification, which no test can, because the system is doing exactly what it was told.
2. The agent reading its own screenshots and video — catches "built it, can't see it".
3. Measurement probes — catch a mechanic that works and carries no weight.
4. Automated tests — catch regressions, and go fake-green when the scenario under test never got set up.
5. A full-speed playthrough — catches deadlocks.

The first two look through a player's eyes; the rest look through the system's, and the system's eye can only prove the system did what it was told.

## Engine Support

- **Godot** — Godot 4 standard build, GDScript. Simulation is pure logic with no engine API, delta time, or engine physics, which is what makes runs replayable from a seed. The guide carries the Windows toolchain traps, the Python runners with mandatory timeouts, and the `--write-movie` capture recipe.
- **Babylon.js** — TypeScript/Vite, served at a live URL. Inherited from upstream and unverified on Windows.

## What Makes This Different

**Knowledge compounds.** Each game starts with every previous game's lessons already in context.

**Proof over claims.** A run is judged on the running game, not on code that compiles.

**Trust the model, but not about the invisible.** The runtime still ships no scaffold and no planner. What it does spend words on is the class of failure that looks like success — a mechanic with no weight, a green test whose scenario never ran, five balance changes landed at once.

**Assets are local and reproducible.** The same Blender script produces the same models forever; one locked style string keeps an icon set coherent. Paid APIs remain for what local models cannot do.

## Runtime Limitations

No in-engine audio pipeline (dynamic mixing, music state machines) — generation and post-processing only. No mobile or native packaging. The Babylon capture path is unverified on Windows. Promotion into the cross-project corpus stays manual by design.
