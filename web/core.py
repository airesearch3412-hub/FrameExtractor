# -*- coding: utf-8 -*-
"""
FrameExtractor 網站版 — 無 Qt 處理核心。

把桌面版 workers.py 的 5 種 QThread 迴圈改寫成「純邏輯 + callbacks」版，
邏輯與輸出檔格式與桌面版完全一致，可被 FastAPI 的 jobs.py 直接呼叫。

- 重用根目錄 deduper.py 的純邏輯（零 Qt）。
- 全程支援中文路徑/檔名（imread_unicode / imwrite_unicode / imencode）。
- 進度回報只透過 cb（None-safe）；完成由 return、錯誤由 raise 表達，
  由 jobs.py 轉成 done / error 事件（核心函式不直接發 done/error）。
"""

import csv
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import cv2

from deduper import (
    DedupConfig,
    Deduper,
    compute_features,
    load_clip_model,
    clip_device_info,
    imread_unicode,
    imwrite_unicode,
)

# 對外可見（jobs.py / app.py 可能引用）
__all__ = [
    "Callbacks",
    "IMAGE_EXTS",
    "DedupConfig",
    "clip_device_info",
    "format_timestamp",
    "format_duration",
    "open_video_capture",
    "encode_preview_jpeg",
    "extract_dedup",
    "extract_only",
    "folder_dedup",
    "batch_videos",
    "batch_crop",
]

# 支援的圖片副檔名（與桌面版一致）
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}


# ============================================================
# Callbacks 機制（皆為 None-safe）
# ============================================================
@dataclass
class Callbacks:
    """輕量回呼容器。所有欄位皆為 Optional callable，未提供者自動忽略。

    - log(msg: str)
    - progress(current: int, total: int)
    - sub_progress(current: int, total: int)   # 僅 batch_videos 用
    - preview(jpg_bytes: bytes, frame_index: int)
    - stats(d: dict)
    """

    log: Optional[Callable[[str], None]] = None
    progress: Optional[Callable[[int, int], None]] = None
    sub_progress: Optional[Callable[[int, int], None]] = None
    preview: Optional[Callable[[bytes, int], None]] = None
    stats: Optional[Callable[[dict], None]] = None

    def emit_log(self, msg: str) -> None:
        if self.log is not None:
            self.log(msg)

    def emit_progress(self, current: int, total: int) -> None:
        if self.progress is not None:
            self.progress(current, total)

    def emit_sub_progress(self, current: int, total: int) -> None:
        if self.sub_progress is not None:
            self.sub_progress(current, total)

    def emit_preview(self, jpg_bytes: bytes, frame_index: int) -> None:
        if self.preview is not None:
            self.preview(jpg_bytes, frame_index)

    def emit_stats(self, d: dict) -> None:
        if self.stats is not None:
            self.stats(d)


def _is_cancelled(cancel) -> bool:
    return cancel is not None and cancel.is_set()


# ============================================================
# 工具函式（複製自 workers.py，移除 Qt 依賴）
# ============================================================
def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def format_duration(seconds: float) -> str:
    """把秒數格式化成易讀的執行時間，如 0.8 秒 / 1 分 23 秒 / 1 時 02 分 05 秒。"""
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} 時 {m:02d} 分 {s:02d} 秒"
    return f"{m} 分 {s:02d} 秒"


def open_video_capture(video_path: str):
    """開啟影片。先試一般路徑；Windows 失敗時改用短路徑 fallback；
    Linux 容器只會走第一支（短路徑分支不觸發）。"""
    cap = cv2.VideoCapture(video_path)
    if cap.isOpened():
        return cap
    cap.release()
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes
            GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
            GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
            GetShortPathNameW.restype = wintypes.DWORD
            buf = ctypes.create_unicode_buffer(260)
            n = GetShortPathNameW(video_path, buf, 260)
            if n:
                cap2 = cv2.VideoCapture(buf.value)
                if cap2.isOpened():
                    return cap2
                cap2.release()
        except Exception:
            pass
    return cv2.VideoCapture(video_path)


def encode_preview_jpeg(frame_bgr) -> bytes:
    """把 BGR 影像編成 JPEG bytes（品質 80），供 SSE 預覽推送。失敗回 b""。"""
    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return b""
    return buf.tobytes()


def _algos_label(cfg: DedupConfig) -> str:
    """依序列出已啟用演算法；全無則回 '(無，僅提取)'。"""
    return ", ".join(
        n for n, on in [
            ("dHash", cfg.use_dhash),
            ("pHash", cfg.use_phash),
            ("Histogram", cfg.use_histogram),
            ("SSIM", cfg.use_ssim),
            ("CLIP", cfg.use_clip),
        ] if on
    ) or "(無，僅提取)"


def _load_clip_if_needed(cfg: DedupConfig, cb: Callbacks):
    """use_clip 時先 log 載入訊息再載入模型；失敗則 raise（由 jobs 轉 error）。"""
    if not cfg.use_clip:
        return None
    cb.emit_log(f"▶ 載入 CLIP 模型中…（裝置={cfg.clip_device}，"
                "首次使用會下載權重，約 300MB）")
    clip_model = load_clip_model(device=cfg.clip_device)
    cb.emit_log(f"  CLIP 就緒（實際裝置={clip_model.device}）\n")
    return clip_model


# ============================================================
# 1) 提取 + 去重（對齊 ExtractDedupWorker）
# ============================================================
def extract_dedup(video_path, output_dir, cfg: DedupConfig, jpg_quality=100,
                  preview_every=30, cb=None, cancel=None) -> dict:
    cb = cb or Callbacks()
    video_path = Path(video_path)
    output_dir = Path(output_dir)

    t0 = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = open_video_capture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"無法開啟影片：{video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    algos = _algos_label(cfg)
    cb.emit_log(f"▶ 影片：{video_path.name}")
    cb.emit_log(f"  {w}x{h} | FPS {fps:.2f} | 總幀數 {total}")
    cb.emit_log(f"▶ 啟用演算法：{algos}")
    cb.emit_log(f"▶ 輸出：{output_dir}\n")

    csv_path = output_dir / "frames_report.csv"
    dup_path = output_dir / "duplicates.csv"
    summary_path = output_dir / "summary.txt"

    csv_file = open(csv_path, "w", newline="", encoding="utf-8-sig")
    csv_w = csv.writer(csv_file)
    csv_w.writerow(["frame_index", "timestamp", "filename",
                    "status", "duplicate_of", "scores"])

    dup_file = open(dup_path, "w", newline="", encoding="utf-8-sig")
    dup_w = csv.writer(dup_file)
    dup_w.writerow(["frame_index", "timestamp",
                    "duplicate_of_frame", "duplicate_of_filename", "scores"])

    try:
        clip_model = _load_clip_if_needed(cfg, cb)
    except Exception:
        cap.release()
        csv_file.close()
        dup_file.close()
        raise

    dedup = Deduper(cfg)
    saved = 0
    dup = 0
    failed = 0
    idx = 0

    try:
        while True:
            if _is_cancelled(cancel):
                cb.emit_log("⏹ 使用者中止")
                break
            ret, frame = cap.read()
            if not ret:
                break

            ts = format_timestamp(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
            feat = compute_features(frame, cfg, index=idx, clip_model=clip_model)

            is_dup, prev, scores = dedup.check(feat)
            if is_dup:
                dup += 1
                csv_w.writerow([idx, ts, "", "duplicate", prev.index, str(scores)])
                dup_w.writerow([idx, ts, prev.index, prev.filename, str(scores)])
            else:
                filename = f"frame_{idx:08d}.jpg"
                ok = imwrite_unicode(
                    str(output_dir / filename), frame,
                    [cv2.IMWRITE_JPEG_QUALITY, int(jpg_quality)])
                if ok:
                    feat.filename = filename
                    feat.timestamp = ts
                    dedup.add(feat)
                    saved += 1
                    csv_w.writerow([idx, ts, filename, "saved", "", ""])
                    if saved % preview_every == 1:
                        cb.emit_preview(encode_preview_jpeg(frame), idx)
                else:
                    failed += 1
                    csv_w.writerow([idx, ts, "", "write_failed", "", ""])

            idx += 1
            if total > 0:
                cb.emit_progress(idx, total)
            if idx % 10 == 0:
                cb.emit_stats({"saved": saved, "duplicates": dup, "processed": idx})
    finally:
        cap.release()
        csv_file.close()
        dup_file.close()

    elapsed = time.perf_counter() - t0
    rate = (dup / idx * 100) if idx else 0
    summary = (f"影片提取統計摘要\n==================\n"
               f"影片檔案    : {video_path.name}\n"
               f"處理時間    : {datetime.now():%Y-%m-%d %H:%M:%S}\n"
               f"執行時間    : {format_duration(elapsed)}\n"
               f"解析度      : {w} x {h}\n原始 FPS    : {fps:.2f}\n"
               f"總幀數      : {idx}\n保留幀數    : {saved}\n"
               f"重複幀數    : {dup}\n寫入失敗    : {failed}\n"
               f"去重率      : {rate:.2f}%\n啟用演算法  : {algos}\n"
               f"JPG 品質    : {jpg_quality}\n"
               f"輸出資料夾  : {output_dir}\n")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)
    cb.emit_log("\n✔ 完成\n" + summary)
    cb.emit_stats({"saved": saved, "duplicates": dup, "processed": idx})

    return {
        "total": idx, "saved": saved, "duplicates": dup,
        "write_failed": failed, "dedup_rate": rate,
        "elapsed": elapsed, "output_dir": str(output_dir),
    }


# ============================================================
# 2) 只提取，不去重（對齊 ExtractOnlyWorker）
# ============================================================
def extract_only(video_path, output_dir, jpg_quality=100, frame_step=1,
                 preview_every=30, cb=None, cancel=None) -> dict:
    cb = cb or Callbacks()
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    frame_step = max(1, int(frame_step))

    t0 = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = open_video_capture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"無法開啟影片：{video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cb.emit_log(f"▶ {video_path.name}  {w}x{h}  FPS {fps:.2f}")
    cb.emit_log(f"▶ 抽幀間隔：每 {frame_step} 幀取 1 張")
    cb.emit_log(f"▶ 輸出：{output_dir}\n")

    csv_path = output_dir / "frames_report.csv"
    csv_file = open(csv_path, "w", newline="", encoding="utf-8-sig")
    csv_w = csv.writer(csv_file)
    csv_w.writerow(["frame_index", "timestamp", "filename", "status"])

    saved = 0
    failed = 0
    idx = 0
    try:
        while True:
            if _is_cancelled(cancel):
                cb.emit_log("⏹ 使用者中止")
                break
            ret, frame = cap.read()
            if not ret:
                break
            if idx % frame_step == 0:
                ts = format_timestamp(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
                filename = f"frame_{idx:08d}.jpg"
                ok = imwrite_unicode(
                    str(output_dir / filename), frame,
                    [cv2.IMWRITE_JPEG_QUALITY, int(jpg_quality)])
                if ok:
                    saved += 1
                    csv_w.writerow([idx, ts, filename, "saved"])
                    if saved % preview_every == 1:
                        cb.emit_preview(encode_preview_jpeg(frame), idx)
                else:
                    failed += 1
                    csv_w.writerow([idx, ts, "", "write_failed"])
            idx += 1
            if total > 0:
                cb.emit_progress(idx, total)
            if idx % 10 == 0:
                cb.emit_stats({"saved": saved, "processed": idx})
    finally:
        cap.release()
        csv_file.close()

    elapsed = time.perf_counter() - t0
    cb.emit_log(f"\n✔ 完成：共 {idx} 幀，輸出 {saved} 張，失敗 {failed}"
                f"，執行時間 {format_duration(elapsed)}")
    cb.emit_stats({"saved": saved, "processed": idx})

    return {
        "total": idx, "saved": saved, "write_failed": failed,
        "elapsed": elapsed, "output_dir": str(output_dir),
    }


# ============================================================
# 3) 僅去重資料夾內現有圖片（對齊 FolderDedupWorker）
# ============================================================
def folder_dedup(input_dir, cfg: DedupConfig, action="move",
                 dup_subdir="_duplicates", preview_every=10,
                 cb=None, cancel=None) -> dict:
    cb = cb or Callbacks()
    input_dir = Path(input_dir)

    t0 = time.perf_counter()
    if not input_dir.exists():
        raise RuntimeError(f"資料夾不存在：{input_dir}")

    files = sorted([p for p in input_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in IMAGE_EXTS])
    total = len(files)
    if total == 0:
        raise RuntimeError("資料夾內找不到圖片檔案")

    cb.emit_log(f"▶ 來源資料夾：{input_dir}")
    cb.emit_log(f"▶ 找到 {total} 張圖片")
    cb.emit_log(f"▶ 動作：{action}\n")

    dup_dir = input_dir / dup_subdir
    if action == "move":
        dup_dir.mkdir(exist_ok=True)

    report_path = input_dir / "_dedup_report.csv"
    rep_file = open(report_path, "w", newline="", encoding="utf-8-sig")
    rep_w = csv.writer(rep_file)
    rep_w.writerow(["index", "filename", "status", "duplicate_of", "scores", "action"])

    try:
        clip_model = _load_clip_if_needed(cfg, cb)
    except Exception:
        rep_file.close()
        raise

    dedup = Deduper(cfg)
    kept = 0
    dup = 0
    failed = 0

    for i, path in enumerate(files):
        if _is_cancelled(cancel):
            cb.emit_log("⏹ 使用者中止")
            break
        img = imread_unicode(str(path))
        if img is None:
            failed += 1
            rep_w.writerow([i, path.name, "read_failed", "", "", ""])
            cb.emit_log(f"⚠ 無法讀取：{path.name}")
            continue

        feat = compute_features(img, cfg, index=i, clip_model=clip_model)
        feat.filename = path.name

        is_dup, prev, scores = dedup.check(feat)
        if is_dup:
            dup += 1
            if action == "move":
                try:
                    shutil.move(str(path), str(dup_dir / path.name))
                    act = f"moved → {dup_subdir}/"
                except Exception as e:
                    act = f"move_failed: {e}"
            elif action == "delete":
                try:
                    path.unlink()
                    act = "deleted"
                except Exception as e:
                    act = f"delete_failed: {e}"
            else:
                act = "marked"
            rep_w.writerow([i, path.name, "duplicate",
                            prev.filename, str(scores), act])
        else:
            dedup.add(feat)
            kept += 1
            rep_w.writerow([i, path.name, "kept", "", "", ""])
            if kept % preview_every == 1:
                cb.emit_preview(encode_preview_jpeg(img), i)

        cb.emit_progress(i + 1, total)
        if (i + 1) % 10 == 0:
            cb.emit_stats({"kept": kept, "duplicates": dup, "processed": i + 1})

    rep_file.close()

    elapsed = time.perf_counter() - t0
    summary_path = input_dir / "_dedup_summary.txt"
    rate = (dup / total * 100) if total else 0
    summary = (f"資料夾去重摘要\n==================\n"
               f"處理時間  : {datetime.now():%Y-%m-%d %H:%M:%S}\n"
               f"執行時間  : {format_duration(elapsed)}\n"
               f"來源資料夾: {input_dir}\n"
               f"圖片總數  : {total}\n保留      : {kept}\n"
               f"重複      : {dup}\n讀取失敗  : {failed}\n"
               f"去重率    : {rate:.2f}%\n動作      : {action}\n"
               f"報表      : {report_path.name}\n")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)
    cb.emit_log("\n✔ 完成\n" + summary)
    cb.emit_stats({"kept": kept, "duplicates": dup, "processed": total})

    return {
        "total": total, "saved": kept, "duplicates": dup,
        "write_failed": failed, "elapsed": elapsed,
        "dedup_rate": rate, "output_dir": str(input_dir),
    }


# ============================================================
# 4) 批次處理多影片（對齊 BatchWorker）
# ============================================================
def batch_videos(video_paths, output_root, cfg: DedupConfig, jpg_quality=100,
                 mode="dedup", cb=None, cancel=None) -> dict:
    cb = cb or Callbacks()
    video_paths = [Path(p) for p in video_paths]
    output_root = Path(output_root)

    t0 = time.perf_counter()
    output_root.mkdir(parents=True, exist_ok=True)
    n = len(video_paths)
    cb.emit_log(f"▶ 批次任務：{n} 個影片  模式：{mode}\n")

    # 子任務的 cb：progress → 父層 sub_progress；log / preview 透傳；不轉發子 stats。
    child_cb = Callbacks(
        log=cb.log,
        progress=cb.sub_progress,
        sub_progress=None,
        preview=cb.preview,
        stats=None,
    )

    videos = 0
    saved_total = 0
    dup_total = 0
    frames_total = 0

    for i, vp in enumerate(video_paths):
        if _is_cancelled(cancel):
            cb.emit_log("⏹ 使用者中止")
            break
        cb.emit_log(f"\n══ [{i+1}/{n}] {vp.name} ══")
        sub_out = output_root / f"{vp.stem}_frames"

        try:
            if mode == "dedup":
                s = extract_dedup(str(vp), str(sub_out), cfg,
                                  jpg_quality=jpg_quality,
                                  cb=child_cb, cancel=cancel)
            else:
                s = extract_only(str(vp), str(sub_out),
                                 jpg_quality=jpg_quality,
                                 cb=child_cb, cancel=cancel)
        except Exception as e:
            cb.emit_log(f"✖ 失敗：{e}")
            s = None

        if s is not None:
            videos += 1
            saved_total += s.get("saved", 0)
            dup_total += s.get("duplicates", 0)
            frames_total += s.get("total", 0)

        cb.emit_progress(i + 1, n)
        cb.emit_stats({
            "videos": videos, "saved_total": saved_total,
            "dup_total": dup_total, "frames_total": frames_total,
        })

    elapsed = time.perf_counter() - t0
    cb.emit_log(
        f"\n══════ 批次完成 ══════\n"
        f"處理影片數：{videos}\n"
        f"總幀數    ：{frames_total:,}\n"
        f"保留      ：{saved_total:,}\n"
        f"重複      ：{dup_total:,}\n"
        f"執行時間  ：{format_duration(elapsed)}\n"
        f"輸出根目錄：{output_root}\n"
    )

    return {
        "videos": videos, "saved_total": saved_total,
        "dup_total": dup_total, "frames_total": frames_total,
        "elapsed": elapsed,
    }


# ============================================================
# 5) 批次裁剪（對齊 BatchCropWorker）
# ============================================================
def _path_key(p) -> str:
    """把路徑正規化成可比較的鍵（解析符號連結 + 小寫），用來偵測同檔。"""
    try:
        return str(Path(p).resolve()).lower()
    except Exception:
        return str(p).lower()


def _unique_out(base_out: Path, src_path: Path, ext: str,
                input_keys: set, produced: set):
    """若輸出檔會撞到「其他來源檔」或「本次已輸出檔」，改名為 stem__2/__3…，
    避免互相覆蓋造成資料遺失。回傳 (最終路徑, 註記)。"""
    key = _path_key(base_out)
    clash = (key in produced) or \
            (key in input_keys and key != _path_key(src_path))
    if not clash:
        return base_out, ""
    k = 2
    while True:
        cand = base_out.with_name(f"{src_path.stem}__{k}{ext}")
        ckey = _path_key(cand)
        if ckey not in produced and ckey not in input_keys and not cand.exists():
            return cand, f"renamed→{cand.name}"
        k += 1


def batch_crop(image_paths, output_dir, crop_box, out_format="jpg",
               jpg_quality=95, resize_to=None, preview_every=10,
               cb=None, cancel=None) -> dict:
    cb = cb or Callbacks()
    image_paths = [Path(p) for p in image_paths]
    output_dir = Path(output_dir)
    crop_box = tuple(int(round(x)) for x in crop_box)
    out_format = str(out_format).lower().lstrip(".")
    jpg_quality = int(jpg_quality)
    resize_to = (tuple(int(v) for v in resize_to) if resize_to else None)
    preview_every = max(1, int(preview_every))

    t0 = time.perf_counter()
    left, top, right, bottom = crop_box
    if right <= left or bottom <= top:
        raise RuntimeError(f"裁剪框無效（右<=左 或 下<=上）：{crop_box}")
    total = len(image_paths)
    if total == 0:
        raise RuntimeError("沒有要處理的圖片")

    output_dir.mkdir(parents=True, exist_ok=True)
    ext = ".png" if out_format == "png" else ".jpg"
    crop_w, crop_h = right - left, bottom - top
    out_w, out_h = (resize_to if resize_to else (crop_w, crop_h))

    cb.emit_log(f"▶ 批次裁剪：{total} 張圖片")
    cb.emit_log(f"▶ 裁剪框 (左,上,右,下)：{crop_box}  → {crop_w}×{crop_h}")
    if resize_to:
        cb.emit_log(f"▶ 統一縮放輸出：{out_w}×{out_h}")
    cb.emit_log(f"▶ 輸出格式：{ext}"
                + (f"（品質 {jpg_quality}）" if ext == ".jpg" else "（PNG 無損）"))
    cb.emit_log(f"▶ 輸出資料夾：{output_dir}\n")

    report_path = output_dir / "_crop_report.csv"
    rep_file = open(report_path, "w", newline="", encoding="utf-8-sig")
    rep_w = csv.writer(rep_file)
    rep_w.writerow(["index", "filename", "src_size", "out_size", "status", "note"])

    done = 0
    failed = 0
    skipped = 0
    processed = 0
    base_size = None
    params = ([cv2.IMWRITE_JPEG_QUALITY, jpg_quality] if ext == ".jpg"
              else [cv2.IMWRITE_PNG_COMPRESSION, 3])
    input_keys = {_path_key(p) for p in image_paths}
    produced = set()
    try:
        for i, path in enumerate(image_paths):
            if _is_cancelled(cancel):
                cb.emit_log("⏹ 使用者中止")
                break
            processed = i + 1
            img = imread_unicode(str(path))
            if img is None:
                failed += 1
                rep_w.writerow([i, path.name, "", "", "read_failed", ""])
                cb.emit_log(f"⚠ 無法讀取：{path.name}")
                cb.emit_progress(i + 1, total)
                continue

            h, w = img.shape[:2]
            src_size = f"{w}x{h}"
            if base_size is None:
                base_size = (w, h)
            elif (w, h) != base_size:
                cb.emit_log(
                    f"⚠ 尺寸不一致：{path.name} 為 {w}x{h}，與首張 "
                    f"{base_size[0]}x{base_size[1]} 不同（仍套用同一裁剪框）")

            base_out = output_dir / (path.stem + ext)
            # 防呆1：輸出檔與「正在處理的這張原檔」同路徑 → 略過保護原圖
            if _path_key(base_out) == _path_key(path):
                skipped += 1
                rep_w.writerow([i, path.name, src_size, "",
                                "skipped_overwrite_source", ""])
                cb.emit_log(f"⚠ 略過（會覆蓋原檔）：{path.name}，請改用其他輸出資料夾")
                cb.emit_progress(i + 1, total)
                continue
            # 防呆2：輸出檔會撞到別的來源檔或本次已輸出檔 → 改名避免覆蓋
            out_path, rename_note = _unique_out(
                base_out, path, ext, input_keys, produced)

            # clamp 裁剪框到影像範圍
            l = max(0, min(left, w))
            r = max(0, min(right, w))
            t = max(0, min(top, h))
            b = max(0, min(bottom, h))
            if r <= l or b <= t:
                failed += 1
                rep_w.writerow([i, path.name, src_size, "",
                                "crop_out_of_bounds", ""])
                cb.emit_log(f"⚠ 裁剪框超出影像範圍：{path.name}")
                cb.emit_progress(i + 1, total)
                continue

            cropped = img[t:b, l:r]
            notes = []
            if (l, t, r, b) != (left, top, right, bottom):
                notes.append(f"clamped→({l},{t},{r},{b})")
            if rename_note:
                notes.append(rename_note)
            if resize_to:
                cropped = cv2.resize(cropped, (out_w, out_h),
                                     interpolation=cv2.INTER_AREA)
            ch, cw = cropped.shape[:2]

            if imwrite_unicode(str(out_path), cropped, params):
                done += 1
                produced.add(_path_key(out_path))
                rep_w.writerow([i, path.name, src_size,
                                f"{cw}x{ch}", "ok", "; ".join(notes)])
                if done % preview_every == 1:
                    cb.emit_preview(encode_preview_jpeg(cropped), i)
            else:
                failed += 1
                rep_w.writerow([i, path.name, src_size, "",
                                "write_failed", "; ".join(notes)])
                cb.emit_log(f"⚠ 寫入失敗：{out_path.name}")

            cb.emit_progress(i + 1, total)
            if (i + 1) % 10 == 0:
                cb.emit_stats({"done": done, "failed_skipped": failed + skipped,
                               "processed": i + 1})
    finally:
        rep_file.close()

    elapsed = time.perf_counter() - t0
    cb.emit_stats({"done": done, "failed_skipped": failed + skipped,
                   "processed": processed})
    summary_path = output_dir / "_crop_summary.txt"
    summary = (f"批次裁剪摘要\n==================\n"
               f"處理時間  : {datetime.now():%Y-%m-%d %H:%M:%S}\n"
               f"執行時間  : {format_duration(elapsed)}\n"
               f"圖片總數  : {total}\n成功裁剪  : {done}\n"
               f"失敗      : {failed}\n略過      : {skipped}\n"
               f"裁剪框    : (左{left}, 上{top}, 右{right}, 下{bottom})\n"
               f"裁剪尺寸  : {crop_w}×{crop_h}\n"
               f"輸出尺寸  : {out_w}×{out_h}\n"
               f"輸出格式  : {ext}\n"
               f"輸出資料夾: {output_dir}\n"
               f"報表      : {report_path.name}\n")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)
    cb.emit_log("\n✔ 完成\n" + summary)

    return {
        "total": total, "done": done, "failed": failed, "skipped": skipped,
        "out_size": f"{out_w}×{out_h}", "elapsed": elapsed,
        "output_dir": str(output_dir),
    }
