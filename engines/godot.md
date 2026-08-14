# Godot 引擎指南

技術棧:**Godot 4 標準版**(不是 .NET/Mono 版)、**GDScript**。3D 用 Jolt Physics 並固定 `physics_ticks_per_second`。

`project.godot` 的版本敏感欄位(`config_version` 等)跟安裝的工具鏈對齊 —— 跑 `godot --version` 確認,不要憑記憶寫死;既有專案則保留原值。

## 專案形狀

```
sim/          純邏輯。不 import 引擎節點、不碰 delta time、不碰引擎物理
render/       呈現層。讀 sim 的狀態畫出來,不做任何判定
data/*.json   單位、地圖、參數。改數值不用改程式
tests/        headless 測試
tools/        驗收工具:量測探針、截圖、autotest
assets/       只放跑起來會載入的檔案(生成的中間產物放別處)
runlogs/      每趟自動寫的純文字紀錄
```

`sim/` 與 `render/` 的界線是這個專案最重要的一條線,理由見 `CLAUDE.md`。判斷方式很簡單:**`sim/` 底下的檔案不應該出現 `Node`、`_process`、`delta`、`get_node`。**

`.tscn` 手工寫或用編輯器拉都可以,不需要在 build 時生成。

## GDScript 的靜默失敗

**最危險的一個:`sort_custom` 的 lambda 每條路徑都要 return。** 漏掉的分支靜默回 `null`,排序變隨機,決定論當場崩潰,而且沒有任何錯誤訊息。

```gdscript
# 壞:少了 return
cands.sort_custom(func(a, b):
    if a[0] != b[0]:
        return a[0] < b[0])
```

其餘會咬人但**會報錯**的:

- **untyped 來源不能用 `:=`。** Dictionary/JSON 取值、`load(...).new()` 的回傳、untyped 參數的成員呼叫全是 Variant。拿 JSON 當資料層就一定會遇到,一律顯式標型別。
- **用型別確定的整數版數學函式** `mini()`/`maxi()`/`absi()`/`clampi()`,不要用多型的 `min()`/`abs()`/`clamp()`。從一開始就用可以迴避整族問題。
- **三元運算子必須整條在同一個表達式裡。** 換行寫 `else` 會被當成獨立語句,錯誤訊息指向無關的行。
- **`JSON.parse_string` 吃到 BOM 回 `null`。** 寫 JSON 的工具不要帶 BOM。

## Windows 工具鏈

Godot 的 Windows 執行檔是 **GUI 子系統程式**,所以:直接呼叫不會等待、stdout 被吞掉,而且 **parse error 會掛住不退出**。

所有驅動 Godot 的腳本用 Python,並且**一定要有 timeout**:

```python
import subprocess, sys
from pathlib import Path

def _decode(raw: bytes) -> str:
    """Godot writes console output in the system ANSI codepage on Windows
    (cp950 here), even through a pipe. Decoding it as UTF-8 turns every
    non-ASCII name into mojibake, so try UTF-8 first and fall back."""
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    for enc in ("cp950", "mbcs"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")

def run_godot(args, timeout=120):
    """GUI-subsystem exe: capture both streams, and never wait forever."""
    try:
        p = subprocess.run([GODOT, *args], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 1, "", f"timed out after {timeout}s (parse error hangs the exe)"
    return p.returncode, _decode(p.stdout), _decode(p.stderr)

# Your own stdout defaults to the local codepage when redirected.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
```

**不要在 `subprocess.run` 上加 `text=True, encoding="utf-8"`** —— 那會把 Godot 印出來的中文全部變成亂碼。方向剛好相反:**寫檔一律強制 `encoding="utf-8"`、不帶 BOM;讀子行程輸出不能強制 UTF-8。** Windows 的預設 locale 是 cp950。

**新增任何 `class_name` 檔案之後要先跑一次 `--import`。** 全域類別註冊來自 import 產生的快取,不是掃原始碼 —— 少了這一步,`--script` 會對每個 `class_name` 報 `Could not find type X`,而那是 parse error,exe 會直接掛住。

## 驗收四件工具

**測試 runner** —— `godot --headless --path . --script res://tests/run_tests.gd`。

**腳本編譯失敗時 Godot 照樣印 `N passed` 並退出 0。** runner 必須自己判紅:

```python
code, out, err = run_godot(["--headless", "--path", ".", "--script", "res://tests/run_tests.gd"])
print(out)
if any(("SCRIPT ERROR" in l or l.startswith("ERROR")) for l in err.splitlines()):
    print("RUNNER: script errors in stderr -> forcing failure")
    code = 1
sys.exit(code)
```

**截圖** —— headless 跑不出畫面。開真視窗、跑 N 幀 `save_png`、自動退出,由環境變數決定輸出路徑;然後**你自己把 PNG 讀回來看**。這一層專抓「做了但看不見」,而且能在 commit 前抓到。

**量測探針** —— 直接驅動 `sim/`,零指令跑幾百場出勝率表。它抓的是測試抓不到的一整類問題:機制正確運作,但在玩家決策裡沒有份量。

**autotest** —— 全速跑完一整場,專抓永不結束。把「超過 N tick 就印出現場狀態並 `quit(2)`」做成常駐診斷。

測試設計上注意:**用對照組不要用絕對值**(「A 應該比 B 小」而不是「傷害 ≤ 某值」),並在斷言前先確認受測情境真的成立 —— 否則會出現「什麼都沒發生所以測試通過」的假綠。

## 錄影

收尾的 15–20 秒實況錄影用 Godot 的 movie writer:

```bash
godot --path . --write-movie screenshots/result/frame.png --fixed-fps 30 --quit-after 450
ffmpeg -y -framerate 30 -pattern_type glob -i "screenshots/result/frame*.png" \
  -c:v libx264 -pix_fmt yuv420p -movflags +faststart screenshots/result/video.mp4
```

`--fixed-fps` 讓動態確定化(450 幀 @30fps = 15 秒)。**鏡頭要在第一幀之前就定位好** —— 第一張 movie frame 在 `_process` 之前就渲染了。錄製期間的輸入由腳本驅動,不要靠實際按鍵。

影片必須整段都有東西在推進,不能有死時間或單格循環。錄影抓得到截圖抓不到的時序問題:原地抖動、節奏、特效時機。

## 3D 陷阱

- **GLB 模型的碰撞形狀要用 AABB 推出的原始形狀**(Box/Sphere/Capsule),絕不要對匯入的 mesh 用 trimesh 或 convex —— 會掉到 1 FPS 以下。
- **`ArrayMesh.GenerateNormals()`** 是程序化 mesh 能**接收**陰影的必要條件。少了它(或用 `CullMode.Disabled` 當「保險」)陰影會靜默消失 —— 該修的是頂點環繞順序。
- **raycast 打不到 `ConcavePolygonShape3D`**(trimesh)。改用 shape query,或用解析式取地形高度。
- **`.gdignore`** 會讓匯入器靜默跳過整個目錄。只有 `screenshots/` 該有,`assets/` 絕對不能有。
- 幀率無關的衰減用 `speed *= exp(-rate * delta)`,不是每 tick 乘 `(1 - drag)`。
- 資產變更後跑 `godot --headless --path . --import` 生 `.import`,否則匯出會少檔案。
- 改完 `.gd` 之後 `reload_current_scene` 吃不到改動,要整個遊戲重開。
