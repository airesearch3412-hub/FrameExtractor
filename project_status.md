# project_status

**用途：** 快速說明 FrameExtractor 目前狀態、未提交變更、阻塞點與下一步。

---

## 一、專案基本狀態

| 欄位 | 內容 |
|---|---|
| 專案名稱 | FrameExtractor |
| 目前分支 | `master` |
| 專案階段 | 維護 / 功能開發中（可用工具，非交付型專案） |
| 最後更新 | 2026-06-30 |

---

## 二、功能完成度

| 功能 | 狀態 |
|---|---|
| 🎬 影片提取 + 去重 | ✅ 完成 |
| 📸 只提取（可設抽幀間隔） | ✅ 完成 |
| 🗂 僅去重資料夾（移動/刪除/報表） | ✅ 完成 |
| 📚 批次處理多影片 | ✅ 完成 |
| ✂ 批次裁剪（框選預覽 + 縮放/平移 + 統一輸出 + CLI） | ✅ 完成 |
| 多演算法分層去重（dHash/pHash/直方圖/SSIM/CLIP） | ✅ 完成 |
| CLIP 裝置可切換（auto/cuda/cpu） | ✅ 完成 |

---

## 三、未提交 / 未推送

| 項目 | 狀態 |
|---|---|
| 裁剪預覽縮放 / 平移 | ✅ 已 commit（`8259140`，DEC-006） |
| SOP 治理文件（CLAUDE/AGENTS/log/status/templates） | ✅ 本輪 commit |
| `master` 領先 `origin/master` | 4 個 commit（批次裁剪、執行緒修正、縮放、治理文件），**尚未 push** |

---

## 四、阻塞 / 待決事項

1. **是否 push** `master` 到 `origin`？（目前領先 4 個 commit）
2. **「批次處理多去重」**功能範圍待確認（先前提出三種解讀，使用者尚未拍板）。
3. `web/`（`UIUX_SPEC.md` + `wireframes/`）+ `.claude/workflows/jarvis-implement-web.js`：平行進行的「web 網站版」任務產物，非本治理任務範圍，未追蹤也未動。

---

## 五、下一步建議

1. 視需要 push `master` 到 `origin`。
2. 釐清「批次處理多去重」要做哪一種（批次資料夾去重 / 裁剪後去重 / 影片去重加強）。
3. 視需要再評估是否補 Tier 2 的更多規格（每個主要功能補 `docs/specs/feature-*.md`）。
