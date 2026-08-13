# 個人版 godogen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 godogen 改造成反映使用者實際做法的個人版產生器,並讓上一個專案的經驗透過 kg 帶到下一個。

**Architecture:** godogen 這個 source repo 本身就是跨專案知識庫(`knowledge/` + `craft.db`)。`publish.py` 把 manifest、engine guide、asset-gen skill、知識種子與 kg 接線一起倒進新遊戲 repo;遊戲 repo 在 run 中把教訓寫進自己的 `<game>.db`,再由 `/kg-harvest` 提案升級回 godogen。

**Tech Stack:** Python 3.13(publish 與素材工具)、Node.js(kg,外部依賴 `ddwolfer/Multi-knowledgeGraph`)、pytest 8.3、Godot 4 GDScript、Blender `bpy`、ComfyUI、ACE Studio。

## Global Constraints

- 平台以 Windows 為主;所有腳本必須在 Windows 與 POSIX 同時可跑。不得依賴 `rsync`、`mktemp`、`trap`、`xvfb`。
- **不寫 PowerShell 腳本。** 需要跨平台的執行邏輯一律用 Python 3。
- **所有檔案 I/O 必須明確指定 `encoding="utf-8"`。** Windows 上 Python 3.13 的預設編碼是 locale(cp950),中文內容會壞。
- 寫出的 `.json` / `.md` 不得帶 BOM(`JSON.parse_string` 吃到 BOM 回 null)。
- 文件語言:`knowledge/`、`engines/*.md`、`prompts/runtime.md` 用中文;`README.md`、CLI 介面與錯誤訊息用英文。
- 引擎目標只有 `godot` 與 `babylon`。host agent 固定 Claude,不再有 `--agent` 旗標。
- kg 位置:`GODOGEN_KG_HOME` 環境變數 > `D:\AI\kg` > 找不到則警告並產出不含 kg 的 repo。
- 每個 task 結束時 commit。分支 `personal-fork`,不推遠端。

---

## File Structure

**新增**

| 檔案 | 責任 |
|---|---|
| `publish.py` | 唯一的 publish 進入點。解析參數、組裝目標 repo、寫 kg 接線 |
| `scripts/publish_lib/layout.py` | 決定「哪些檔案去哪裡」——純資料與純函式,不碰磁碟 |
| `scripts/publish_lib/kgwire.py` | 產生 `.mcp.json` 與 `.claude/settings.json` 的內容 |
| `tests/test_layout.py` | `layout.py` 的單元測試 |
| `tests/test_kgwire.py` | `kgwire.py` 的單元測試 |
| `tests/test_publish_e2e.py` | 對暫存目錄跑完整 publish 的整合測試 |
| `knowledge/{principles,pitfalls,patterns}/*.md` | 跨專案知識種子語料 |
| `hooks/harvest_commit.py` | 第 1 層寫入:從 commit body 抽 episode |
| `tests/test_harvest_commit.py` | commit 解析的單元測試 |
| `skills/kg-harvest/SKILL.md` | 第 2 層:session 結束的升級提案 |
| `asset-gen/tools/sfx_gen.py` | ACE Studio 生成 + 後處理 |
| `asset-gen/tools/comfy_gen.py` | ComfyUI workflow 模板驅動 |
| `asset-gen/tools/blender_gen.py` | Blender `bpy` 腳本驅動 |
| `tests/test_sfx_post.py` | 音訊後處理的單元測試(不需要 ACE 服務) |

**修改**

| 檔案 | 改什麼 |
|---|---|
| `scripts/render_dir.py` | 加 `encoding="utf-8"` |
| `prompts/runtime.md` | 從 11 行擴為約 50 行,加入方法論 |
| `engines/godot.md` | 整份重寫:GDScript、sim/render、Windows |
| `engines/babylon.md` | 移除 Codex token,確認新 manifest 段落成立 |
| `asset-gen/SKILL.md` | 本地三條線為主體,雲端降級 |
| `README.md` | 反映新的引擎清單、publish 指令、kg 前置需求 |
| `AGENTS.md` | 反映新的 source layout |
| `docs/PROJECT.md` | 同上 |

**刪除**

`publish.sh`、`engines/bevy.md`、`scripts/generate_codex_metadata.py`、`docs/gdscript-vs-csharp.md`

---

## 階段 1 — 骨架與砍除

### Task 1: `layout.py` — publish 的純函式核心

**Files:**
- Create: `scripts/publish_lib/__init__.py`
- Create: `scripts/publish_lib/layout.py`
- Create: `tests/test_layout.py`

**Interfaces:**
- Consumes: 無
- Produces:
  - `ENGINES: dict[str, str]` — `{"godot": "Godot", "babylon": "Babylon.js"}`
  - `runtime_asset_dir(engine: str) -> str`
  - `manifest_tokens(engine: str) -> dict[str, str]`
  - `gitignore_lines(engine: str) -> list[str]`
  - `UnknownEngine(Exception)`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_layout.py
import pytest
from scripts.publish_lib import layout


def test_engines_are_godot_and_babylon_only():
    assert set(layout.ENGINES) == {"godot", "babylon"}


def test_runtime_asset_dir_differs_per_engine():
    assert layout.runtime_asset_dir("godot") == "assets"
    assert layout.runtime_asset_dir("babylon") == "src/assets"


def test_manifest_tokens_carry_display_name_and_guide_file():
    tokens = layout.manifest_tokens("godot")
    assert tokens["ENGINE_NAME"] == "Godot"
    assert tokens["ENGINE_GUIDE_FILE"] == "godot.md"
    assert tokens["ASSET_SKILL_COMMAND"] == "/asset-gen"


def test_gitignore_includes_engine_specific_and_common_lines():
    lines = layout.gitignore_lines("godot")
    assert ".claude" in lines
    assert "CLAUDE.md" in lines
    assert "godot.md" in lines
    assert ".godot" in lines
    assert "bin/" in lines


def test_unknown_engine_raises():
    with pytest.raises(layout.UnknownEngine):
        layout.manifest_tokens("bevy")
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_layout.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.publish_lib'`

- [ ] **Step 3: 實作**

```python
# scripts/publish_lib/layout.py
"""Pure decisions about what a published repo contains. No disk access."""

from __future__ import annotations

ENGINES: dict[str, str] = {"godot": "Godot", "babylon": "Babylon.js"}

_RUNTIME_ASSET_DIR = {"godot": "assets", "babylon": "src/assets"}

_ENGINE_IGNORES = {
    "godot": ["assets", "screenshots", ".godot", "*.import", "bin/", "obj/"],
    "babylon": ["/node_modules", "/dist", "/screenshots"],
}


class UnknownEngine(Exception):
    """Raised when an engine outside ENGINES is requested."""


def _check(engine: str) -> None:
    if engine not in ENGINES:
        raise UnknownEngine(f"unknown engine: {engine!r} (expected one of {sorted(ENGINES)})")


def runtime_asset_dir(engine: str) -> str:
    _check(engine)
    return _RUNTIME_ASSET_DIR[engine]


def manifest_tokens(engine: str) -> dict[str, str]:
    _check(engine)
    return {
        "ENGINE_NAME": ENGINES[engine],
        "ENGINE_GUIDE_FILE": f"{engine}.md",
        "ASSET_SKILL_COMMAND": "/asset-gen",
    }


def gitignore_lines(engine: str) -> list[str]:
    _check(engine)
    return [".claude", "CLAUDE.md", f"{engine}.md", *_ENGINE_IGNORES[engine]]
```

也要建立空的 `scripts/publish_lib/__init__.py` 與 `scripts/__init__.py`(讓 `from scripts.publish_lib import layout` 可解析),並在 repo 根目錄加 `pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_layout.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/__init__.py scripts/publish_lib/ tests/test_layout.py pytest.ini
git commit -m "feat(publish): pure layout decisions for godot and babylon"
```

---

### Task 2: `publish.py` — 組裝目標 repo

**Files:**
- Create: `publish.py`
- Create: `tests/test_publish_e2e.py`
- Modify: `scripts/render_dir.py`

**Interfaces:**
- Consumes: `layout.ENGINES`, `layout.manifest_tokens`, `layout.runtime_asset_dir`, `layout.gitignore_lines`
- Produces:
  - `publish(engine: str, out: Path, force: bool = False, kg_home: Path | None = None) -> None`
  - `render_text(text: str, tokens: dict[str, str]) -> str`

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_publish_e2e.py
import json
from pathlib import Path

import pytest

import publish


def test_publish_godot_creates_expected_files(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out)

    assert (out / "CLAUDE.md").is_file()
    assert (out / "godot.md").is_file()
    assert (out / ".claude" / "skills" / "asset-gen" / "SKILL.md").is_file()
    assert (out / ".gitignore").is_file()


def test_manifest_tokens_are_substituted(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out)
    text = (out / "CLAUDE.md").read_text(encoding="utf-8")
    assert "${" not in text
    assert "Godot" in text


def test_skill_tokens_are_substituted(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("babylon", out)
    text = (out / ".claude" / "skills" / "asset-gen" / "SKILL.md").read_text(encoding="utf-8")
    assert "${" not in text
    assert "src/assets" in text


def test_force_wipes_existing_target(tmp_path: Path):
    out = tmp_path / "game"
    out.mkdir()
    stale = out / "stale.txt"
    stale.write_text("old", encoding="utf-8")

    publish.publish("godot", out, force=True)
    assert not stale.exists()


def test_without_force_existing_files_survive(tmp_path: Path):
    out = tmp_path / "game"
    out.mkdir()
    keep = out / "keep.txt"
    keep.write_text("mine", encoding="utf-8")

    publish.publish("godot", out)
    assert keep.read_text(encoding="utf-8") == "mine"


def test_unknown_engine_is_rejected(tmp_path: Path):
    with pytest.raises(publish.layout.UnknownEngine):
        publish.publish("bevy", tmp_path / "game")


def test_no_bom_in_written_json(tmp_path: Path):
    out = tmp_path / "game"
    publish.publish("godot", out)
    for path in out.rglob("*.json"):
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), path
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_publish_e2e.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'publish'`

- [ ] **Step 3: 實作 `publish.py`**

要點:
- `shutil.copytree(..., dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))` 取代 `rsync`
- `tempfile.TemporaryDirectory()` 取代 `mktemp -d` + `trap`
- 所有 `read_text` / `write_text` 帶 `encoding="utf-8"`,寫檔一律 `newline="\n"`
- `--force` 用 `shutil.rmtree(out)`;先驗證 `out` 不是 repo 根目錄本身
- `git init` 用 `subprocess.run([...], check=False)`,失敗不中斷

```python
#!/usr/bin/env python3
"""Publish godogen runtime files into a target game repo."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.publish_lib import layout

REPO_ROOT = Path(__file__).resolve().parent


def render_text(text: str, tokens: dict[str, str]) -> str:
    for key, value in tokens.items():
        text = text.replace(f"${{{key}}}", value)
    return text


def _render_tree(root: Path, tokens: dict[str, str]) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rendered = render_text(original, tokens)
        if rendered != original:
            path.write_text(rendered, encoding="utf-8", newline="\n")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
```

`publish()` 的流程:驗證 engine → 解析 `out` → `--force` 清空 → 暫存目錄渲染 skill → 複製到 `.claude/skills/asset-gen/` → 渲染 manifest 成 `CLAUDE.md` → 複製 `engines/<engine>.md` → 寫 `.gitignore`(不存在才寫)→ `git init`。

CLI:`--engine`(必填,choices 來自 `layout.ENGINES`)、`--out`(必填,也接受位置參數)、`--force`。

- [ ] **Step 4: 修 `render_dir.py` 的編碼**

`path.read_text()` → `path.read_text(encoding="utf-8")`,`path.write_text(text)` → `path.write_text(text, encoding="utf-8", newline="\n")`。

- [ ] **Step 5: 跑測試確認通過**

Run: `python -m pytest tests/ -v`
Expected: 12 passed

- [ ] **Step 6: Commit**

```bash
git add publish.py tests/test_publish_e2e.py scripts/render_dir.py
git commit -m "feat(publish): python publish replacing publish.sh"
```

---

### Task 3: 砍掉 Bevy 與 Codex

**Files:**
- Delete: `publish.sh`, `engines/bevy.md`, `scripts/generate_codex_metadata.py`, `docs/gdscript-vs-csharp.md`
- Modify: `README.md`, `AGENTS.md`, `docs/PROJECT.md`

- [ ] **Step 1: 刪檔**

```bash
git rm publish.sh engines/bevy.md scripts/generate_codex_metadata.py docs/gdscript-vs-csharp.md
```

- [ ] **Step 2: 更新三份文件**

`README.md` — 引擎清單只留 Godot / Babylon;prerequisites 移除 Rust/Cargo,加上 kg 與 Node.js;publish 範例改 `python publish.py --engine godot --out ~/my-game`;移除 Codex 相關敘述與上游作者的推廣連結(改為註明 fork 自 `alex_erm/godogen`)。

`AGENTS.md` — source layout 段落改為新結構(加 `knowledge/`、`hooks/`、`skills/`,移除 `scripts/generate_codex_metadata.py`)。保留「Don't give obvious guidance」那條編輯規則。

`docs/PROJECT.md` — 移除 Bevy 段落與 Codex 敘述;「Runtime Limitations」那句「does not ship a dedicated audio pipeline」要刪掉,因為階段 5 會補上音訊。

- [ ] **Step 3: 確認沒有殘留引用**

Run: `grep -rniE "bevy|codex|openai\.yaml|publish\.sh|\.agents/" --include='*.md' --include='*.py' . | grep -v docs/superpowers`
Expected: 無輸出

- [ ] **Step 4: 跑測試**

Run: `python -m pytest tests/ -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: drop bevy and codex targets"
```

---

## 階段 2 — 知識層

### Task 4: 種子語料

**Files:**
- Create: `knowledge/README.md`
- Create: `knowledge/pitfalls/{windows-godot-toolchain,gdscript-silent-failures,godot-headless-windows,silent-lookup-apis,blender-gltf-orientation,fake-green-tests}.md`
- Create: `knowledge/principles/{mechanism-weight,difficulty-tracks-player-power,readability-is-gameplay,rules-own-their-failures,presentation-before-numbers,one-knob-at-a-time,disaggregate-your-stats}.md`
- Create: `knowledge/patterns/{deterministic-tick-sim,five-layer-verification,local-asset-pipeline}.md`
- Create: `tests/test_knowledge_corpus.py`

**Interfaces:**
- Produces: 每個 `.md` 的第一行是 `# <標題>`,供 kg 匯入時當 node name。

每條的內容來源見規格文件的「元件 / `knowledge/`」章節。`windows-godot-toolchain`、`mechanism-weight`、`difficulty-tracks-player-power`、`readability-is-gameplay`、`rules-own-their-failures`、`deterministic-tick-sim` 從 `D:\AI\guildrun\kg-knowledge\` 對應檔案搬,其餘依規格新寫。

**寫作規範**(寫進 `knowledge/README.md`):每條必須有「規則」與「案例」兩段。案例要具體到可驗證(數字、檔名、seed)。沒有案例的條目不收 —— 沒踩過的教訓不是知識。

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_knowledge_corpus.py
from pathlib import Path

import pytest

CORPUS = Path("knowledge")
CATEGORIES = ("pitfalls", "principles", "patterns")


def _entries():
    return [p for c in CATEGORIES for p in (CORPUS / c).glob("*.md")]


def test_corpus_has_all_three_categories():
    for category in CATEGORIES:
        assert (CORPUS / category).is_dir(), category


def test_corpus_is_not_empty():
    assert len(_entries()) >= 15


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_starts_with_h1(path: Path):
    first = path.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("# "), f"{path} must start with an H1 title"


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_has_a_case_section(path: Path):
    text = path.read_text(encoding="utf-8")
    assert "案例" in text or "實例" in text, f"{path} needs a concrete case"


@pytest.mark.parametrize("path", _entries(), ids=lambda p: p.name)
def test_entry_has_no_bom(path: Path):
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), path
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_knowledge_corpus.py -v`
Expected: FAIL — `knowledge` 目錄不存在

- [ ] **Step 3: 寫語料**

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/test_knowledge_corpus.py -v`
Expected: all passed(16 個條目 × 3 條參數化檢查 + 2 條總體)

- [ ] **Step 5: Commit**

```bash
git add knowledge/ tests/test_knowledge_corpus.py
git commit -m "feat(knowledge): seed cross-project corpus"
```

---

### Task 5: kg 接線

**Files:**
- Create: `scripts/publish_lib/kgwire.py`
- Create: `tests/test_kgwire.py`
- Modify: `publish.py`
- Modify: `tests/test_publish_e2e.py`

**Interfaces:**
- Consumes: 無
- Produces:
  - `find_kg_home(env: dict[str, str] | None = None) -> Path | None`
  - `mcp_config(kg_home: Path, craft_db: Path, game_db: Path) -> dict`
  - `hook_settings(kg_home: Path, craft_db: Path, game_db: Path) -> dict`
  - `KG_MISSING_WARNING: str`

hook 接線規則:`session-start`、`post-compact`、`auto-recall` 各對兩個 DB 跑一次(先 craft 後 game);`search-enforcer` 只對 game DB 跑一次。

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_kgwire.py
from pathlib import Path

from scripts.publish_lib import kgwire


def test_env_override_wins(tmp_path: Path):
    kg = tmp_path / "custom-kg"
    kg.mkdir()
    (kg / "main.js").touch()
    found = kgwire.find_kg_home({"GODOGEN_KG_HOME": str(kg)})
    assert found == kg


def test_missing_kg_returns_none():
    assert kgwire.find_kg_home({"GODOGEN_KG_HOME": "/nonexistent/kg"}) is None


def test_mcp_config_declares_two_servers(tmp_path: Path):
    cfg = kgwire.mcp_config(tmp_path / "kg", tmp_path / "craft.db", tmp_path / "game.db")
    assert set(cfg["mcpServers"]) == {"kg-craft", "kg-game"}


def test_injecting_hooks_run_against_both_dbs(tmp_path: Path):
    settings = kgwire.hook_settings(tmp_path / "kg", tmp_path / "craft.db", tmp_path / "game.db")
    compact = [g for g in settings["hooks"]["SessionStart"] if g["matcher"] == "compact"][0]
    assert len(compact["hooks"]) == 2
    commands = " ".join(h["command"] for h in compact["hooks"])
    assert "craft.db" in commands and "game.db" in commands


def test_search_enforcer_runs_once_against_game_db(tmp_path: Path):
    settings = kgwire.hook_settings(tmp_path / "kg", tmp_path / "craft.db", tmp_path / "game.db")
    pre = settings["hooks"]["PreToolUse"]
    assert sum(len(g["hooks"]) for g in pre) == 1
    assert "game.db" in pre[0]["hooks"][0]["command"]
    assert "craft.db" not in pre[0]["hooks"][0]["command"]
```

整合測試補三條:kg 存在時 `.mcp.json` 與 `.claude/settings.json` 都寫出來;kg 不存在時兩者都不寫、但 publish 仍成功且印出警告;`knowledge/` 種子有複製進 `kg-seed/`。

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_kgwire.py -v`
Expected: FAIL — 模組不存在

- [ ] **Step 3: 實作 `kgwire.py` 並接進 `publish.py`**

`find_kg_home` 依序檢查:`env["GODOGEN_KG_HOME"]`、`D:\AI\kg`、godogen 同層的 `../kg`。認定條件是該目錄下有 `main.js` 與 `hooks/`。

`publish()` 新增:kg 找到就寫 `.mcp.json` + `.claude/settings.json`,把 `knowledge/` 複製到目標的 `kg-seed/`,並在輸出提示如何匯入;找不到就 `print(KG_MISSING_WARNING, file=sys.stderr)` 後照常完成。

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/ -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add scripts/publish_lib/kgwire.py tests/test_kgwire.py publish.py tests/test_publish_e2e.py
git commit -m "feat(kg): wire craft and game knowledge bases into published repos"
```

---

## 階段 3 — 寫入路徑

### Task 6: 第 1 層 — commit 收割 hook

**Files:**
- Create: `hooks/harvest_commit.py`
- Create: `tests/test_harvest_commit.py`
- Modify: `scripts/publish_lib/kgwire.py`(加 `PostToolUse` 接線)
- Modify: `tests/test_kgwire.py`

**Interfaces:**
- Produces:
  - `parse_sections(body: str) -> dict[str, str]`
  - `to_episodes(subject: str, body: str) -> list[dict]` — 每個 episode 有 `type`、`summary`、`outcome`
  - `HARVEST_HEADINGS: tuple[str, ...]` — `("踩到的坑", "平衡回歸", "Pitfall:", "Regression:")`

- [ ] **Step 1: 寫失敗測試**

用 guildrun 的真實 commit body 當測試素材(`084f126`),這是已知可解析的真樣本。

```python
# tests/test_harvest_commit.py
from hooks import harvest_commit

BODY = """高度層管「站得上去嗎」，新的 terrain 層管「站在上面會怎樣」。

- 泥沼：移動 -40%、不能發動衝鋒

踩到的坑：A* 加了地形成本後 octile 啟發式會高估（道路 70 < 基礎 100），
A* 失去最佳性、算出來的路根本不走道路。啟發式乘上最小地形成本當下界。
另一個：第一版測試把地形蓋在 add_squad 的錨點上，但編隊會位移，
六條測試全假綠——改成蓋在單位真正站的格子上。

平衡回歸（探針，零指令）：斷橋雙島大幅改善（獵弓 75% 2/6→6/6）。

1015 項測試綠。
"""


def test_extracts_pitfall_section():
    sections = harvest_commit.parse_sections(BODY)
    assert "踩到的坑" in sections
    assert "octile" in sections["踩到的坑"]


def test_pitfall_section_stops_at_next_section():
    sections = harvest_commit.parse_sections(BODY)
    assert "斷橋雙島" not in sections["踩到的坑"]


def test_extracts_balance_section():
    sections = harvest_commit.parse_sections(BODY)
    assert "平衡回歸" in sections
    assert "獵弓" in sections["平衡回歸"]


def test_body_without_headings_yields_nothing():
    assert harvest_commit.parse_sections("just a normal commit\n\nno sections here") == {}


def test_to_episodes_tags_type_and_carries_subject():
    episodes = harvest_commit.to_episodes("feat: 地形屬性", BODY)
    kinds = {e["type"] for e in episodes}
    assert kinds == {"pitfall", "regression"}
    assert all("地形屬性" in e["summary"] for e in episodes)


def test_to_episodes_empty_for_plain_commit():
    assert harvest_commit.to_episodes("chore: bump", "nothing structured") == []
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_harvest_commit.py -v`
Expected: FAIL — 模組不存在

- [ ] **Step 3: 實作**

`parse_sections` 掃描 body 的每一行,遇到以 `HARVEST_HEADINGS` 任一項開頭的行就開始收集,直到遇到下一個標題行或空行後接非縮排的新段落為止。標題後可接全形或半形冒號。

hook 本體從 stdin 讀 Claude Code 的 `PostToolUse` payload,判斷 `tool_input.command` 是否含 `git commit`,若是則跑 `git log -1 --format=%s%n%b` 取得剛才的 commit,解析後寫進 `<game>.db`。寫入用 `node <kg>/scripts/...` 還是直接 sqlite,取決於 kg 的 API —— **實作時先讀 `kg/lib/db.js` 確認 `episodes` 表的欄位與寫入路徑**,以該檔為準。

失敗一律靜默(`sys.exit(0)`):收割壞掉不該擋住使用者 commit。

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/ -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add hooks/ tests/test_harvest_commit.py scripts/publish_lib/kgwire.py tests/test_kgwire.py
git commit -m "feat(kg): harvest pitfalls from commit bodies into game db"
```

---

### Task 7: 第 2 層 — `/kg-harvest` skill

**Files:**
- Create: `skills/kg-harvest/SKILL.md`
- Modify: `publish.py`(把 `skills/` 底下的 skill 一起 publish)
- Modify: `tests/test_publish_e2e.py`

skill 內容要求:回看本 session 的 commit 與 `<game>.db` 的 episode,挑出**跨專案成立**的教訓(判準:換一個遊戲、換一個題材仍然為真),提案 0–3 條,每條附:建議的檔名、分類、完整 `.md` 內容、以及它從哪個 episode 來。提案後等使用者核可,核可才寫進 godogen 的 `knowledge/`。

明確寫進 skill:**寧可提 0 條也不要湊數。** 大部分 session 不會產生跨專案知識。

- [ ] **Step 1: 加整合測試**

```python
def test_publish_installs_kg_harvest_skill(tmp_path):
    out = tmp_path / "game"
    publish.publish("godot", out)
    assert (out / ".claude" / "skills" / "kg-harvest" / "SKILL.md").is_file()
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/test_publish_e2e.py::test_publish_installs_kg_harvest_skill -v`
Expected: FAIL

- [ ] **Step 3: 寫 skill 並讓 publish 複製整個 `skills/` 目錄**

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/ -v`

- [ ] **Step 5: Commit**

```bash
git add skills/ publish.py tests/test_publish_e2e.py
git commit -m "feat(kg): kg-harvest skill for promoting lessons to craft knowledge"
```

---

## 階段 4 — 文件層

### Task 8: `prompts/runtime.md`

**Files:** Modify `prompts/runtime.md`

保留現有的 asset / engine guide / README 三條,以及 Delivery 段落。新增四段,每段最多三句:sim/render 分離與決定論(附「非模擬型遊戲可不採用」的逃生門)、驗收五層梯、先查呈現層再查數值、一次只轉一個旋鈕。

必須對 Godot 與 Babylon 同時成立 —— 不得出現 GDScript、`.tscn`、Windows 路徑。

- [ ] **Step 1: 加測試**

```python
# tests/test_manifest.py
from pathlib import Path

MANIFEST = Path("prompts/runtime.md")


def test_manifest_is_engine_neutral():
    text = MANIFEST.read_text(encoding="utf-8")
    for banned in ("GDScript", ".tscn", "C:\\", "D:\\", "godot.md", "babylon.md"):
        assert banned not in text, banned


def test_manifest_covers_the_four_methods():
    text = MANIFEST.read_text(encoding="utf-8")
    for topic in ("決定論", "呈現層", "旋鈕", "驗收"):
        assert topic in text, topic


def test_manifest_keeps_its_tokens():
    text = MANIFEST.read_text(encoding="utf-8")
    for token in ("${ENGINE_NAME}", "${ENGINE_GUIDE_FILE}", "${ASSET_SKILL_COMMAND}"):
        assert token in text, token
```

- [ ] **Step 2–4: 失敗 → 改寫 → 通過**
- [ ] **Step 5: Commit** — `docs(manifest): encode methodology in the runtime manifest`

---

### Task 9: `engines/godot.md` 重寫

**Files:** Modify `engines/godot.md`

章節:Stack(GDScript)、專案形狀(sim/render 分離的目錄)、GDScript 靜默失敗、Windows 工具鏈、驗收(截圖/測試 runner/探針/autotest)、錄影、從上游保留的 3D 陷阱。

- [ ] **Step 1: 加測試**

```python
# tests/test_engine_guides.py
from pathlib import Path


def test_godot_guide_has_no_csharp_leftovers():
    text = Path("engines/godot.md").read_text(encoding="utf-8")
    for banned in ("partial", ".csproj", "dotnet build", "SetScript()", "EnableDynamicLoading"):
        assert banned not in text, banned


def test_godot_guide_covers_windows_traps():
    text = Path("engines/godot.md").read_text(encoding="utf-8")
    for topic in ("WaitForExit", "SCRIPT ERROR", "sort_custom", "BOM"):
        assert topic in text, topic


def test_no_xvfb_anywhere():
    for path in Path("engines").glob("*.md"):
        assert "xvfb" not in path.read_text(encoding="utf-8"), path
```

- [ ] **Step 2–4: 失敗 → 重寫 → 通過**
- [ ] **Step 5: Commit** — `docs(godot): rewrite guide for gdscript, sim/render, and windows`

---

### Task 10: `engines/babylon.md`

**Files:** Modify `engines/babylon.md`

移除 Codex 相關 token 與 xvfb;在檔頭加一行「未在 Windows 驗證」。確認 Task 8 新增的 manifest 段落對它成立(它有自己的 sim/render 對應說法)。

- [ ] **Step 1: 跑 Task 9 的 `test_no_xvfb_anywhere`,確認 babylon 讓它紅**
- [ ] **Step 2: 修改**
- [ ] **Step 3: 跑測試確認通過**
- [ ] **Step 4: Commit** — `docs(babylon): drop codex and xvfb, mark windows-unverified`

---

## 階段 5 — 素材管線

三個工具彼此獨立,可任意順序。共同約定:CLI 輸出 JSON 到 stdout(`{"ok": true, "path": ..., "cost_cents": 0}`),進度到 stderr —— 與現有 `asset_gen.py` 一致,讓 SKILL.md 的用法統一。

### Task 11: `sfx_gen.py`

**Files:**
- Create: `asset-gen/tools/sfx_gen.py`
- Create: `tests/test_sfx_post.py`

**Interfaces:**
- Produces:
  - `trim_onset(samples: list[int], peak_ratio: float = 0.02, lead_ms: float = 3.0, rate: int = 44100) -> list[int]`
  - `fade_out(samples: list[int], ms: float = 50.0, rate: int = 44100) -> list[int]`
  - `rms_dbfs(samples: list[int]) -> float`
  - `normalize_to(samples: list[int], target_dbfs: float) -> list[int]`
  - `soft_compress(samples: list[int], amount: float = 3.2) -> list[int]`

後處理是純函式,不需要 ACE 服務就能測 —— 這是把它跟網路呼叫分開的理由。

- [ ] **Step 1: 寫失敗測試**

```python
# tests/test_sfx_post.py
import math

from asset_gen_tools import sfx_gen  # see conftest for path wiring


def test_trim_onset_removes_leading_silence():
    samples = [0] * 1000 + [10000, -10000] * 100
    trimmed = sfx_gen.trim_onset(samples, rate=1000, lead_ms=0)
    assert len(trimmed) == 200


def test_trim_onset_keeps_lead_in():
    samples = [0] * 1000 + [10000] * 100
    trimmed = sfx_gen.trim_onset(samples, rate=1000, lead_ms=10)
    assert len(trimmed) == 110


def test_fade_out_ends_at_zero():
    samples = [10000] * 1000
    faded = sfx_gen.fade_out(samples, ms=100, rate=1000)
    assert faded[-1] == 0
    assert faded[0] == 10000


def test_rms_dbfs_of_full_scale_square_is_near_zero():
    samples = [32767, -32767] * 100
    assert abs(sfx_gen.rms_dbfs(samples)) < 0.1


def test_normalize_raises_quiet_signal():
    quiet = [100, -100] * 100
    louder = sfx_gen.normalize_to(quiet, -17.0)
    assert abs(sfx_gen.rms_dbfs(louder) - (-17.0)) < 0.2


def test_soft_compress_lifts_small_and_holds_peaks():
    samples = [1000, 32000]
    out = sfx_gen.soft_compress(samples, amount=3.2)
    assert out[0] > samples[0]          # quiet detail lifted
    assert abs(out[1]) <= 32767         # peak stays in range


def test_soft_compress_never_clips():
    samples = [32767, -32767, 30000]
    out = sfx_gen.soft_compress(samples, amount=5.0)
    assert all(-32768 <= s <= 32767 for s in out)
```

- [ ] **Step 2: 跑測試確認失敗**
- [ ] **Step 3: 實作** — 只用 `wave`、`struct`、`math`、`json`、`urllib`。`generate` 子命令 POST 到 `http://127.0.0.1:8002/generate`;`post` 子命令對既有 wav 跑後處理鏈。
- [ ] **Step 4: 跑測試確認通過**
- [ ] **Step 5: Commit** — `feat(asset-gen): local sfx generation with post-processing`

---

### Task 12: `comfy_gen.py`

**Files:** Create `asset-gen/tools/comfy_gen.py`, `tests/test_comfy_gen.py`

**Interfaces:**
- Produces:
  - `STYLE_PROMPT: str` — 鎖定的風格字串
  - `build_prompt(subject: str, style: str = STYLE_PROMPT) -> str`
  - `patch_workflow(workflow: dict, prompt: str, seed: int, width: int, height: int) -> dict`

測試針對 `build_prompt` 與 `patch_workflow`(純函式,不需要 ComfyUI 服務):風格字串必須出現在每個 prompt 裡;`patch_workflow` 不得就地修改輸入;找不到 CLIPTextEncode 節點要 raise。

- [ ] **Step 1–5:** 同上節奏,commit 訊息 `feat(asset-gen): comfyui workflow-template image generation`

---

### Task 13: `blender_gen.py`

**Files:** Create `asset-gen/tools/blender_gen.py`, `asset-gen/blender.md`, `tests/test_blender_gen.py`

參考 `D:\AI\guildrun\game\tools\make_units.py` 的實際寫法。`blender_gen.py` 本身是**驅動器**不是建模器:找到 blender 執行檔、用 `--background --python <script>` 跑使用者的建模腳本、驗證輸出的 glTF 存在且非空。

`asset-gen/blender.md` 寫約定:Z-up / 腳底 z=0 / 正面 -Y(轉 glTF 後變 +Z)、輪廓優先、3–8 個幾何體、色塊無貼圖、顏色表與渲染層常數同步、旗面與弓身要斜向鏡頭。

測試針對 `find_blender()` 的搜尋順序(env `BLENDER_PATH` > Steam 預設路徑 > `PATH`)與 glTF 輸出驗證,不實際跑 Blender。

- [ ] **Step 1–5:** commit 訊息 `feat(asset-gen): blender procedural modeling driver`

---

### Task 14: `asset-gen/SKILL.md` 重寫

**Files:** Modify `asset-gen/SKILL.md`

結構:核心原則(生成只是第一步,後處理才是關鍵)→ 三條本地線 → 現成素材混用(KayKit:用內容物不用地磚、樹林兼 blocked tiles)→ 雲端 fallback(降到最後,標明「沒有本地 GPU 時」)→ 資產清單規範(保留上游的 in-game Size 欄)。

- [ ] **Step 1: 加測試**

```python
# tests/test_asset_skill.py
from pathlib import Path

SKILL = Path("asset-gen/SKILL.md")


def test_local_tools_come_before_cloud():
    text = SKILL.read_text(encoding="utf-8")
    assert text.index("blender_gen") < text.index("asset_gen.py")
    assert text.index("sfx_gen") < text.index("Tripo3D")


def test_skill_keeps_asset_manifest_rule():
    text = SKILL.read_text(encoding="utf-8")
    assert "Size" in text


def test_skill_keeps_its_tokens():
    text = SKILL.read_text(encoding="utf-8")
    for token in ("${ASSET_GEN_SKILL_DIR}", "${RUNTIME_ASSET_DIR}"):
        assert token in text, token
```

- [ ] **Step 2–4: 失敗 → 重寫 → 通過**
- [ ] **Step 5: Commit** — `docs(asset-gen): local-first pipeline with cloud demoted`

---

## 階段 6 — 端對端

### Task 15: 實跑驗收

**Files:** 無新增

- [ ] **Step 1: 全套測試**

Run: `python -m pytest tests/ -v`
Expected: all passed

- [ ] **Step 2: publish 到暫存目錄並人工檢查**

```bash
python publish.py --engine godot --out /tmp/godogen-smoke --force
```

檢查:`CLAUDE.md` 無殘留 `${`、`godot.md` 存在、`.claude/skills/` 有 `asset-gen` 與 `kg-harvest`、`.mcp.json` 兩個 server(或 kg 缺席的警告)。

- [ ] **Step 3: 記錄未完成項目**

規格「驗收方式」的第 2–5 項需要 kg 實際安裝在 `D:\AI\kg` 才能跑。若 kg 尚未安裝,把這四項寫進 `docs/superpowers/plans/` 底下的驗收待辦,不要宣稱通過。

- [ ] **Step 4: Commit** — `chore: end-to-end publish smoke check`

---

## 驗收結果(2026-08-13)

kg 指向 `D:/AI/guildrun/kg`(已安裝的既有實例,唯讀)進行驗證。

**通過**

1. `publish.py --engine godot` 產出完整 repo,含 `CLAUDE.md`、`godot.md`、兩個 skill、`.mcp.json`、`.claude/settings.json`、`.kg/`,零殘留 `${TOKEN}`。
2. 三個注入型 hook 各對兩個 DB 接線,`post-compact.js` 實跑成功並注入知識。
3. 收割 hook 端對端:真 commit(含「踩到的坑」段落)→ PostToolUse payload → episode 正確寫入,`type=lesson`、`context=踩到的坑`、`session_id` 都對。
4. 對 guildrun 真實歷史 `--replay HEAD~40..HEAD` 收割出 3 條,依段落正確分類,資料為正確 UTF-8。
5. 種子語料匯入:**17/17 皆為 `trust='principle'`**,`post-compact` 確認會注入。
6. 全套測試 216 passed。

**未驗證**

- 端對端跑一次真實 generation run(需要 Godot 專案與數小時)。
- Babylon 的 capture 路徑(從上游繼承,未在 Windows 驗證)。
- `auto-recall.js` 與 `session-start.js` 只驗證了接線,未在真實 session 觀察注入內容。

**實跑發現的兩個新問題**(都在 kg 側,不在本 repo)

- **`post-compact.js` 只取 `LIMIT 10`,依 `access_count DESC` 排序。** 語料有 17 條,而全新匯入時 `access_count` 全為 0,所以壓縮後注入哪 10 條是不定的。語料再長就會有條目永遠進不了注入。
- **`sqlite-vec` 擴充載入失敗(`no such module: vec0`),向量檢索是空的**,目前只有 FTS5 全文檢索有效。匯入時 `0 with embeddings` 就是這個徵兆。語意相近但用詞不同的查詢會召回不到。

兩者都列入 Task 18 的範圍。

## Self-Review

**Spec coverage** — 規格各節對應的 task:知識迴圈 → Task 4/5/6/7;兩個知識庫 → Task 5;kg 安裝 → Task 5;讀取路徑 → Task 5;寫入三層 → Task 6(第 1 層)、Task 7(第 2 層)、Task 7 的 skill 內容(第 3 層);種子語料 → Task 4;manifest → Task 8;godot.md → Task 9;babylon.md → Task 10;asset-gen → Task 11–14;publish.py → Task 1/2;移除項目 → Task 3;GDScript 決策 → Task 9 的內容與 Task 3 刪掉舊比較文件;驗收方式 → Task 15。

**已知缺口** — 規格「非目標」明列不自動化第 3 層寫入,故 Task 7 只做提案不做自動寫入,這是刻意的。規格驗收項目 2–5 依賴 kg 實裝,Task 15 Step 3 明確要求誠實記錄而非宣稱通過。

**Type consistency** — `layout.manifest_tokens` 回傳的 key 與 `publish.render_text` 消費的 token 名一致(`ENGINE_NAME`、`ENGINE_GUIDE_FILE`、`ASSET_SKILL_COMMAND`);`kgwire.find_kg_home` 在 `publish.publish(kg_home=...)` 未指定時被呼叫;`harvest_commit.HARVEST_HEADINGS` 同時被 `parse_sections` 與測試消費。
