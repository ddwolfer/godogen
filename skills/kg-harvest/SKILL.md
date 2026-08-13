---
name: kg-harvest
display_name: Knowledge Harvest
short_description: 把這個 session 學到的、跨專案成立的教訓,提案升級進 godogen
default_prompt: "用 ${KG_HARVEST_COMMAND} 檢查這個 session 有沒有值得帶到下一個專案的教訓。"
allow_implicit_invocation: false
description: |
  在向使用者交付一段工作時執行:回顧這次做了什麼、差點搞砸什麼,挑出跨專案成立的教訓,提案寫進 godogen 的 knowledge/。
  交付流程的一步,不是有空才做的整理。
---

# 知識收割

這個遊戲 repo 是拋棄式的。在這裡學到的東西,**寫回 godogen 才活得下來** —— 下一個專案第一天就會帶著它入場。

你的工作是提案,不是決定。**寫入 godogen 前一定要拿到使用者核可。**

## 什麼時候跑

**在你要向使用者報告一段工作完成的時候,報告的同時跑這個。**

時機是刻意選的。這份語料裡最有價值的幾條 —— 假綠測試、靜默 API、統計要拆開 —— **沒有一條是在 commit 的時候寫下的**。它們全部產生在「向人解釋完成度」的那一刻,因為只有那一刻會逼你回答**「所以下次呢?」**。

commit message 是寫給 diff 的:它記錄你改了什麼。交付報告是寫給人的:它逼你講出你**差點**搞砸什麼。後者才是教訓的產地。

## 資料在哪

**主要來源是你自己這次的工作記憶** —— 特別是這幾個問題:

- 這次有沒有什麼東西**看起來對但其實錯了**,而你是靠某個特定手法才發現的?
- 有沒有哪個 bug 讓你**先找錯了地方**?錯在哪個假設上?
- 有沒有什麼是**做完之後才發現早該先決定**的?
- 使用者的哪一句回饋,推翻了你原本認為沒問題的東西?

輔助來源:

- **`.kg/game.db` 的 `episodes` 表** —— commit hook 自動抓的原料。`context` 欄是段落名。**這是網不是主要入口** —— 實測命中率約 7%,而且它抓到的是「你寫下來的」,不是「你學到的」。當提示用,不要當清單用。
- **本 session 的 commit** —— `git log --format='%h%n%s%n%b' <範圍>`
- **godogen 現有語料** —— `${GODOGEN_ROOT}/knowledge/`,先讀過再提案,避免重複或矛盾。

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
