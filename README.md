# FrameExtractor · 影片逐幀提取與去重工具

逐幀提取影片畫面為 **JPG 100% 品質**，使用 **pHash 感知雜湊** 自動判斷重複畫面，並輸出 CSV 報表、重複清單與統計摘要。

## 安裝

```bash
pip install -r requirements.txt
```

## 使用

### GUI 版本（推薦）

```bash
python extract_frames_gui.py
```

深色現代風介面，含即時預覽、KPI 統計卡、進度條、處理日誌。

### 命令列版本

```bash
python extract_frames.py "你的影片.mp4"
python extract_frames.py "影片.mp4" -o 輸出資料夾 -t 5
```

參數：
- `-o / --output`：輸出資料夾（預設 `影片名稱_frames`）
- `-t / --threshold`：pHash 漢明距離閾值，越小越嚴格（預設 5，0 = 完全相同）
- `--hash-size`：pHash 雜湊大小（預設 8）

## 輸出檔案

在輸出資料夾中會產生：

| 檔案 | 說明 |
|---|---|
| `frame_00000000.jpg` … | 去重後保留的 JPG 圖片（品質 100） |
| `frames_report.csv` | 每一幀的完整記錄（含 hash、狀態、時間戳） |
| `duplicates.csv` | 被判定為重複而跳過的幀清單 |
| `summary.txt` | 統計摘要（總幀數、保留數、去重率） |

## pHash 閾值參考

| 閾值 | 嚴格度 | 適用情境 |
|---|---|---|
| 0 | 最嚴格（完全相同） | 只去除一模一樣的幀 |
| 3-5 | 嚴格（推薦） | 去除幾乎相同的連續幀 |
| 8-10 | 中等 | 去除視覺上相似的畫面 |
| 12+ | 寬鬆 | 只保留場景變化大的關鍵幀 |

## 授權 License

本專案採用 **PolyForm Noncommercial License 1.0.0**（非商業授權）。

- ✅ 個人、學術、研究、嗜好、非營利組織等**非商業用途**可自由使用、修改、散布。
- ❌ **商業用途未獲授權**。任何商業使用（含營利、為企業帶來直接或間接利益）必須先取得書面商業授權。

> 商業授權請聯絡著作權人：**airesearch3412-hub** — https://github.com/airesearch3412-hub

詳見 [LICENSE](LICENSE)。
