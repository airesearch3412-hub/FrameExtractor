# decision_log

**用途：** 記錄會影響後續維護、擴充或驗收方式的重要技術/架構決策。
**硬規則：** 凡改變「做法、標準、工具、範圍」的決定，不能只留在對話裡，必須寫成 `DEC-XXX`。

---

### DEC-007：只導入 SOP 模板的輕量治理（Tier 1+2）

| 欄位 | 內容 |
|---|---|
| 日期 | 2026-06-30 |
| 狀態 | Accepted |
| 背景 | 評估導入 `ai_fde_project_sop_template`。該框架定位為「網站/接案/多人」企業級治理，含大量 CI gate、`tools/` 自動化、Docker、知識庫同步、客戶報價合約。FrameExtractor 是單人自用桌面工具（對應其分類的「本地工具」）。 |
| 決策 | 只導入「輕量治理核心」：AI 入口（`CLAUDE.md`/`AGENTS.md`）、`decision_log.md`、`dev_log.md`、`project_status.md`、`TASK_TEMPLATE.md`、`docs/specs/` 規格模板。**不導入** `PROJECT_RULES.md` 全集、`.github/workflows/` PR gate、`tools/`、`Dockerfile`、知識庫同步、客戶/網站交付文件。必要規則（可改/禁改區、DoD、commit 規則）改為精簡內嵌於 `CLAUDE.md`。 |
| 替代方案（否決） | (1) 全導入 → 對單人自用嚴重過重，維護負擔遠大於收益。(2) 完全不導入 → 失去「跨 session 專案記憶」這個對 AI 協作 CP 值最高的部分。 |

---

### DEC-006：裁剪預覽改用視圖轉換（scale + pan）支援縮放

| 欄位 | 內容 |
|---|---|
| 日期 | 2026-06-29 |
| 狀態 | Accepted（commit `8259140`） |
| 背景 | `CropSelector` 原本只把影像等比例貼合視窗，無法放大檢視裁剪邊界細節。 |
| 決策 | 改為維護視圖轉換 `widget = origin + img × scale`：滾輪以游標為定點縮放、中鍵拖曳平移、工具列（−/＋/適應/1:1）。裁剪框維持原圖座標、不受縮放影響。繪製改為「只畫可見區域」的即時 blit（`drawPixmap(target, pix, source)`），避免高倍率配置巨大點陣圖。縮放下限=適應視窗、上限=16×。 |
| 替代方案（否決） | 預先 `pixmap.scaled()` 整張快取 → 16× 時記憶體爆量（~530MB）；改採只畫可見區的 source-rect blit。 |

---

### DEC-005：GUI 關閉時的執行緒安全收尾

| 欄位 | 內容 |
|---|---|
| 日期 | 2026-06-29 |
| 狀態 | Accepted |
| 背景 | 原 `closeEvent` 只 `wait(2000)` 便接受關閉；worker 若未在 2 秒內停止，視窗/元件被銷毀後執行緒仍在 emit 訊號到已釋放物件，導致 `QThread: Destroyed while thread is still running` 崩潰。`BatchWorker.stop()` 又沒把中止傳給正在跑的子 worker。 |
| 決策 | `closeEvent`：先對所有在跑的 worker `blockSignals(True)`+`stop()`（切斷訊號），再逐一 `wait()` 等執行緒真正結束；逾時（5s）以 `terminate()` 作最後保險，**絕不帶著活執行緒銷毀視窗**。`BatchWorker` 記住目前子 worker，`stop()` 一併往下傳。 |
| 替代方案（否決） | 維持短 timeout 後直接 accept → 即為崩潰主因；不可行。 |

---

### DEC-004：批次裁剪採純本地實作（取代 Colab notebook）

| 欄位 | 內容 |
|---|---|
| 日期 | 2026-06-29 |
| 狀態 | Accepted |
| 背景 | 需求是把 `crop_ebook_colab.ipynb`（Google Drive + Colab 的電子書批次裁剪）併入本專案批次處理。 |
| 決策 | 去掉 Google Drive/Colab，改為純本地：新增 `BatchCropWorker`（QThread，訊號介面對齊既有 worker）、GUI 新增「✂ 批次裁剪」分頁與互動式框選元件 `CropSelector`、CLI `crop_images.py`。對一批相同尺寸圖像套用同一裁剪框、輸出統一格式，並防呆避免覆蓋原檔/同名來源互相覆蓋。 |
| 替代方案（否決） | 保留 Google Drive 流程 → 與「本地自用」定位不符、徒增 google-api 重依賴。 |

---

### DEC-003：CLIP 為選用重依賴、進程內快取、可切換運算裝置

| 欄位 | 內容 |
|---|---|
| 日期 | 2026-06-29 |
| 狀態 | Accepted |
| 背景 | CLIP 語意去重精度高但依賴 `torch`+`open-clip-torch`（重）、且 GPU 可大幅加速。 |
| 決策 | 僅 `ultra` 等級載入 CLIP；模型於進程內快取（`_CLIP_CACHE`）；裝置可選 `auto`/`cuda`/`cpu`，指定 `cuda` 卻偵測不到時明確報錯（不默默回退）。不使用 ultra 即可不安裝 torch。 |

---

### DEC-002：中文路徑以 imencode/tofile + fromfile/imdecode 繞過 OpenCV

| 欄位 | 內容 |
|---|---|
| 日期 | 2026-06-27 |
| 狀態 | Accepted |
| 背景 | `cv2.imread/imwrite` 在 Windows 對非 ASCII 路徑會失敗。 |
| 決策 | 統一用 `imread_unicode`（`np.fromfile`+`cv2.imdecode`）/ `imwrite_unicode`（`cv2.imencode`+`buf.tofile`）。所有影像讀寫都走這兩個函式。 |

---

### DEC-001：採分層多演算法去重管線（短路）

| 欄位 | 內容 |
|---|---|
| 日期 | 2026-06-27 |
| 狀態 | Accepted |
| 背景 | 單一演算法去重在速度/精度間難兼顧。 |
| 決策 | 採分層管線 dHash 快篩 → pHash → 直方圖 → SSIM →（選用）CLIP，任一層判定不相似即 short-circuit；以預設等級 `fast/standard/precise/ultra` 對應不同層組合，GUI 進階面板可自訂閾值與滑動視窗。 |
