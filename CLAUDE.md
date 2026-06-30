# CLAUDE.md — FrameExtractor

> 本專案的 AI 協作工作指引（個人自用桌面工具）。讀完本檔即可開始工作。
> 治理框架取自 `ai_fde_project_sop_template`，但**刻意只導入輕量核心（Tier 1+2）**：
> 採用 AI 入口 / 決策紀錄 / 開發紀錄 / 任務卡 / 規格模板；**不採用** PROJECT_RULES 全集、
> CI PR gate、`tools/` 自動化、Docker、知識庫同步等接案/網站/多人才需要的部分（見 [DEC-007](decision_log.md)）。

---

## 一、專案基本資訊

| 欄位 | 內容 |
|---|---|
| 專案名稱 | FrameExtractor |
| 專案目的 | 影片逐幀提取 + 多演算法智慧去重 + 批次裁剪的本地桌面工具（個人自用） |
| 主要技術棧 | Python 3 · PyQt6 · OpenCV(opencv-python) · NumPy · Pillow · imagehash ·（選用）PyTorch + open-clip-torch |
| 部署環境 | 本地桌面（主：Windows）。無雲端 / 伺服器 / Docker / CI |
| 專案負責人 | airesearch3412-hub（個人自用） |

---

## 二、開始工作前必讀

1. `project_status.md` — 目前進度、未提交變更、阻塞點、下一步
2. 相關 `docs/specs/*.md` — 該功能的規格與驗收（若有）
3. 本檔 — 可改/禁改區、慣例、完成定義

---

## 三、檔案分區（可改 / 禁改）

| 區域 | 路徑 | 規則 |
|---|---|---|
| 應用程式碼 | `extract_frames_gui.py`、`extract_frames.py`、`crop_images.py`、`workers.py`、`deduper.py` | 可改；改核心前先 Read |
| 核心（謹慎） | `deduper.py`（去重演算法）、`workers.py`（QThread） | 改前先讀懂分層管線與訊號介面，勿破壞既有 worker 契約 |
| 文件 | `README.md`、`docs/`、`*_log.md`、`project_status.md` | 可改；任務完成需同步 |
| 禁動 | `LICENSE`、`.git/`、既有 commit 歷史 | 不得擅改 |
| 非本工具產物 | `web/`（`UIUX_SPEC.md` 等，他處生成） | **不要碰**，除非使用者明確指示 |
| 使用者資料 | 任何輸出資料夾 / 影片 / 圖片 | 不得刪除或覆蓋 |

---

## 四、開發慣例

- **Commit**：Conventional Commits（`feat/fix/docs/refactor/test/chore`），描述用繁中（沿用既有風格）；訊息結尾加 `Co-Authored-By`。完成一個功能或修復即 commit。
- **分支 / Push**：使用者個人專案，已確認可直接 commit 到當前分支；**push 只在使用者明確要求時**做。動破壞性 git 操作前先問。
- **UI 變更**：必須做視覺驗證（實機，或 `QT_QPA_PLATFORM=offscreen` 渲染截圖），不可只靠編譯/測試判定正確。沿用既有設計語彙：`DARK_QSS`/`LIGHT_QSS` 色票、`make_card`/`section_label`/`field_label`、`primary`/`danger` 按鈕；不臨時引入新字型/色票/尺寸。
- **執行緒**：每個 `QThread` worker 必須可被 `stop()` 中止；新 worker 的訊號介面對齊既有 worker（`progress/log/preview/stats_update/finished_ok/error`）。關閉視窗時 `closeEvent` 必須先 `stop()`+切斷訊號、再 `wait()` 等執行緒結束才銷毀（見 [DEC-005](decision_log.md)）。
- **中文路徑**：影像讀寫一律走 `imread_unicode` / `imwrite_unicode`（見 [DEC-002](decision_log.md)），不直接用 `cv2.imread/imwrite`。
- **相依**：不隨意新增重依賴；`torch` / `open-clip-torch` 為選用，僅 `ultra` 去重等級載入。

---

## 五、Definition of Done（FrameExtractor 版）

- [ ] 變更已 `python -m py_compile` 通過
- [ ] 受影響功能已實際驗證（CLI 端到端 / headless worker / GUI offscreen 渲染或實機）
- [ ] UI 變更已視覺確認
- [ ] 若使用方式或功能有變 → `README.md` 已同步
- [ ] 若有架構/技術取捨 → `decision_log.md` 補一筆 `DEC-XXX`
- [ ] 任務完成 → `dev_log.md` 補一筆（問題 / 解法 / 驗證，不只列改了哪些檔）
- [ ] `project_status.md` 已更新（完成度 / 未提交變更 / 下一步）
- [ ] 完成一個功能或修復即 commit（push 等使用者指示）

---

## 六、AI 不得自行決定

1. 刪除或覆蓋使用者的影片 / 圖片 / 輸出資料夾
2. `git push`、force push 或其他破壞性 git 操作
3. 新增重量級外部相依（如預設安裝 torch）
4. 刪除非本人建立的檔案（例如 `web/`）

---

## 七、文件地圖

| 想做什麼 | 去哪 |
|---|---|
| 了解功能與用法 | `README.md` |
| 看目前狀態 / 未提交變更 | `project_status.md` |
| 寫/查架構決策 | `decision_log.md`（`DEC-XXX`） |
| 看開發歷程 | `dev_log.md` |
| 開新任務卡 | 複製 `TASK_TEMPLATE.md` → `docs/specs/task-XXX-*.md` |
| 寫功能規格 | 複製 `docs/specs/feature_spec_template.md`；範例見 `docs/specs/feature-batch-crop.md` |
