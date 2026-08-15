---
source: pitguild-2026-08
verified: true
---
# 桌面與 web 用不同 renderer,顏色不一樣

> 「在桌面調好的美術,上 itch.io 之後整個發灰。」

Godot 桌面預設 **Forward+**,web 只能用 **Compatibility**(WebGL2)。同一個場景在兩邊的色調、tonemap、光照**明顯不同**。

## 規則

- **如果這個專案會出 web,一開始就把 `rendering_method` 設成 `gl_compatibility`,兩邊都用它。**
- 晚做的代價是所有燈光與顏色重調一次 —— 而且是在你已經覺得調好了之後。
- 不確定會不會出 web 的時候,選 `gl_compatibility` 比較安全:它在桌面上也能跑,只是少一些高階效果。反過來則不成立。

## 案例

深坑公會在桌面(Forward+)調好美術,上 itch.io 之後整個發灰,燈光與色調全部要重來。

## 相關

[[godot-web-font]] 與 [[godot-web-audio-buses]] 是同一次 web 匯出會一起撞到的另外兩個問題。決定「要不要出 web」是 day-1 的事,因為這三條的修正成本都隨時間急遽上升。
