---
name: kg-harvest
display_name: Knowledge Harvest
short_description: 把這個 session 學到的、跨專案成立的教訓,提案升級進 godogen
default_prompt: "用 ${KG_HARVEST_COMMAND} 檢查這個 session 有沒有值得帶到下一個專案的教訓。"
allow_implicit_invocation: false
description: |
  回看本 session 的 commit 與知識庫 episode,挑出跨專案成立的教訓,提案寫進 godogen 的 knowledge/。
  在一段工作告一段落、或使用者說「收工」「整理一下」時使用。
---

# 知識收割

這個遊戲 repo 是拋棄式的。在這裡學到的東西,**寫回 godogen 才活得下來** —— 下一個專案第一天就會帶著它入場。

你的工作是提案,不是決定。**寫入 godogen 前一定要拿到使用者核可。**

## 資料在哪

- **本 session 的 commit** —— `git log --format='%h%n%s%n%b' <session 開始以來的範圍>`
- **已收割的 episode** —— `.kg/game.db` 的 `episodes` 表,`context` 欄是段落名(`踩到的坑`、`平衡回歸`…)。這些是 commit hook 自動抓的原料。
- **godogen 現有語料** —— `${GODOGEN_ROOT}/knowledge/`,先讀過再提案,避免重複。

## 升級門檻

一條教訓要能進 `knowledge/`,**三個條件同時成立**:

1. **模型推不出來。** 從程式碼、文件或第一原理讀不出這件事。
   - ❌「要寫測試」—— 模型本來就知道
   - ✅「`play_sound()` 查無此名是靜默 return,所以要為它寫存在性測試」
2. **跨專案成立。** 換一個遊戲、換一個題材仍然為真。
   - ❌「弓手費用應該是 10」
   - ✅「動玩家資源曲線必須附難度回歸量測」
3. **踩過。** 有具體案例:數字、檔名、commit hash、seed、實際錯誤訊息。

## 最重要的一條

**寧可提 0 條,也不要湊數。**

大部分 session 不會產生跨專案知識,這是正常的。語料的價值來自密度 —— 摻進通則和廢話之後,auto-recall 每次注入的東西就變成雜訊,整套機制的效果會下降。**沒有就說沒有。**

如果這個 session 只是把既有機制做完、沒踩到新的坑,正確的輸出是:

> 這個 session 沒有跨專案教訓。踩到的兩個坑都是本專案的數值問題。

## 提案格式

每條提案給:

**檔名與分類** —— `pitfalls/` 會靜默失敗的技術陷阱、`principles/` 設計與決策通則、`patterns/` 可重用的架構或流程。slug 用 kebab-case。

**完整的 `.md` 內容** —— 照 `${GODOGEN_ROOT}/knowledge/README.md` 的規範:第一行 `# 標題`,必須有「規則」與「案例」兩段,案例要具體。相關條目用 `[[slug]]` 連結。

**來源** —— 哪個 commit、哪條 episode。

如果是**修改**既有條目而不是新增(常見:同一條原則多一個案例),直接給 diff,不要另開新檔。

## 核可之後

1. 寫進 `${GODOGEN_ROOT}/knowledge/<分類>/<slug>.md`
2. 在 godogen 那邊 commit,message 說明這條來自哪個專案的哪個 commit
3. 重新匯入 `craft.db`,否則新條目不會被檢索到:
   ```
   node "<kg>/scripts/import-skills.js" --db "${GODOGEN_ROOT}/craft.db" "${GODOGEN_ROOT}/knowledge"
   ```
4. 匯入後確認 `trust` 是 `principle` —— `post-compact` hook 只注入 `trust = 'principle'` 的節點,設錯的話壓縮後注入會是空的

## 不要做的事

- 不要在沒有核可的情況下寫進 godogen
- 不要把本專案的數值、平衡、劇情設定寫進去 —— 那些屬於 `game.db`
- 不要為了讓語料看起來豐富而降低門檻
