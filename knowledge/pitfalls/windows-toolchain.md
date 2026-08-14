---
source: pitguild-2026-08
verified: true
---
# Windows 工具鏈陷阱

> 「在 Windows 上,agent 最常見的自傷不是寫錯程式,是寫檔案的過程本身把檔案弄壞。」

在 Windows 上,agent 最常見的自傷不是寫錯程式,是**寫檔案的過程本身把檔案弄壞**,而且沒有任何錯誤訊息。

## 規則

- **不要用 PowerShell 5.1 改檔案。** 需要跨平台的執行邏輯一律用 Python 3。
- **不要用 shell heredoc 寫含 Windows 路徑的內容。** 反斜線在 bash → python → 字面值之間會被吃掉。用檔案寫入工具直接寫。
- **所有檔案 I/O 明確指定 `encoding="utf-8"`。** Windows 上 Python 3.13 的預設編碼是 locale(cp950),中文內容會壞或直接拋例外。
- **但讀子行程的 stdout 相反:不要硬指定 `encoding="utf-8"`。** Godot 在 Windows 用系統 ANSI codepage(cp950)寫 console 輸出,即使被導向管線也一樣。用 `capture_output=True` 拿 bytes,先試 UTF-8、`UnicodeDecodeError` 再退回 cp950。
- **自己的 stdout 被導向時也要 `reconfigure(encoding="utf-8")`。** 否則印中文會 `UnicodeEncodeError`,而那通常發生在你已經跑完幾百場模擬之後。
- **寫出的檔案不帶 BOM。** 下游解析器(尤其 `JSON.parse_string`)吃到 BOM 會靜默回 null。
- 非用 PowerShell 不可時:`.ps1` 檔案必須純 ASCII;不要用 `Get-Content`/`Out-File` 往返 UTF-8 檔案;讀 UTF-8 輸出檔要 `-Encoding UTF8`。

## 案例

**heredoc 吃掉反斜線(2026-08-13,深坑公會)**

用 `python - <<'PYEOF'` 寫一個含 Blender 路徑的說明檔,字串裡的 `\b` 被當成 backspace 字元寫進檔案,`Blender\blender.exe` 變成 `Blenderlender.exe`。

**PowerShell 5.1 把檔案截成 115 bytes(同日,同一個檔)**

想用 PowerShell 修上面那個錯:

```powershell
$out.Add($l -replace 'A','B')
```

PS 5.1 的 `-replace` 在輸入是陣列時回傳陣列,`List.Add()` 沒有對應多載,整個 else 分支每行都失敗。**它不會停** —— 繼續跑完並把壞結果寫進去,檔案從數 KB 變成 115 bytes,先前兩則訊息全沒了。

教訓不是「小心一點」,是**這條 pipeline 半路失敗仍然會寫入**,所以事前檢查比事後補救重要。

**探針表整排中文變亂碼(元素牌堆,2026-08-14)**

`subprocess.run(..., text=True, encoding="utf-8", errors="replace")` —— 這正是 `engines/godot.md` 範本裡寫的那段 —— 讓探針輸出的 `步兵` 變成 `�B�L`。可以逐位元組對上:Big5 的 `步` 是 `A8 42`、`兵` 是 `A7 4C`,用 UTF-8 加 `errors="replace"` 解就是 `FFFD 'B' FFFD 'L'`。

整張「誰在漏過去」的統計表因此不可讀 —— 而那張表正是拿來做平衡決策的東西。改成拿 bytes 再 try utf-8 / except → cp950 之後正常。

注意方向:**寫檔要強制 UTF-8,讀子行程輸出不能強制 UTF-8。** 同一個 cp950,兩個相反的處置。

**cp950 吞換行(深坑公會,踩了三次)**

無 BOM UTF-8 的中文註解在 `.ps1` 裡被 cp950 誤解析,吞掉換行、把下一行併進註解 —— 變數悄悄變 null,沒有任何錯誤。

## 相關

[[godot-headless-windows]] 是 Godot 專屬的 Windows 行為。
