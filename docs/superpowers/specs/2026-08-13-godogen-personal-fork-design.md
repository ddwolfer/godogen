# 個人版 godogen — 設計文件

日期:2026-08-13
狀態:待審

## 目標

把上游 godogen(`alex_erm`,37 個 commit,fork 在 `ddwolfer/godogen`)改造成一版反映使用者實際做法的產生器,並且讓**上一個專案的經驗能帶到下一個**。

跨專案傳承是第一需求,不是附加功能。其他改動(GDScript、本地素材管線、Windows)都是為了讓那個迴圈跑在使用者真正的工作環境裡。

## 上游現狀

godogen 不是引擎也不是框架,是一包會被 render 出去的文件。28 個檔案,產物四樣:

- `prompts/runtime.md` — 11 行的 manifest,render 成目標 repo 的 `CLAUDE.md`
- `engines/{godot,bevy,babylon}.md` — 一頁的引擎指南
- `asset-gen/` — 唯一的 skill(Gemini / Grok / Tripo3D + rembg + 切圖 + loop frame)
- `publish.sh` — token 替換後倒進新 repo

哲學:**trust the model** —— 不給 scaffold、不給 planner,只寫模型猜不到或查很慢的東西。`AGENTS.md` 明文「Don't give obvious guidance」。

## 證據來源

本設計的實證輸入來自《深坑公會》(`D:\AI\guildrun\game\`,GDScript,1015 條測試),透過檔案信箱(`D:\AI\shared-mailbox\`)向該專案的 agent 取得第一手回答,並以該 repo 的 commit message 與原始碼交叉驗證。

注意:`D:\AI\guildrun` 根目錄同時放著另一款商業遊戲《Guildrun 裂隙遠征》(Leyline)的研究工具(`tools/read_run.py`、`overlay.py`、`docs/01-08`),與本設計無關。

## 已定案的決策

| # | 決策 | 選擇 |
|---|---|---|
| 1 | 用途定位 | 自己用為主,保留未來公開的可能 |
| 2 | 執行平台 | Windows 優先,其他平台可再討論 |
| 3 | 素材管線 | 本地優先,雲端降級保留 |
| 4 | 引擎矩陣 | 留 Godot + Babylon,砍 Bevy 和 Codex |
| 5 | 經驗寫入深度 | 完整搬 kg 機制 |
| 6 | kg 安裝方式 | 共用一份放固定位置,遊戲 repo 用絕對路徑指過去 |

## 架構

### 1. 知識迴圈

遊戲 repo 是拋棄式的,godogen 不是。在遊戲 repo 裡誕生的知識必須流回 godogen 才活得下來。

```
   godogen  ──── publish + 種子 ────►  遊戲 repo
      ▲                                    │
      │                                    │ run 中自動累積
      └──────── 收割(人審過)────────────┘
```

godogen 這個 source repo **本身就是跨專案知識庫**。

### 2. 兩個知識庫

利用使用者自己加給 `Multi-knowledgeGraph` 的 `--db` 旗標做多庫隔離:

| 知識庫 | 位置 | 內容 | 寫入者 |
|---|---|---|---|
| `craft.db` | godogen repo | 跨專案:引擎陷阱、Windows 工具鏈、設計原則、方法論 | 收割時寫,人審過 |
| `<game>.db` | 遊戲 repo | 本專案:設計決策、平衡發現、pivot 紀錄 | run 中自動寫 |

`.mcp.json` 宣告兩個 server 實例(`kg-craft`、`kg-game`)。三個**注入型** hook(`session-start`、`post-compact`、`auto-recall`)各對兩個庫跑一次,輸出是純文字,兩份自然串接;`search-enforcer` 是政策閘門不是內容注入,只跑一次,避免重複攔阻。

新遊戲第一天就帶著全部 craft 知識入場,同時開始長自己的。

### 3. kg 安裝

kg 裝在機器上的固定位置(預設 `D:\AI\kg`,可由 `GODOGEN_KG_HOME` 覆寫),`craft.db` 與 godogen 的 `knowledge/` 同住。`npm install` 與 Qwen3-Embedding 模型(約 560MB)只下載一次。

publish 時把絕對路徑寫進遊戲 repo 的 `.mcp.json` 與 `.claude/settings.json`。找不到 kg 時 publish 印出警告並產出不含 kg 的 repo —— 遊戲仍然能做,只是沒有記憶。

### 4. 讀取路徑(照抄 kg 現行機制)

四個 hook,沿用 guildrun 已驗證的配置:

| Hook | 時機 | 作用 |
|---|---|---|
| `session-start.js` | SessionStart(startup) | 開場注入核心規則 |
| `post-compact.js` | SessionStart(compact) | **壓縮後重新注入** |
| `auto-recall.js` | UserPromptSubmit | 依當下訊息檢索相關知識 |
| `search-enforcer.js` | PreToolUse | 動手前強制查記憶 |

`post-compact` 是其中最關鍵的一個:一次 generation run 要跑幾小時、必定壓縮,而 engine guide 只在開頭讀一次。這是上游 docs-only 設計的真實破洞。

設計依據(guildrun 原話):**agent 不會主動查自己不知道自己需要的東西。** 自動注入的效果與「需要時去查」有本質差別。

### 5. 寫入路徑 —— 三層,摩擦遞增

原專案的寫入已死 11 天,原因是「整理知識」門檻太高。本設計**不要求任何人整理**。

**第 1 層|零摩擦,每次 commit 自動**

`PostToolUse` 攔 `git commit`,解析 commit body,把 `踩到的坑` / `Pitfall:` / `平衡回歸` 段落抽成 episode 寫進 `<game>.db`。不判斷、不篩選、不打擾。

可行性已驗證:guildrun 的 commit body 穩定含有這些段落。例如 `084f126` 的「踩到的坑」段落同時記了 A* 啟發式高估與測試假綠兩條。

**第 2 層|低摩擦,session 結束批次**

`/kg-harvest` skill 回看本 session 的 commit 與 episode,**提案** 0–3 條夠格升級成 craft 的條目並附 diff,由人核可。一個 session 一次決定,不是一條教訓一次決定。

**第 3 層|高價值,升級進 godogen**

核可的條目寫成 `.md` 進 godogen 的 `knowledge/` 並 commit。這是跨專案那一跳,可 review、可 diff、可 revert。

**為什麼這次不會死:** 第 1 層不需要任何人做任何事。就算數週不跑收割,原料一條都不丟,`/kg-harvest` 隨時可往回撈。原系統死於**沒有第 1 層** —— 原料只存在於沒人讀回去的 commit message 裡。

## 元件

### `knowledge/` — 種子語料

從 guildrun 直接搬(已是通用):

- `pitfalls/windows-godot-toolchain.md`
- `principles/mechanism-weight.md`
- `principles/difficulty-tracks-player-power.md`
- `principles/readability-is-gameplay.md`
- `principles/rules-own-their-failures.md`
- `patterns/deterministic-tick-sim.md`

本次新寫:

- `pitfalls/gdscript-silent-failures.md` — `sort_custom` lambda 漏 return 靜默回 null(排序變隨機、決定論崩潰);Dictionary/JSON 取值一律 Variant;三元運算子不可跨行;`JSON.parse_string` 吃到 BOM 回 null
- `pitfalls/godot-headless-windows.md` — Godot 是 GUI 型 exe,parse error 掛住不退出,截圖批次必須 `WaitForExit(ms)` + `Kill()`;腳本編譯失敗仍 exit 0 印假綠燈,runner 必須掃 stderr 的 `SCRIPT ERROR` 強制判紅;`reload_current_scene` 吃不到腳本改動
- `pitfalls/silent-lookup-apis.md` — `play_sound()` 這類「查無此名靜默 return」的 API 是假機制溫床,任何「名字→資源」查找都要一條掃表存在性測試
- `pitfalls/blender-gltf-orientation.md` — Blender Z-up、腳底 z=0、正面 -Y,轉 glTF 後正面變 +Z;固定俯角下旗面與弓身正側面幾乎隱形,要斜向鏡頭擺
- `pitfalls/fake-green-tests.md` — 對照組比絕對值可靠;實例:地形蓋在 `add_squad` 錨點上而編隊會位移,六條測試全假綠
- `principles/presentation-before-numbers.md` — 「使用者說 X 不好玩」時先查呈現層再查數值,約三分之二根因在呈現層;對 agent 特別重要,因為 agent 的直覺永遠是調數字
- `principles/one-knob-at-a-time.md` — 五個削弱一起上導致 6/6 → 0/6 且無法歸因;改動之間會互相放大(「箭會落空」×「行進間不能射」= 推進途中零輸出)
- `principles/disaggregate-your-stats.md` — 「落水 18.4」實為敵 12.1 + 我方 4.8;任何聚合統計先問「有沒有混進不該算的東西」
- `patterns/five-layer-verification.md` — 驗收五層梯與各自抓到的問題類型
- `patterns/local-asset-pipeline.md` — Blender 程式化 / ComfyUI / ACE 三條線與後處理紀律

### `prompts/runtime.md` — manifest

從 11 行擴為約 50 行。新增內容必須對 Godot 與 Babylon 同時成立:

- **sim / render 分離與決定論** —— 模擬層不碰引擎、不碰 delta time、不碰物理。第一價值是決定論可重播(同種子=同一場),測試是第二,呈現層可自由撒謊是第三。附逃生門:不是模擬型遊戲時可不採用。
- **驗收五層梯** —— 使用者實玩+run 紀錄 > agent 自己讀截圖 > 平衡探針 > headless 測試 > autotest 抓死鎖。前兩名是「用玩家的眼睛看」,後三名是「用系統的眼睛看」,而系統的眼睛只能證明系統做到了它被告知的事。
- **先查呈現層再查數值**
- **一次只轉一個旋鈕**

保留上游的 delivery 段落(依任務框架決定要不要即時互動、結尾錄 15–20 秒影片並看過)。

### `engines/godot.md` — 整份重寫

- 語言改 **GDScript**(依據見下方「GDScript 決策」)
- 手工 `.tscn` 可接受,不強制 build-time 生成
- sim / render 目錄配置
- Windows 工具鏈:PowerShell 5.1 的 `.ps1` 純 ASCII 要求、不可用 `Get-Content`/`Out-File` 往返 UTF-8、`Start-Process -Wait -RedirectStandardOutput/Error`
- 截圖:開真視窗跑 N 幀 `save_png` 自動退出,包 `WaitForExit` + `Kill`
- 測試 runner 掃 `SCRIPT ERROR` 判紅
- 平衡探針樣式、autotest 死鎖守衛(超過 N tick 印現場並 `quit(2)`)
- **錄影 recipe 保留**(去掉 xvfb)。guildrun 明確表示錄影優於其截圖:近戰單位原地抖動的問題截圖看不出來,錄影一眼可見。

從上游保留:GLB 用 AABB 推原始碰撞形狀(不可用 trimesh/convex)、`ArrayMesh.GenerateNormals()` 才收得到陰影、`MultiMeshInstance3D` + GLB 打包會掉 mesh、raycast 打不到 `ConcavePolygonShape3D`、`.gdignore` 靜默跳過、指數衰減。

移除:C# 專屬內容(`partial`、`.csproj`、`SetScript()` 釋放、C# enum 名稱不可靠)。

### `engines/babylon.md` — 輕度調整

保留上游內容。移除 Codex 相關 token,確認 manifest 新增段落對它成立。不做 Windows 驗證,標明「未在 Windows 驗證」。

### `asset-gen/` — 本地優先

| 工具 | 狀態 | 內容 |
|---|---|---|
| `blender_gen.py` | 新增 | 驅動 `bpy` 程式化建模腳本;約定:輪廓優先、3–8 個幾何體、色塊無貼圖、顏色表與渲染層常數同步 |
| `comfy_gen.py` | 新增 | 讀 workflow API json 當模板改欄位 POST;鎖一條風格字串、只換主體描述那段;範圍紀律:只生圖示與主視覺,不生角色圖 |
| `sfx_gen.py` | 新增 | ACE Studio 端點(SFX `:8002` / BGM `:8001`);後處理四步:切起音點(峰值 2%,前留 3ms)、裁長(短音 0.28–0.35s)、尾巴淡出 50ms、RMS 對齊既有音效庫;過輕的音用 `tanh` 軟壓縮。純 `wave` + `struct`,零依賴 |
| `asset_gen.py` | 保留降級 | Tripo3D / Gemini / Grok,原封不動,文件位置降為「沒有本地 GPU 時走這條」 |
| `rembg_matting.py` `grid_slice.py` `find_loop_frame.py` | 保留 | 對本地生成同樣適用 |

`SKILL.md` 重寫,主體是三條本地線。核心原則寫在最前面:**生成只是第一步,後處理才是能不能用的關鍵 —— 生成器吐出來的東西一律不直接進專案。**

保留上游的資產清單規範(README.md 的表格必須有「in-game Size」欄)。

### `publish.py` — 取代 `publish.sh`

改用 Python 3 單一實作。Python 本來就是必要條件(`render_dir.py` 與所有素材工具),改寫後:

- 兩個平台一份實作
- 閃掉整族 PowerShell 5.1 陷阱(`-replace` 回傳陣列導致 pipeline 半路失敗仍寫入、`.ps1` 純 ASCII 限制)
- 不再依賴 `rsync` / `mktemp` / `trap`

新增職責:寫出 `.mcp.json` 與 kg hook 的 `.claude/settings.json`(絕對路徑)、複製 `knowledge/` 種子、初始化空的 `<game>.db`。

`--engine {godot,babylon}`,移除 `--agent`(固定 claude)。

## 移除項目

- `engines/bevy.md` 與所有 Bevy 引用
- Codex 目標:`scripts/generate_codex_metadata.py`、`--agent` 旗標、`.agents/skills/`、`openai.yaml`
- `docs/gdscript-vs-csharp.md` — 換成一段簡短說明,附使用者的實測數據
- `publish.sh`

## GDScript 決策

上游選 C# 的理由是 `:=` 型別推導對 LLM 不友善:`load()` 回 Resource、`instantiate()` 回 Variant、`abs()`/`clamp()`/`min()` 回 Variant。

實測反駁(《深坑公會》1015 條測試,GDScript):

- 上游點名的來源**幾乎沒咬到** —— Godot 4 的 `mini()`/`maxi()`/`absi()`/`clampi()` 型別確定,從一開始就用這些即可迴避
- 真正咬人的是兩個上游沒提的來源:**Dictionary 取值一律 Variant**(拿 JSON 當資料層必中,換 C# 也要 cast,只是編譯期喊)、測試 harness 的 `load(...).new()` 回傳全是 Variant
- 各層 `:=` 對明寫型別比例:`sim_battle.gd` 64:84、`sim_map.gd` 7:24、`main.gd` 116:82、`run_tests.gd` 93:104 —— 模擬層明寫比推導多
- 影響評估:**不痛,煩。** 錯誤訊息明確、30 秒修完,**從未造成執行期 bug**。一整天約 3 分鐘
- 同日真正的坑(A* 啟發式高估、測試假綠、PowerShell 截檔)沒有一個是 C# 能救的

真正該進 engine guide 的 GDScript 坑是另一個:**`sort_custom` 的 lambda 漏掉 return 分支會靜默回 null,排序結果變隨機,決定論直接崩** —— 這是執行期靜默失敗,比型別推導危險得多。

## 假設

**文件語言。** `knowledge/`、`engines/*.md`、`prompts/runtime.md` 用中文撰寫 —— 原始語料本來就是中文,而目標讀者是使用者與其 agent,LLM 不因語言損失理解。`README.md`、`publish.py` 的 CLI 介面與錯誤訊息維持英文,保留公開的門面。若日後決定公開,再處理翻譯。

此為假設而非已定案決策,使用者可推翻。

## 建置順序

元件之間有依賴,順序如下。每一階段結束時 repo 都處於可用狀態。

**階段 1 — 骨架與砍除**
`publish.py` 取代 `publish.sh`;砍掉 Bevy、Codex、`generate_codex_metadata.py`、`gdscript-vs-csharp.md`。此時產出的 repo 與現在等價,只是換了實作、少了兩個目標。可獨立驗證(產出的 repo 與 `publish.sh` 的輸出比對)。

**階段 2 — 知識層**
建 `knowledge/` 種子語料;kg 安裝約定與 `craft.db` 初始化;`publish.py` 加上寫 `.mcp.json` 與 `.claude/settings.json` 的職責。驗收項目 1 與 2 在此可跑。

**階段 3 — 寫入路徑**
第 1 層 commit 解析 hook;`/kg-harvest` skill。驗收項目 3 與 4 在此可跑。

**階段 4 — 文件層**
`prompts/runtime.md` 擴寫;`engines/godot.md` 重寫;`engines/babylon.md` 調整。

**階段 5 — 素材管線**
`blender_gen.py`、`comfy_gen.py`、`sfx_gen.py`;`SKILL.md` 重寫。三個工具彼此獨立,可平行。

**階段 6 — 端對端**
驗收項目 5:用一份簡短 brief 跑一次小型 generation run。

## 驗收方式

設計是否成立,以實跑證明,不以檔案齊全證明:

1. `publish.py --engine godot --out <tmp>` 產出的 repo 能開起 Claude Code,且 kg 四個 hook 都有作用(session-start 有注入、手動觸發 compact 後仍有注入)
2. 種子語料能被 `auto-recall` 檢索到 —— 送出一則提到「音效」的訊息,應召回 `silent-lookup-apis`
3. 在該 repo 做一次含 `踩到的坑` 段落的 commit,episode 確實寫進 `<game>.db`
4. `/kg-harvest` 能從該 episode 提出升級提案
5. 用一份簡短 brief 跑一次小型 generation run,結尾產出可播放的錄影

## 非目標

- 不做音訊「引擎內」管線(BGM 動態混音、音軌狀態機),只做素材生成與後處理
- 不做行動平台或原生打包
- 不驗證 Babylon 在 Windows 上的 capture 路徑
- 不自動化第 3 層寫入(升級進 godogen 維持人工核可)
- 不處理多人同時寫同一個 `craft.db` 的併發

## 已知限制

- kg 共用一份代表遊戲 repo 不自包含,換機器要重裝;公開時他人需自行先裝 kg
- 種子語料以 Godot / 戰術模擬類為主,對其他類型遊戲的覆蓋率未知
- 第 1 層寫入依賴 commit message 含既定段落標題;不寫這些段落的 commit 不會產生 episode
