# TASK_TEMPLATE（FrameExtractor 精簡版）

> 用法：**複製本檔**為 `docs/specs/task-XXX-簡述.md` 再填，不要直接編輯本檔。
> 個人自用專案，欄位已精簡；不適用的填「N/A」。

---

## 一、基本資訊

| 欄位 | 內容 |
|---|---|
| 任務名稱 | （動詞 + 目標 + 範圍） |
| 任務編號 | `task-XXX` |
| 類型 | Feature / Bugfix / Refactor / Docs / Research |
| 優先級 | P0 / P1 / P2 |
| 日期 | YYYY-MM-DD |

## 二、目的與範圍

- **為什麼做：**（1~2 句說明價值/動機）
- **允許修改：**（檔案 / 目錄路徑）
- **禁止修改：**（若無填「無」）
- **相關規格 / 決策：**（`docs/specs/*.md` / `DEC-XXX`，無則「N/A」）

## 三、預期輸出（每項要有完成條件）

| 輸出 | 完成條件 |
|---|---|
| 程式碼 |  |
| 驗證 | 每條 AC 有驗證方式與結果 |
| 文件 | 列出要同步的文件 |

## 四、驗收標準（至少 3 條）

| 編號 | 驗收條件 | 驗證方式（Unit/Integration/Manual/Review） | 結果 |
|---|---|---|---|
| AC-01 |  |  | Pass/Fail/Pending |
| AC-02 |  |  |  |
| AC-03 |  |  |  |

## 五、完成檢查（對齊 `CLAUDE.md` §五 DoD）

- [ ] 編譯通過、功能已驗證、UI 變更已視覺確認
- [ ] `README.md` / `decision_log.md` / `dev_log.md` / `project_status.md` 視需要同步
- [ ] 已 commit（push 等使用者指示）

## 六、交付摘要

- **完成項目：**
- **未完成 / 已知限制：**（無則「無」）
- **遇到問題與解法：**
- **建議下一步：**
- **相關 commit / 文件：**
