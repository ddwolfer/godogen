# GDScript 的靜默失敗

GDScript 有兩類問題,危險程度差很多。型別推導失敗**會報錯**,只是煩;lambda 漏 return **不會報錯**,而且會摧毀決定論。先處理後者。

## 規則

- **`sort_custom` 的 lambda 每條路徑都要 return。** 漏掉的分支靜默回 `null`,排序結果變隨機,決定論當場崩潰。這是執行期靜默失敗,沒有任何錯誤訊息。
- **三元運算子必須整條在同一個表達式裡。** 換行寫 `else` 會被解析器當成獨立語句,錯誤訊息指向完全無關的行。
- **untyped 來源不能用 `:=`。** Dictionary/JSON 取值、untyped 參數的成員呼叫、`load(...).new()` 的回傳值全是 Variant,一律顯式標型別。
- **用型別確定的整數版數學函式:** `mini()`/`maxi()`/`absi()`/`clampi()`,不要用多型的 `min()`/`abs()`/`clamp()`。從一開始就用,可以迴避掉整族推導問題。
- **`JSON.parse_string` 吃到 BOM 回 null。** 寫 JSON 的工具不要帶 BOM。

## 案例

**排序變隨機**

```gdscript
# 壞:少了 return,靜默回 null
cands.sort_custom(func(a, b):
    if a[0] != b[0]:
        return a[0] < b[0])
```

**型別推導的真實比例(深坑公會,1015 條測試的 GDScript 專案)**

| 檔案 | `:=` 推導 | 明寫型別 |
|---|---|---|
| `sim/sim_battle.gd`(純模擬,1000+ 行) | 64 | 84 |
| `sim/sim_map.gd` | 7 | 24 |
| `main.gd`(碰引擎 API 最多) | 116 | 82 |
| `tests/run_tests.gd` | 93 | 104 |

真正咬人的來源是 **Dictionary 取值**(`u.stats.get("charge_min_dist")`、`params.get("shove_pct", 18)`)—— 只要拿 JSON 當資料層就一定遇到,跟引擎 API 無關。第二個是測試 harness 的 `load("res://x.gd").new()`,回傳值全是 Variant。

實測影響:**不痛,煩。** 錯誤訊息明確(`Cannot infer the type of "c0" variable because the value doesn't have a set type`),30 秒修完,**從未造成執行期 bug**。一整天約 3 分鐘。

這是選擇 GDScript 而非 C# 的依據:型別推導是編輯期摩擦,不是正確性風險;而同一天真正的坑(A* 啟發式高估、測試假綠、PowerShell 截檔)沒有一個是編譯器能救的。
