---
name: asset-gen
display_name: Asset Generator
short_description: 生成遊戲的 3D 模型、圖示、音效與動畫,本地優先
default_prompt: "用 ${ASSET_SKILL_COMMAND} 幫這個遊戲做模型、圖示或音效。"
allow_implicit_invocation: true
description: |
  生成遊戲素材:Blender 程式化建模輸出 GLB、ComfyUI 出圖、本地引擎生音效,以及後處理。
  沒有本地 GPU 時可退回雲端 API(Gemini / Grok / Tripo3D,付費)。遊戲需要美術或音訊時使用。
---

# 素材生成

**這個專案選定的後端:${ASSET_BACKENDS}**

三軸是獨立的 —— 用雲端出圖配本地 Blender 建模是正常組合。**照上面那行走**,不要自己挑;那是使用者在設定時決定的。標成 `not used` 的那一軸就不要生,問使用者要用什麼替代(現成素材、純色塊、之後再補)。

工具在 `${ASSET_GEN_SKILL_DIR}/tools/`,從專案根目錄執行。跑起來會載入的產物放 `${RUNTIME_ASSET_DIR}/`,生成的中間產物(參考圖、原始音檔、建模腳本)放在那之外。

## 一條原則

**生成只是第一步,後處理才是能不能用的關鍵。生成器吐出來的東西一律不直接進專案。**

原始音檔前面有 0.1 秒靜音、結尾有斷點、音量跟現有素材差 10 dB;生成的圖跨批次會漂移;生成的 3D 每次形狀都不一樣。這些不是瑕疵,是預期行為 —— 管線要處理掉它們。

## 範圍紀律

**只生圖示與一張主視覺,不生角色圖。** 角色美術跨批次會漂移、在棋盤尺寸下讀不出來,而且早早押在上面會讓設計改動變貴。圖示小、可替換,而且扛下大部分「這是個完成品」的感覺。

3D 單位用程式化建模,不用生成式。

## 3D 模型 — Blender 程式化

```bash
python ${ASSET_GEN_SKILL_DIR}/tools/blender_gen.py tools/make_units.py --out ${RUNTIME_ASSET_DIR}/models
```

你寫一份 `bpy` 腳本堆幾何體並匯出 GLB,這個驅動器負責找到 Blender、限時執行、**驗證產物非空**(Blender 在 Python 出錯後仍退出 0,會留下 0 byte 的檔案)。

建模約定讀 `${ASSET_GEN_SKILL_DIR}/blender.md` —— 座標(Z-up、正面 -Y,轉 glTF 後變 +Z)、輪廓優先、細桿要斜向鏡頭、顏色表與渲染層同步。這幾條每一條都能讓整批模型報廢而不報錯。

## 2D 圖 — ComfyUI

```bash
python ${ASSET_GEN_SKILL_DIR}/tools/comfy_gen.py \
  --subject "a crude short sword forged from scrap iron, pitted blade, cloth-wrapped grip" \
  -o ${RUNTIME_ASSET_DIR}/icons/sword.png \
  --workflow workflows/flux_api.json
```

從 ComfyUI 介面匯出 API 格式的 workflow 當模板,程式只改三個欄位。

**最重要的一招:鎖一條風格字串,所有圖共用,每張只換主體描述。** 這是「一套圖示」和「一堆不相關的圖」的差別。風格字串寫在 `comfy_gen.py` 的 `STYLE_PROMPT`,改了它就要重生整套。

workflow 裡有兩個 `CLIPTextEncode` 時,工具會**拒絕猜測**哪個是正向提示,要用 `--positive-node` 指定 —— 蓋錯會把反向提示覆寫掉,結果看起來像模型壞了。

8GB VRAM 用 Flux 12 步就夠。

## 音效 — 本地引擎

```bash
python ${ASSET_GEN_SKILL_DIR}/tools/sfx_gen.py generate \
  --prompt "single armored boot plants on packed dirt, soft dull thud with faint chainmail jingle, dry close mic, very fast decay, no reverb" \
  -o ${RUNTIME_ASSET_DIR}/sfx/step.wav
```

**prompt 寫法:英文,「聲音事件 + 材質 + 衰減 + 錄音特徵」,不要寫音樂風格。**

後處理自動跑,四步:切起音點(峰值 2%,前留 3ms)、裁長(短音 0.28–0.35 秒)、尾巴淡出 50ms、RMS 對齊目標音量。過輕的音會先過 `tanh` 軟壓縮再拉音量 —— 細碎的摩擦聲峰值高但主體很小,直接放大會先爆掉峰值。

對既有音檔單獨跑後處理:

```bash
python ${ASSET_GEN_SKILL_DIR}/tools/sfx_gen.py post raw.wav -o ${RUNTIME_ASSET_DIR}/sfx/step.wav --target-dbfs -17
```

**加完音效一定要補一條存在性測試。** `play_sound()` 這類 API 查無此名是**靜默 return**,沒有這條測試就會做出「程式叫得出來、玩家永遠聽不到」的假機制。

## 現成素材包

免費素材包照用它的**內容物**(建築、樹、道具),**不用它的地磚** —— 地皮幾何跟不上模擬邏輯就別硬套。樹林等擺飾可以身兼地形障礙,視覺與戰術複雜度一次解。授權檔跟素材一起進版控。

## 後處理工具

- `rembg_matting.py` 去背 —— 讀 `${ASSET_GEN_SKILL_DIR}/rembg.md`。**絕不要 prompt「透明背景」**(生成器會畫出棋盤格),要 prompt 純色再去背。
- `grid_slice.py` 切圖 —— 一張圖生多個物件再切開,`--grid 2x2 --names "a,b,c,d"`。
- `find_loop_frame.py` 找循環幀 —— 走路/待機這類要循環的動畫用,一次性動作(攻擊/死亡)不用。

尺寸不一致會毀掉去背:圖片幀約 1024px、影片幀約 720px,**先全部縮到最小的來源尺寸再去背**。

## 雲端 fallback(付費)

沒有本地 GPU、或需要本地模型做不出的東西(寫實照片、精確跟隨複雜指令)時,用 `asset_gen.py`。**每次呼叫都是真的錢,第一次付費生成前先跟使用者確認。**

| 模型 | 旗標 | 費用 | 適合 |
|---|---|---|---|
| Gemini | `--model gemini` | 5¢(512)· 7¢(1K)· 10¢(2K)· 15¢(4K) | 精確跟隨提示:參考圖、角色、3D 用參考圖 |
| Grok | `--model grok`(預設) | 2¢ | 好看但不精確:貼圖、簡單物件、場景背景 |

```bash
python ${ASSET_GEN_SKILL_DIR}/tools/asset_gen.py image --prompt "..." -o ${RUNTIME_ASSET_DIR}/img/car.png
python ${ASSET_GEN_SKILL_DIR}/tools/asset_gen.py glb --image ref.png -o model.glb     # 30¢ / 60¢ --quality hd
python ${ASSET_GEN_SKILL_DIR}/tools/asset_gen.py rig --image ref.png -o rigged.glb    # +25¢,僅人型
```

**Tripo3D 逾時不代表失敗,絕對不要重送 —— 那會重複收費。** 任務 id 存在 `<output>.tripo.json`,免費續接:

```bash
python ${ASSET_GEN_SKILL_DIR}/tools/asset_gen.py resume -o model.glb
```

可安全重跑,完成後會 no-op。刪掉 sidecar 才會重新開始。

`glb` 的來源圖:3/4 仰角、純白或灰底、霧面、單一置中主體,而且**不要去背**(Tripo3D 需要純色背景)。

## 資產清單

每個生成的素材都要記進 `README.md`,而且**必須有 in-game Size 欄** —— 沒有它,寫程式的人會一致地把素材縮放錯。

- 3D 模型:公尺,例如 `4m long`、`1.8m tall`
- 貼圖:鋪磚尺寸,例如 `2m tile`
- 背景:像素尺寸 + 行為,例如 `1920x1080, fullscreen`
- 圖示/Sprite:顯示像素,例如 `128x128 px`

| Name | Description | Size | Path | Cost |
|------|-------------|------|------|------|
| sword | 廢鐵短劍圖示 | 128x128 px | ${RUNTIME_ASSET_DIR}/icons/sword.png | 0 |
| car | 有尾翼的房車 | 4m long | ${RUNTIME_ASSET_DIR}/glb/car.glb | 37¢ |

## 輸出格式

每個指令印 JSON 到 stdout(`{"ok": true, "path": "...", "cost_cents": 0}`),進度到 stderr。把 stderr 導到暫存檔、只在失敗時讀,保持 context 乾淨:

```bash
_log=.asset-gen.log
result=$(python ${ASSET_GEN_SKILL_DIR}/tools/sfx_gen.py post raw.wav -o out.wav 2>"$_log") || tail -20 "$_log"
```

彼此獨立的生成可以平行跑(一則訊息裡發多個指令)。

## 視覺陷阱

生成器與視覺檢查的空間感都很弱,重要的時候從截圖確認。

- **方向與朝向不可靠**(「面朝左」跟「面朝右」常常長一樣)。生一個方向,執行期水平翻轉,不要付錢生鏡像。
- **播放幀率**:來源影片約 24fps,sprite 播放要用經過的時間去驅動(約 1/24 秒一幀),而且只在動畫狀態真的改變時才重啟循環。
