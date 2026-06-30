# FrameExtractor 網站版 — 高保真 UI 原型

> 作者：Uma（資深 UI/UX）· 唯一視覺/互動真實來源：`web/UIUX_SPEC.md`
> 對接生產前端：Jarvis

這是 FrameExtractor 網站版的**高保真、可離線操作的 UI 原型**。它把 `UIUX_SPEC.md` 的 design tokens、5 個分頁、23 個元件、所有狀態與微文案完整落地成可點擊的畫面，用來在動工生產前端前先對齊視覺與互動。

**這是原型，不是生產程式**：所有「真資料」都由前端 mock（計時器、假目錄樹、SVG 佔位圖）模擬，沒有任何後端呼叫。每一處待接線都以 `TODO(Jarvis)` 在 `app.js` 標註。

---

## 1. 如何離線開啟預覽

直接用瀏覽器開 `index.html` 即可，**不需要伺服器、不需要 build、不需要安裝任何東西**：

- **Windows**：在檔案總管雙擊 `web/prototype/index.html`（或拖到瀏覽器視窗）。
- 路徑：`D:/GitHub/person_projects/FrameExtractor/web/prototype/index.html`
- 也可在任意瀏覽器網址列輸入 `file:///D:/GitHub/person_projects/FrameExtractor/web/prototype/index.html`。

三個檔案彼此以相對路徑連結，整個資料夾搬到哪都能離線開：

```
web/prototype/
├── index.html   ← 結構（殼層 + 5 tab + 8 個對話框 + Demo 控制列）
├── styles.css   ← 正式設計系統樣式表（§3 tokens + 23 元件 + 深淺主題 + 響應式 + 無障礙）
└── app.js       ← 互動 mock（主題切換 / Tabs / Dialog / JobRunner / 裁剪 Canvas / 結果圖庫…）
```

主題（深/淺）會記在 `localStorage`（key `fe-theme`），首次載入跟隨系統偏好；`<head>` 內聯腳本先設 `data-theme` 防 FOUC。

---

## 2. Demo 控制列怎麼用（檢視所有狀態）

頁面最上方有一條**虛線標示、明確標記「非正式 UI」**的 Demo 控制列（正式產品不會有）。它讓你不必真的跑後端，就能把規格裡的每個狀態叫出來檢視：

| 群組 | 按鈕 | 作用 |
|---|---|---|
| **作用分頁狀態** | 空 / 上傳中 / 處理中 / 完成 / 錯誤 / 中止 | 對「目前作用中的 tab」套用該狀態：進度條、KPI、預覽、日誌、pill、操作列、tab 處理中圓點全部聯動。「處理中」會跑一段 mock SSE 動畫直到 100%。 |
| **對話框** | 關於 / 說明 / 偏好 / 伺服器選擇器 / 完成摘要 / **完成(0 重複)** / **磁碟失敗** / 結果圖庫 / 刪除確認 | 直接開各對話框。完成摘要有 4 種變體：正常完成、去重 0 重複（正向綠語氣）、中止、中途寫入失敗（已保留部分結果）。 |
| **其他** | 錯誤 Toast | 彈出 `role="alert"` 的錯誤 toast（含「重試」鈕，不自動消失）。 |
| | GPU 偵測四態下拉 | 切換進階面板的 GPU 偵測：偵測中（spinner）/ 有 GPU / 無 GPU / 偵測失敗（含「重試」鈕）。 |
| | 灌入 mock 資料 | 一鍵把清單 / 預覽 / KPI / 日誌填入範例值（裁剪 tab 會載入範例圖）。 |

**建議檢視動線**：
1. 切到每個 tab，用「作用分頁狀態」六鍵走一輪 idle → uploading → running → done → error → cancelled。
2. 用右上角主題鈕（或 `Ctrl/⌘+T`）在深/淺主題各看一次。
3. 縮放瀏覽器視窗到手機寬度（< 640）看響應式重排（tab 橫向捲動、KPI 2×2、預覽/日誌堆疊、操作列 sticky 底部）。
4. 用鍵盤 Tab/方向鍵走一遍，確認 focus ring 與 tablist 方向鍵切換。

---

## 3. 原型已涵蓋的畫面 / 對話框 / 狀態清單

**5 個分頁（tab）**：🎬 提取 + 去重、📸 只提取、🗂 僅去重資料夾、📚 批次處理（雙進度條）、✂ 批次裁剪（Canvas + 4 數字框）。各 tab 的輸入卡、進階面板、參數卡、操作列、進度格式、KPI 四色語意、完成欄位皆依 §5 落地。

**8 個對話框 / 浮層**：關於、使用說明、偏好設定、伺服器資料夾選擇器（麵包屑 + 上一層鎖定）、完成摘要（4 變體）、結果圖庫（縮圖網格 / 檔案 CSV 雙檢視）、刪除二次確認、Lightbox（放大 + ← →）、Toast 容器。

**狀態**：idle / 上傳中（indeterminate）/ 處理中（即時進度・KPI・預覽・日誌・tab 脈動圓點）/ 完成 / 完成 0 重複（正向）/ 錯誤（有部分輸出，結果鈕仍可用）/ 中止 / GPU 偵測四態 / 連線中斷 pill / 裁剪壞檔態 / 空狀態（正向 vs 負向）。

**橫向能力**：深/淺主題（記憶 + 跟隨系統 + 防 FOUC）、響應式（手機/平板/桌面）、WCAG 2.1 AA（實色雙環 focus ring、ARIA roles、全域 sr-only 播報區、`prefers-reduced-motion` 降動效、處理中 tab 非顏色冗餘）、日誌環狀緩衝 800 行 + trim 提示 + 「↓ 跳到最新」、數字框越界 clamp 閃示、KPI 大數 clamp 縮放。

---

## 4. 哪些是 mock（生產時要換掉）

以下在原型中是假的，`app.js` 內皆有 `TODO(Jarvis)` 標註：

- **所有處理流程**：`runJob` 用 `setInterval` 假裝 SSE，進度/KPI/預覽圖（SVG data URL）全是算出來的，沒有真的抽幀/去重/裁剪。
- **伺服器資料夾選擇器**：`SERVER_TREE` 是寫死的假目錄樹，沒有打 `/api/browse`。
- **上傳**：dropzone 選檔只彈 toast，沒有真的上傳、沒有 size 預檢/逾時/每檔進度條（`.upload-progress` / `.dropzone__file` CSS 已備、未接線）。
- **下載 ZIP**：只有「打包中…」loading 動畫 + 成功 toast，沒有真的串流下載。
- **GPU 偵測**：`setTimeout` 隨機回 good/warn，沒有打 `/api/clip-device-info`。
- **結果圖庫**：固定 24 張縮圖全量塞入；**清單與縮圖虛擬化（VirtualList / VirtualGrid）尚未實作**（選取已用 id 集合保存、與 DOM 解耦，可直接沿用），縮圖載入骨架 `.thumb--skeleton` 已備未接。
- **偏好設定**：只有「主題」下拉真的生效，其餘欄位（上傳上限/日誌行數/逾時）為 mock。

---

## 5. 給 Jarvis：如何把原型轉成生產前端

**核心策略：沿用 `index.html` + `styles.css`，只把 `app.js` 的 mock 換成真 API / SSE。** 視覺層已定稿，不要重畫。

### 5.1 直接沿用、不要動

- **`styles.css`**：這就是正式設計系統樣式表。零 magic number、全走 §3 tokens、深淺主題、響應式、無障礙都已完成。新元件一律沿用既有 class 與 token，需要新尺寸/色先在 `:root` 立 token 再用。
- **`index.html` 的結構與 class**：5 tab 骨架、卡片、欄位、對話框（原生 `<dialog>`，自帶 focus trap + Esc + scrim）、ARIA 屬性都已就位。
- **移除 Demo 控制列**：刪掉 `<div class="demo-bar">…</div>` 整段與 `app.js` §12 的 `[data-demo-*]` 綁定即可，其餘不受影響。

### 5.2 把 mock 換成真實後端（依 `app.js` 章節）

| `app.js` 區塊 | 現況（mock） | 換成 |
|---|---|---|
| §7 `runJob` / `setState` | `setInterval` 假進度 | `POST /api/jobs/...` 取 `job_id` → `EventSource(/api/jobs/{id}/events)`；把 `log/progress/sub_progress/stats/preview/done/error/cancelled` 事件分派到既有的 `setProgress/setKpi/logLine/預覽` 函式（介面不變）。 |
| §8 伺服器選擇器 | `SERVER_TREE` 假樹 | `GET /api/browse?path=`（回 `{dirs,files,cwd}`）；麵包屑根目錄鎖定已做，後端須 `realpath` 驗證在 `/data` 內，400 → 既有 error toast。 |
| §8 dropzone `mockPickFile` | 只彈 toast | 真上傳 + 前端 `file.size` 預檢（超 `MAX_UPLOAD_BYTES` 擋下引導改瀏覽伺服器）+ 逾時重傳；接 `.upload-progress` / `.dropzone__file` 樣式。 |
| §5 GPU `runDetect` | 隨機 good/warn | `GET /api/clip-device-info`，沿用既有 `setGpu` 四態（busy/good/warn/error）。 |
| §7b 下載 ZIP | loading 動畫 | 觸發 `GET /api/jobs/{id}/download`（後端 streaming / server 落地）；按鈕 `aria-busy` 防重複已做。 |
| §11 `openResults` | 24 張全量 | 接 `/api/jobs/{id}/files` + 縮圖 `/api/jobs/{id}/file/{name}`；實作 §11.3 **VirtualGrid**（>200 張 windowing + 分頁 + skeleton + IntersectionObserver 回收）。 |
| §9 `setupFilelist` | 全量重建 DOM | 實作 §11.3 **VirtualList**（>1000 列 windowing）；選取 Set 已解耦可沿用。 |

### 5.3 鐵則（沿用原型已遵守的規範）

- **禁止 JS 寫死色碼 / px**：需要色或尺寸時用 class + CSS 變數，或 `getComputedStyle` 讀 token（裁剪 Canvas 已示範）。主題切換才不會壞。
- **報讀不洪水**：progress 每幀更新 width 但 `aria-valuetext` 不每幀；里程碑與每 10%/10s 摘要才進全域 `#srStatus`（`role=status aria-live=polite`）。日誌 `aria-live="off"`。
- **focus ring 不可移除**：`:focus-visible` 的實色雙環是純鍵盤使用者唯一定位線索。
- **中文檔名**：一律 `textContent`（非 `innerHTML`）顯示，前端不做破壞性 encode。
- 技術合約以 `web_spec.md` 為準，視覺/互動以 `web/UIUX_SPEC.md` 為準。

### 5.4 驗收

對照 `UIUX_SPEC.md` 附錄 A/B 逐項勾：5 tab 深淺主題、SSE 即時動、完成摘要 + 下載 ZIP、批次雙進度條（僅整體條播報）、裁剪雙向同步（含壞檔態）、中文檔名、preset 回填、GPU 四態、全鍵盤可達、focus ring ≥3:1、primary 白字四態 ≥4.5:1、虛擬化、路徑越權與磁碟失敗可見回饋。
