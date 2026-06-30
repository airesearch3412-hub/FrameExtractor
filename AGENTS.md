# AGENTS.md — FrameExtractor

跨工具 AI 入口。完整工作指引見 **[`CLAUDE.md`](CLAUDE.md)**（自足文件，讀完即可開工）。

## 一、專案基本資訊

| 欄位 | 內容 |
|---|---|
| 專案名稱 | FrameExtractor |
| 專案目的 | 影片逐幀提取 + 多演算法智慧去重 + 批次裁剪的本地桌面工具（個人自用） |
| 主要技術棧 | Python 3 · PyQt6 · OpenCV · NumPy · Pillow · imagehash ·（選用）PyTorch + open-clip-torch |
| 部署環境 | 本地桌面（主 Windows）。無雲端 / Docker / CI |
| 專案負責人 | airesearch3412-hub |

## 二、進入專案第一步

1. 讀 `project_status.md`（目前狀態、未提交變更）
2. 讀 `CLAUDE.md`（可改/禁改區、慣例、完成定義）
3. 涉及某功能 → 讀對應 `docs/specs/*.md`

> 本專案只導入 SOP 模板的輕量治理（Tier 1+2），詳見 `CLAUDE.md` 開頭與 `decision_log.md` DEC-007。
