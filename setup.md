# Workstation Setup

Windows-first. Everything here works on macOS and Linux too, but only Windows
is verified.

## Required

### Godot 4 — standard build

The **standard** build, not .NET/Mono. This fork targets GDScript, so the
extra toolchain buys nothing.

Install from [godotengine.org](https://godotengine.org/download/), Steam, or
`winget install GodotEngine.GodotEngine`, then either put it on `PATH` or note
the full path — the runners in a published repo read `GODOT_PATH`.

```
godot --version          # 4.x.x.stable
godot --headless --quit  # harmless RID warnings on exit are fine
```

Godot's Windows executable is a GUI-subsystem program: a direct call neither
waits nor yields stdout, and a parse error hangs it instead of exiting. Never
drive it without a timeout. The engine guide has a runner that gets this right.

### Python 3.11+

```
python --version
pip install -r asset-gen/tools/requirements.txt
```

`google-genai` is only needed for the paid Gemini fallback:

```
pip install google-genai
```

### ffmpeg and ImageMagick

Proof-video encoding and sprite frame work.

```
winget install Gyan.FFmpeg ImageMagick.ImageMagick
```

## Knowledge base

The point of this fork: what one game learns, the next one starts with.
Without it, every project begins from zero.

```
git clone https://github.com/ddwolfer/Multi-knowledgeGraph D:\AI\kg
cd D:\AI\kg && npm install
```

Needs Node.js 22.12+. First run downloads a ~560MB embedding model, once.

`publish.py` looks for it at `GODOGEN_KG_HOME`, then `D:\AI\kg`, then a `kg/`
folder beside this checkout. Publishing still works without it — it prints a
warning and produces a repo with no memory.

Import the seed corpus into the shared craft database:

```
node D:\AI\kg\scripts\import-skills.js --db <godogen>\craft.db <godogen>\knowledge
```

Check afterwards that the imported nodes carry `trust = 'principle'`. The
post-compact hook only re-injects those, so getting it wrong means the
injection is silently empty.

## Optional — local asset generation

All three are free per call and reproducible. Skip any you do not need; the
skill falls back to paid cloud APIs.

**Blender** — procedural unit models. Any recent version. Set `BLENDER_PATH`
if it is not on `PATH` or in a conventional install location.

**ComfyUI** — icons and key art, expected at `127.0.0.1:8188`. Export a
working workflow in **API format** and keep it as a template. Flux at 12 steps
fits in 8GB VRAM.

**A local audio model** — sound effects over HTTP at `127.0.0.1:8002`,
accepting `{prompt, duration, seed, steps}` and returning `{raw_path}`.
Point `sfx_gen.py --endpoint` elsewhere if yours differs.

## Optional — Babylon.js

Node.js 22.12+ and a Chrome/Chromium with hardware WebGL2 for capture. Set
`CHROME_BIN` if it is not on a common path. Note that the Babylon guide is
inherited from upstream and unverified on Windows.

## Optional — paid asset APIs

Only needed for the cloud fallback. Every call costs money.

- `GOOGLE_API_KEY` — [Google AI Studio](https://aistudio.google.com/), Gemini images
- `XAI_API_KEY` — [xAI](https://console.x.ai/home), Grok images and video
- `TRIPO3D_API_KEY` — [Tripo3D](https://platform.tripo3d.ai/), image to 3D

## Verify

```
python -m pytest tests/ -v
python publish.py --engine godot --out %TEMP%\godogen-check --force
```

The publish output names every file it wrote and warns if the knowledge base
is missing.
