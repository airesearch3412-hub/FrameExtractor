# -*- coding: utf-8 -*-
"""
背景處理執行緒。
五種工作模式：
  1) ExtractDedupWorker   - 影片提取 + 去重
  2) ExtractOnlyWorker    - 影片只提取，不去重
  3) FolderDedupWorker    - 僅對資料夾內現有圖片做去重
  4) BatchWorker          - 批次處理多個影片
  5) BatchCropWorker      - 批次裁剪（一批相同尺寸圖像套用同一裁剪框 → 統一格式）
"""

import csv
import shutil
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from deduper import (
    DedupConfig, Deduper, compute_features, load_clip_model,
    imread_unicode, imwrite_unicode,
)


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


def cv2_to_qimage(frame_bgr) -> QImage:
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = frame_rgb.shape
    return QImage(frame_rgb.data, w, h, ch * w,
                  QImage.Format.Format_RGB888).copy()


def open_video_capture(video_path: str):
    import sys
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


# ============================================================
# 1) 提取 + 去重
# ============================================================
class ExtractDedupWorker(QThread):
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str)
    preview = pyqtSignal(QImage, int)
    stats_update = pyqtSignal(int, int, int)
    finished_ok = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, video_path, output_dir, cfg: DedupConfig,
                 jpg_quality=100, preview_every=30, parent=None):
        super().__init__(parent)
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.cfg = cfg
        self.jpg_quality = jpg_quality
        self.preview_every = preview_every
        self._stop = False

    def stop(self): self._stop = True

    def run(self):
        try:
            t0 = time.perf_counter()
            self.output_dir.mkdir(parents=True, exist_ok=True)
            cap = open_video_capture(str(self.video_path))
            if not cap.isOpened():
                self.error.emit(f"無法開啟影片：{self.video_path}")
                return

            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            algos = ", ".join([n for n, on in [
                ("dHash", self.cfg.use_dhash), ("pHash", self.cfg.use_phash),
                ("Histogram", self.cfg.use_histogram),
                ("SSIM", self.cfg.use_ssim), ("CLIP", self.cfg.use_clip),
            ] if on]) or "(無，僅提取)"

            self.log.emit(f"▶ 影片：{self.video_path.name}")
            self.log.emit(f"  {w}x{h} | FPS {fps:.2f} | 總幀數 {total}")
            self.log.emit(f"▶ 啟用演算法：{algos}")
            self.log.emit(f"▶ 輸出：{self.output_dir}\n")

            csv_path = self.output_dir / "frames_report.csv"
            dup_path = self.output_dir / "duplicates.csv"
            summary_path = self.output_dir / "summary.txt"

            csv_file = open(csv_path, "w", newline="", encoding="utf-8-sig")
            csv_w = csv.writer(csv_file)
            csv_w.writerow(["frame_index", "timestamp", "filename",
                            "status", "duplicate_of", "scores"])

            dup_file = open(dup_path, "w", newline="", encoding="utf-8-sig")
            dup_w = csv.writer(dup_file)
            dup_w.writerow(["frame_index", "timestamp",
                            "duplicate_of_frame", "duplicate_of_filename", "scores"])

            clip_model = None
            if self.cfg.use_clip:
                try:
                    self.log.emit(f"▶ 載入 CLIP 模型中…（裝置={self.cfg.clip_device}，"
                                  "首次使用會下載權重，約 300MB）")
                    clip_model = load_clip_model(device=self.cfg.clip_device)
                    self.log.emit(f"  CLIP 就緒（實際裝置={clip_model.device}）\n")
                except Exception as e:
                    self.error.emit(f"CLIP 載入失敗：{e}")
                    cap.release(); csv_file.close(); dup_file.close()
                    return

            dedup = Deduper(self.cfg)
            saved = 0; dup = 0; failed = 0; idx = 0

            try:
                while True:
                    if self._stop:
                        self.log.emit("⏹ 使用者中止")
                        break
                    ret, frame = cap.read()
                    if not ret:
                        break

                    ts = format_timestamp(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
                    feat = compute_features(frame, self.cfg, index=idx,
                                            clip_model=clip_model)

                    is_dup, prev, scores = dedup.check(feat)
                    if is_dup:
                        dup += 1
                        csv_w.writerow([idx, ts, "", "duplicate",
                                        prev.index, str(scores)])
                        dup_w.writerow([idx, ts, prev.index, prev.filename, str(scores)])
                    else:
                        filename = f"frame_{idx:08d}.jpg"
                        ok = imwrite_unicode(
                            str(self.output_dir / filename), frame,
                            [cv2.IMWRITE_JPEG_QUALITY, int(self.jpg_quality)])
                        if ok:
                            feat.filename = filename
                            feat.timestamp = ts
                            dedup.add(feat)
                            saved += 1
                            csv_w.writerow([idx, ts, filename, "saved", "", ""])
                            if saved % self.preview_every == 1:
                                self.preview.emit(cv2_to_qimage(frame), idx)
                        else:
                            failed += 1
                            csv_w.writerow([idx, ts, "", "write_failed", "", ""])

                    idx += 1
                    if total > 0:
                        self.progress.emit(idx, total)
                    if idx % 10 == 0:
                        self.stats_update.emit(saved, dup, idx)
            finally:
                cap.release(); csv_file.close(); dup_file.close()

            elapsed = time.perf_counter() - t0
            rate = (dup / idx * 100) if idx else 0
            summary = (f"影片提取統計摘要\n==================\n"
                       f"影片檔案    : {self.video_path.name}\n"
                       f"處理時間    : {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                       f"執行時間    : {format_duration(elapsed)}\n"
                       f"解析度      : {w} x {h}\n原始 FPS    : {fps:.2f}\n"
                       f"總幀數      : {idx}\n保留幀數    : {saved}\n"
                       f"重複幀數    : {dup}\n寫入失敗    : {failed}\n"
                       f"去重率      : {rate:.2f}%\n啟用演算法  : {algos}\n"
                       f"JPG 品質    : {self.jpg_quality}\n"
                       f"輸出資料夾  : {self.output_dir}\n")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary)
            self.log.emit("\n✔ 完成\n" + summary)
            self.stats_update.emit(saved, dup, idx)
            self.finished_ok.emit({
                "total": idx, "saved": saved, "duplicates": dup,
                "write_failed": failed, "dedup_rate": rate,
                "elapsed": elapsed, "output_dir": str(self.output_dir),
            })
        except Exception as e:
            self.error.emit(str(e))


# ============================================================
# 2) 只提取，不去重
# ============================================================
class ExtractOnlyWorker(QThread):
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str)
    preview = pyqtSignal(QImage, int)
    stats_update = pyqtSignal(int, int)   # saved, total
    finished_ok = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, video_path, output_dir, jpg_quality=100,
                 frame_step=1, preview_every=30, parent=None):
        super().__init__(parent)
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.jpg_quality = jpg_quality
        self.frame_step = max(1, int(frame_step))
        self.preview_every = preview_every
        self._stop = False

    def stop(self): self._stop = True

    def run(self):
        try:
            t0 = time.perf_counter()
            self.output_dir.mkdir(parents=True, exist_ok=True)
            cap = open_video_capture(str(self.video_path))
            if not cap.isOpened():
                self.error.emit(f"無法開啟影片：{self.video_path}")
                return
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.log.emit(f"▶ {self.video_path.name}  {w}x{h}  FPS {fps:.2f}")
            self.log.emit(f"▶ 抽幀間隔：每 {self.frame_step} 幀取 1 張")
            self.log.emit(f"▶ 輸出：{self.output_dir}\n")

            csv_path = self.output_dir / "frames_report.csv"
            csv_file = open(csv_path, "w", newline="", encoding="utf-8-sig")
            csv_w = csv.writer(csv_file)
            csv_w.writerow(["frame_index", "timestamp", "filename", "status"])

            saved = 0; failed = 0; idx = 0
            try:
                while True:
                    if self._stop:
                        self.log.emit("⏹ 使用者中止")
                        break
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if idx % self.frame_step == 0:
                        ts = format_timestamp(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
                        filename = f"frame_{idx:08d}.jpg"
                        ok = imwrite_unicode(
                            str(self.output_dir / filename), frame,
                            [cv2.IMWRITE_JPEG_QUALITY, int(self.jpg_quality)])
                        if ok:
                            saved += 1
                            csv_w.writerow([idx, ts, filename, "saved"])
                            if saved % self.preview_every == 1:
                                self.preview.emit(cv2_to_qimage(frame), idx)
                        else:
                            failed += 1
                            csv_w.writerow([idx, ts, "", "write_failed"])
                    idx += 1
                    if total > 0:
                        self.progress.emit(idx, total)
                    if idx % 10 == 0:
                        self.stats_update.emit(saved, idx)
            finally:
                cap.release(); csv_file.close()

            elapsed = time.perf_counter() - t0
            self.log.emit(f"\n✔ 完成：共 {idx} 幀，輸出 {saved} 張，失敗 {failed}"
                          f"，執行時間 {format_duration(elapsed)}")
            self.stats_update.emit(saved, idx)
            self.finished_ok.emit({
                "total": idx, "saved": saved, "write_failed": failed,
                "elapsed": elapsed, "output_dir": str(self.output_dir),
            })
        except Exception as e:
            self.error.emit(str(e))


# ============================================================
# 3) 僅去重資料夾內現有圖片
# ============================================================
class FolderDedupWorker(QThread):
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str)
    preview = pyqtSignal(QImage, int)
    stats_update = pyqtSignal(int, int, int)
    finished_ok = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, input_dir, cfg: DedupConfig, action="move",
                 dup_subdir="_duplicates", preview_every=10, parent=None):
        super().__init__(parent)
        self.input_dir = Path(input_dir)
        self.cfg = cfg
        self.action = action       # "move" | "delete" | "report"
        self.dup_subdir = dup_subdir
        self.preview_every = preview_every
        self._stop = False

    def stop(self): self._stop = True

    def run(self):
        try:
            t0 = time.perf_counter()
            if not self.input_dir.exists():
                self.error.emit(f"資料夾不存在：{self.input_dir}")
                return

            exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}
            files = sorted([p for p in self.input_dir.iterdir()
                            if p.is_file() and p.suffix.lower() in exts])
            total = len(files)
            if total == 0:
                self.error.emit("資料夾內找不到圖片檔案")
                return

            self.log.emit(f"▶ 來源資料夾：{self.input_dir}")
            self.log.emit(f"▶ 找到 {total} 張圖片")
            self.log.emit(f"▶ 動作：{self.action}\n")

            dup_dir = self.input_dir / self.dup_subdir
            if self.action == "move":
                dup_dir.mkdir(exist_ok=True)

            report_path = self.input_dir / "_dedup_report.csv"
            rep_file = open(report_path, "w", newline="", encoding="utf-8-sig")
            rep_w = csv.writer(rep_file)
            rep_w.writerow(["index", "filename", "status",
                            "duplicate_of", "scores", "action"])

            clip_model = None
            if self.cfg.use_clip:
                try:
                    self.log.emit(f"▶ 載入 CLIP 模型中…（裝置={self.cfg.clip_device}，"
                                  "首次使用會下載權重，約 300MB）")
                    clip_model = load_clip_model(device=self.cfg.clip_device)
                    self.log.emit(f"  CLIP 就緒（實際裝置={clip_model.device}）\n")
                except Exception as e:
                    self.error.emit(f"CLIP 載入失敗：{e}")
                    rep_file.close()
                    return

            dedup = Deduper(self.cfg)
            kept = 0; dup = 0; failed = 0

            for i, path in enumerate(files):
                if self._stop:
                    self.log.emit("⏹ 使用者中止")
                    break
                img = imread_unicode(str(path))
                if img is None:
                    failed += 1
                    rep_w.writerow([i, path.name, "read_failed", "", "", ""])
                    self.log.emit(f"⚠ 無法讀取：{path.name}")
                    continue

                feat = compute_features(img, self.cfg, index=i,
                                        clip_model=clip_model)
                feat.filename = path.name

                is_dup, prev, scores = dedup.check(feat)
                if is_dup:
                    dup += 1
                    act = ""
                    if self.action == "move":
                        try:
                            shutil.move(str(path), str(dup_dir / path.name))
                            act = f"moved → {self.dup_subdir}/"
                        except Exception as e:
                            act = f"move_failed: {e}"
                    elif self.action == "delete":
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
                    if kept % self.preview_every == 1:
                        self.preview.emit(cv2_to_qimage(img), i)

                self.progress.emit(i + 1, total)
                if (i + 1) % 10 == 0:
                    self.stats_update.emit(kept, dup, i + 1)

            rep_file.close()

            elapsed = time.perf_counter() - t0
            summary_path = self.input_dir / "_dedup_summary.txt"
            rate = (dup / total * 100) if total else 0
            summary = (f"資料夾去重摘要\n==================\n"
                       f"處理時間  : {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                       f"執行時間  : {format_duration(elapsed)}\n"
                       f"來源資料夾: {self.input_dir}\n"
                       f"圖片總數  : {total}\n保留      : {kept}\n"
                       f"重複      : {dup}\n讀取失敗  : {failed}\n"
                       f"去重率    : {rate:.2f}%\n動作      : {self.action}\n"
                       f"報表      : {report_path.name}\n")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary)
            self.log.emit("\n✔ 完成\n" + summary)
            self.stats_update.emit(kept, dup, total)
            self.finished_ok.emit({
                "total": total, "saved": kept, "duplicates": dup,
                "write_failed": failed, "elapsed": elapsed,
                "dedup_rate": rate, "output_dir": str(self.input_dir),
            })
        except Exception as e:
            self.error.emit(str(e))


# ============================================================
# 4) 批次處理多影片
# ============================================================
class BatchWorker(QThread):
    progress = pyqtSignal(int, int)        # 整體進度
    sub_progress = pyqtSignal(int, int)    # 子任務進度
    log = pyqtSignal(str)
    preview = pyqtSignal(QImage, int)
    finished_ok = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, video_paths, output_root, cfg: DedupConfig,
                 jpg_quality=100, mode="dedup", parent=None):
        """
        mode: "dedup" 提取+去重 / "extract" 只提取
        """
        super().__init__(parent)
        self.video_paths = [Path(p) for p in video_paths]
        self.output_root = Path(output_root)
        self.cfg = cfg
        self.jpg_quality = jpg_quality
        self.mode = mode
        self._stop = False

    def stop(self): self._stop = True

    def run(self):
        try:
            t0 = time.perf_counter()
            self.output_root.mkdir(parents=True, exist_ok=True)
            n = len(self.video_paths)
            self.log.emit(f"▶ 批次任務：{n} 個影片  模式：{self.mode}\n")

            agg = {"videos": 0, "saved_total": 0, "dup_total": 0, "frames_total": 0}
            for i, vp in enumerate(self.video_paths):
                if self._stop:
                    self.log.emit("⏹ 使用者中止")
                    break
                self.log.emit(f"\n══ [{i+1}/{n}] {vp.name} ══")
                sub_out = self.output_root / f"{vp.stem}_frames"

                if self.mode == "dedup":
                    w = ExtractDedupWorker(str(vp), str(sub_out), self.cfg,
                                           jpg_quality=self.jpg_quality)
                else:
                    w = ExtractOnlyWorker(str(vp), str(sub_out),
                                          jpg_quality=self.jpg_quality)

                # 直接同步呼叫 run（在本執行緒內）
                done = {"stats": None, "err": None}
                w.log.connect(self.log.emit)
                w.preview.connect(self.preview.emit)
                w.progress.connect(lambda c, t: self.sub_progress.emit(c, t))
                w.finished_ok.connect(lambda s: done.update(stats=s))
                w.error.connect(lambda e: done.update(err=e))
                # 注意：這裡用 run() 而非 start()，避免額外執行緒
                w.run()

                if done["err"]:
                    self.log.emit(f"✖ 失敗：{done['err']}")
                elif done["stats"]:
                    s = done["stats"]
                    agg["videos"] += 1
                    agg["saved_total"] += s.get("saved", 0)
                    agg["dup_total"] += s.get("duplicates", 0)
                    agg["frames_total"] += s.get("total", 0)

                self.progress.emit(i + 1, n)

            agg["elapsed"] = time.perf_counter() - t0
            self.log.emit(
                f"\n══════ 批次完成 ══════\n"
                f"處理影片數：{agg['videos']}\n"
                f"總幀數    ：{agg['frames_total']:,}\n"
                f"保留      ：{agg['saved_total']:,}\n"
                f"重複      ：{agg['dup_total']:,}\n"
                f"執行時間  ：{format_duration(agg['elapsed'])}\n"
                f"輸出根目錄：{self.output_root}\n"
            )
            self.finished_ok.emit(agg)
        except Exception as e:
            self.error.emit(str(e))


# ============================================================
# 5) 批次裁剪（相同尺寸圖像 → 同一裁剪框 → 統一格式）
# ============================================================
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}


def _path_key(p) -> str:
    """把路徑正規化成可比較的鍵（解析符號連結 + 小寫），用來偵測同檔。"""
    try:
        return str(Path(p).resolve()).lower()
    except Exception:
        return str(p).lower()


class BatchCropWorker(QThread):
    """把一批圖像套用同一個裁剪框（左,上,右,下，原圖像素座標），
    輸出成統一格式（JPG/PNG）、可選統一尺寸。源自 crop_ebook_colab.ipynb，
    但改為純本地、支援中文路徑、保護原檔不被覆蓋。"""

    progress = pyqtSignal(int, int)            # 目前 / 總數
    log = pyqtSignal(str)
    preview = pyqtSignal(QImage, int)          # 裁剪後預覽
    stats_update = pyqtSignal(int, int, int)   # 成功, 失敗, 略過
    finished_ok = pyqtSignal(dict)
    error = pyqtSignal(str)

    @staticmethod
    def _unique_out(base_out, src_path, ext, input_keys, produced):
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

    def __init__(self, image_paths, output_dir, crop_box,
                 out_format="jpg", jpg_quality=95, resize_to=None,
                 preview_every=10, parent=None):
        super().__init__(parent)
        self.image_paths = [Path(p) for p in image_paths]
        self.output_dir = Path(output_dir)
        # crop_box: (left, top, right, bottom) —— 原圖像素座標
        self.crop_box = tuple(int(round(x)) for x in crop_box)
        self.out_format = str(out_format).lower().lstrip(".")
        self.jpg_quality = int(jpg_quality)
        self.resize_to = (tuple(int(v) for v in resize_to)
                          if resize_to else None)   # None 或 (w, h)
        self.preview_every = max(1, int(preview_every))
        self._stop = False

    def stop(self): self._stop = True

    def run(self):
        try:
            t0 = time.perf_counter()
            left, top, right, bottom = self.crop_box
            if right <= left or bottom <= top:
                self.error.emit(
                    f"裁剪框無效（右<=左 或 下<=上）：{self.crop_box}")
                return
            total = len(self.image_paths)
            if total == 0:
                self.error.emit("沒有要處理的圖片")
                return

            self.output_dir.mkdir(parents=True, exist_ok=True)
            ext = ".png" if self.out_format == "png" else ".jpg"
            crop_w, crop_h = right - left, bottom - top
            out_w, out_h = (self.resize_to if self.resize_to else (crop_w, crop_h))

            self.log.emit(f"▶ 批次裁剪：{total} 張圖片")
            self.log.emit(f"▶ 裁剪框 (左,上,右,下)：{self.crop_box}  → {crop_w}×{crop_h}")
            if self.resize_to:
                self.log.emit(f"▶ 統一縮放輸出：{out_w}×{out_h}")
            self.log.emit(f"▶ 輸出格式：{ext}"
                          + (f"（品質 {self.jpg_quality}）" if ext == ".jpg" else "（PNG 無損）"))
            self.log.emit(f"▶ 輸出資料夾：{self.output_dir}\n")

            report_path = self.output_dir / "_crop_report.csv"
            rep_file = open(report_path, "w", newline="", encoding="utf-8-sig")
            rep_w = csv.writer(rep_file)
            rep_w.writerow(["index", "filename", "src_size",
                            "out_size", "status", "note"])

            done = 0; failed = 0; skipped = 0; processed = 0; base_size = None
            params = ([cv2.IMWRITE_JPEG_QUALITY, self.jpg_quality] if ext == ".jpg"
                      else [cv2.IMWRITE_PNG_COMPRESSION, 3])
            input_keys = {_path_key(p) for p in self.image_paths}
            produced = set()
            try:
                for i, path in enumerate(self.image_paths):
                    if self._stop:
                        self.log.emit("⏹ 使用者中止")
                        break
                    processed = i + 1
                    img = imread_unicode(str(path))
                    if img is None:
                        failed += 1
                        rep_w.writerow([i, path.name, "", "", "read_failed", ""])
                        self.log.emit(f"⚠ 無法讀取：{path.name}")
                        self.progress.emit(i + 1, total)
                        continue

                    h, w = img.shape[:2]
                    src_size = f"{w}x{h}"
                    if base_size is None:
                        base_size = (w, h)
                    elif (w, h) != base_size:
                        self.log.emit(
                            f"⚠ 尺寸不一致：{path.name} 為 {w}x{h}，與首張 "
                            f"{base_size[0]}x{base_size[1]} 不同（仍套用同一裁剪框）")

                    base_out = self.output_dir / (path.stem + ext)
                    # 防呆1：輸出檔與「正在處理的這張原檔」同路徑 → 略過保護原圖
                    if _path_key(base_out) == _path_key(path):
                        skipped += 1
                        rep_w.writerow([i, path.name, src_size, "",
                                        "skipped_overwrite_source", ""])
                        self.log.emit(f"⚠ 略過（會覆蓋原檔）：{path.name}"
                                      "，請改用其他輸出資料夾")
                        self.progress.emit(i + 1, total)
                        continue
                    # 防呆2：輸出檔會撞到別的來源檔或本次已輸出檔 → 改名避免覆蓋
                    out_path, rename_note = self._unique_out(
                        base_out, path, ext, input_keys, produced)

                    # clamp 裁剪框到影像範圍
                    l = max(0, min(left, w)); r = max(0, min(right, w))
                    t = max(0, min(top, h));  b = max(0, min(bottom, h))
                    if r <= l or b <= t:
                        failed += 1
                        rep_w.writerow([i, path.name, src_size, "",
                                        "crop_out_of_bounds", ""])
                        self.log.emit(f"⚠ 裁剪框超出影像範圍：{path.name}")
                        self.progress.emit(i + 1, total)
                        continue

                    cropped = img[t:b, l:r]
                    notes = []
                    if (l, t, r, b) != (left, top, right, bottom):
                        notes.append(f"clamped→({l},{t},{r},{b})")
                    if rename_note:
                        notes.append(rename_note)
                    if self.resize_to:
                        cropped = cv2.resize(cropped, (out_w, out_h),
                                             interpolation=cv2.INTER_AREA)
                    ch, cw = cropped.shape[:2]

                    if imwrite_unicode(str(out_path), cropped, params):
                        done += 1
                        produced.add(_path_key(out_path))
                        rep_w.writerow([i, path.name, src_size,
                                        f"{cw}x{ch}", "ok", "; ".join(notes)])
                        if (done - 1) % self.preview_every == 0:
                            self.preview.emit(cv2_to_qimage(cropped), i)
                    else:
                        failed += 1
                        rep_w.writerow([i, path.name, src_size, "",
                                        "write_failed", "; ".join(notes)])
                        self.log.emit(f"⚠ 寫入失敗：{out_path.name}")

                    self.progress.emit(i + 1, total)
                    if (i + 1) % 10 == 0:
                        self.stats_update.emit(done, failed, skipped)
            finally:
                rep_file.close()

            elapsed = time.perf_counter() - t0
            stopped = self._stop
            self.stats_update.emit(done, failed, skipped)
            summary_path = self.output_dir / "_crop_summary.txt"
            summary = (f"批次裁剪摘要\n==================\n"
                       f"狀態      : {'已中止' if stopped else '完成'}\n"
                       f"處理時間  : {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                       f"執行時間  : {format_duration(elapsed)}\n"
                       f"圖片總數  : {total}\n已處理    : {processed}\n"
                       f"成功裁剪  : {done}\n"
                       f"失敗      : {failed}\n略過      : {skipped}\n"
                       f"裁剪框    : (左{left}, 上{top}, 右{right}, 下{bottom})\n"
                       f"裁剪尺寸  : {crop_w}×{crop_h}\n"
                       f"輸出尺寸  : {out_w}×{out_h}\n"
                       f"輸出格式  : {ext}\n"
                       f"輸出資料夾: {self.output_dir}\n"
                       f"報表      : {report_path.name}\n")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary)
            self.log.emit(("\n⏹ 已中止\n" if stopped else "\n✔ 完成\n") + summary)
            self.finished_ok.emit({
                "total": total, "processed": processed, "done": done,
                "failed": failed, "skipped": skipped, "stopped": stopped,
                "out_size": f"{out_w}×{out_h}",
                "elapsed": elapsed, "output_dir": str(self.output_dir),
            })
        except Exception as e:
            self.error.emit(str(e))
