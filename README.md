# Godogen

Autonomous game development for Godot and Babylon.js with Claude Code.

A personal fork of [alex_erm/godogen](https://github.com/alex-erm/godogen) — see [Differences from upstream](#differences-from-upstream).

[Watch the upstream demos](https://youtu.be/eUz19GROIpY) · [Prompts](docs/demo_prompts.md)

Describe a game. The agent builds it, generates assets, runs the engine, and proves the result — as a live game you watch and steer, or as a recorded video when you're not there. It reads the situation and decides which, in the run.

This repo is not a game. It is the source for a generator that produces games: **godogen -> game repo -> game**. You publish into a fresh game repo — choosing an engine — then the agent runs inside that repo and builds the actual game from a short engine guide.

## Source layout

A published repo is intentionally thin: a runtime manifest, a one-page engine guide, and the asset-generation skill. The agent recreates everything else (project scaffold, capture tooling) from the guide.

- `prompts/runtime.md` — the runtime manifest
- `asset-gen/` — the cross-engine asset-generation skill
- `engines/godot.md`, `engines/babylon.md` — per-engine guides
- [publish.py](publish.py) — renders the runtime layout for the chosen engine

Engine is a publish-time render choice, not a separate source tree.

## What the agent does

- **Godot 4** — C#/.NET projects with build-time scene generation, runtime scripts, and Jolt physics.
- **Babylon.js** — TypeScript/Vite browser games served at a live URL.
- **Asset generation** — Gemini for precise references and characters, xAI Grok for textures and simple objects, Tripo3D for image-to-3D and rigged biped animation; animated sprites via Grok video with loop detection and background removal.
- **Proof over claims** — the agent judges results from the running game (a live URL or a recorded clip), not from a clean compile, so visible defects drive the next iteration.
- **You choose your involvement** — watch the live game (a Babylon.js URL, or a Godot project you run) and steer at decision points, or leave the run unattended and get a 15–20s proof recording at the end. The agent takes its cue from how you frame the task.

## Getting started

### Prerequisites

- [Godot 4](https://godotengine.org/download/) (.NET build) on `PATH` for Godot projects
- Node.js 22.12+ and npm for Babylon.js projects
- Chrome or Chromium with hardware WebGL2 for Babylon.js browser capture
- Python 3.11+
- API keys as environment variables:
  - `GOOGLE_API_KEY` — [Google AI Studio](https://aistudio.google.com/) for Gemini image generation
  - `XAI_API_KEY` — [xAI Grok](https://console.x.ai/home) for image/video generation
  - `TRIPO3D_API_KEY` — [Tripo3D](https://platform.tripo3d.ai/) for 3D generation
- System packages from [setup.md](setup.md): `ffmpeg`, `imagemagick`, plus platform-specific extras
- Claude Code

### Publish a game repo

Pick the engine:

```bash
python publish.py --engine godot   --out ~/my-game
python publish.py --engine babylon --out ~/my-game
```

Pass `--force` to wipe existing contents at the target before re-publishing.

## Differences from upstream

This fork targets a Windows-first, Godot-centric workflow:

- **Engines** — Godot and Babylon.js only. Bevy support is dropped.
- **Host agent** — Claude Code only. Codex rendering (`AGENTS.md` + `.agents/skills/` + `openai.yaml`) is dropped.
- **Publish** — `publish.py` replaces `publish.sh`. One implementation for Windows and POSIX, with no `rsync`, `mktemp`, or `xvfb` dependency.

## Development

```bash
python -m pytest tests/ -v
```

## Running a long generation

A full generation run can take hours.

- Keep the session alive across drops with `tmux` or `screen` on POSIX hosts.
- Enable remote control so you can check in and steer the run from any device.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
