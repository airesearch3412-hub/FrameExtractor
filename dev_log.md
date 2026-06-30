# dev_log

**用途：** 記錄每輪主要任務的問題、解法、驗證結果。
**硬規則：** 每輪完成後補記，內容不能只列「改了哪些檔」。

---

### 2026-06-30｜導入 SOP 治理（Tier 1+2）

| 欄位 | 內容 |
|---|---|
| 任務 | 評估並導入 `ai_fde_project_sop_template` 的治理框架 |
| 動機 | 為 FrameExtractor 建立「跨 session 專案記憶」，讓後續 AI 協作有一致的規則與脈絡 |
| 處理 | 評估後判定全導入過重（見 DEC-007），只建輕量核心：`CLAUDE.md`、`AGENTS.md`、`decision_log.md`、`dev_log.md`、`project_status.md`、`TASK_TEMPLATE.md`、`docs/specs/feature_spec_template.md`，並附範例規格 `docs/specs/feature-batch-crop.md`。全部客製為 FrameExtractor 版，未照搬 starter。 |
| 驗證 | 文件結構自檢；DEC-001~006 回溯既有 git 歷史與本輪工作填實 |
| 同步 | 本檔、`decision_log.md`(DEC-007)、`project_status.md`、`README.md`（文件地圖 + 檔案結構） |
| Commit | `1721240 docs: 導入輕量治理框架（SOP Tier 1+2）`（9 檔）；已隨 master push 至 origin |

---

### 2026-06-29｜裁剪預覽縮放 / 平移

| 欄位 | 內容 |
|---|---|
| 任務 | 為「✂ 批次裁剪」的 `CropSelector` 加入放大 / 縮小 |
| 問題 | 原元件只貼合視窗、無法放大檢視裁剪邊界；且縮放會牽動框選/控制點座標換算 |
| 解法 | 改用視圖轉換（scale+pan）：滾輪定點縮放、中鍵平移、工具列 −/＋/適應/1:1；裁剪框維持原圖座標；繪製改「只畫可見區」blit 避免高倍率記憶體爆量（DEC-006） |
| 驗證 | headless 測試：焦點不變性、中心定點縮放、平移夾住不露白邊、適應/1:1/下限、座標往返一致、縮放不改裁剪框、16× 高倍率繪製不崩潰；offscreen 渲染截圖確認 |
| Commit | `8259140 feat(crop): 裁剪預覽支援縮放與平移（滾輪/中鍵/工具列）`（在 master） |

---

### 2026-06-29｜關閉視窗崩潰修正（執行緒收尾）

| 欄位 | 內容 |
|---|---|
| 任務 | 修「關掉 GUI 會當機 / thread 處理有問題」 |
| 問題 | `closeEvent` 只 `wait(2000)` 就接受關閉 → worker 未停時帶著活執行緒銷毀元件 → `QThread: Destroyed while thread is still running` 崩潰；`BatchWorker.stop()` 未傳給子 worker |
| 解法 | `closeEvent` 先 `blockSignals+stop`、再逐一 `wait()` 等結束，逾時 `terminate()` 保險；`BatchWorker` 記住並下傳中止（DEC-005） |
| 驗證 | headless：裁剪進行中關閉後無殘留執行緒且訊號已切斷、無任務關閉乾淨、卡住的 worker 5s 後 terminate 不 hang（實測 5.1s）、`BatchWorker` 中止下傳 |
| Commit | `1a9d575 fix(crop/threading): 關閉視窗時安全結束背景執行緒，避免崩潰`（在 master） |

---

### 2026-06-29｜批次裁剪功能（併入 Colab notebook）

| 欄位 | 內容 |
|---|---|
| 任務 | 把 `crop_ebook_colab.ipynb` 功能併入批次處理，需預覽 + 框選 + 統一輸出 |
| 處理 | 新增 `BatchCropWorker`（workers.py）、`CropSelector` 互動框選元件 + 「✂ 批次裁剪」分頁（extract_frames_gui.py）、CLI `crop_images.py`；去除 Google Drive；支援中文路徑、防覆蓋（DEC-004） |
| 驗證 | CLI 端到端（混合尺寸/resize/PNG/中文檔名）、headless `BatchCropWorker`、防覆蓋 guard、GUI 五分頁建構、`CropSelector` 座標往返、版面截圖 |
| 對抗審查 | 跑多代理對抗審查（24 agent），確認 12 項真缺陷並全修：CLI `--resize` 驗證、同 stem 覆蓋、`set_crop` 回寫、spin 上限、中止謊報完成、KPI 對應、1px 接縫、效能、`mkdir` 錯誤處理等 |
| Commit | `b0c8047 feat(crop): 新增批次裁剪功能（互動式框選預覽 + CLI）`（在 master） |
