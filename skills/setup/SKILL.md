---
name: setup
display_name: Godogen Setup
short_description: 把這台機器設定好,產出 .env 並建立知識索引
default_prompt: "用 ${SETUP_COMMAND} 幫我把 godogen 設定起來。"
allow_implicit_invocation: false
description: |
  引導使用者完成 godogen 的機器設定:偵測已安裝的工具、詢問素材後端偏好、寫出 .env、建立知識索引並驗證。
  使用者問「怎麼開始」「怎麼用」「how do I start」時執行。
---

# 設定

新 clone 下來的 godogen **是空的** —— `craft.db` 不在版控裡(`knowledge/*.md` 才是真相來源),所以知識庫要在本機重建。而且**沒有任何東西會提醒你**:publish 照樣成功、agent 照樣跑,只是什麼都不記得。

這個 skill 就是把那件事做完,並且**驗證過才說完成**。

## 一條原則:偵測優先於詢問

**不要問使用者你自己查得到的事。**

「你有沒有裝 Blender?」是事實,去看。「你想用本地還是雲端?」是偏好,才問。

每問一題就是一次讓人放棄的機會。目標是**只問一題**。

## 第 1 步:偵測

一次做完,不要邊問邊查:

| 查什麼 | 怎麼查 |
|---|---|
| Godot | `godot --version`;不在 PATH 就找常見安裝位置 |
| Python | `python --version`,要 3.11+ |
| Node.js | `node --version`,要 22.12+ |
| ffmpeg | `ffmpeg -version` |
| kg | `<godogen>/kg`、`<godogen>/../kg`、`~/.godogen/kg`,看有沒有 `main.js` 與 `hooks/` |
| Blender | `blender --version`;Windows 上找 Steam 與 Program Files |
| ComfyUI | `GET <COMFYUI_URL>/system_stats`,逾時 2 秒 |
| 音效服務 | `SFX_ENDPOINT` 的主機通不通 |
| 雲端金鑰 | 環境變數裡有沒有 `GOOGLE_API_KEY` / `XAI_API_KEY` / `TRIPO3D_API_KEY` |

**把結果整理成一張表給使用者看。** 他要先知道自己站在哪裡。

## 第 2 步:問那一題

**素材要用哪些後端。** 三軸獨立 —— 有人會想用雲端 LLM 配本地 Blender,那完全合理:

| 軸 | 選項 |
|---|---|
| **3D 模型** | `blender` 程式化(免費、可重現、要裝 Blender)· `tripo3d` 圖轉模(約 30–60¢/個)· `none` |
| **2D 圖** | `comfyui` 本地(免費、要 GPU)· `gemini`(5–15¢/張,精準)· `grok`(2¢/張,快但不精準)· `none` |
| **音效** | `local` 本地模型(免費)· `none` |

**依偵測結果給推薦,不要給空白選單。** 偵測到 Blender 就推薦 `blender` 並說明理由;沒偵測到而使用者也沒有 GPU,就推薦雲端並**講清楚一次 run 大概多少錢**。

**`none` 是正當選項。** 只想先做玩法、美術之後再說的人,三軸全 `none` 完全合理 —— 不要勸退。

## 第 3 步:寫 `.env`

照 `.env.example` 的結構,只填有值的欄位。**已存在的 `.env` 要保留使用者自己改過的東西**,只補缺的,不要整份覆蓋。

只有選到的後端才需要它的設定 —— 選 `tripo3d` 就不用問 Blender 在哪。

## 第 4 步:知識索引

kg 沒裝就先裝(這是唯一需要下載的東西,約 560MB 模型):

```bash
git clone https://github.com/ddwolfer/Multi-knowledgeGraph kg
cd kg && npm install
```

裝在 godogen 目錄裡面就好,`kg/` 已經在 `.gitignore` 裡。然後:

```bash
python scripts/bootstrap.py
```

它會匯入語料、產生向量、排注入優先權,而且**驗證過才回報成功** —— 底下兩個步驟都會「靜默地少做一點事然後印成功」,所以不要只看它印什麼。

## 第 5 步:回報

跑完給一張總結:哪些能用、哪些跳過了、以及**下一步怎麼開始做遊戲**:

```bash
python publish.py --engine godot --out <遊戲目錄>
```

如果有東西沒設好(例如選了 `comfyui` 但服務沒起來),**明確講出來以及影響是什麼** —— 不要假裝一切正常。使用者晚點自己撞到會更貴。

## 不要做的事

- 不要問可以偵測的事
- 不要在使用者沒同意前安裝任何東西
- 不要覆蓋既有的 `.env`
- 不要在無法驗證的情況下宣稱設定完成
