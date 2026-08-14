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
git clone https://github.com/ddwolfer/Multi-knowledgeGraph <kg>
cd <kg> && npm install
```

Needs Node.js 22.12+. First run downloads a ~560MB embedding model, once.

`publish.py` looks for it at `GODOGEN_KG_HOME`, then `<kg>`, then a `kg/`
folder beside this checkout. Publishing still works without it — it prints a
warning and produces a repo with no memory.

Import the seed corpus into the shared craft database. Three steps, none of
them optional:

```
node <kg>\scripts\import-skills.js knowledge --db craft.db
node <kg>\scripts\backfill-embeddings.js --db craft.db
python scripts\seed_priority.py --db craft.db
```

**The backfill is not optional.** `import-skills.js` gates embedding on
`isReady()`, which only becomes true after `embed()` has been called -- so a
fresh process always writes zero vectors and still reports success. The
backfill calls `embed()` directly. First run downloads a ~560MB model.

**The priority seeding is not optional either.** The post-compact hook injects
`ORDER BY access_count DESC LIMIT 10`; with a fresh import every count is 0
and the selection is arbitrary. On a 20-entry corpus that dropped every
principle, leaving traps and no method. Re-run it after every import.

Verify -- do not trust the import's own reporting:

```
cd <kg>
node -e "const D=require('better-sqlite3'),V=require('sqlite-vec');const db=new D('craft.db',{readonly:true});V.load(db);console.log('nodes',db.prepare('SELECT count(*) c FROM nodes').get().c,'vec',db.prepare('SELECT count(*) c FROM vec_nodes').get().c)"
```

Both numbers must match. `vec 0` means the backfill did not run.

## Optional — local asset generation

All three are free per call and reproducible. Skip any you do not need; the
skill falls back to paid cloud APIs.

**Blender** — procedural unit models. Any recent version. Set `BLENDER_PATH`
if it is not on `PATH` or in a conventional install location.

**ComfyUI** — icons and key art, expected at `127.0.0.1:8188`. Export a
working workflow in **API format** and keep it as a template. Flux at 12 steps
fits in 8GB VRAM.

**[ACE Studio](https://github.com/ddwolfer/ACE_Studio)** — music and sound
effects, generated locally and kept in a library that carries across projects.
Wired as an MCP server, so the agent gets `list_library` and the generators as
tools rather than shelling out over HTTP. Found at `<godogen>/ACE_Studio`,
`../ACE_Studio` or `~/.godogen/ACE_Studio`, or set `ACE_STUDIO_HOME`.

Its library is the audio equivalent of `craft.db`: search it before generating.
`sfx_gen.py library --query footstep` filters it without pulling everything
into context, and `sfx_gen.py post <path> -o ...` fits an existing sound to
this game — ACE trims silence, but only godogen knows how loud the rest of
this game is.

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
