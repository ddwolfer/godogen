# Godogen Source Repo

This repository is not a published game repo. It is the source that `publish.py` renders into a runtime game repo for a chosen engine.

## Source Layout

- `prompts/runtime.md` — the engine-agnostic runtime manifest text
- `asset-gen/` — the asset-generation skill (CLI tools + docs), the one skill every published repo carries
- `engines/godot.md`, `engines/babylon.md` — per-engine guides (stack, project sketch, capture recipe, silent-failure traps)
- `knowledge/` — the cross-project corpus, indexed into `craft.db` by `scripts/bootstrap.py`
- `skills/` — skills installed into published repos alongside `asset-gen`
- `hooks/harvest_commit.py` — the commit harvester, referenced by published repos at an absolute path
- `publish.py` — renders a runtime repo with `--engine {godot,babylon} --agent {claude,codex}`
- `scripts/publish_lib/` — pure publish decisions (`layout.py`, `kgwire.py`), kept free of disk access so they stay testable
- `tests/` — pytest suite; run with `python -m pytest tests/ -v`

## Editing Rules

- Do not create or maintain `.claude/skills/` or `.agents/skills/` in this source repo.
- A new `${TOKEN}` must be added to `layout._SKILL_COMMANDS` or both token functions. Reaching one document and not the other ships a literal `${TOKEN}`.
- Corpus entries need `source`, `verified`, and an opening `> 「one-line summary」`. The summary is what makes the importer mark the node a principle, and only principles survive compaction.
- Don't give obvious guidance. The agent is a highly capable LLM, and the deliverable (a recorded video, or a live URL the user watches) surfaces its own mistakes — so keep the guides to what the model can't infer or discover fast.
- When you change or remove a feature, describe the new state on its own terms. Name the new thing as if it were always the design.
- All file I/O specifies `encoding="utf-8"` and writes LF endings. The default locale encoding on Windows is cp950 and will corrupt the guides.
- No PowerShell scripts. Cross-platform execution logic is Python 3.
