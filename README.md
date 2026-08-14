# Godogen

Autonomous game development for Godot and Babylon.js with Claude Code or Codex — where each project starts with what the last one learned.

[繁體中文](README.zh-TW.md) | English

A personal fork of [alex_erm/godogen](https://github.com/alex-erm/godogen). See [Differences from upstream](#differences-from-upstream).

Describe a game. The agent builds it, generates assets, runs the engine, and proves the result — as a live game you watch and steer, or as a recorded video when you're not there.

This repo is not a game. It is the source for a generator that produces games: **godogen -> game repo -> game**. You publish into a fresh game repo, and the agent builds the actual game inside it from a short engine guide.

## The part that compounds

Game repos are disposable. This one is not, so it holds the memory.

```
   godogen  ──── publish + seed ────►  game repo
      ▲                                    │
      │                                    │ accumulates during the run
      └────────  harvest (reviewed) ───────┘
```

Two knowledge bases, both mounted in every published repo:

- **`craft.db`** lives here and carries what every game should already know — engine traps, toolchain traps, design principles. Built from [`knowledge/`](knowledge/), which is 19 entries of reviewable markdown.
- **`game.db`** lives in the game repo and accumulates that game's own findings.

Writing back asks nothing of you. `/kg-harvest` runs as a step of delivery and proposes the handful of lessons that generalise; you approve or reject. A commit hook catches anything you happened to write into a commit body.

## Setting up on a new machine

Cloning is not enough. **`craft.db` is not versioned** — `knowledge/*.md` is the source of truth and the database is its search index — so a fresh clone starts amnesic, and nothing tells you: publishing still succeeds and the agent still runs, it just knows nothing.

```bash
git clone https://github.com/ddwolfer/godogen
cd godogen
```

Then open Claude Code or Codex here and ask **how do I start**. The `setup` skill detects what is already installed, asks only what it cannot detect — which asset backends you want — writes `.env`, and builds the index.

Doing it by hand instead:

```bash
# the knowledge engine, once per machine
git clone https://github.com/ddwolfer/Multi-knowledgeGraph kg
cd kg && npm install && cd ..

# imports, embeds, and prioritises in one go
cp .env.example .env      # then edit it
python scripts/bootstrap.py
```

`kg/` is gitignored, so cloning it inside the checkout is fine; `../kg` and `~/.godogen/kg` are also searched, and `GODOGEN_KG_HOME` overrides all of them.

`bootstrap.py` ends with a line like `Ready. 20 entries indexed, 20 vectorized, 7 principles prioritized`. If it prints an error instead, believe the error: both underlying steps fail by quietly doing less, which is why this refuses to report success it cannot verify.

Re-run it after editing `knowledge/`.

Full prerequisites — Godot, Python, ffmpeg, the optional local asset services — are in [setup.md](setup.md).

### Asset backends

Three independent choices in `.env`, because they are independent: procedural models in Blender alongside cloud image generation is a normal setup.

| | options |
|---|---|
| `ASSET_3D` | `blender` (local, free) · `tripo3d` (~30–60¢ each) · `none` |
| `ASSET_2D` | `comfyui` (local, free) · `gemini` (5–15¢) · `grok` (2¢) · `none` |
| `ASSET_AUDIO` | `ace` ([ACE Studio](https://github.com/ddwolfer/ACE_Studio), local, free) · `none` |

The choice is baked into the published repo's asset skill, so the agent does not have to guess which pipeline this project uses.

ACE Studio is wired as an MCP server, so the agent gets its tools directly — including `list_library`. **Its library is to sound what `craft.db` is to knowledge:** a store that outlives any one game. The skill's rule is to search it before generating, because a library entry is one you have already listened to.

Like the knowledge engine, it is found by path rather than vendored — its models and its library are both outside git, so a submodule would hand you an empty shell. Searched at `<godogen>/ACE_Studio`, `../ACE_Studio` and `~/.godogen/ACE_Studio`, or set `ACE_STUDIO_HOME`.

## Making a game

```bash
python publish.py --engine godot   --out ~/my-game
python publish.py --engine babylon --out ~/my-game
python publish.py --engine godot --agent codex --out ~/my-game
```

`--force` wipes the target first. Then open your agent in that directory and describe the game you want.

The published repo carries the manifest (`CLAUDE.md`, or `AGENTS.md` for Codex), a one-page engine guide, three skills, and wiring to both knowledge bases. Everything else — project scaffold, capture tooling — the agent builds from the guide.

Before writing code the agent runs `/game-design`: an interview that produces `DESIGN.md` — core verb, the decision the player keeps making, what the game explicitly will not do and why. "Make a tower defense" carries about three percent of the game you have in mind, and the rest is otherwise invented silently and lost at the first compaction.

### Codex

Codex is a supported target, with a smaller knowledge story. It has `SessionStart`, `UserPromptSubmit` and `PostToolUse`, but **no event that fires after context compaction** — and a generation run compacts several times over hours. So on Codex, knowledge arrives at session start and on each prompt, but is not re-injected after a compaction.

Codex hooks are also opt-in and experimental: set `[features].codex_hooks = true` in `~/.codex/config.toml` and trust the project's `.codex/` layer.

## Source layout

- `prompts/runtime.md` — the runtime manifest, rendered to `CLAUDE.md`
- `engines/godot.md`, `engines/babylon.md` — per-engine guides
- `knowledge/` — the cross-project corpus
- `asset-gen/` — the asset-generation skill
- `skills/` — additional skills installed into published repos
- `hooks/` — the commit harvester
- `scripts/` — `bootstrap.py`, `seed_priority.py`, publish internals
- [publish.py](publish.py) — renders all of it for the chosen engine

## What the agent does

- **Godot 4** — GDScript on the standard build, simulation split from rendering so runs are deterministic and replayable.
- **Babylon.js** — TypeScript/Vite served at a live URL. Inherited from upstream, unverified on Windows.
- **Assets, locally** — Blender procedural models, ComfyUI icons, and a local audio model for sound effects, with the post-processing that makes their output usable. Free per call and reproducible. Paid cloud APIs remain as a fallback.
- **Proof over claims** — judged from the running game, never from a clean build. Five layers, ordered by what actually catches problems: your playthrough, the agent reading its own screenshots, measurement probes, tests, then deadlock checks.
- **You choose your involvement** — steer a live game, or leave the run unattended and get a 15–20s proof recording. The agent takes its cue from how you frame the task.

## Differences from upstream

Windows-first, Godot-centric, and opinionated where upstream is deliberately not.

- **Memory across projects.** Upstream ships no knowledge layer; a run's lessons die with the repo.
- **GDScript, not C#.** Upstream switched to C# over GDScript's type-inference traps. Measured against a 1015-test GDScript project those cost about three minutes a day and never caused a runtime bug, while that day's real bugs were all things a compiler cannot catch.
- **Local assets first.** Upstream generates everything through paid APIs and ships no audio pipeline at all.
- **An opinionated manifest.** Upstream's is eleven lines and says nothing about method. This one adds sim/render separation, the verification ladder, and two debugging rules — the failures that look like success.
- **A design step.** Upstream goes from one sentence straight to code. This one interviews first and writes down what was decided, including what was ruled out.
- **Engines** — Godot and Babylon.js. Bevy is dropped.
- **`publish.py` replaces `publish.sh`** — one implementation for Windows and POSIX, no `rsync`, `mktemp`, or `xvfb`.

Documents in Chinese have been verified against real runs; documents in English are inherited from upstream and have not.

## Known limitations

- `auto-recall` matches by splitting on whitespace, so it misses Chinese prompts that contain no spaces. This matters most on Codex, where it is the only always-available injection channel.
- Codex has no post-compaction hook, so knowledge is not re-injected after a compaction there.
- The post-compaction budget is ten entries; `scripts/seed_priority.py` decides which ten.
- The Babylon guide and its capture path are unverified on Windows.
- Nothing here has yet built a complete game. Every part is verified; the whole path is not.

## Development

```bash
python -m pytest tests/ -v
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
