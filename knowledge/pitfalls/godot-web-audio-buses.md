---
source: elemental-deck-2026-08
verified: true
---
# 執行期建立的音訊 bus 會讓 web 版整個靜音

> 「引擎說驅動起來了、串流正在播,然後送出一片精確的零——桌面同一份程式碼是正常的。」

用 `AudioServer.add_bus()` 在執行期建立音訊 bus(常見於「主音量 / 音效 / BGM」三軌設定頁),在桌面完全正常,**在 web 匯出會讓整個混音變成靜音**。

失敗方式是這條最惡劣的地方:**沒有任何錯誤訊息**。`AudioServer.get_driver_name()` 回 `AudioWorklet`、`bus_count` 是對的、每條 bus 的音量與 mute 狀態都正確、`AudioStreamPlayer.playing` 是 `true`、瀏覽器的 `AudioContext.state` 是 `running`、worklet 節點確實接在 destination 上 —— 而它送出的是零。

## 規則

- **要出 web 就不要在執行期 `AudioServer.add_bus()`。** 音量做在播放器的 `volume_db` 上,或用一個 `default_bus_layout.tres` 資源(隨專案打包,不是執行期建的)。
- **bus 效果(限幅器、等化器)也一起放棄**,除非你在瀏覽器裡實測過。原本靠 bus 限幅器擋住的問題,要用別的方式解 —— 例如把每個音效的基準音量調低,自己留出疊加的餘裕。
- **`AudioServer.get_bus_peak_volume_left_db()` 在 web 恆為 −200,不管有沒有聲音。** 拿它當 web 的驗證等於沒驗證。
- **web 的聲音只有一個可信的量法:在頁面裡攔 `AudioNode.prototype.connect`,把接到 `destination` 的東西也接一個 `AnalyserNode`,讀它的峰值。** 那是瀏覽器自己的圖,不經過引擎的任何 API。

## 案例

**元素牌堆,2026-08-15**

設定頁需要主音量 / 音效 / BGM 三軌,所以在 `_ready()` 裡建了兩條 bus(`SFX`、`BGM`),送到 Master,並在 SFX bus 掛了一個 `AudioEffectHardLimiter` 擋音效疊加。桌面完全正常,錄影量到 peak −18 dBFS。

上 itch.io 之後**完全沒有聲音**。逐一排除,每一輪都要重新匯出:

| 假設 | 結果 |
|---|---|
| 瀏覽器自動播放政策 | ✗ Godot 的 AudioContext 是 `running` |
| 播放時序太早(`_ready()` 就 play) | ✗ 改成第一次手勢後才播,仍然靜音 |
| 執行緒支援 | ✗ 單執行緒與多執行緒都靜音 |
| bus 限幅器 | ✗ 拿掉仍然靜音 |
| ogg 解碼 | ✗ wav 也一樣沒聲音 |
| **完全不建 bus,只用 Master** | **✓ 有聲音** |

決定性的比對來自使用者:**同一台機器、同一個 Godot、同一套匯出範本的另一個專案在 itch.io 上有聲音**,而那個專案**一條 bus 都沒建**,音量直接寫在每個 `AudioStreamPlayer.volume_db` 上。

瀏覽器端的量測:修復前 destination 的峰值是精確的 `0.0`(−200 dB),修復後 −40.3 dB。

**兩個誤導我很久的東西**:Godot 的 `get_bus_peak_volume_left_db()` 在 web 恆為 −200,所以它在「有聲音」與「沒聲音」兩種情況下給出一樣的讀數;以及我第一次的 A/B 測試只把播放器改路由到 Master,**卻沒有停掉建立 bus 的程式碼**,於是錯誤地把 bus 從嫌疑名單上劃掉了。

## 相關

[[godot-web-font]] 與 [[godot-web-renderer]] 是同一族:桌面正常、瀏覽器才爆,而且都無聲無息。三條合起來的意思是 **web 匯出是一個獨立的目標平台,不是「桌面版再按一個鈕」** —— 要出 web 就早點做一次真的匯出,在瀏覽器裡把畫面看過、把聲音量過。
