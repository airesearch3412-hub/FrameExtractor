"""
影片提取 JPG (品質 100%) + pHash 去重 GUI 工具
使用 PyQt6 介面（深色現代風 UI/UX）

★ 已修正：支援中文路徑（影片讀取與 JPG 寫入）

依賴：
    pip install opencv-python Pillow imagehash PyQt6 numpy
執行：
    python extract_frames_gui.py
"""

import csv
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QPalette, QColor
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QTextEdit, QVBoxLayout, QWidget, QSizePolicy,
)


# ===================== Unicode 路徑相容函式 =====================
def imwrite_unicode(path: str, img, params=None) -> bool:
    """支援中文路徑寫入影像。OpenCV 的 cv2.imwrite 在 Windows 對中文路徑
    會靜默失敗，這裡改用 imencode + numpy.tofile bypass。"""
    try:
        ext = os.path.splitext(path)[1]  # 例如 ".jpg"
        ok, buf = cv2.imencode(ext, img, params or [])
        if not ok:
            return False
        buf.tofile(path)
        return True
    except Exception:
        return False


def open_video_capture(video_path: str):
    """以支援中文路徑的方式開啟 VideoCapture。
    若直接開失敗，Windows 下嘗試 8.3 短檔名。"""
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
                short_path = buf.value
                cap2 = cv2.VideoCapture(short_path)
                if cap2.isOpened():
                    return cap2
                cap2.release()
        except Exception:
            pass
    return cv2.VideoCapture(video_path)


# ===================== 樣式 =====================
STYLESHEET = """
* { font-family: "Segoe UI", "Microsoft JhengHei", "PingFang TC", sans-serif; }

QMainWindow, QWidget#root { background: #0f1419; color: #e6edf3; }
QLabel { color: #e6edf3; }
QLabel#title { font-size: 22px; font-weight: 700; color: #ffffff; }
QLabel#subtitle { font-size: 12px; color: #8b949e; }
QLabel#sectionTitle { font-size: 13px; font-weight: 600; color: #c9d1d9; padding-bottom: 4px; }
QLabel#fieldLabel { font-size: 12px; color: #8b949e; }
QLabel#kpiLabel { font-size: 11px; color: #8b949e; letter-spacing: 1px; }
QLabel#kpiValue { font-size: 24px; font-weight: 700; color: #ffffff; }
QLabel#kpiValueAccent { font-size: 24px; font-weight: 700; color: #58a6ff; }
QLabel#kpiValueGood   { font-size: 24px; font-weight: 700; color: #3fb950; }
QLabel#kpiValueWarn   { font-size: 24px; font-weight: 700; color: #f0883e; }

QFrame#card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; }
QFrame#kpiCard { background: #161b22; border: 1px solid #30363d; border-radius: 10px; }
QFrame#previewFrame { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; }

QLineEdit, QSpinBox {
    background: #0d1117; color: #e6edf3; border: 1px solid #30363d;
    border-radius: 8px; padding: 8px 10px;
    selection-background-color: #1f6feb;
}
QLineEdit:focus, QSpinBox:focus { border: 1px solid #1f6feb; }

QPushButton {
    background: #21262d; color: #e6edf3; border: 1px solid #30363d;
    border-radius: 8px; padding: 8px 16px; font-weight: 500;
}
QPushButton:hover  { background: #30363d; border-color: #6e7681; }
QPushButton:pressed{ background: #1c2128; }
QPushButton:disabled { color: #6e7681; background: #161b22; }

QPushButton#primary {
    background: #238636; border: 1px solid #2ea043; color: #ffffff; font-weight: 600;
}
QPushButton#primary:hover    { background: #2ea043; }
QPushButton#primary:pressed  { background: #1f7a30; }
QPushButton#primary:disabled { background: #1b3a23; color: #6e7681; border-color: #21392a; }

QPushButton#danger {
    background: #21262d; border: 1px solid #f85149; color: #f85149;
}
QPushButton#danger:hover     { background: #2d1417; }
QPushButton#danger:disabled  { color: #6e7681; border-color: #30363d; }

QProgressBar {
    background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
    height: 22px; text-align: center; color: #e6edf3; font-weight: 600;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1f6feb, stop:1 #58a6ff);
    border-radius: 6px;
}

QTextEdit {
    background: #0d1117; color: #c9d1d9; border: 1px solid #30363d;
    border-radius: 10px; padding: 10px;
    font-family: "Cascadia Code", "Consolas", "Menlo", monospace; font-size: 12px;
}

QCheckBox { color: #c9d1d9; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid #30363d; background: #0d1117;
}
QCheckBox::indicator:checked { background: #1f6feb; border-color: #1f6feb; }

QToolTip {
    background: #161b22; color: #e6edf3;
    border: 1px solid #30363d; border-radius: 6px; padding: 4px;
}
"""


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def make_card(layout_cls=QVBoxLayout, margin=16, spacing=10):
    card = QFrame()
    card.setObjectName("card")
    lay = layout_cls(card)
    lay.setContentsMargins(margin, margin, margin, margin)
    lay.setSpacing(spacing)
    return card, lay


# ===================== 背景處理執行緒 =====================
class ExtractWorker(QThread):
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str)
    preview = pyqtSignal(QImage, int)
    stats_update = pyqtSignal(int, int, int)
    finished_ok = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, video_path, output_dir, threshold, hash_size,
                 jpg_quality=100, preview_every=30, parent=None):
        super().__init__(parent)
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.threshold = threshold
        self.hash_size = hash_size
        self.jpg_quality = jpg_quality
        self.preview_every = preview_every
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            cap = open_video_capture(str(self.video_path))
            if not cap.isOpened():
                self.error.emit(f"無法開啟影片：{self.video_path}")
                return

            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            self.log.emit(f"▶ 影片：{self.video_path.name}")
            self.log.emit(f"  解析度 {width}x{height}  |  FPS {fps:.2f}  |  總幀數 {total_frames}")
            self.log.emit(f"▶ 輸出：{self.output_dir}")
            self.log.emit(f"▶ pHash 閾值 {self.threshold}  |  Hash 大小 {self.hash_size}  |  JPG 品質 {self.jpg_quality}")
            self.log.emit("── 開始處理 ──\n")

            csv_path = self.output_dir / "frames_report.csv"
            dup_path = self.output_dir / "duplicates.csv"
            summary_path = self.output_dir / "summary.txt"

            csv_file = open(csv_path, "w", newline="", encoding="utf-8-sig")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([
                "frame_index", "timestamp", "filename", "phash",
                "status", "duplicate_of", "min_distance"
            ])

            dup_file = open(dup_path, "w", newline="", encoding="utf-8-sig")
            dup_writer = csv.writer(dup_file)
            dup_writer.writerow([
                "frame_index", "timestamp", "duplicate_of_frame",
                "duplicate_of_filename", "hamming_distance"
            ])

            seen_hashes = []
            saved_count = 0
            duplicate_count = 0
            write_fail_count = 0
            frame_index = 0

            try:
                while True:
                    if self._stop:
                        self.log.emit("⏹ [使用者中止]")
                        break

                    ret, frame = cap.read()
                    if not ret:
                        break

                    timestamp_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                    timestamp_str = format_timestamp(timestamp_sec)

                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(frame_rgb)
                    phash = imagehash.phash(pil_img, hash_size=self.hash_size)

                    is_duplicate = False
                    duplicate_of = None
                    duplicate_filename = None
                    min_distance = None

                    for prev_idx, prev_hash, prev_name in seen_hashes:
                        dist = phash - prev_hash
                        if min_distance is None or dist < min_distance:
                            min_distance = dist
                            duplicate_of = prev_idx
                            duplicate_filename = prev_name
                        if dist <= self.threshold:
                            is_duplicate = True
                            break

                    if is_duplicate:
                        duplicate_count += 1
                        csv_writer.writerow([
                            frame_index, timestamp_str, "", str(phash),
                            "duplicate", duplicate_of, min_distance
                        ])
                        dup_writer.writerow([
                            frame_index, timestamp_str, duplicate_of,
                            duplicate_filename, min_distance
                        ])
                    else:
                        filename = f"frame_{frame_index:08d}.jpg"
                        filepath = self.output_dir / filename
                        # ★ 使用 imwrite_unicode 支援中文路徑
                        ok = imwrite_unicode(
                            str(filepath), frame,
                            [cv2.IMWRITE_JPEG_QUALITY, int(self.jpg_quality)]
                        )
                        if ok:
                            seen_hashes.append((frame_index, phash, filename))
                            saved_count += 1
                            csv_writer.writerow([
                                frame_index, timestamp_str, filename, str(phash),
                                "saved", "",
                                min_distance if min_distance is not None else ""
                            ])
                            if saved_count % self.preview_every == 1:
                                qimg = self._cv2_to_qimage(frame_rgb)
                                self.preview.emit(qimg, frame_index)
                        else:
                            write_fail_count += 1
                            csv_writer.writerow([
                                frame_index, timestamp_str, "", str(phash),
                                "write_failed", "", ""
                            ])
                            if write_fail_count <= 3:
                                self.log.emit(f"⚠ 寫入失敗：{filepath}")

                    frame_index += 1
                    if total_frames > 0:
                        self.progress.emit(frame_index, total_frames)
                    if frame_index % 10 == 0:
                        self.stats_update.emit(saved_count, duplicate_count, frame_index)
            finally:
                cap.release()
                csv_file.close()
                dup_file.close()

            total_processed = frame_index
            dedup_rate = (duplicate_count / total_processed * 100) if total_processed else 0

            summary = (
                f"影片提取統計摘要\n"
                f"==================\n"
                f"影片檔案    : {self.video_path.name}\n"
                f"處理時間    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"解析度      : {width} x {height}\n"
                f"原始 FPS    : {fps:.2f}\n"
                f"總幀數      : {total_processed}\n"
                f"保留幀數    : {saved_count}\n"
                f"重複幀數    : {duplicate_count}\n"
                f"寫入失敗    : {write_fail_count}\n"
                f"去重率      : {dedup_rate:.2f}%\n"
                f"pHash 閾值  : {self.threshold}\n"
                f"JPG 品質    : {self.jpg_quality}\n"
                f"輸出資料夾  : {self.output_dir}\n"
                f"CSV 報表    : {csv_path.name}\n"
                f"重複清單    : {dup_path.name}\n"
            )
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary)

            self.log.emit("\n✔ 處理完成")
            self.log.emit(summary)
            self.stats_update.emit(saved_count, duplicate_count, total_processed)
            self.finished_ok.emit({
                "total": total_processed,
                "saved": saved_count,
                "duplicates": duplicate_count,
                "write_failed": write_fail_count,
                "dedup_rate": dedup_rate,
                "output_dir": str(self.output_dir),
            })
        except Exception as e:
            self.error.emit(str(e))

    @staticmethod
    def _cv2_to_qimage(frame_rgb):
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        return QImage(frame_rgb.data, w, h, bytes_per_line,
                      QImage.Format.Format_RGB888).copy()


class KpiCard(QFrame):
    def __init__(self, label: str, value: str = "—", value_class: str = "kpiValue"):
        super().__init__()
        self.setObjectName("kpiCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)
        self.lbl = QLabel(label)
        self.lbl.setObjectName("kpiLabel")
        self.val = QLabel(value)
        self.val.setObjectName(value_class)
        lay.addWidget(self.lbl)
        lay.addWidget(self.val)

    def set_value(self, text: str):
        self.val.setText(text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FrameExtractor · 影片逐幀提取與去重")
        self.resize(1100, 760)
        self.setMinimumSize(QSize(960, 680))
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("FrameExtractor")
        title.setObjectName("title")
        subtitle = QLabel("影片逐幀提取 · JPG 100% · pHash 智慧去重 · 資料整理")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self.status_badge = QLabel("● 待命")
        self.status_badge.setStyleSheet(
            "background:#21262d;color:#8b949e;border-radius:10px;"
            "padding:6px 12px;font-weight:600;"
        )
        header.addWidget(self.status_badge)
        outer.addLayout(header)

        file_card, fcl = make_card()
        fcl.addWidget(self._section_label("檔案設定"))

        v_row = QVBoxLayout(); v_row.setSpacing(4)
        v_row.addWidget(self._field_label("影片檔案"))
        v_inner = QHBoxLayout()
        self.video_edit = QLineEdit()
        self.video_edit.setPlaceholderText("選擇 mp4 / mov / avi / mkv …")
        v_inner.addWidget(self.video_edit, 1)
        btn_v = QPushButton("瀏覽"); btn_v.clicked.connect(self.choose_video)
        v_inner.addWidget(btn_v)
        v_row.addLayout(v_inner)
        fcl.addLayout(v_row)

        o_row = QVBoxLayout(); o_row.setSpacing(4)
        o_row.addWidget(self._field_label("輸出資料夾（留空自動建立）"))
        o_inner = QHBoxLayout()
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("預設：影片名稱_frames")
        o_inner.addWidget(self.out_edit, 1)
        btn_o = QPushButton("瀏覽"); btn_o.clicked.connect(self.choose_output)
        o_inner.addWidget(btn_o)
        o_row.addLayout(o_inner)
        fcl.addLayout(o_row)
        outer.addWidget(file_card)

        param_card, pcl = make_card()
        pcl.addWidget(self._section_label("處理參數"))
        params_grid = QGridLayout()
        params_grid.setHorizontalSpacing(20)
        params_grid.setVerticalSpacing(6)

        params_grid.addWidget(self._field_label("pHash 閾值 (0=嚴格)"), 0, 0)
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 64); self.threshold_spin.setValue(5)
        self.threshold_spin.setToolTip("漢明距離 ≤ 此值視為重複\n0 = 完全相同 / 越大越寬鬆")
        params_grid.addWidget(self.threshold_spin, 1, 0)

        params_grid.addWidget(self._field_label("Hash 大小"), 0, 1)
        self.hashsize_spin = QSpinBox()
        self.hashsize_spin.setRange(4, 32); self.hashsize_spin.setValue(8)
        params_grid.addWidget(self.hashsize_spin, 1, 1)

        params_grid.addWidget(self._field_label("JPG 品質"), 0, 2)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100); self.quality_spin.setValue(100)
        self.quality_spin.setSuffix(" %")
        params_grid.addWidget(self.quality_spin, 1, 2)

        self.preview_check = QCheckBox("即時預覽")
        self.preview_check.setChecked(True)
        params_grid.addWidget(self.preview_check, 1, 3, Qt.AlignmentFlag.AlignVCenter)

        params_grid.setColumnStretch(4, 1)
        pcl.addLayout(params_grid)
        outer.addWidget(param_card)

        action_row = QHBoxLayout(); action_row.setSpacing(10)
        self.start_btn = QPushButton("▶  開始處理")
        self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumHeight(38)
        self.start_btn.clicked.connect(self.start_extract)

        self.stop_btn = QPushButton("■  中止")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setMinimumHeight(38)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_extract)

        self.open_btn = QPushButton("📂  打開輸出資料夾")
        self.open_btn.setMinimumHeight(38)
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_output_folder)

        action_row.addWidget(self.start_btn)
        action_row.addWidget(self.stop_btn)
        action_row.addWidget(self.open_btn)
        action_row.addStretch(1)
        outer.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("%v / %m 幀  ·  %p%")
        self.progress_bar.setValue(0)
        outer.addWidget(self.progress_bar)

        kpi_row = QHBoxLayout(); kpi_row.setSpacing(12)
        self.kpi_total = KpiCard("總幀數", "—", "kpiValue")
        self.kpi_saved = KpiCard("保留", "—", "kpiValueGood")
        self.kpi_dup   = KpiCard("重複", "—", "kpiValueWarn")
        self.kpi_rate  = KpiCard("去重率", "—", "kpiValueAccent")
        for c in (self.kpi_total, self.kpi_saved, self.kpi_dup, self.kpi_rate):
            kpi_row.addWidget(c, 1)
        outer.addLayout(kpi_row)

        bottom = QHBoxLayout(); bottom.setSpacing(12)
        preview_card, pvl = make_card(margin=12, spacing=8)
        pvl.addWidget(self._section_label("即時預覽"))
        self.preview_label = QLabel("尚未開始")
        self.preview_label.setObjectName("previewFrame")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(260)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.preview_label.setStyleSheet(
            "background:#0d1117;color:#6e7681;border:1px solid #30363d;"
            "border-radius:10px;font-size:13px;"
        )
        pvl.addWidget(self.preview_label, 1)
        bottom.addWidget(preview_card, 1)

        log_card, lcl = make_card(margin=12, spacing=8)
        lcl.addWidget(self._section_label("處理日誌"))
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("等待開始…")
        lcl.addWidget(self.log_edit, 1)
        bottom.addWidget(log_card, 1)

        outer.addLayout(bottom, 1)

    def _section_label(self, text):
        lbl = QLabel(text); lbl.setObjectName("sectionTitle"); return lbl

    def _field_label(self, text):
        lbl = QLabel(text); lbl.setObjectName("fieldLabel"); return lbl

    def _set_status(self, text: str, color: str):
        self.status_badge.setText(f"● {text}")
        self.status_badge.setStyleSheet(
            f"background:#21262d;color:{color};border-radius:10px;"
            f"padding:6px 12px;font-weight:600;"
        )

    def choose_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇影片",
            filter="影片檔 (*.mp4 *.mov *.avi *.mkv *.flv *.wmv *.m4v *.webm);;所有檔案 (*.*)"
        )
        if path:
            self.video_edit.setText(path)
            if not self.out_edit.text().strip():
                p = Path(path)
                self.out_edit.setText(str(p.parent / f"{p.stem}_frames"))

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "選擇輸出資料夾")
        if path:
            self.out_edit.setText(path)

    def start_extract(self):
        video = self.video_edit.text().strip()
        out = self.out_edit.text().strip()
        if not video or not Path(video).exists():
            QMessageBox.warning(self, "請選擇影片", "請選擇有效的影片檔案")
            return
        if not out:
            p = Path(video)
            out = str(p.parent / f"{p.stem}_frames")
            self.out_edit.setText(out)

        self.log_edit.clear()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        for kpi, v in ((self.kpi_total, "0"), (self.kpi_saved, "0"),
                       (self.kpi_dup, "0"), (self.kpi_rate, "0%")):
            kpi.set_value(v)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.open_btn.setEnabled(False)
        self._set_status("處理中", "#58a6ff")

        self.worker = ExtractWorker(
            video_path=video,
            output_dir=out,
            threshold=self.threshold_spin.value(),
            hash_size=self.hashsize_spin.value(),
            jpg_quality=self.quality_spin.value(),
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.log.connect(self.append_log)
        self.worker.preview.connect(self.on_preview)
        self.worker.stats_update.connect(self.on_stats)
        self.worker.finished_ok.connect(self.on_done)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def stop_extract(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.append_log("⏹ 使用者要求中止…")
            self._set_status("中止中", "#f0883e")

    def on_progress(self, cur, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(cur)

    def on_stats(self, saved, dup, total):
        self.kpi_total.set_value(f"{total:,}")
        self.kpi_saved.set_value(f"{saved:,}")
        self.kpi_dup.set_value(f"{dup:,}")
        rate = (dup / total * 100) if total else 0
        self.kpi_rate.set_value(f"{rate:.1f}%")

    def append_log(self, text):
        self.log_edit.append(text)
        sb = self.log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_preview(self, qimg, frame_index):
        if not self.preview_check.isChecked():
            return
        pix = QPixmap.fromImage(qimg).scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(pix)
        self.preview_label.setToolTip(f"frame #{frame_index}")

    def on_done(self, stats):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.open_btn.setEnabled(True)
        self._set_status("已完成", "#3fb950")
        fail_line = ""
        if stats.get("write_failed", 0) > 0:
            fail_line = f"\n⚠ 寫入失敗：{stats['write_failed']} 張"
        QMessageBox.information(
            self, "處理完成",
            f"✔ 完成！\n\n"
            f"總幀數：{stats['total']:,}\n"
            f"保留：{stats['saved']:,}\n"
            f"重複：{stats['duplicates']:,}\n"
            f"去重率：{stats['dedup_rate']:.2f}%{fail_line}\n\n"
            f"輸出：{stats['output_dir']}"
        )

    def on_error(self, msg):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_status("錯誤", "#f85149")
        QMessageBox.critical(self, "錯誤", msg)
        self.append_log(f"✖ [錯誤] {msg}")

    def open_output_folder(self):
        out = self.out_edit.text().strip()
        if not out or not Path(out).exists():
            return
        if sys.platform.startswith("win"):
            os.startfile(out)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", out])
        else:
            subprocess.Popen(["xdg-open", out])

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        event.accept()


def apply_dark_palette(app: QApplication):
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#0f1419"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#e6edf3"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#0d1117"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#e6edf3"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#21262d"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#e6edf3"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#1f6feb"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_dark_palette(app)
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
