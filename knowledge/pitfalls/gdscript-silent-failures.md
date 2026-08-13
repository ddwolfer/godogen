---
source: pitguild-2026-08
verified: partial
---
# GDScript 的型別推導與靜默失敗

> 「型別推導是編輯期摩擦,不是正確性風險——一整天約 3 分鐘,從未造成執行期 bug。」

GDScript 有兩類問題。型別推導**會報錯**,煩但無害;另一類不報錯,危險程度要個別看。這條原本把後者整族講得太重,已依實測修正。

## 型別推導(實測,不痛只是煩)

- **untyped 來源不能用 `:=`。** Dictionary/JSON 取值、`load(...).new()` 的回傳、untyped 參數的成員呼叫全是 Variant。拿 JSON 當資料層就一定會遇到,一律顯式標型別。
- **用型別確定的整數版數學函式** `mini()`/`maxi()`/`absi()`/`clampi()`,不要用多型的 `min()`/`abs()`/`clamp()`。從一開始就用可以迴避整族問題。

## 不報錯的那些

- **`sort_custom` 的 lambda 每條路徑都要 return。** 漏掉的分支回 `null`(falsy),比較器變成「a 不排在 b 前面」,**排序結果會是非預期的順序**。⚠️ **未實測** —— 這是推論出的危險,不是事故報告,危險程度未經證實。
- **三元運算子必須整條在同一個表達式裡。** 換行寫 `else` 會被當成獨立語句,錯誤訊息指向完全無關的行。
- **`JSON.parse_string` 吃到 BOM 回 `null`。** 寫 JSON 的工具不要帶 BOM。(來源:深坑公會的既有語料,未附事故紀錄。)

**注意 `sort_custom` 這條不會破壞決定論。** 比較器就算邏輯錯了,輸出仍然是輸入的純函數 —— 同一個種子還是得到同一場戰鬥,只是那場戰鬥的排序不是你設計的那個。壞的是正確性,不是可重播性。這個區別重要,因為它決定你該去哪裡找 bug。

## 案例

**型別推導的真實比例**(深坑公會,1015 條測試的 GDScript 專案)

| 檔案 | `:=` 推導 | 明寫型別 |
|---|---|---|
| `sim/sim_battle.gd`(純模擬,1000+ 行) | 64 | 84 |
| `sim/sim_map.gd` | 7 | 24 |
| `main.gd`(碰引擎 API 最多) | 116 | 82 |
| `tests/run_tests.gd` | 93 | 104 |

真正咬人的來源是 **Dictionary 取值**(`u.stats.get("charge_min_dist")`、`params.get("shove_pct", 18)`)—— 只要拿 JSON 當資料層就一定遇到,跟引擎 API 無關。第二個是測試 harness 的 `load("res://x.gd").new()`,回傳值全是 Variant。

錯誤訊息明確(`Cannot infer the type of "c0" variable because the value doesn't have a set type`),30 秒修完,一整天約 3 分鐘,**從未造成執行期 bug**。

這是選擇 GDScript 而非 C# 的依據:同一天真正的坑(A* 啟發式高估、測試假綠、PowerShell 截檔)沒有一個是編譯器能救的。

**這條的修訂紀錄**

初版把 `sort_custom` 漏 return 寫成「排序變隨機、決定論當場崩潰」並排在第一位。原始提供者事後自行更正:它不會變隨機(null 是 falsy,比較器仍是純函數),而且**他從未真的踩過** —— 翻自己的 `_try_ranged`,那個 tie-break 是完整的。

留這段是因為教訓本身有價值:**這份語料裡每一條都有事故編號,只有那條沒有,而它被排到了第一位。** 沒有案例的規則會被自己的措辭放大。見 [[fake-green-tests]] 的同族問題。
