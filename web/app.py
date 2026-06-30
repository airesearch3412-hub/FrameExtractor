# -*- coding: utf-8 -*-
"""
FrameExtractor 網站版 — FastAPI 應用層（HTTP API + SSE + 靜態檔）。

對齊 web_spec.md §4。把 web/core.py 的處理核心與 web/jobs.py 的任務管理
接成 HTTP / Server-Sent Events，並服務 web/static 的前端。

執行（本機，無 docker）：
    pip install -r web/requirements.txt
    uvicorn web.app:app --host 0.0.0.0 --port 8000
（從 repo 根目錄執行，使 `import deduper` 可解析。）
"""

import io
import json
import mimetypes
import sys
import zipfile
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile

# 確保 repo 根目錄在 sys.path（jobs/core 內 from deduper import ...）。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from web import core  # noqa: E402
from web.jobs import (  # noqa: E402
    DATA_DIR, build_cfg, build_crop, ensure_dirs, manager, to_int,
)

try:
    from deduper import clip_device_info  # noqa: E402
except Exception:  # pragma: no cover - 極端情況下的退路
    def clip_device_info():
        return {"available": False, "cuda": False, "gpu_name": None,
                "torch_version": None, "reason": "無法載入 torch / deduper"}


STATIC_DIR = Path(__file__).resolve().parent / "static"
IMAGE_EXTS = core.IMAGE_EXTS

app = FastAPI(title="FrameExtractor Web", version="2.0")
ensure_dirs()


# ============================================================
# 工具：表單解析 / 路徑安全 / 上傳落地
# ============================================================
async def parse_form(request: Request):
    """把 multipart 表單拆成 (fields: dict[str,str], files: dict[str,list[UploadFile]])。"""
    form = await request.form()
    fields: dict = {}
    files: dict = {}
    for key, value in form.multi_items():
        if isinstance(value, UploadFile):
            files.setdefault(key, []).append(value)
        else:
            fields[key] = value
    return fields, files


def _safe_data_path(rel: str) -> Path:
    """把使用者提供的相對路徑解析到 DATA_DIR 內，越界則 400（防目錄穿越）。"""
    rel = (rel or "").strip().replace("\\", "/").lstrip("/")
    p = (DATA_DIR / rel).resolve()
    if p != DATA_DIR and not p.is_relative_to(DATA_DIR):
        raise HTTPException(
            status_code=400,
            detail="路徑超出允許範圍，僅能存取掛載資料夾內的內容")
    return p


def _safe_under(base: Path, name: str) -> Path:
    """把輸出檔名解析到 base 內，越界則 400。"""
    base = base.resolve()
    p = (base / name).resolve()
    if p != base and not p.is_relative_to(base):
        raise HTTPException(status_code=400, detail="非法檔名")
    return p


async def save_uploads(uploads: List[UploadFile], dest_dir: Path) -> List[Path]:
    """把上傳檔寫入 dest_dir，保留原檔名（含中文），同名自動加序號避免覆蓋。"""
    saved: List[Path] = []
    for up in uploads:
        name = Path(up.filename or "upload").name or "upload"
        dest = dest_dir / name
        if dest.exists():
            stem, suf, i = dest.stem, dest.suffix, 1
            while dest.exists():
                dest = dest_dir / f"{stem}_{i}{suf}"
                i += 1
        dest.write_bytes(await up.read())
        saved.append(dest)
    return saved


async def _resolve_single_video(fields: dict, files: dict, job) -> Path:
    """提取類：取單一影片（上傳檔優先，否則伺服器路徑）。"""
    ups = files.get("video") or []
    if ups:
        saved = await save_uploads(ups, job.input_dir)
        return saved[0]
    sp = fields.get("server_path")
    if sp:
        p = _safe_data_path(sp)
        if not p.is_file():
            raise HTTPException(status_code=400, detail="找不到指定的影片檔")
        return p
    raise HTTPException(status_code=400, detail="請選擇影片檔或伺服器路徑")


def _collect_server_paths(fields: dict, want_file: bool = True) -> List[Path]:
    """解析 server_paths（JSON 陣列字串）為安全的絕對路徑清單。"""
    raw = fields.get("server_paths")
    if not raw:
        return []
    try:
        rels = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="server_paths 格式錯誤")
    out: List[Path] = []
    for rel in rels:
        p = _safe_data_path(str(rel))
        if (p.is_file() if want_file else p.exists()):
            out.append(p)
    return out


def _launch(job, runner):
    """啟動 job 並回傳標準回應。"""
    manager.start(job, runner)
    return {"job_id": job.id}


# ============================================================
# 建立各模式 job
# ============================================================
@app.post("/api/jobs/extract-dedup")
async def api_extract_dedup(request: Request):
    fields, files = await parse_form(request)
    job = manager.new_job("extract-dedup")
    try:
        video = await _resolve_single_video(fields, files, job)
        cfg = build_cfg(fields)
        jpg_q = to_int(fields.get("jpg_quality"), 100)
    except HTTPException:
        manager.discard(job)
        raise

    def runner(cb, cancel, j):
        return core.extract_dedup(str(video), str(j.output_dir), cfg,
                                  jpg_quality=jpg_q, cb=cb, cancel=cancel)

    return _launch(job, runner)


@app.post("/api/jobs/extract-only")
async def api_extract_only(request: Request):
    fields, files = await parse_form(request)
    job = manager.new_job("extract-only")
    try:
        video = await _resolve_single_video(fields, files, job)
        jpg_q = to_int(fields.get("jpg_quality"), 100)
        frame_step = to_int(fields.get("frame_step"), 1)
    except HTTPException:
        manager.discard(job)
        raise

    def runner(cb, cancel, j):
        return core.extract_only(str(video), str(j.output_dir), jpg_quality=jpg_q,
                                 frame_step=frame_step, cb=cb, cancel=cancel)

    return _launch(job, runner)


@app.post("/api/jobs/folder-dedup")
async def api_folder_dedup(request: Request):
    fields, files = await parse_form(request)
    job = manager.new_job("folder-dedup")
    try:
        ups = files.get("images") or []
        if ups:
            await save_uploads(ups, job.input_dir)
            target = job.input_dir
        else:
            sp = fields.get("server_path")
            if not sp:
                raise HTTPException(status_code=400, detail="請選擇資料夾或上傳圖片")
            target = _safe_data_path(sp)
            if not target.is_dir():
                raise HTTPException(status_code=400, detail="找不到指定的資料夾")
        cfg = build_cfg(fields)
        action = (fields.get("action") or "move").strip()
    except HTTPException:
        manager.discard(job)
        raise

    def runner(cb, cancel, j):
        return core.folder_dedup(str(target), cfg, action=action, cb=cb, cancel=cancel)

    return _launch(job, runner)


@app.post("/api/jobs/batch")
async def api_batch(request: Request):
    fields, files = await parse_form(request)
    job = manager.new_job("batch")
    try:
        paths: List[Path] = []
        ups = files.get("videos") or []
        if ups:
            paths += await save_uploads(ups, job.input_dir)
        paths += _collect_server_paths(fields, want_file=True)
        if not paths:
            raise HTTPException(status_code=400, detail="請加入至少一個影片")
        cfg = build_cfg(fields)
        mode = (fields.get("mode") or "dedup").strip()
        jpg_q = to_int(fields.get("jpg_quality"), 100)
    except HTTPException:
        manager.discard(job)
        raise

    def runner(cb, cancel, j):
        return core.batch_videos([str(p) for p in paths], str(j.output_dir), cfg,
                                 jpg_quality=jpg_q, mode=mode, cb=cb, cancel=cancel)

    return _launch(job, runner)


@app.post("/api/jobs/batch-crop")
async def api_batch_crop(request: Request):
    fields, files = await parse_form(request)
    job = manager.new_job("batch-crop")
    try:
        paths: List[Path] = []
        ups = files.get("images") or []
        if ups:
            paths += await save_uploads(ups, job.input_dir)
        paths += _collect_server_paths(fields, want_file=True)
        if not paths:
            raise HTTPException(status_code=400, detail="請加入至少一張圖片")
        crop = build_crop(fields)
    except HTTPException:
        manager.discard(job)
        raise

    def runner(cb, cancel, j):
        return core.batch_crop([str(p) for p in paths], str(j.output_dir),
                               crop["crop_box"], out_format=crop["out_format"],
                               jpg_quality=crop["jpg_quality"],
                               resize_to=crop["resize_to"], cb=cb, cancel=cancel)

    return _launch(job, runner)


# ============================================================
# SSE / 取消 / 結果
# ============================================================
@app.get("/api/jobs/{job_id}/events")
def api_events(job_id: str):
    if manager.get(job_id) is None:
        raise HTTPException(status_code=404, detail="找不到工作")
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(manager.events(job_id),
                             media_type="text/event-stream", headers=headers)


@app.post("/api/jobs/{job_id}/cancel")
def api_cancel(job_id: str):
    if not manager.cancel(job_id):
        raise HTTPException(status_code=404, detail="找不到工作")
    return {"ok": True}


@app.get("/api/jobs/{job_id}/result")
def api_result(job_id: str):
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="找不到工作")
    return {"status": job.status, "result": job.result, "error": job.error}


@app.get("/api/jobs/{job_id}/files")
def api_files(job_id: str):
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="找不到工作")
    out = Path(job.output_dir)
    items = []
    if out.is_dir():
        for p in sorted(out.rglob("*")):
            if p.is_file():
                items.append({
                    "name": p.relative_to(out).as_posix(),
                    "size": p.stat().st_size,
                    "is_image": p.suffix.lower() in IMAGE_EXTS,
                })
    return JSONResponse(items)


@app.get("/api/jobs/{job_id}/file/{name:path}")
def api_file(job_id: str, name: str):
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="找不到工作")
    p = _safe_under(Path(job.output_dir), name)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="找不到檔案")
    return FileResponse(str(p), filename=p.name)


@app.get("/api/jobs/{job_id}/download")
def api_download(job_id: str):
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="找不到工作")
    out = Path(job.output_dir)
    if not out.is_dir():
        raise HTTPException(status_code=404, detail="尚無輸出可下載")
    # 寫到 job 工作目錄的暫存 zip（避免大量結果在記憶體中組裝）。
    zip_path = Path(job.work_dir) / "_download.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(out.rglob("*")):
            if p.is_file() and p != zip_path:
                zf.write(p, p.relative_to(out).as_posix())
    return FileResponse(str(zip_path), media_type="application/zip",
                        filename=f"frameextractor_{job_id[:8]}.zip")


# ============================================================
# 其他：CLIP 裝置 / 伺服器瀏覽 / 伺服器圖片
# ============================================================
@app.get("/api/clip-device-info")
def api_clip_device_info():
    return clip_device_info()


@app.get("/api/browse")
def api_browse(path: str = ""):
    base = _safe_data_path(path)
    if not base.is_dir():
        raise HTTPException(status_code=404, detail="找不到資料夾")
    dirs, files = [], []
    for p in sorted(base.iterdir(), key=lambda x: x.name.lower()):
        try:
            if p.is_dir():
                dirs.append({"name": p.name})
            elif p.is_file():
                files.append({
                    "name": p.name,
                    "size": p.stat().st_size,
                    "is_image": p.suffix.lower() in IMAGE_EXTS,
                })
        except OSError:
            continue
    cwd = "" if base == DATA_DIR else base.relative_to(DATA_DIR).as_posix()
    return {"cwd": cwd, "dirs": dirs, "files": files}


@app.get("/api/server-image")
def api_server_image(path: str):
    p = _safe_data_path(path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="找不到圖片")
    mime, _ = mimetypes.guess_type(p.name)
    return FileResponse(str(p), media_type=mime or "application/octet-stream")


# ============================================================
# 靜態前端（最後掛載，使 /api/* 路由優先）
# ============================================================
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
