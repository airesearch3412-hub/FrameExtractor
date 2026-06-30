# -*- coding: utf-8 -*-
"""
FrameExtractor 網站版 — 任務層（Job / JobManager / 請求→設定轉換）。

設計（對齊 web_spec.md §3）：
- 每個 job 一條 threading.Thread 跑對應的 core 函式。
- core 的 callbacks 被包成事件 dict，put 進 thread-safe queue.Queue。
- events(id) 為一個同步產生器，輪詢 queue，yield SSE 格式字串，
  收到終止事件（done / error）即停止。
- cancel(id) 設定 job 的 threading.Event；core 迴圈會偵測並提早收尾。
- 工作目錄：DATA_DIR/jobs/{id}/{input,output}
  （DATA_DIR 預設 web/data，可由環境變數 FE_DATA_DIR 覆蓋；Docker 設 /data）。
"""

import base64
import json
import os
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# 確保可解析 repo 根目錄的 deduper（core 內 from deduper import ...）。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from web.core import Callbacks, DedupConfig  # noqa: E402


# ============================================================
# 工作目錄
# ============================================================
DATA_DIR = Path(
    os.environ.get("FE_DATA_DIR") or (Path(__file__).resolve().parent / "data")
).resolve()


def ensure_dirs() -> None:
    """建立 DATA_DIR 與 jobs 子目錄（啟動時呼叫）。"""
    (DATA_DIR / "jobs").mkdir(parents=True, exist_ok=True)


# ============================================================
# 表單值解析工具（multipart 欄位皆為字串）
# ============================================================
def to_bool(v, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on", "y")


def to_int(v, default: int = 0) -> int:
    if v is None or v == "":
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def to_float(v, default: float = 0.0) -> float:
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ============================================================
# 請求 → 設定 轉換
# ============================================================
def build_cfg(payload: dict) -> DedupConfig:
    """把前端送來的去重設定欄位轉成 DedupConfig。

    以 preset 為基底（DedupConfig.from_preset），再用 payload 中實際出現的欄位覆蓋。
    未出現的欄位沿用 preset 值（與桌面版 / web_spec §5 一致）。
    """
    preset = (payload.get("preset") or "standard").strip()
    cfg = DedupConfig.from_preset(preset)

    if "use_dhash" in payload:
        cfg.use_dhash = to_bool(payload.get("use_dhash"), cfg.use_dhash)
    if "use_phash" in payload:
        cfg.use_phash = to_bool(payload.get("use_phash"), cfg.use_phash)
    if "use_histogram" in payload:
        cfg.use_histogram = to_bool(payload.get("use_histogram"), cfg.use_histogram)
    if "use_ssim" in payload:
        cfg.use_ssim = to_bool(payload.get("use_ssim"), cfg.use_ssim)
    if "use_clip" in payload:
        cfg.use_clip = to_bool(payload.get("use_clip"), cfg.use_clip)

    if "dhash_threshold" in payload:
        cfg.dhash_threshold = to_int(payload.get("dhash_threshold"), cfg.dhash_threshold)
    if "phash_threshold" in payload:
        cfg.phash_threshold = to_int(payload.get("phash_threshold"), cfg.phash_threshold)
    if "hist_threshold" in payload:
        cfg.hist_threshold = to_float(payload.get("hist_threshold"), cfg.hist_threshold)
    if "ssim_threshold" in payload:
        cfg.ssim_threshold = to_float(payload.get("ssim_threshold"), cfg.ssim_threshold)
    if "clip_threshold" in payload:
        cfg.clip_threshold = to_float(payload.get("clip_threshold"), cfg.clip_threshold)

    if "hash_size" in payload:
        cfg.hash_size = to_int(payload.get("hash_size"), cfg.hash_size)
    if "window_size" in payload:
        cfg.window_size = to_int(payload.get("window_size"), cfg.window_size)
    if "clip_device" in payload and payload.get("clip_device"):
        cfg.clip_device = str(payload.get("clip_device")).strip()

    return cfg


def build_crop(payload: dict) -> dict:
    """把批次裁剪欄位轉成 core.batch_crop 需要的參數。"""
    left = to_int(payload.get("left"), 0)
    top = to_int(payload.get("top"), 0)
    right = to_int(payload.get("right"), 0)
    bottom = to_int(payload.get("bottom"), 0)
    out_format = (payload.get("out_format") or "jpg").strip().lower()
    jpg_quality = to_int(payload.get("jpg_quality"), 95)

    # 前端僅在勾選「統一輸出尺寸」時送出 resize_w/resize_h（不另送 resize 旗標），
    # 故以「兩尺寸皆 > 0」判定啟用；若有顯式 resize 旗標（false）則尊重之。
    resize_to = None
    rw = to_int(payload.get("resize_w"), 0)
    rh = to_int(payload.get("resize_h"), 0)
    flag = payload.get("resize")
    enabled = to_bool(flag, True) if flag is not None else (rw > 0 and rh > 0)
    if enabled and rw > 0 and rh > 0:
        resize_to = (rw, rh)

    return {
        "crop_box": (left, top, right, bottom),
        "out_format": out_format,
        "jpg_quality": jpg_quality,
        "resize_to": resize_to,
    }


# ============================================================
# Job / JobManager
# ============================================================
@dataclass
class Job:
    id: str
    mode: str
    work_dir: Path
    input_dir: Path
    output_dir: Path
    cancel: threading.Event = field(default_factory=threading.Event)
    queue: "queue.Queue" = field(default_factory=queue.Queue)
    thread: Optional[threading.Thread] = None
    status: str = "pending"          # pending | running | done | error | cancelled
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


def _data_url(jpg_bytes: bytes) -> str:
    if not jpg_bytes:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(jpg_bytes).decode("ascii")


# runner 簽章：runner(cb: Callbacks, cancel: threading.Event, job: Job) -> dict
Runner = Callable[[Callbacks, threading.Event, Job], dict]


class JobManager:
    """以 dict 註冊所有 job，提供建立 / 查詢 / SSE 串流 / 取消。"""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    # ---- 建立 ----
    def new_job(self, mode: str) -> Job:
        """配置工作目錄並註冊 job（尚未啟動執行緒）。

        分兩段（new_job → start）讓 app 層能先把上傳檔寫入 input/ 再啟動。
        """
        jid = uuid.uuid4().hex
        work = DATA_DIR / "jobs" / jid
        inp = work / "input"
        out = work / "output"
        inp.mkdir(parents=True, exist_ok=True)
        out.mkdir(parents=True, exist_ok=True)
        job = Job(id=jid, mode=mode, work_dir=work, input_dir=inp, output_dir=out)
        with self._lock:
            self._jobs[jid] = job
        return job

    def start(self, job: Job, runner: Runner) -> Job:
        """啟動 job 的工作執行緒。"""
        job.status = "running"
        t = threading.Thread(target=self._run, args=(job, runner), daemon=True)
        job.thread = t
        t.start()
        return job

    def create(self, mode: str, runner: Runner) -> Job:
        """便捷：配置 + 立即啟動（符合 web_spec §3 的 create 介面）。"""
        return self.start(self.new_job(mode), runner)

    def discard(self, job: Job) -> None:
        """放棄一個尚未啟動的 job（驗證失敗時清理註冊表）。"""
        with self._lock:
            self._jobs.pop(job.id, None)

    # ---- 查詢 / 取消 ----
    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        job.cancel.set()
        return True

    # ---- 工作執行緒 ----
    def _run(self, job: Job, runner: Runner) -> None:
        q = job.queue
        cb = Callbacks(
            log=lambda msg: q.put({"type": "log", "msg": msg}),
            progress=lambda c, t: q.put({"type": "progress", "current": c, "total": t}),
            sub_progress=lambda c, t: q.put(
                {"type": "sub_progress", "current": c, "total": t}),
            preview=lambda b, i: q.put(
                {"type": "preview", "image": _data_url(b), "frame": i}),
            stats=lambda d: q.put({"type": "stats", **d}),
        )
        try:
            res = runner(cb, job.cancel, job) or {}
            job.result = res
            out_dir = res.get("output_dir")
            if out_dir:
                job.output_dir = Path(out_dir)
            if job.cancel.is_set():
                job.status = "cancelled"
                q.put({"type": "done", "result": res, "cancelled": True})
            else:
                job.status = "done"
                q.put({"type": "done", "result": res})
        except Exception as e:  # noqa: BLE001 — 任何錯誤都轉成 error 事件回報
            job.status = "error"
            job.error = str(e)
            q.put({"type": "error", "msg": str(e)})

    # ---- SSE 產生器 ----
    def events(self, job_id: str):
        """產生 SSE 字串，直到收到終止事件（done / error）。

        以小睡輪詢 thread-safe queue；佇列空閒時送出註解心跳避免反代 buffering。
        """
        job = self._jobs.get(job_id)
        if job is None:
            return
        q = job.queue
        while True:
            try:
                ev = q.get(timeout=0.5)
            except queue.Empty:
                yield ": keep-alive\n\n"
                if job.thread is not None and not job.thread.is_alive() and q.empty():
                    break
                continue
            yield "data: " + json.dumps(ev, ensure_ascii=False) + "\n\n"
            if ev.get("type") in ("done", "error"):
                break


# 全域單例（app.py 直接 import 使用）
manager = JobManager()
