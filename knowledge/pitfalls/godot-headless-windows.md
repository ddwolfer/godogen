---
source: pitguild-2026-08
verified: true
---
# Godot 在 Windows 上是 GUI 型 exe

> 「Godot 的 Windows 執行檔是 GUI 型程式:不等待、吞掉 stdout、parse error 掛住不退出,而且編譯失敗還印綠燈。」

Godot 的 Windows 執行檔是 GUI 子系統程式。這代表它的行為跟你在 Linux 上的直覺**每一項都不同**,而且失敗方式全部是靜默的。

## 規則

- **直接呼叫不會等待,stdout 會被吞掉。** 從腳本啟動一律 `Start-Process -Wait -RedirectStandardOutput -RedirectStandardError`,或用 Python 的 `subprocess.run(..., capture_output=True)`。
- **腳本編譯失敗仍然退出 0,並印出假綠燈。** 測試 runner 必須掃 stderr 的 `SCRIPT ERROR` 並強制判紅,否則壞掉的程式碼會頂著綠燈過夜。
- **parse error 會掛住不退出。** 任何批次跑 Godot 的地方都要包 timeout:`WaitForExit(ms)` + `Kill()`,或 `subprocess.run(..., timeout=N)`。
- **headless 跑不出截圖。** 要看畫面就開真視窗跑 N 幀 `save_png` 後自動退出,agent 再用讀圖工具把 PNG 看回來。
- **`reload_current_scene` 吃不到腳本改動。** 改完 `.gd` 要整個遊戲重開,不能只按 R。
- **`class_name` 的全域註冊來自 import 產生的快取,不是掃原始碼。** 新專案、或新增任何一個 `class_name` 檔案之後,先跑一次 `--import`,否則 `--script` 會對每一個 `class_name` 報 `Could not find type X`;而那是 parse error,所以 exe 直接掛住,不是報錯退出。
- 資產變更後要 `godot --headless --path <proj> --import` 生 `.import`,否則 web 匯出會少檔案。

## 案例

**掛住不退出(深坑公會)**

一次截圖批次跑到一半停住不動,沒有錯誤輸出。原因是被截圖的場景有 parse error,GUI 型 exe 彈不出視窗也不退出,就那樣掛著。加上 `WaitForExit` + `Kill` 之後才變成可診斷的失敗。

**class_name 沒註冊 → parse error → 掛住(元素牌堆,2026-08-14)**

新專案第一次跑 `--script res://tests/run_tests.gd`,stderr 是四十行 `Parse Error: Could not find type "SimData" in the current scope.` —— 而 `sim/sim_data.gd` 第一行就是 `class_name SimData`。原因是專案還沒被 import 過,全域類別快取根本不存在。

同一個坑在加了 `render/theme.gd`(`class_name DeckTheme`)之後又踩一次,這次是**畫面版**:截圖腳本開了真視窗,parse error 讓 GUI exe 掛住,180 秒 timeout 才回來,而且沒有任何輸出。

**假綠燈**

`godot --headless --script tests/run_tests.gd` 在腳本編譯失敗時照樣印 `N passed` 並退出 0。這代表 CI 綠燈**不能證明測試跑過**。深坑公會的 runner 因此改成:掃 stderr,只要出現 `SCRIPT ERROR` 就覆寫成失敗。

## 相關

[[windows-toolchain]] 是通用的 Windows 檔案 I/O 陷阱。[[fake-green-tests]] 是測試本身騙人的另一類。
