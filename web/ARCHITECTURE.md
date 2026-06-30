# FrameExtractor 網站版（Docker 部署）— 實作規格與合約（唯一真實來源）

> Tina 技術評估收斂結果。所有實作 agent 必須嚴格遵守此合約，確保前後端與 Docker 對齊。
> 目標：把 PyQt6 桌面版（5 大功能）做成「功能一模一樣、可 Docker 部署」的網站。
> 重用 `deduper.py`（純邏輯，零 Qt）。把 `workers.py` 的 5 種 QThread 迴圈改寫成「無 Qt + callback」版。
> 開發機沒有 docker，但有 Python 3.11 → 必須能 `uvicorn web.app:app` 本機跑起來驗證。

---

## 0. 架構決策（Key Decisions）

| 決策 | 選擇 | 理由 |
|---|---|---|
| 後端框架 | **FastAPI + Uvicorn (ASGI)** | 原生 async/SSE、自帶 OpenAPI、單檔可跑、Docker 化簡單 |
| 前端 | **純 HTML + CSS + 原生 JS（無 build step）** | Docker 零建置、沿用既有設計語彙、最易維護 |
| 即時通訊 | **SSE（text/event-stream）** 推送 log/progress/preview/stats/done/error | 單向推送足夠、比 WebSocket 簡單、易在 Docker/反代下運作 |
| 輸入模型 | **混合**：① 瀏覽器上傳檔案 ② 伺服器掛載資料夾 `/data` 瀏覽選取 | 上傳適合單檔；資料夾去重/批次/超大影片走掛載 volume，達成完整功能對等 |
| 結果輸出 | 每個 job 一個工作目錄；提供結果檔清單、縮圖、單檔下載、**整包 ZIP 下載** | 取代桌面版「打開輸出資料夾」 |
| 預覽 | `cv2.imencode('.jpg')` → bytes → base64 data URL，經 SSE 推送 | 取代 `cv2_to_qimage` / QImage |
| CLIP | **預設映像不裝 torch**；提供 `--build-arg INSTALL_CLIP=1` 與 compose `clip` profile，權重快取於具名 volume | 預設映像小（CPU），ultra 等級才需要重依賴 |
| 中文路徑/檔名 | 全程 `imread_unicode`/`imwrite_unicode`/`imencode`，禁用 `cv2.imread/imwrite` | 與桌面版等效 |
| 並行 | 每個 job 一條 `threading.Thread`；`JobManager` 以 dict 註冊；事件經 thread-safe queue 給 SSE | 簡單可靠 |

### 給使用者的開放問題（Alex 回報時提出，預設已可運作）
1. 輸入以「瀏覽器上傳」為主、另支援掛載 `/data` 資料夾 —— 是否符合預期？（超大影片建議走掛載）
2. 預設映像不預裝 CLIP/torch（ultra 等級需用 `INSTALL_CLIP=1` 重建或 clip profile）—— 可接受？
3. 技術棧 FastAPI + 原生 JS —— 可接受？

---

## 1. 目錄結構（全部新增於 `web/`，重用根目錄 `deduper.py`）

```
FrameExtractor/
├── deduper.py                 # 既有，重用（勿改）
├── web/
│   ├── core.py                # 無 Qt 處理核心（5 函式 + 工具），重用 deduper
│   ├── jobs.py                # JobManager / Job / 事件佇列 / 請求→設定轉換
│   ├── app.py                 # FastAPI app：所有 API + 靜態檔 + SSE
│   ├── requirements.txt       # 網站版依賴（不含 CLIP）
│   ├── requirements-clip.txt  # 選用：torch + open-clip-torch
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .dockerignore
│   ├── README.md              # 部署與使用說明（docker + 本機）
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js
└── .gitignore                 # 追加 web/data/ 等忽略
```

執行（本機驗證，無 docker）：`pip install -r web/requirements.txt` → `uvicorn web.app:app --host 0.0.0.0 --port 8000`（從 repo 根目錄跑，使 `import deduper` 可解析；`app.py` 需把 repo 根加入 sys.path）。

---

## 2. `web/core.py` 合約（無 Qt 處理核心）

重用：`from deduper import DedupConfig, Deduper, compute_features, load_clip_model, clip_device_info, imread_unicode, imwrite_unicode`。
複製（從 workers.py，移除 Qt）：`format_timestamp`、`format_duration`、`open_video_capture`。
新增 helper：`encode_preview_jpeg(frame_bgr) -> bytes`（`cv2.imencode('.jpg', frame, [IMWRITE_JPEG_QUALITY, 80])`，回 bytes）。

### Callbacks 物件（用一個簡單的 dataclass 或直接收 kwargs 函式）
所有處理函式接受一個 `cb`（callbacks）與 `cancel: threading.Event`。`cb` 提供（皆可為 None）：
- `cb.log(msg: str)`
- `cb.progress(current: int, total: int)`
- `cb.sub_progress(current: int, total: int)`  # 僅 batch_videos 用
- `cb.preview(jpg_bytes: bytes, frame_index: int)`
- `cb.stats(d: dict)`
- 完成/錯誤由函式 return / raise 表達，由 jobs.py 轉成 done/error 事件（核心函式不直接發 done/error）。
cancel：迴圈內檢查 `cancel.is_set()`，命中即 `cb.log("⏹ 使用者中止")` 並 break（已處理結果照常寫出與 return）。

### 函式簽章與語義（務必逐項對齊 workers.py，輸出檔案格式見 §6）

```python
def extract_dedup(video_path, output_dir, cfg: DedupConfig, jpg_quality=100,
                  preview_every=30, cb=None, cancel=None) -> dict
```
- 對齊 `ExtractDedupWorker`。產出 `frames_report.csv`(6欄)、`duplicates.csv`(5欄)、`summary.txt`。
- 保留幀 `frame_{idx:08d}.jpg`，`imwrite_unicode(..., [IMWRITE_JPEG_QUALITY, int(jpg_quality)])`。
- `cb.preview` 條件：`saved % preview_every == 1`。`cb.progress(idx, total)`（total>0）。`cb.stats({"saved":saved,"duplicates":dup,"processed":idx})` 每 `idx % 10 == 0`，結束再發一次最終值。
- `use_clip` → 先 `cb.log` 載入訊息 → `load_clip_model(device=cfg.clip_device)`，失敗則 raise（jobs 轉 error）。
- return dict keys：`total`(=idx), `saved`, `duplicates`, `write_failed`, `dedup_rate`, `elapsed`, `output_dir`。

```python
def extract_only(video_path, output_dir, jpg_quality=100, frame_step=1,
                 preview_every=30, cb=None, cancel=None) -> dict
```
- 對齊 `ExtractOnlyWorker`。`frame_step=max(1,int)`。僅 `idx % frame_step == 0` 處理。
- 產出 `frames_report.csv`(**4欄**：frame_index,timestamp,filename,status)。**不產 summary/duplicates**。
- `cb.stats({"saved":saved,"processed":idx})`。return keys：`total`(=idx),`saved`,`write_failed`,`elapsed`,`output_dir`。

```python
def folder_dedup(input_dir, cfg: DedupConfig, action="move",
                 dup_subdir="_duplicates", preview_every=10, cb=None, cancel=None) -> dict
```
- 對齊 `FolderDedupWorker`。掃描副檔名 `{.jpg,.jpeg,.png,.bmp,.webp,.tiff,.tif}`，`sorted`。
- action ∈ {move,delete,report}。move→`shutil.move` 到 `input_dir/dup_subdir`；delete→`unlink`；report→`marked`。
- 產出 `_dedup_report.csv`(6欄)、`_dedup_summary.txt`。
- `cb.stats({"kept":kept,"duplicates":dup,"processed":i+1})`。`cb.preview` 條件 `kept % preview_every == 1`。
- return keys：`total`,`saved`(=kept),`duplicates`,`write_failed`,`elapsed`,`dedup_rate`,`output_dir`(=input_dir)。

```python
def batch_videos(video_paths, output_root, cfg, jpg_quality=100,
                 mode="dedup", cb=None, cancel=None) -> dict
```
- 對齊 `BatchWorker`。每影片 `output_root/{stem}_frames`；mode=="dedup"→呼叫 `extract_dedup` 否則 `extract_only`，**傳入一個轉接 cb**：子任務的 progress→`cb.sub_progress`，log/preview 透傳；不要巢狀執行緒。
- 每影片完成後 `cb.progress(i+1, n)`、`cb.stats({"videos":videos,"saved_total":...,"dup_total":...,"frames_total":...})`。
- 聚合：videos、saved_total(+=子 saved)、dup_total(+=子 duplicates)、frames_total(+=子 total)。
- return keys：`videos`,`saved_total`,`dup_total`,`frames_total`,`elapsed`。

```python
def batch_crop(image_paths, output_dir, crop_box, out_format="jpg",
               jpg_quality=95, resize_to=None, preview_every=10, cb=None, cancel=None) -> dict
```
- 對齊 `BatchCropWorker`。`crop_box=(left,top,right,bottom)` 原圖像素，`int(round())`。
- 早退：`right<=left or bottom<=top` → raise「裁剪框無效」；`total==0` → raise。
- `ext = .png if out_format=="png" else .jpg`；`out_w,out_h = resize_to or (crop_w,crop_h)`。
- 逐張：讀失敗→`read_failed`；輸出與原檔同路徑→`skipped_overwrite_source` 跳過；clamp 後無效→`crop_out_of_bounds`；`cropped=img[t:b,l:r]`，resize_to→`cv2.resize(...,INTER_AREA)`；`imwrite_unicode` 成功→`ok`，否則 `write_failed`。
- 產出 `_crop_report.csv`(6欄)、`_crop_summary.txt`。輸出檔名 `{原檔stem}{ext}`。
- `cb.stats({"done":done,"failed_skipped":failed+skipped,"processed":i+1})`。`cb.preview` 條件 `done % preview_every == 1`。
- return keys：`total`,`done`,`failed`,`skipped`,`out_size`(=`f"{out_w}×{out_h}"`),`elapsed`,`output_dir`。

工具函式（複製自 workers.py，去 Qt）：
- `format_timestamp(s)`→`"{h:02d}:{m:02d}:{s:06.3f}"`
- `format_duration(s)`→ `<60`:`"{:.1f} 秒"`；`<3600`:`"{m} 分 {s:02d} 秒"`；else `"{h} 時 {m:02d} 分 {s:02d} 秒"`
- `open_video_capture(path)`→ 先試 `VideoCapture`，Windows fallback 短路徑，最後再試一次（Linux 容器只走第一支）。

---

## 3. `web/jobs.py` 合約

- `Job`：`id`(uuid hex), `mode`(str), `status`('running'|'done'|'error'|'cancelled'), `thread`, `cancel: threading.Event`, `queue`(thread-safe，如 `queue.Queue`), `work_dir`(Path), `output_dir`(Path), `result`(dict|None), `error`(str|None), `created_at`。
- `JobManager`：`create(mode, runner_callable) -> Job`（建工作目錄、起執行緒跑 runner，runner 內建 cb 把事件 put 進 queue）、`get(id)`、`events(id)`(generator，yield SSE 格式字串，直到收到 done/error/cancelled 終止事件)、`cancel(id)`。
- cb 實作：把 core 的 callback 轉成事件 dict put 進 queue：
  - log→`{"type":"log","msg":...}`
  - progress→`{"type":"progress","current":...,"total":...}`
  - sub_progress→`{"type":"sub_progress","current":...,"total":...}`
  - preview→`{"type":"preview","image":"data:image/jpeg;base64,"+b64,"frame":idx}`
  - stats→`{"type":"stats", ...d}`（直接攤平 d）
  - 完成→runner 取得 return dict 後 put `{"type":"done","result":{...}}`，設 status/result/output_dir。
  - 例外→put `{"type":"error","msg":str(e)}`，設 status='error'。
  - 取消→core break 後仍 return；status 設 'cancelled'，put `{"type":"done","result":{...},"cancelled":true}`。
- 工作目錄：`DATA_DIR/jobs/{job_id}/`（DATA_DIR 預設 `web/data`，可由環境變數 `FE_DATA_DIR` 覆蓋；Docker 設 `/data`）。輸入上傳檔存 `.../{job_id}/input/`，輸出存 `.../{job_id}/output/`（或對應模式語義）。
- 請求→設定轉換：`build_cfg(payload) -> DedupConfig`（見 §5 欄位）；`build_crop(...)`。

---

## 4. `web/app.py` HTTP API 合約（FastAPI）

啟動時把 repo 根加入 `sys.path`（`import deduper` 與 `from web import core` 皆可）。掛載 `web/static` 為靜態檔，`GET /` 回 `index.html`。`app.add_middleware(CORS, *)` 寬鬆即可（同源也行）。

| Method | Path | 請求 | 回應 | 用途 |
|---|---|---|---|---|
| POST | `/api/jobs/extract-dedup` | multipart：`video`(file，可選) 或 `server_path`(str)；`jpg_quality`(int)；config 欄位(§5) | `{"job_id":...}` | 建提取+去重 job |
| POST | `/api/jobs/extract-only` | `video`/`server_path`；`frame_step`,`jpg_quality` | `{"job_id":...}` | 建只提取 job |
| POST | `/api/jobs/folder-dedup` | `server_path`(資料夾) 或 `images`(多檔上傳)；`action`；config | `{"job_id":...}` | 建資料夾去重 job |
| POST | `/api/jobs/batch` | `videos`(多檔) 或 `server_paths`(JSON 陣列)；`mode`,`jpg_quality`；config | `{"job_id":...}` | 建批次多影片 job |
| POST | `/api/jobs/batch-crop` | `images`(多檔) 或 `server_paths`；`left,top,right,bottom`；`out_format`,`jpg_quality`；`resize_w`,`resize_h`(可選) | `{"job_id":...}` | 建批次裁剪 job |
| GET | `/api/jobs/{id}/events` | — | `text/event-stream`（SSE，§3 事件） | 即時進度串流 |
| POST | `/api/jobs/{id}/cancel` | — | `{"ok":true}` | 中止 |
| GET | `/api/jobs/{id}/result` | — | result dict | 取最終結果 |
| GET | `/api/jobs/{id}/files` | — | `[{"name","size","is_image"}]` | 列輸出檔 |
| GET | `/api/jobs/{id}/file/{name}` | — | 檔案內容（圖片/CSV/txt） | 預覽/下載單檔（防目錄穿越） |
| GET | `/api/jobs/{id}/download` | — | `application/zip` | 整包輸出 ZIP |
| GET | `/api/clip-device-info` | — | `clip_device_info()` dict | 「偵測 GPU」按鈕 |
| GET | `/api/browse?path=` | path(相對 DATA_DIR) | `{"dirs":[...],"files":[...],"cwd":...}` | 伺服器資料夾選擇器 |
| GET | `/api/server-image?path=` | path | 圖片 bytes | 裁剪用：取伺服器端圖片原始尺寸/預覽 |

- SSE 實作：`StreamingResponse(gen(), media_type="text/event-stream")`，每事件 `data: {json}\n\n`。為避免 buffering 加 header `X-Accel-Buffering: no`、`Cache-Control: no-cache`。用執行緒佇列 → 以小睡輪詢 queue（FastAPI sync generator 即可，或 async + run_in_executor）。
- 上傳檔以 `await file.read()` 寫入 `input/`，保留原檔名（含中文）；`server_path` 模式直接用 `DATA_DIR/path`（驗證在 DATA_DIR 內，防穿越）。
- 安全：所有 path 參數 `os.path.realpath` 後須位於允許根目錄內，否則 400。

---

## 5. 設定欄位（前端送出 → DedupConfig）。範圍/預設必須與桌面版一致

去重三分頁（extract-dedup / folder-dedup / batch）共用「演算法面板」，欄位：
- `preset`：`fast|standard|precise|ultra`，預設 `standard`。前端切換 preset 時用 `DedupConfig.from_preset` 的等效值回填下列欄位。
- 啟用開關：`use_dhash,use_phash,use_histogram,use_ssim,use_clip`（bool）。
- 閾值：`dhash_threshold`(int 0–64,預設5)、`phash_threshold`(int 0–64,5)、`hist_threshold`(float 0–1 step0.01,0.95)、`ssim_threshold`(float 0–1,0.92)、`clip_threshold`(float 0–1,0.95)。
- `hash_size`(int 4–32,8)、`window_size`(int 0–99999,0)、`clip_device`(`auto|cuda|cpu`,auto)。
- 後端 `build_cfg` 直接塞進 `DedupConfig(...)`。

preset 等效值表（前端 JS 與後端皆需，與 deduper.from_preset 一致）：
| preset | dHash | pHash | hist | ssim | clip | dhash_th | phash_th | hist_th | ssim_th | clip_th |
|---|---|---|---|---|---|---|---|---|---|---|
| fast | ✓ | ✗ | ✗ | ✗ | ✗ | 5 | 5 | 0.95 | 0.92 | 0.95 |
| standard | ✓ | ✓ | ✗ | ✗ | ✗ | 5 | 5 | 0.95 | 0.92 | 0.95 |
| precise | ✓ | ✓ | ✓ | ✓ | ✗ | 6 | 6 | 0.95 | 0.92 | 0.95 |
| ultra | ✓ | ✓ | ✓ | ✓ | ✓ | 8 | 8 | 0.93 | 0.90 | 0.93 |

其他分頁欄位：
- extract-only：`frame_step`(int 1–9999,1)、`jpg_quality`(int 1–100,100)。
- extract-dedup / batch：`jpg_quality`(int 1–100,100)。batch 另有 `mode`(`dedup|extract`)。
- folder-dedup：`action`（`move|delete|report`，預設 move；delete 前端需二次確認）。
- batch-crop：`left,top,right,bottom`(int 原圖像素)、`out_format`(`jpg|png`)、`jpg_quality`(int 1–100,**95**)、`resize`(bool)、`resize_w,resize_h`(int 1–99999)。

---

## 6. 輸出檔案格式（逐欄，務必精確；CSV `utf-8-sig`，txt `utf-8`）

**extract-dedup** `frames_report.csv` 表頭：`frame_index,timestamp,filename,status,duplicate_of,scores`
- saved:`idx,ts,filename,saved,,`；duplicate:`idx,ts,,duplicate,prev.index,str(scores)`；write_failed:`idx,ts,,write_failed,,`
`duplicates.csv` 表頭：`frame_index,timestamp,duplicate_of_frame,duplicate_of_filename,scores`
`summary.txt`：
```
影片提取統計摘要
==================
影片檔案    : {name}
處理時間    : {YYYY-mm-dd HH:MM:SS}
執行時間    : {format_duration}
解析度      : {w} x {h}
原始 FPS    : {fps:.2f}
總幀數      : {idx}
保留幀數    : {saved}
重複幀數    : {dup}
寫入失敗    : {failed}
去重率      : {rate:.2f}%
啟用演算法  : {algos}
JPG 品質    : {jpg_quality}
輸出資料夾  : {output_dir}
```
`algos`：依序 dHash,pHash,Histogram,SSIM,CLIP 已啟用者用 `, ` 連接；全無→`(無，僅提取)`。

**extract-only** `frames_report.csv` 表頭(4欄)：`frame_index,timestamp,filename,status`（無 summary/duplicates）。

**folder-dedup** `_dedup_report.csv` 表頭：`index,filename,status,duplicate_of,scores,action`
`_dedup_summary.txt`：
```
資料夾去重摘要
==================
處理時間  : {ts}
執行時間  : {dur}
來源資料夾: {input_dir}
圖片總數  : {total}
保留      : {kept}
重複      : {dup}
讀取失敗  : {failed}
去重率    : {rate:.2f}%
動作      : {action}
報表      : _dedup_report.csv
```

**batch-crop** `_crop_report.csv` 表頭：`index,filename,src_size,out_size,status,note`
`_crop_summary.txt`：
```
批次裁剪摘要
==================
處理時間  : {ts}
執行時間  : {dur}
圖片總數  : {total}
成功裁剪  : {done}
失敗      : {failed}
略過      : {skipped}
裁剪框    : (左{left}, 上{top}, 右{right}, 下{bottom})
裁剪尺寸  : {crop_w}×{crop_h}
輸出尺寸  : {out_w}×{out_h}
輸出格式  : {ext}
輸出資料夾: {output_dir}
報表      : _crop_report.csv
```

**batch**：不產彙總檔；每影片在 `{stem}_frames/` 下產對應 worker 全套檔案。

---

## 7. 前端 `static/`（沿用桌面版設計語彙，UI 一致性）

單頁，5 個 tab（順序與 emoji）：`🎬 提取 + 去重`、`📸 只提取`、`🗂 僅去重資料夾`、`📚 批次處理`、`✂ 批次裁剪`。
Header：左 `FrameExtractor`(title 22px/700) + 副標 `v2.0 · 影片提取 · 智慧去重 · 批次處理 · 批次裁剪`；右上狀態 pill（圓角10px padding 6px 12px font-weight600）。
每個 tab 底部含 **StatsAndPreview**：4 張 KPI 卡 + 即時預覽 + 進度條 + 日誌（等寬字）。

### 設計 Tokens（CSS 變數，深/淺主題；預設深色；`Ctrl/⌘+T` 或按鈕切換；存 localStorage）
字型：`"Segoe UI","Microsoft JhengHei","PingFang TC",sans-serif`；等寬：`"Cascadia Code","Consolas","Menlo",monospace` 12px。
字級：title 22/700、subtitle 12、sectionTitle 13/600、fieldLabel 12、kpiLabel 11(letter-spacing 1px)、kpiValue 22/700、button padding 7px14px/500(primary600)。
圓角：卡片12、kpiCard/preview/log 10、輸入/按鈕/tab 8、progress 6、pill 10。
間距：tab 內容 margin14 gap12；卡片 padding14 gap10。

深色 DARK：
- 視窗 `#0f1419`；卡片 `#161b22`；輸入/日誌/預覽/progress 底 `#0d1117`；邊框 `#30363d`(hover `#6e7681`)。
- 主文字 `#e6edf3`；次文字 `#8b949e`/placeholder `#6e7681`；section/checkbox `#c9d1d9`；純白標題 `#ffffff`。
- accent 藍 `#1f6feb`(亮 `#58a6ff`)；一般按鈕 `#21262d`(hover `#30363d`,pressed `#1c2128`)。
- primary 綠 bg `#238636` border `#2ea043`(hover `#2ea043`,disabled bg `#1b3a23`)；danger 紅 border/text `#f85149`(hover bg `#2d1417`)。
- KPI：good 綠 `#3fb950`、warn 橘 `#f0883e`、accent 藍 `#58a6ff`、中性白。progress 漸層 `#1f6feb→#58a6ff`。
- tab 選中 bg `#0f1419` text `#58a6ff` border-bottom 2px `#1f6feb`。

淺色 LIGHT：
- 視窗 `#f6f8fa`；卡片/輸入/tab `#ffffff`；邊框 `#d0d7de`(hover `#afb8c1`)。
- 主文字 `#1f2328`；次文字 `#57606a`；accent `#0969da`(progress chunk `#1f6feb`)。
- primary 綠 bg `#2da44e` border `#2c974b`；danger `#cf222e`；KPI good `#1a7f37`/warn `#bc4c00`；一般按鈕 bg `#f6f8fa` hover `#eaeef2`；tab 選中 text/border `#0969da`。

### 各 tab KPI 標籤（4 格，顏色語意：中性/綠/橘/藍）
- 提取+去重：`總幀數,保留,重複,去重率`
- 只提取：`總幀數,已輸出,—,—`
- 僅去重資料夾：`圖片總數,保留,重複,去重率`
- 批次處理：`已處理影片,保留總計,重複總計,—`（雙進度條：整體 + 子任務）
- 批次裁剪：`圖片總數,已裁剪,失敗／略過,—`
數字千分位 `n.toLocaleString()`；去重率 `xx.x%`。

### 進階設定面板（去重三分頁共用，預設摺疊「▼ 進階設定」/展開「▲ 隱藏進階」）
- 上排：`預設等級` 下拉（快速/標準(預設)/精準/最精準）。
- 5 列演算法：啟用 checkbox + 閾值輸入（dHash/pHash=整數 0–64；hist/ssim/clip=0–1 step0.01）。
- `Hash 大小`(4–32,8)、`時間視窗`(0–99999,0)、`CLIP 裝置`下拉(自動偵測/GPU(CUDA)/CPU) + `偵測 GPU` 按鈕（呼叫 `/api/clip-device-info`，顯示 `✓ GPU：name (torch ver)` / `✗ 無 GPU…` / `⚠ reason`）。
- 切 preset 自動回填 use_* 與 5 個閾值（hash_size/window/device 不變）。

### 批次裁剪互動（CropSelector → HTML5 Canvas）
- 上傳/選第一張圖 → 用 `Image()`/`FileReader` 取得原圖 `iw×ih`，畫到 canvas（等比置中縮放 `s=min(W/iw,H/ih)`，offset 置中）。
- 三模式：空白拖曳=畫新框；框內拖曳=平移；命中 8 控制點(tl,tr,bl,br,t,b,l,r，容差約10px)=縮放。座標一律換算回**原圖像素**。
- 4 個數字框 `左/上/右/下`（range 隨圖片 0–w/0–h）與 canvas 雙向同步（防迴圈）。`重設為整張` 按鈕。即時 `裁剪尺寸：W × H`，無效時顯示 `裁剪尺寸：無效（右須大於左、下須大於上）`。
- 繪製：整圖蒙 `rgba(0,0,0,0.47)`，裁剪區清晰；藍框 `#1f6feb` 寬2；白底藍邊控制點；左上尺寸標籤。
- 提示：`裁剪框會套用到所有圖片`。輸出設定：輸出格式(JPG/PNG，PNG 停用品質)、JPG 品質(預設95)、統一輸出尺寸 checkbox（勾選啟用 w×h，否則跟隨裁剪框）。

### 互動行為
- 開始→POST 建 job→拿 job_id→開 `EventSource(/api/jobs/{id}/events)`→更新 progress/log/preview/stats。
- done→顯示完成摘要（含執行時間 `format_duration`、各 KPI、輸出位置）+ 顯示「下載 ZIP / 檢視結果檔」。
- 中止鈕→POST cancel。
- 上傳大檔顯示上傳中狀態。delete 動作前端 `confirm()` 二次確認。
- 關於：作者 **airesearch3412-hub**、原始碼 https://github.com/airesearch3412-hub/FrameExtractor 、授權 **PolyForm Noncommercial 1.0.0**、核心套件 OpenCV·imagehash·open-clip·FastAPI。

---

## 8. `web/requirements.txt`（不含 CLIP）
```
fastapi>=0.110
uvicorn[standard]>=0.29
python-multipart>=0.0.9
opencv-python-headless>=4.8.0
Pillow>=10.0.0
imagehash>=4.3.1
numpy>=1.24.0
```
`web/requirements-clip.txt`：`torch>=2.0.0` / `open-clip-torch>=2.20.0`。

> 注意：根目錄 `deduper.py` import `cv2`；容器用 `opencv-python-headless`（無 GUI 依賴）即可，省 libGL。但若用 headless 仍建議裝 `libglib2.0-0`；用非 headless 才需 `libgl1`。本專案用 **headless**。

---

## 9. Docker

`web/Dockerfile`（build context = repo 根目錄，才能 COPY deduper.py）：
```dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 FE_DATA_DIR=/data PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY web/requirements.txt /app/web/requirements.txt
RUN pip install -r /app/web/requirements.txt
ARG INSTALL_CLIP=0
COPY web/requirements-clip.txt /app/web/requirements-clip.txt
RUN if [ "$INSTALL_CLIP" = "1" ]; then pip install -r /app/web/requirements-clip.txt; fi
COPY deduper.py /app/deduper.py
COPY web /app/web
EXPOSE 8000
VOLUME ["/data"]
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
```
`web/docker-compose.yml`：
```yaml
services:
  frameextractor-web:
    build:
      context: ..
      dockerfile: web/Dockerfile
      args:
        INSTALL_CLIP: "0"   # 設 "1" 啟用 CLIP/ultra
    ports: ["8000:8000"]
    volumes:
      - ./data:/data           # 上傳/結果/可被「伺服器資料夾」瀏覽
      - clip-cache:/root/.cache # CLIP 權重快取
    environment:
      FE_DATA_DIR: /data
    restart: unless-stopped
volumes:
  clip-cache:
```
`web/.dockerignore`：忽略 `**/__pycache__`、`*.pyc`、`web/data`、`.git`、桌面版無關大檔。
`app.py` 須能在 `web.app:app` 匯入路徑下運作（package 形式）：建立 `web/__init__.py`（空）。本機從 repo 根 `uvicorn web.app:app`。

`.gitignore` 追加：`web/data/`、`web/__pycache__/`。

---

## 10. 驗收清單（實作後我會在本機 uvicorn 逐一驗證）
1. `uvicorn web.app:app` 可啟動，`GET /` 顯示 5-tab UI（深色預設，主題可切）。
2. 用小測試影片跑 extract-dedup / extract-only：產出 jpg + 正確欄位的 CSV + summary.txt，SSE 即時更新 KPI/preview/log/progress，完成可下載 ZIP。
3. folder-dedup（move/report）：產出 `_dedup_report.csv`/`_dedup_summary.txt`，move 真的搬到 `_duplicates`。
4. batch：多影片各自 `{stem}_frames/`，雙進度條。
5. batch-crop：canvas 互動選框 + 4 數字框雙向同步，輸出尺寸/格式正確，`_crop_report.csv`/`_crop_summary.txt`。
6. 中文檔名影片/圖片全程正常（上傳與輸出）。
7. preset 切換正確回填閾值；`偵測 GPU` 按鈕回報（無 torch 時顯示未安裝）。
8. Dockerfile/compose 經人工檢視正確（此機無 docker 無法實跑，需明確標註）。
```
