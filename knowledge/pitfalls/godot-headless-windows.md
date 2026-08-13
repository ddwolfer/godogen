# Godot 在 Windows 上是 GUI 型 exe

Godot 的 Windows 執行檔是 GUI 子系統程式。這代表它的行為跟你在 Linux 上的直覺**每一項都不同**,而且失敗方式全部是靜默的。

## 規則

- **直接呼叫不會等待,stdout 會被吞掉。** 從腳本啟動一律 `Start-Process -Wait -RedirectStandardOutput -RedirectStandardError`,或用 Python 的 `subprocess.run(..., capture_output=True)`。
- **腳本編譯失敗仍然退出 0,並印出假綠燈。** 測試 runner 必須掃 stderr 的 `SCRIPT ERROR` 並強制判紅,否則壞掉的程式碼會頂著綠燈過夜。
- **parse error 會掛住不退出。** 任何批次跑 Godot 的地方都要包 timeout:`WaitForExit(ms)` + `Kill()`,或 `subprocess.run(..., timeout=N)`。
- **headless 跑不出截圖。** 要看畫面就開真視窗跑 N 幀 `save_png` 後自動退出,agent 再用讀圖工具把 PNG 看回來。
- **`reload_current_scene` 吃不到腳本改動。** 改完 `.gd` 要整個遊戲重開,不能只按 R。
- 資產變更後要 `godot --headless --path <proj> --import` 生 `.import`,否則 web 匯出會少檔案。

## 案例

**掛住不退出(深坑公會)**

一次截圖批次跑到一半停住不動,沒有錯誤輸出。原因是被截圖的場景有 parse error,GUI 型 exe 彈不出視窗也不退出,就那樣掛著。加上 `WaitForExit` + `Kill` 之後才變成可診斷的失敗。

**假綠燈**

`godot --headless --script tests/run_tests.gd` 在腳本編譯失敗時照樣印 `N passed` 並退出 0。這代表 CI 綠燈**不能證明測試跑過**。深坑公會的 runner 因此改成:掃 stderr,只要出現 `SCRIPT ERROR` 就覆寫成失敗。

## 相關

[[windows-toolchain]] 是通用的 Windows 檔案 I/O 陷阱。[[fake-green-tests]] 是測試本身騙人的另一類。
