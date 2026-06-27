# FrameExtractor v2

影片逐幀提取與智慧去重工具。**選單列 + 四分頁 + 多演算法分層去重**，提供 GUI 與命令列兩種介面，全程支援中文路徑。

## 安裝

```bash
pip install -r requirements.txt
```

核心依賴：`opencv-python`、`Pillow`、`imagehash`、`PyQt6`、`numpy`、`tqdm`。
CLIP 語意比對（`ultra` 等級）另需 `torch` + `open-clip-torch`，已一併列入 `requirements.txt`；
若不使用 `ultra` 等級，可不安裝這兩個重依賴。

## 執行

### GUI 版本（推薦）

```bash
python extract_frames_gui.py
```

深色現代 UI，含即時預覽、KPI 統計卡、進度條與處理日誌。

### 命令列版本

```bash
python extract_frames.py "你的影片.mp4"
python extract_frames.py "影片.mp4" -o 輸出資料夾 -p precise
```

| 參數 | 說明 |
|---|---|
| `video` | 影片檔案路徑（必填） |
| `-o / --output` | 輸出資料夾（預設 `影片名稱_frames`） |
| `-p / --preset` | 演算法等級：`fast` / `standard`(預設) / `precise` / `ultra` |
| `--hash-size` | 感知雜湊大小（預設 8） |
| `--quality` | JPG 品質（預設 100） |

## 檔案結構

```
FrameExtractor/
├── extract_frames_gui.py   # GUI 主程式（選單列、四分頁、即時預覽）
├── extract_frames.py       # 命令列版（提取 + 去重）
├── deduper.py              # 多演算法去重核心（DedupConfig / Deduper）
├── workers.py              # 四個背景執行緒（QThread）
├── requirements.txt
├── LICENSE                 # PolyForm Noncommercial 1.0.0
└── README.md
```

## 四個分頁（GUI）

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

| 等級 (`preset`) | 啟用演算法 | 預設閾值 | 速度 | 精準度 |
|---|---|---|---|---|
| `fast` 快速 | dHash | dHash≤5 | ★★★★★ | ★★ |
| `standard` 標準（預設） | dHash + pHash | dHash≤5, pHash≤5 | ★★★★ | ★★★ |
| `precise` 精準 | + 直方圖 + SSIM | dHash≤6, pHash≤6, hist≥0.95, ssim≥0.92 | ★★ | ★★★★ |
| `ultra` 最精準 | + CLIP 語意 | dHash≤8, pHash≤8, hist≥0.93, ssim≥0.90, clip≥0.93 | ★ | ★★★★★ |

**分層管線**：dHash 快篩過濾連續幀 → pHash 比對紋理 → 直方圖比對色彩 → SSIM 比對結構 → CLIP 比對語意。任一層判定不相似立刻 short-circuit，所以總時間反而比單跑 SSIM 還快。

GUI 中點「▼ 進階設定」可自由勾選與調整每個演算法的閾值，並可設定**滑動視窗**（只與最近 N 張比對）。

## 輸出檔案

**影片提取 / 去重**（輸出資料夾內）：

| 檔案 | 說明 |
|---|---|
| `frame_00000000.jpg` … | 去重後保留的 JPG 圖片（品質可設，預設 100） |
| `frames_report.csv` | 每一幀的完整記錄（狀態、時間戳、各演算法分數） |
| `duplicates.csv` | 被判定為重複而跳過的幀清單 |
| `summary.txt` | 統計摘要（總幀數、保留數、去重率、啟用演算法） |

**資料夾去重模式**（來源資料夾內）：

| 檔案 | 說明 |
|---|---|
| `_dedup_report.csv` | 每張圖片的判定與處置動作 |
| `_dedup_summary.txt` | 去重摘要 |

## 重複圖片處理（資料夾去重模式）

- **移動到 `_duplicates` 子資料夾**（建議，安全）
- **直接刪除**（會跳出確認對話框）
- **僅產生報表**（不動原檔，只輸出 `_dedup_report.csv`）

## 演算法實作狀態

五種演算法**皆已完整實作**：

- **dHash / pHash** — `imagehash` 感知雜湊，漢明距離比對。
- **直方圖** — HSV 色彩直方圖（H 50 bins、S 60 bins）相關係數比對。
- **SSIM** — 純 numpy + OpenCV 高斯窗實作的結構相似度（無額外依賴）。
- **CLIP** — `open-clip-torch`（ViT-B-32 / openai 權重）影像語意向量 + 餘弦相似度；模型於進程內快取，僅 `ultra` 等級才載入。

## 已知限制

- CLIP 語意比對（`ultra` 等級）首次使用會自動下載模型權重（約 300MB）；無 GPU 時以 CPU 推論，速度較慢。
- 中文路徑已支援（透過 `imencode + numpy.tofile` / `numpy.fromfile + imdecode` bypass OpenCV 的限制）

## 授權 License

本專案採用 **PolyForm Noncommercial License 1.0.0**（非商業授權）。

- ✅ 個人、學術、研究、嗜好、非營利組織等**非商業用途**可自由使用、修改、散布。
- ❌ **商業用途未獲授權**。任何商業使用（含營利、為企業帶來直接或間接利益）必須先取得書面商業授權。

> 商業授權請聯絡著作權人：**airesearch3412-hub** — https://github.com/airesearch3412-hub

詳見 [LICENSE](LICENSE)。
