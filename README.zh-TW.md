# Godogen

用 Claude Code 或 Codex 自動開發 Godot 與 Babylon.js 遊戲 —— 而且每個新專案都從上一個學到的東西開始。

繁體中文 | [English](README.md)

Fork 自 [alex_erm/godogen](https://github.com/alex-erm/godogen),見[與上游的差異](#與上游的差異)。

描述一個遊戲。agent 把它蓋出來、生成素材、跑起引擎,然後**證明**結果 —— 你在旁邊看就給你可以操作的實況,你不在就給你一段錄影。

**這個 repo 不是遊戲,是一個產生遊戲的產生器:godogen → 遊戲 repo → 遊戲。** 你把它 publish 進一個全新的 repo,agent 就在那裡面照著一頁的引擎指南把遊戲蓋出來。

## 會累積的那一部分

遊戲 repo 是拋棄式的,這個不是,所以記憶放在這裡。

```
   godogen  ──── publish + 種子 ────►  遊戲 repo
      ▲                                    │
      │                                    │ run 中累積
      └──────── 收割(人審核可)───────────┘
```

兩個知識庫,每個 publish 出去的 repo 都會掛上:

- **`craft.db`** 住在這裡,裝「每個遊戲都該先知道」的東西 —— 引擎陷阱、工具鏈陷阱、設計原則。由 [`knowledge/`](knowledge/) 建出來,19 條可 review 的 markdown。
- **`game.db`** 住在遊戲 repo,累積那個遊戲自己的發現。

**寫回來不需要你做任何事。** `/kg-harvest` 是交付流程的一步,它挑出少數幾條跨專案成立的教訓提案給你,你決定收不收。另外有一個 commit hook 會順手撈你寫在 commit message 裡的東西。

## 在新電腦上開始

**光 clone 是不夠的。**

`craft.db` **不在版控裡** —— `knowledge/*.md` 才是真相來源,`.db` 只是它的檢索索引。所以新 clone 下來的 repo **知識庫是空的,而且沒有任何東西會告訴你**:publish 照樣成功、agent 照樣跑,只是什麼都不記得。

```bash
git clone https://github.com/ddwolfer/godogen
cd godogen
```

然後在這個目錄開 Claude Code 或 Codex,問一句 **「我要怎麼開始?」**。

`setup` skill 會**先去偵測**你機器上已經有什麼(Godot、Blender、ComfyUI、kg……),只問它查不到的事 —— 主要就一題:**素材要用哪些後端**。然後幫你寫 `.env`、建好索引、並驗證過才說完成。

要手動做的話:

```bash
# 知識引擎,每台機器一次
git clone https://github.com/ddwolfer/Multi-knowledgeGraph kg
cd kg && npm install && cd ..

# 匯入、產生向量、排注入優先權,一次做完
cp .env.example .env      # 然後編輯它
python scripts/bootstrap.py
```

`kg/` 已經在 `.gitignore` 裡,所以直接 clone 在 checkout 內就好;`../kg` 和 `~/.godogen/kg` 也會被搜尋,`GODOGEN_KG_HOME` 可以覆寫全部。

### 素材後端(三軸獨立)

寫在 `.env` 裡。三軸分開是因為它們本來就獨立 —— **用雲端出圖配本地 Blender 建模是正常組合**:

| | 選項 |
|---|---|
| `ASSET_3D` | `blender` 程式化(本地、免費)· `tripo3d`(約 30–60¢/個)· `none` |
| `ASSET_2D` | `comfyui`(本地、免費)· `gemini`(5–15¢/張,精準)· `grok`(2¢/張)· `none` |
| `ASSET_AUDIO` | `ace`([ACE Studio](https://github.com/ddwolfer/ACE_Studio),本地、免費)· `none` |

這個選擇會在 publish 時**烘進遊戲 repo 的素材 skill**,agent 不用猜這個專案該用哪條管線。

ACE Studio 是掛成 **MCP server**,所以 agent 直接拿得到它的工具,包含 `list_library`。

**它的作品庫之於音效,就是 `craft.db` 之於知識** —— 跨專案累積的store。skill 的規則是**生成前先查庫**:庫裡的每一個音都是你已經聽過、確認可用的,新生的沒有。

跟知識引擎一樣是**靠路徑找**而不是 vendored —— 它的模型和作品庫都在 git 之外,submodule 只會給你一個空殼。搜尋 `<godogen>/ACE_Studio`、`../ACE_Studio`、`~/.godogen/ACE_Studio`,或設 `ACE_STUDIO_HOME`。

`none` 是正當選項 —— 只想先做玩法、美術之後再說完全合理。

跑完最後一行會像這樣:

```
Ready. 20 entries indexed, 20 vectorized, 7 principles prioritized for post-compaction recall.
```

**如果它印的是錯誤,就相信那個錯誤。** 它包起來的兩個步驟都會「靜默地少做一點事」然後回報成功 —— 這正是它拒絕在無法驗證時宣稱成功的原因。第一次跑會下載約 560MB 的 embedding 模型。

改過 `knowledge/` 之後要重跑。

完整的前置需求(Godot、Python、ffmpeg、選用的本地素材服務)在 [setup.md](setup.md)。

## 做一個遊戲

```bash
python publish.py --engine godot   --out ~/my-game
python publish.py --engine babylon --out ~/my-game
python publish.py --engine godot --agent codex --out ~/my-game
```

`--force` 會先清空目標目錄。然後在那個目錄開你的 agent,描述你要的遊戲。

publish 出去的 repo 只帶四樣:manifest(`CLAUDE.md`,Codex 是 `AGENTS.md`)、一頁的引擎指南、三個 skill、以及兩個知識庫的接線。其他一切 —— 專案骨架、截圖錄影工具 —— agent 自己照指南蓋。

**動手之前它會先跑 `/game-design`** —— 一段訪談,產出 `DESIGN.md`:核心動詞、玩家反覆在做的那個決策、明確不做什麼以及為什麼。

理由是:「做一個塔防」那句話裡只有 3% 的資訊量,剩下的 97% 如果不問出來,就會在實作過程中被默默替你決定,然後在第一次壓縮時消失。**最貴的錯不是程式碼寫錯,是蓋錯東西。**

### Codex

Codex 是支援的目標,但**知識迴圈比較弱**。

它有 `SessionStart`、`UserPromptSubmit`、`PostToolUse`,但**沒有壓縮後觸發的事件** —— 而一次 generation run 跑幾小時、會壓縮好幾次。所以在 Codex 上,知識在開場和每則訊息時進來,但**壓縮之後不會被重新注入**。

Codex 的 hooks 目前還是 experimental 而且要手動開啟:在 `~/.codex/config.toml` 設 `[features].codex_hooks = true`,並信任專案的 `.codex/` 層。

## 原始碼配置

| 路徑 | 作用 |
|---|---|
| `prompts/runtime.md` | runtime manifest,會 render 成目標 repo 的 `CLAUDE.md` |
| `engines/godot.md`、`engines/babylon.md` | 各引擎的一頁指南 |
| `knowledge/` | 跨專案語料 |
| `asset-gen/` | 素材生成 skill |
| `skills/` | 會裝進 published repo 的其他 skill |
| `hooks/` | commit 收割器 |
| `scripts/` | `bootstrap.py`、`seed_priority.py`、publish 的內部模組 |
| `publish.py` | 把上面這些依選定的引擎 render 出去 |

## agent 會做什麼

- **Godot 4** —— 標準版 + GDScript,模擬層與呈現層分離,所以同一個種子跑得出同一場。
- **Babylon.js** —— TypeScript/Vite,產出一個可以直接打開玩的網址。**從上游繼承,未在 Windows 驗證。**
- **素材全部本地生成** —— Blender 程式化建模、ComfyUI 出圖、本地模型生音效,而且帶著讓它們真的能用的後處理。零成本、可重現。付費雲端 API 留著當 fallback。
- **證明而不是宣稱** —— 從跑起來的遊戲判斷,絕不從編譯乾淨判斷。五層驗收,按「最常抓到真問題」排序:你實際玩、agent 自己讀截圖、量測探針、自動化測試、死鎖檢查。
- **你決定要參與多少** —— 邊看邊指揮,或是丟著讓它跑完再看 15–20 秒的成果錄影。agent 從你怎麼交代任務判斷該用哪一種。

## 與上游的差異

以 Windows 為主、以 Godot 為主,而且在上游刻意不表態的地方表態。

- **跨專案的記憶。** 上游沒有知識層,一次 run 學到的東西跟著 repo 一起死。
- **用 GDScript 不用 C#。** 上游因為 GDScript 的型別推導陷阱改用 C#。但用一個 1015 條測試的 GDScript 專案實測,那些陷阱一整天大約花掉 3 分鐘、從未造成執行期 bug;而同一天真正的坑(A* 啟發式高估、測試假綠、PowerShell 截檔)沒有一個是編譯器能救的。
- **素材本地優先。** 上游全部走付費 API,而且完全沒有音訊管線。
- **有意見的 manifest。** 上游的是 11 行、對「怎麼做」隻字不提。這一版加了 sim/render 分離、驗收五層梯,以及兩條除錯守則 —— 都是**看起來像成功的失敗**。
- **多了設計階段。** 上游從一句話直接進程式碼。這一版先訪談,而且把決定寫下來 —— 包含**被排除掉的東西**。
- **引擎** —— Godot 與 Babylon.js,砍掉 Bevy。
- **`publish.py` 取代 `publish.sh`** —— 一份實作同時支援 Windows 與 POSIX,不依賴 `rsync`、`mktemp`、`xvfb`。

**中文的文件是實際驗證過的,英文的是從上游繼承、尚未驗證的。**

## 已知限制

- **`auto-recall` 對純中文無效。** 它依空白切詞,而中文沒有空格,整句會變成一個 phrase query。另外兩個注入 hook(開場、壓縮後)不受影響。**這條在 Codex 上影響最大** —— 那邊它是唯一全程可用的注入管道。
- **Codex 沒有壓縮後注入。** 見上。
- **壓縮後的注入額度是 10 條**,由 `scripts/seed_priority.py` 決定是哪 10 條(方法論優先於情境性陷阱)。
- Babylon 的指南與截圖路徑未在 Windows 驗證。
- 從來沒有用它真的做出一個完整的遊戲 —— 零件都驗過,整條路沒走過。

## 開發

```bash
python -m pytest tests/ -v
```

## 更新紀錄

見 [CHANGELOG.md](CHANGELOG.md)。
