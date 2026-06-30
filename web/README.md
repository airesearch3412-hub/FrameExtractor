# FrameExtractor 網站版

把 PyQt6 桌面版的 5 大功能移植成「功能一模一樣、可 Docker 部署」的網站。
後端 FastAPI + Uvicorn（ASGI），前端純 HTML/CSS/原生 JS（無建置步驟），即時進度走 SSE。
重用根目錄的純邏輯核心 `deduper.py`（零 Qt 依賴）。

## 五大功能

| Tab | 功能 | 說明 |
|---|---|---|
| 🎬 提取 + 去重 | extract-dedup | 從影片逐幀提取並即時智慧去重，輸出保留幀 + `frames_report.csv` / `duplicates.csv` / `summary.txt` |
| 📸 只提取 | extract-only | 純逐幀提取（可設 frame_step），輸出 jpg + 4 欄 `frames_report.csv` |
| 🗂 僅去重資料夾 | folder-dedup | 對既有圖片資料夾去重（move / delete / report），輸出 `_dedup_report.csv` / `_dedup_summary.txt` |
| 📚 批次處理 | batch | 多影片批次（dedup 或 extract 模式），每影片各自 `{stem}_frames/`，雙進度條 |
| ✂ 批次裁剪 | batch-crop | Canvas 互動選框，統一套用到所有圖片，輸出 `_crop_report.csv` / `_crop_summary.txt` |

全程支援中文路徑與檔名（核心使用 `imread_unicode` / `imwrite_unicode` / `imencode`，不使用 `cv2.imread/imwrite`）。

---

## 部署方式 A：Docker（建議）

需求：Docker + docker compose。在 `web/` 目錄下執行：

```bash
docker compose up --build
```

啟動後開啟 <http://localhost:8000>（對外埠 `8000`）。

### 啟用 CLIP / ultra（語意去重）

預設映像**不裝** torch/open-clip，以保持映像精簡、CPU 即可運行。
`ultra` 預設等級才需要 CLIP。要啟用，把 `docker-compose.yml` 中的 build arg 改為 `"1"` 後重建：

```yaml
    build:
      args:
        INSTALL_CLIP: "1"
```

```bash
docker compose up --build
```

或直接以 docker build：

```bash
# 注意：build context 必須是 repo 根目錄（上一層），才能 COPY 根目錄的 deduper.py
docker build -f web/Dockerfile --build-arg INSTALL_CLIP=1 -t frameextractor-web ..
```

CLIP 權重快取在具名 volume `clip-cache`（掛在容器 `/root/.cache`），避免每次重新下載。

### GPU（CUDA）

預設映像為 CPU。若主機具備 NVIDIA GPU 並安裝 NVIDIA Container Toolkit，需自行：
- 以支援 CUDA 的 base image / 安裝 GPU 版 torch（修改 `requirements-clip.txt` 或 Dockerfile），
- 在 compose 服務加上 `deploy.resources.reservations.devices`（GPU 保留）或 `--gpus all`。

UI 進階面板的「偵測 GPU」按鈕會呼叫 `/api/clip-device-info` 回報實際可用裝置；
CLIP 裝置可選 `自動偵測 / GPU(CUDA) / CPU`。

### `/data` 掛載用途

容器內 `FE_DATA_DIR=/data`，compose 將主機 `./data` 掛到 `/data`。其用途：
- **job 工作目錄**：每個任務的上傳輸入與輸出結果存於 `/data/jobs/{job_id}/`。
- **伺服器資料夾瀏覽**：超大影片 / 既有圖片資料夾，不必經瀏覽器上傳，
  直接放進主機 `./data`，於 UI 用「伺服器資料夾」選取（路徑限定在 `/data` 內，防目錄穿越）。

---

## 部署方式 B：本機無 Docker（開發 / 驗證）

需求：Python 3.11。**從 repo 根目錄**執行（讓 `import deduper` 與 `web.app:app` 都能解析）：

```bash
pip install -r web/requirements.txt
uvicorn web.app:app --host 0.0.0.0 --port 8000
```

開啟 <http://localhost:8000>。

- 本機未設 `FE_DATA_DIR` 時，資料目錄預設為 `web/data`（已於 `.gitignore` 忽略）。
- 啟用 CLIP（選用）：`pip install -r web/requirements-clip.txt`。
- Windows 主機可正常運行；容器為 Linux。兩者皆全程支援中文路徑/檔名。

---

## 依賴

`web/requirements.txt`（不含 CLIP）：FastAPI、Uvicorn、python-multipart、
`opencv-python-headless`（無 GUI 依賴，省 libGL）、Pillow、imagehash、numpy。

`web/requirements-clip.txt`（選用）：`torch` / `open-clip-torch`。

---

## 授權與來源

- 授權：**PolyForm Noncommercial License 1.0.0**（非商業使用）。
- 作者：**airesearch3412-hub**
- 原始碼：<https://github.com/airesearch3412-hub/FrameExtractor>
- 核心套件：OpenCV · imagehash · open-clip · FastAPI
