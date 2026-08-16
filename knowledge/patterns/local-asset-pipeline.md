---
source: pitguild-2026-08
verified: true
---
# 本地素材管線 —— 三條線

> 「生成只是第一步,後處理才是能不能用的關鍵。」

3D 模型、2D 圖、音效各一條線,全部本地、全部可重複、全部無人值守。一晚可以從零長出含美術音效的可玩版本,零 API 成本。

**共同原則:生成只是第一步,後處理才是能不能用的關鍵。生成器吐出來的東西一律不直接進專案。**

## 規則

- **3D 用程式化建模,不用生成式。** 同一個腳本跑一百次長得一模一樣,改一個參數就改造型。生成式 3D 的風格漂移會讓同一場戰鬥裡的兵種看起來像不同遊戲。
- **2D 鎖一條風格字串,所有圖共用**,每張只換「主體描述」那一段。
- **範圍紀律:只生圖示與主視覺,不生角色圖。** 角色美術跨批次會漂移、在棋盤尺寸下讀不出來,而且早早押上去會讓設計改動變貴。圖示小、可替換,而且扛下大部分「這是個完成品」的感覺。
- **音效一定要後處理。** 生成出來的音檔直接用會有延遲感、斷點、音量不一致。
- **後處理步驟帶著沒寫下來的資產類別假設。** 音效用的後處理會「裁長度」,把它套在音樂上就是把 60 秒的曲子裁成 0.3 秒,而且照樣回報成功。每一條線要有自己的後處理路徑,不要共用一個 `post`。
- **驗證工具要雙邊檢查。** 太小聲跟太大聲一樣算失敗,太短跟太長一樣算失敗。只檢查上限的工具對「小到不存在」完全沒有意見,而那正是有方向的規則會產生的失敗 —— 見 [[conservative-needs-a-floor]]。
- **離線渲染的 sprite 要驗證沒有被畫框裁掉。** 被裁掉的高單位跟「這一階沒有變大」在畫面上是同一件事,而且看起來就是後者 —— 你會去改幾何,發現改了沒變化,然後改更多幾何。
- **現成素材包用它的「內容物」,不用它的地磚。** 地皮幾何跟不上模擬邏輯就別硬套。樹林等擺飾可以身兼地形障礙,視覺與戰術複雜度一次解。授權檔跟素材一起進版控。

## 三條線

**3D — Blender `bpy` 程式化**

`blender --background --python make_units.py` 純程式堆幾何體輸出 glTF。每個單位 3–8 個幾何體,輪廓優先(瞇眼看要能分出種類),色塊無貼圖。顏色表與渲染層常數同步。座標與鏡頭陷阱見 [[blender-gltf-orientation]]。

**2D — ComfyUI + Flux**

拿 workflow 的 API json 當模板,程式改欄位再 POST,輪詢 `/history/<id>` 抓圖。8GB VRAM 用 Flux 12 步就夠。

**音效 — 本地 Stable Audio Open**

prompt 寫「聲音事件 + 材質 + 衰減 + 錄音特徵」,英文,**不要寫音樂風格**:

```
single armored boot plants on packed dirt, soft dull thud with faint
chainmail jingle, dry close mic, very fast decay, no reverb
```

後處理四步(純 `wave` + `struct`,零依賴):

1. **切起音點** —— 掃到第一個超過峰值 2% 的取樣,往前留 3ms。生成的音檔前面常有 0.1 秒靜音,直接用會有延遲感。
2. **裁長度** —— 短音效裁到 0.28–0.35 秒。
3. **尾巴淡出 50ms** —— 不然結尾有可聽見的斷點。
4. **對齊音量** —— 量既有音效庫的 RMS,讓新音效落在同一帶。

## 案例

**風格字串鎖定(29 張圖看起來像同一個美術做的)**

```
game UI icon, single centred object, hand painted, matte finish,
muted desaturated palette of teal-grey rust and bone, one soft magenta
rim light from the upper left, flat dark charcoal background,
no text, no letters, no border, no frame, clean silhouette,
readable at small size
```

每張只換主體:`a crude short sword forged from scrap iron, pitted blade, cloth-wrapped grip`。

**過輕的音要軟壓縮,不能直接放大**

「拿起」那個音生出來只有 **-28 dBFS** —— 它是很輕的摩擦聲,峰值高但主體很小,直接放大會爆。用 `tanh` 軟壓縮(`y = tanh(x*3.2)/tanh(3.2)`)把細碎的部分提起來,尖峰自然被收住,拉到 -17.8 dBFS 才聽得見。

參考基準:`sword_clash` -11 dBFS、`arrow_shot` -17 dBFS。

**18 個檔案全部回報 ok,而配樂不存在(血脈防線,2026-08-16)**

音訊管線建好之後,15 個音效 + 3 首 BGM 全部回報 `ok`。量測工具上線第一次跑就報出:

```
== assets/bgm   target RMS -36..-24 dBFS, 8.0..300.0s
!! battle    0.30s  rms -30.0  TOO SHORT (0.30s)
!! boss      0.30s  rms -30.0  TOO SHORT (0.30s)
!! menu      0.30s  rms -30.0  TOO SHORT (0.30s)
```

三首 51–90 秒的曲子被音效用的後處理(裁到 0.28–0.35 秒)整個裁掉。**整個配樂實際上不存在,而每一個檔案都回報成功。**

同一次還抓到四個音效削波到 0.0 dBFS —— RMS 對齊把打擊類音效的峰值推到滿刻度。數位削波聽起來不是「大聲」,是「這個遊戲壞了」。

**畫框裁掉高塔(同專案,commit `d43d548`)**

塔有四個階級。一個沒有前後文的美術評審量到「第 3 階與第 4 階的 bounding box 完全相同、面積只差 0.3%」,我原本要去改幾何,追下去才發現正交鏡頭的畫框(1.55 格)裝不下最高的塔 —— **第 3、4 階都頂到天花板所以看起來一樣**。改成 2.0 格、鏡頭瞄準點上移之後,同一份幾何立刻分得開。

**加音效一定要補存在性測試**

見 [[silent-lookup-apis]]。`play_sound()` 查無此名是靜默 return,而且存在性測試只走到一半 —— 另一半是數實際觸發次數。
