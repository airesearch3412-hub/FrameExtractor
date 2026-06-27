# FrameExtractor v2

影片逐幀提取與智慧去重工具。**選單列 + 四分頁 + 多演算法**。

## 安裝

```bash
pip install -r requirements.txt
```

## 執行

```bash
python extract_frames_gui.py
```

## 檔案結構

```
FrameExtractor/
├── extract_frames_gui.py   # 主程式（GUI、選單、四分頁）
├── deduper.py              # 多演算法去重核心
├── workers.py              # 四個背景執行緒
├── requirements.txt
└── README.md
```

## 四個分頁

| 分頁 | 用途 |
|---|---|
| 🎬 提取 + 去重 | 影片逐幀提取，同步去除相似畫面（一般用） |
| 📸 只提取 | 完整保留所有幀，不去重；可設定抽幀間隔 |
| 🗂 僅去重資料夾 | 對既有圖片資料夾做去重，可移動／刪除／僅報表 |
| 📚 批次處理 | 一次處理多個影片，自動為每個建立子資料夾 |

## 選單列

- **檔案**：開啟影片 (Ctrl+O)、開啟資料夾去重、匯出報表 (Ctrl+E)、離開 (Ctrl+Q)
- **編輯**：複製路徑 (Ctrl+C)、清除日誌 (Ctrl+L)、偏好設定 (Ctrl+,)
- **檢視**：切換主題 (Ctrl+T)、全螢幕 (F11)、顯示狀態列
- **說明**：使用說明 (F1)、檢查更新、關於

## 演算法等級

| 等級 | 啟用演算法 | 速度 | 精準度 |
|---|---|---|---|
| 快速 | dHash | ★★★★★ | ★★ |
| 標準（預設） | dHash + pHash | ★★★★ | ★★★ |
| 精準 | + 直方圖 + SSIM | ★★ | ★★★★ |
| 最精準 | + CLIP 語意 | ★ | ★★★★★ |

**分層管線**：dHash 快篩過濾連續幀 → pHash 比對紋理 → 直方圖比對色彩 → SSIM 比對結構 → CLIP 比對語意。任一層判定不相似立刻 short-circuit，所以總時間反而比單跑 SSIM 還快。

點「▼ 進階設定」可自由勾選與調整每個演算法的閾值。

## 重複圖片處理（資料夾去重模式）

- **移動到 _duplicates 子資料夾**（建議，安全）
- **直接刪除**（會跳出確認對話框）
- **僅產生報表**（不動原檔，只輸出 `_dedup_report.csv`）

## 已知限制

- CLIP 語意比對需另外安裝 PyTorch 與 CLIP 模型（首次使用會下載約 300MB）
- 中文路徑已支援（透過 `imencode + numpy.tofile` bypass OpenCV 的限制）
