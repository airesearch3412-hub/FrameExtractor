# -*- coding: utf-8 -*-
"""
FrameExtractor v2 · 影片提取 + 智慧去重工具

★ 主要功能
  - 選單列：檔案 / 編輯 / 檢視 / 說明
  - 四個分頁：提取+去重 / 只提取 / 僅去重資料夾 / 批次處理
  - 多演算法分層去重（dHash / pHash / 直方圖 / SSIM / CLIP）
  - 預設等級（快速/標準/精準/最精準）+ 進階設定面板
  - 支援中文路徑、深色現代 UI

依賴：
    pip install opencv-python Pillow imagehash PyQt6 numpy
執行：
    python extract_frames_gui.py
"""

import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QPalette, QColor, QPixmap, QKeySequence, QImage
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMenuBar, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStatusBar, QTabWidget,
    QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from deduper import DedupConfig
from workers import (
    ExtractDedupWorker, ExtractOnlyWorker, FolderDedupWorker, BatchWorker,
    format_duration,
)


# ===================== 主題樣式 =====================
DARK_QSS = """
* { font-family: "Segoe UI", "Microsoft JhengHei", "PingFang TC", sans-serif; }

QMainWindow, QWidget#root { background: #0f1419; color: #e6edf3; }
QLabel { color: #e6edf3; }
QLabel#title { font-size: 22px; font-weight: 700; color: #ffffff; }
QLabel#subtitle { font-size: 12px; color: #8b949e; }
QLabel#sectionTitle { font-size: 13px; font-weight: 600; color: #c9d1d9; padding-bottom: 4px; }
QLabel#fieldLabel { font-size: 12px; color: #8b949e; }
QLabel#kpiLabel { font-size: 11px; color: #8b949e; letter-spacing: 1px; }
QLabel#kpiValue { font-size: 22px; font-weight: 700; color: #ffffff; }
QLabel#kpiValueAccent { font-size: 22px; font-weight: 700; color: #58a6ff; }
QLabel#kpiValueGood   { font-size: 22px; font-weight: 700; color: #3fb950; }
QLabel#kpiValueWarn   { font-size: 22px; font-weight: 700; color: #f0883e; }

QFrame#card, QGroupBox { background: #161b22; border: 1px solid #30363d; border-radius: 12px; }
QFrame#kpiCard { background: #161b22; border: 1px solid #30363d; border-radius: 10px; }
QFrame#previewFrame { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; }

QGroupBox {
    margin-top: 14px; padding-top: 12px; font-weight: 600; color: #c9d1d9;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: #8b949e;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #0d1117; color: #e6edf3; border: 1px solid #30363d;
    border-radius: 8px; padding: 6px 10px;
    selection-background-color: #1f6feb;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid #1f6feb; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #161b22; color: #e6edf3; border: 1px solid #30363d;
    selection-background-color: #1f6feb;
}

QPushButton {
    background: #21262d; color: #e6edf3; border: 1px solid #30363d;
    border-radius: 8px; padding: 7px 14px; font-weight: 500;
}
QPushButton:hover  { background: #30363d; border-color: #6e7681; }
QPushButton:pressed{ background: #1c2128; }
QPushButton:disabled { color: #6e7681; background: #161b22; }

QPushButton#primary {
    background: #238636; border: 1px solid #2ea043; color: #ffffff; font-weight: 600;
}
QPushButton#primary:hover    { background: #2ea043; }
QPushButton#primary:disabled { background: #1b3a23; color: #6e7681; border-color: #21392a; }

QPushButton#danger {
    background: #21262d; border: 1px solid #f85149; color: #f85149;
}
QPushButton#danger:hover     { background: #2d1417; }
QPushButton#danger:disabled  { color: #6e7681; border-color: #30363d; }

QProgressBar {
    background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
    height: 20px; text-align: center; color: #e6edf3; font-weight: 600;
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

QListWidget {
    background: #0d1117; color: #c9d1d9; border: 1px solid #30363d;
    border-radius: 8px; padding: 4px;
}
QListWidget::item { padding: 6px; border-radius: 4px; }
QListWidget::item:selected { background: #1f6feb; color: #ffffff; }

QTabWidget::pane { border: 1px solid #30363d; border-radius: 10px; top: -1px; background: #0f1419; }
QTabBar::tab {
    background: #161b22; color: #8b949e; padding: 9px 18px;
    border: 1px solid #30363d; border-bottom: none;
    border-top-left-radius: 8px; border-top-right-radius: 8px;
    margin-right: 2px; font-weight: 500;
}
QTabBar::tab:selected { background: #0f1419; color: #58a6ff; border-bottom: 2px solid #1f6feb; }
QTabBar::tab:hover:!selected { background: #21262d; color: #e6edf3; }

QMenuBar { background: #161b22; color: #e6edf3; border-bottom: 1px solid #30363d; }
QMenuBar::item { padding: 6px 12px; background: transparent; }
QMenuBar::item:selected { background: #21262d; }
QMenu { background: #161b22; color: #e6edf3; border: 1px solid #30363d; padding: 4px; }
QMenu::item { padding: 6px 24px; border-radius: 4px; }
QMenu::item:selected { background: #1f6feb; }
QMenu::separator { height: 1px; background: #30363d; margin: 4px 0; }

QStatusBar { background: #161b22; color: #8b949e; border-top: 1px solid #30363d; }

QToolButton {
    background: #21262d; color: #c9d1d9; border: 1px solid #30363d;
    border-radius: 6px; padding: 4px 8px;
}
QToolButton:hover { background: #30363d; }

QToolTip {
    background: #161b22; color: #e6edf3;
    border: 1px solid #30363d; border-radius: 6px; padding: 4px;
}

QLabel#previewFrame {
    background: #0d1117; color: #6e7681;
    border: 1px solid #30363d; border-radius: 10px;
}

QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px 2px 2px 0; }
QScrollBar::handle:vertical { background: #30363d; border-radius: 5px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: #484f58; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0 2px 2px 2px; }
QScrollBar::handle:horizontal { background: #30363d; border-radius: 5px; min-width: 32px; }
QScrollBar::handle:horizontal:hover { background: #484f58; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""

LIGHT_QSS = """
* { font-family: "Segoe UI", "Microsoft JhengHei", sans-serif; color: #1f2328; }
QMainWindow, QWidget#root { background: #f6f8fa; }
QFrame#card, QGroupBox { background: #ffffff; border: 1px solid #d0d7de; border-radius: 12px; }
QLabel#title { font-size: 22px; font-weight: 700; color: #1f2328; }
QLabel#subtitle { font-size: 12px; color: #57606a; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #ffffff; border: 1px solid #d0d7de; border-radius: 8px; padding: 6px 10px;
}
QPushButton {
    background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 8px; padding: 7px 14px;
}
QPushButton:hover { background: #eaeef2; }
QPushButton#primary { background: #2da44e; color: white; border-color: #2c974b; }
QPushButton#primary:hover { background: #2c974b; }
QPushButton#danger { background: #ffffff; color: #cf222e; border-color: #cf222e; }
QToolButton { background: #f6f8fa; color: #1f2328; border: 1px solid #d0d7de; border-radius: 6px; padding: 4px 8px; }
QToolButton:hover { background: #eaeef2; }
QCheckBox { color: #1f2328; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #afb8c1; background: #ffffff; }
QCheckBox::indicator:checked { background: #0969da; border-color: #0969da; }
QProgressBar { background: #eaeef2; border: 1px solid #d0d7de; border-radius: 8px; text-align: center; }
QProgressBar::chunk { background: #1f6feb; border-radius: 6px; }
QTextEdit { background: #ffffff; border: 1px solid #d0d7de; border-radius: 10px; font-family: Consolas, monospace; }
QTabWidget::pane { border: 1px solid #d0d7de; border-radius: 10px; background: #ffffff; }
QTabBar::tab { background: #f6f8fa; padding: 9px 18px; border: 1px solid #d0d7de; border-bottom: none; }
QTabBar::tab:selected { background: #ffffff; color: #0969da; border-bottom: 2px solid #0969da; }
QMenuBar { background: #ffffff; border-bottom: 1px solid #d0d7de; }
QMenu { background: #ffffff; border: 1px solid #d0d7de; }
QStatusBar { background: #ffffff; color: #57606a; border-top: 1px solid #d0d7de; }
QLabel#previewFrame { background: #f6f8fa; color: #8b949e; border: 1px solid #d0d7de; border-radius: 10px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px 2px 2px 0; }
QScrollBar::handle:vertical { background: #d0d7de; border-radius: 5px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: #afb8c1; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: #d0d7de; border-radius: 5px; min-width: 32px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""


# ===================== 工具元件 =====================
class KpiCard(QFrame):
    def __init__(self, label, value="—", color_class="kpiValue"):
        super().__init__()
        self.setObjectName("kpiCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10); lay.setSpacing(2)
        self.lbl = QLabel(label); self.lbl.setObjectName("kpiLabel")
        self.val = QLabel(value); self.val.setObjectName(color_class)
        lay.addWidget(self.lbl); lay.addWidget(self.val)

    def set_value(self, text): self.val.setText(text)


def section_label(text):
    lbl = QLabel(text); lbl.setObjectName("sectionTitle"); return lbl


def field_label(text):
    lbl = QLabel(text); lbl.setObjectName("fieldLabel"); return lbl


def make_card(margin=14, spacing=10):
    f = QFrame(); f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(margin, margin, margin, margin)
    lay.setSpacing(spacing)
    return f, lay


# ===================== 演算法設定面板 =====================
class AlgoPanel(QGroupBox):
    """下拉預設等級 + 進階設定面板（可摺疊）"""
    def __init__(self, title="去重演算法"):
        super().__init__(title)
        self.advanced_visible = False
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 18, 14, 14); v.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(field_label("預設等級"))
        self.preset = QComboBox()
        self.preset.addItems(["快速（dHash）", "標準（dHash+pHash）",
                              "精準（+直方圖+SSIM）", "最精準（+CLIP，需 PyTorch）"])
        self.preset.setCurrentIndex(1)
        self.preset.currentIndexChanged.connect(self._apply_preset)
        top.addWidget(self.preset, 1)

        self.adv_btn = QToolButton()
        self.adv_btn.setText("▼ 進階設定")
        self.adv_btn.setCheckable(True)
        self.adv_btn.toggled.connect(self._toggle_advanced)
        top.addWidget(self.adv_btn)
        v.addLayout(top)

        # 進階面板
        self.adv = QFrame(); self.adv.setObjectName("card")
        adv_l = QGridLayout(self.adv)
        adv_l.setContentsMargins(10, 10, 10, 10)
        adv_l.setHorizontalSpacing(14); adv_l.setVerticalSpacing(6)

        # checkbox 啟用
        self.cb_dhash = QCheckBox("dHash（連續幀快篩）")
        self.cb_phash = QCheckBox("pHash（DCT 感知）")
        self.cb_hist  = QCheckBox("直方圖（色彩分布）")
        self.cb_ssim  = QCheckBox("SSIM（結構相似）")
        self.cb_clip  = QCheckBox("CLIP（AI 語意，慢）")
        for r, cb in enumerate([self.cb_dhash, self.cb_phash, self.cb_hist,
                                self.cb_ssim, self.cb_clip]):
            adv_l.addWidget(cb, r, 0)

        # 閾值
        self.sp_dhash = QSpinBox(); self.sp_dhash.setRange(0, 64); self.sp_dhash.setValue(5)
        self.sp_phash = QSpinBox(); self.sp_phash.setRange(0, 64); self.sp_phash.setValue(5)
        self.sp_hist  = QDoubleSpinBox(); self.sp_hist.setRange(0, 1); self.sp_hist.setDecimals(2)
        self.sp_hist.setSingleStep(0.01); self.sp_hist.setValue(0.95)
        self.sp_ssim  = QDoubleSpinBox(); self.sp_ssim.setRange(0, 1); self.sp_ssim.setDecimals(2)
        self.sp_ssim.setSingleStep(0.01); self.sp_ssim.setValue(0.92)
        self.sp_clip  = QDoubleSpinBox(); self.sp_clip.setRange(0, 1); self.sp_clip.setDecimals(2)
        self.sp_clip.setSingleStep(0.01); self.sp_clip.setValue(0.95)
        for r, (lab, sp) in enumerate([
            ("閾值 (距離≤)", self.sp_dhash), ("閾值 (距離≤)", self.sp_phash),
            ("閾值 (相關≥)", self.sp_hist),  ("閾值 (SSIM≥)", self.sp_ssim),
            ("閾值 (cos≥)", self.sp_clip),
        ]):
            adv_l.addWidget(field_label(lab), r, 1)
            adv_l.addWidget(sp, r, 2)

        # hash 大小 / 視窗（對齊上方的「閾值欄」col1=說明 / col2=數值）
        self.sp_hash_size = QSpinBox(); self.sp_hash_size.setRange(4, 32); self.sp_hash_size.setValue(8)
        self.sp_window = QSpinBox(); self.sp_window.setRange(0, 99999); self.sp_window.setValue(0)
        adv_l.addWidget(field_label("Hash 大小"), 5, 1)
        adv_l.addWidget(self.sp_hash_size, 5, 2)
        adv_l.addWidget(field_label("時間視窗 (0=全比)"), 6, 1)
        adv_l.addWidget(self.sp_window, 6, 2)
        adv_l.setColumnStretch(3, 1)

        self.adv.setVisible(False)
        v.addWidget(self.adv)

        # 套用初始 preset
        self._apply_preset(1)

    def _toggle_advanced(self, checked):
        self.advanced_visible = checked
        self.adv.setVisible(checked)
        self.adv_btn.setText("▲ 隱藏進階" if checked else "▼ 進階設定")

    def _apply_preset(self, i):
        name = ["fast", "standard", "precise", "ultra"][i]
        c = DedupConfig.from_preset(name)
        self.cb_dhash.setChecked(c.use_dhash)
        self.cb_phash.setChecked(c.use_phash)
        self.cb_hist.setChecked(c.use_histogram)
        self.cb_ssim.setChecked(c.use_ssim)
        self.cb_clip.setChecked(c.use_clip)
        self.sp_dhash.setValue(c.dhash_threshold)
        self.sp_phash.setValue(c.phash_threshold)
        self.sp_hist.setValue(c.hist_threshold)
        self.sp_ssim.setValue(c.ssim_threshold)
        self.sp_clip.setValue(c.clip_threshold)

    def get_config(self) -> DedupConfig:
        return DedupConfig(
            use_dhash=self.cb_dhash.isChecked(),
            use_phash=self.cb_phash.isChecked(),
            use_histogram=self.cb_hist.isChecked(),
            use_ssim=self.cb_ssim.isChecked(),
            use_clip=self.cb_clip.isChecked(),
            dhash_threshold=self.sp_dhash.value(),
            phash_threshold=self.sp_phash.value(),
            hist_threshold=self.sp_hist.value(),
            ssim_threshold=self.sp_ssim.value(),
            clip_threshold=self.sp_clip.value(),
            hash_size=self.sp_hash_size.value(),
            window_size=self.sp_window.value(),
        )


# ===================== 共用：預覽 + KPI + 日誌 =====================
class StatsAndPreview(QWidget):
    def __init__(self, kpi_labels=("總幀數", "保留", "重複", "去重率")):
        super().__init__()
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(10)

        # KPI
        kpi_row = QHBoxLayout(); kpi_row.setSpacing(10)
        classes = ["kpiValue", "kpiValueGood", "kpiValueWarn", "kpiValueAccent"]
        self.kpis = []
        for lab, cls in zip(kpi_labels, classes):
            k = KpiCard(lab, "—", cls); kpi_row.addWidget(k, 1); self.kpis.append(k)
        v.addLayout(kpi_row)

        # 預覽 + 日誌
        bottom = QHBoxLayout(); bottom.setSpacing(10)
        pcard, pl = make_card(12, 6)
        pl.addWidget(section_label("即時預覽"))
        self.preview = QLabel("尚未開始")
        self.preview.setObjectName("previewFrame")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(220)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        pl.addWidget(self.preview, 1)
        bottom.addWidget(pcard, 1)

        lcard, ll = make_card(12, 6)
        ll.addWidget(section_label("處理日誌"))
        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setPlaceholderText("等待開始…")
        ll.addWidget(self.log, 1)
        bottom.addWidget(lcard, 1)
        v.addLayout(bottom, 1)

    def set_kpi(self, idx, text):
        self.kpis[idx].set_value(text)

    def reset(self):
        for k in self.kpis:
            k.set_value("0")
        self.log.clear()
        self.preview.setText("處理中…")
        self.preview.setPixmap(QPixmap())

    def append_log(self, text):
        self.log.append(text)
        sb = self.log.verticalScrollBar(); sb.setValue(sb.maximum())

    def set_preview(self, qimg: QImage):
        if qimg.isNull():
            return
        pix = QPixmap.fromImage(qimg).scaled(
            self.preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(pix)


# ===================== 分頁 1：提取 + 去重 =====================
class TabExtractDedup(QWidget):
    def __init__(self, mainwin):
        super().__init__()
        self.mainwin = mainwin
        self.worker = None
        self._build()

    def _build(self):
        v = QVBoxLayout(self); v.setContentsMargins(14, 14, 14, 14); v.setSpacing(12)

        # 檔案
        fc, fl = make_card()
        fl.addWidget(section_label("檔案設定"))
        fl.addWidget(field_label("影片檔案"))
        r1 = QHBoxLayout()
        self.video_edit = QLineEdit(); self.video_edit.setPlaceholderText("選擇影片…")
        r1.addWidget(self.video_edit, 1)
        b = QPushButton("瀏覽"); b.clicked.connect(self.choose_video); r1.addWidget(b)
        fl.addLayout(r1)
        fl.addWidget(field_label("輸出資料夾（留空自動建立）"))
        r2 = QHBoxLayout()
        self.out_edit = QLineEdit(); self.out_edit.setPlaceholderText("影片名稱_frames")
        r2.addWidget(self.out_edit, 1)
        b2 = QPushButton("瀏覽"); b2.clicked.connect(self.choose_out); r2.addWidget(b2)
        fl.addLayout(r2)
        v.addWidget(fc)

        # 演算法
        self.algo = AlgoPanel("去重演算法")
        v.addWidget(self.algo)

        # 其他參數
        pc, pl = make_card()
        pl.addWidget(section_label("輸出參數"))
        prow = QHBoxLayout()
        prow.addWidget(field_label("JPG 品質"))
        self.quality = QSpinBox(); self.quality.setRange(1, 100); self.quality.setValue(100)
        self.quality.setSuffix(" %")
        prow.addWidget(self.quality); prow.addStretch(1)
        pl.addLayout(prow)
        v.addWidget(pc)

        # 操作列
        ar = QHBoxLayout()
        self.start_btn = QPushButton("▶  開始處理"); self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumHeight(36); self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("■  中止"); self.stop_btn.setObjectName("danger")
        self.stop_btn.setMinimumHeight(36); self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        self.open_btn = QPushButton("📂  打開輸出資料夾"); self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_out)
        ar.addWidget(self.start_btn); ar.addWidget(self.stop_btn); ar.addWidget(self.open_btn)
        ar.addStretch(1)
        v.addLayout(ar)

        self.progress = QProgressBar(); self.progress.setFormat("%v / %m 幀  ·  %p%")
        v.addWidget(self.progress)

        self.sp = StatsAndPreview()
        v.addWidget(self.sp, 1)

    def choose_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇影片",
            filter="影片 (*.mp4 *.mov *.avi *.mkv *.flv *.wmv *.m4v *.webm);;所有 (*.*)")
        if path:
            self.video_edit.setText(path)
            if not self.out_edit.text().strip():
                p = Path(path)
                self.out_edit.setText(str(p.parent / f"{p.stem}_frames"))

    def choose_out(self):
        p = QFileDialog.getExistingDirectory(self, "選擇輸出資料夾")
        if p: self.out_edit.setText(p)

    def start(self):
        v = self.video_edit.text().strip()
        if not v or not Path(v).exists():
            QMessageBox.warning(self, "錯誤", "請選擇有效的影片"); return
        out = self.out_edit.text().strip()
        if not out:
            p = Path(v); out = str(p.parent / f"{p.stem}_frames")
            self.out_edit.setText(out)

        self.sp.reset(); self.progress.setValue(0)
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.open_btn.setEnabled(False)
        self.mainwin.set_status("處理中…", "#58a6ff")

        cfg = self.algo.get_config()
        self.worker = ExtractDedupWorker(v, out, cfg, jpg_quality=self.quality.value())
        self.worker.progress.connect(lambda c, t: (self.progress.setMaximum(t), self.progress.setValue(c)))
        self.worker.log.connect(self.sp.append_log)
        self.worker.preview.connect(lambda img, i: self.sp.set_preview(img))
        self.worker.stats_update.connect(self._on_stats)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.error.connect(self._on_err)
        self.worker.start()

    def _on_stats(self, saved, dup, total):
        self.sp.set_kpi(0, f"{total:,}")
        self.sp.set_kpi(1, f"{saved:,}")
        self.sp.set_kpi(2, f"{dup:,}")
        self.sp.set_kpi(3, f"{(dup/total*100 if total else 0):.1f}%")

    def _on_done(self, s):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.open_btn.setEnabled(True)
        self.mainwin.set_status("已完成", "#3fb950")
        big_info(self, "完成", [
            ("總幀數", f"{s['total']:,}"),
            ("保留", f"{s['saved']:,}"),
            ("重複", f"{s['duplicates']:,}"),
            ("去重率", f"{s['dedup_rate']:.2f}%"),
            ("執行時間", format_duration(s.get("elapsed", 0))),
        ], footer=s["output_dir"])

    def _on_err(self, msg):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.mainwin.set_status("錯誤", "#f85149")
        QMessageBox.critical(self, "錯誤", msg)
        self.sp.append_log(f"✖ [錯誤] {msg}")

    def stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.sp.append_log("⏹ 中止中…")
            self.mainwin.set_status("中止中", "#f0883e")

    def open_out(self):
        out = self.out_edit.text().strip()
        if out and Path(out).exists():
            open_folder(out)


# ===================== 分頁 2：只提取 =====================
class TabExtractOnly(QWidget):
    def __init__(self, mainwin):
        super().__init__()
        self.mainwin = mainwin; self.worker = None
        self._build()

    def _build(self):
        v = QVBoxLayout(self); v.setContentsMargins(14, 14, 14, 14); v.setSpacing(12)

        fc, fl = make_card()
        fl.addWidget(section_label("檔案設定"))
        fl.addWidget(field_label("影片檔案"))
        r1 = QHBoxLayout()
        self.video_edit = QLineEdit()
        r1.addWidget(self.video_edit, 1)
        b = QPushButton("瀏覽"); b.clicked.connect(self.choose_video); r1.addWidget(b)
        fl.addLayout(r1)
        fl.addWidget(field_label("輸出資料夾"))
        r2 = QHBoxLayout()
        self.out_edit = QLineEdit()
        r2.addWidget(self.out_edit, 1)
        b2 = QPushButton("瀏覽"); b2.clicked.connect(self.choose_out); r2.addWidget(b2)
        fl.addLayout(r2)
        v.addWidget(fc)

        pc, pl = make_card()
        pl.addWidget(section_label("提取參數"))
        g = QGridLayout()
        g.addWidget(field_label("抽幀間隔（每 N 幀取 1）"), 0, 0)
        self.step = QSpinBox(); self.step.setRange(1, 9999); self.step.setValue(1)
        self.step.setToolTip("1 = 每一幀都取，30 = 每 30 幀取一張")
        g.addWidget(self.step, 0, 1)
        g.addWidget(field_label("JPG 品質"), 0, 2)
        self.quality = QSpinBox(); self.quality.setRange(1, 100); self.quality.setValue(100)
        self.quality.setSuffix(" %")
        g.addWidget(self.quality, 0, 3)
        g.setColumnStretch(4, 1)
        pl.addLayout(g)
        v.addWidget(pc)

        ar = QHBoxLayout()
        self.start_btn = QPushButton("▶  開始提取"); self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumHeight(36); self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("■  中止"); self.stop_btn.setObjectName("danger")
        self.stop_btn.setMinimumHeight(36); self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        self.open_btn = QPushButton("📂  打開輸出資料夾"); self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_out)
        ar.addWidget(self.start_btn); ar.addWidget(self.stop_btn); ar.addWidget(self.open_btn)
        ar.addStretch(1); v.addLayout(ar)

        self.progress = QProgressBar(); self.progress.setFormat("%v / %m 幀  ·  %p%")
        v.addWidget(self.progress)
        self.sp = StatsAndPreview(("總幀數", "已輸出", "—", "—"))
        v.addWidget(self.sp, 1)

    def choose_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "選擇影片",
            filter="影片 (*.mp4 *.mov *.avi *.mkv *.flv *.wmv *.m4v *.webm)")
        if path:
            self.video_edit.setText(path)
            if not self.out_edit.text().strip():
                p = Path(path)
                self.out_edit.setText(str(p.parent / f"{p.stem}_frames"))

    def choose_out(self):
        p = QFileDialog.getExistingDirectory(self, "選擇輸出資料夾")
        if p: self.out_edit.setText(p)

    def start(self):
        v = self.video_edit.text().strip()
        if not v or not Path(v).exists():
            QMessageBox.warning(self, "錯誤", "請選擇有效的影片"); return
        out = self.out_edit.text().strip()
        if not out:
            p = Path(v); out = str(p.parent / f"{p.stem}_frames")
            self.out_edit.setText(out)
        self.sp.reset(); self.progress.setValue(0)
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.open_btn.setEnabled(False)
        self.mainwin.set_status("提取中…", "#58a6ff")

        self.worker = ExtractOnlyWorker(v, out, jpg_quality=self.quality.value(),
                                        frame_step=self.step.value())
        self.worker.progress.connect(lambda c, t: (self.progress.setMaximum(t), self.progress.setValue(c)))
        self.worker.log.connect(self.sp.append_log)
        self.worker.preview.connect(lambda img, i: self.sp.set_preview(img))
        self.worker.stats_update.connect(lambda saved, total: (
            self.sp.set_kpi(0, f"{total:,}"), self.sp.set_kpi(1, f"{saved:,}")))
        self.worker.finished_ok.connect(self._done)
        self.worker.error.connect(self._err)
        self.worker.start()

    def _done(self, s):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.open_btn.setEnabled(True)
        self.mainwin.set_status("已完成", "#3fb950")
        big_info(self, "完成", [
            ("總幀數", f"{s['total']:,}"),
            ("已輸出", f"{s['saved']:,}"),
            ("執行時間", format_duration(s.get("elapsed", 0))),
        ], footer=s["output_dir"])

    def _err(self, msg):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.mainwin.set_status("錯誤", "#f85149")
        QMessageBox.critical(self, "錯誤", msg)

    def stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()

    def open_out(self):
        out = self.out_edit.text().strip()
        if out and Path(out).exists():
            open_folder(out)


# ===================== 分頁 3：僅去重資料夾 =====================
class TabFolderDedup(QWidget):
    def __init__(self, mainwin):
        super().__init__()
        self.mainwin = mainwin; self.worker = None
        self._build()

    def _build(self):
        v = QVBoxLayout(self); v.setContentsMargins(14, 14, 14, 14); v.setSpacing(12)

        fc, fl = make_card()
        fl.addWidget(section_label("資料夾設定"))
        fl.addWidget(field_label("圖片來源資料夾"))
        r1 = QHBoxLayout()
        self.in_edit = QLineEdit()
        self.in_edit.setPlaceholderText("選擇含 jpg/png 的資料夾…")
        r1.addWidget(self.in_edit, 1)
        b = QPushButton("瀏覽"); b.clicked.connect(self.choose_in); r1.addWidget(b)
        fl.addLayout(r1)

        actrow = QHBoxLayout()
        actrow.addWidget(field_label("重複圖片處理方式"))
        self.action = QComboBox()
        self.action.addItems([
            "移動到 _duplicates 子資料夾（建議）",
            "直接刪除（危險！）",
            "僅產生報表，不動原檔",
        ])
        actrow.addWidget(self.action, 1)
        fl.addLayout(actrow)
        v.addWidget(fc)

        self.algo = AlgoPanel("去重演算法")
        v.addWidget(self.algo)

        ar = QHBoxLayout()
        self.start_btn = QPushButton("▶  開始去重"); self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumHeight(36); self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("■  中止"); self.stop_btn.setObjectName("danger")
        self.stop_btn.setMinimumHeight(36); self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        self.open_btn = QPushButton("📂  打開資料夾"); self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_in)
        ar.addWidget(self.start_btn); ar.addWidget(self.stop_btn); ar.addWidget(self.open_btn)
        ar.addStretch(1); v.addLayout(ar)

        self.progress = QProgressBar(); self.progress.setFormat("%v / %m 張  ·  %p%")
        v.addWidget(self.progress)
        self.sp = StatsAndPreview(("圖片總數", "保留", "重複", "去重率"))
        v.addWidget(self.sp, 1)

    def choose_in(self):
        p = QFileDialog.getExistingDirectory(self, "選擇圖片資料夾")
        if p: self.in_edit.setText(p)

    def start(self):
        d = self.in_edit.text().strip()
        if not d or not Path(d).exists():
            QMessageBox.warning(self, "錯誤", "請選擇有效的資料夾"); return

        act_idx = self.action.currentIndex()
        act_name = ["move", "delete", "report"][act_idx]
        if act_name == "delete":
            ret = QMessageBox.question(
                self, "確認刪除",
                "你選擇了「直接刪除」重複圖片，這個動作無法復原！\n\n確定要繼續嗎？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return

        self.sp.reset(); self.progress.setValue(0)
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.open_btn.setEnabled(False)
        self.mainwin.set_status("去重中…", "#58a6ff")

        cfg = self.algo.get_config()
        self.worker = FolderDedupWorker(d, cfg, action=act_name)
        self.worker.progress.connect(lambda c, t: (self.progress.setMaximum(t), self.progress.setValue(c)))
        self.worker.log.connect(self.sp.append_log)
        self.worker.preview.connect(lambda img, i: self.sp.set_preview(img))
        self.worker.stats_update.connect(lambda k, du, total: (
            self.sp.set_kpi(0, f"{total:,}"), self.sp.set_kpi(1, f"{k:,}"),
            self.sp.set_kpi(2, f"{du:,}"),
            self.sp.set_kpi(3, f"{(du/total*100 if total else 0):.1f}%")))
        self.worker.finished_ok.connect(self._done)
        self.worker.error.connect(self._err)
        self.worker.start()

    def _done(self, s):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.open_btn.setEnabled(True)
        self.mainwin.set_status("已完成", "#3fb950")
        big_info(self, "完成", [
            ("總圖片", f"{s['total']:,}"),
            ("保留", f"{s['saved']:,}"),
            ("重複", f"{s['duplicates']:,}"),
            ("去重率", f"{s['dedup_rate']:.2f}%"),
            ("執行時間", format_duration(s.get("elapsed", 0))),
        ], footer=s.get("output_dir", ""))

    def _err(self, msg):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.mainwin.set_status("錯誤", "#f85149")
        QMessageBox.critical(self, "錯誤", msg)

    def stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()

    def open_in(self):
        p = self.in_edit.text().strip()
        if p and Path(p).exists(): open_folder(p)


# ===================== 分頁 4：批次處理 =====================
class TabBatch(QWidget):
    def __init__(self, mainwin):
        super().__init__()
        self.mainwin = mainwin; self.worker = None
        self._build()

    def _build(self):
        v = QVBoxLayout(self); v.setContentsMargins(14, 14, 14, 14); v.setSpacing(12)

        fc, fl = make_card()
        fl.addWidget(section_label("影片清單"))
        self.list_w = QListWidget()
        self.list_w.setMinimumHeight(120)
        fl.addWidget(self.list_w, 1)
        brow = QHBoxLayout()
        b_add = QPushButton("+ 加入影片"); b_add.clicked.connect(self.add_videos)
        b_adddir = QPushButton("+ 加入資料夾"); b_adddir.clicked.connect(self.add_dir)
        b_rm = QPushButton("− 移除選取"); b_rm.clicked.connect(self.remove_sel)
        b_clr = QPushButton("清空"); b_clr.clicked.connect(self.list_w.clear)
        brow.addWidget(b_add); brow.addWidget(b_adddir)
        brow.addWidget(b_rm); brow.addWidget(b_clr); brow.addStretch(1)
        fl.addLayout(brow)
        fl.addWidget(field_label("輸出根目錄（每個影片建立子資料夾）"))
        r2 = QHBoxLayout()
        self.out_edit = QLineEdit()
        r2.addWidget(self.out_edit, 1)
        b2 = QPushButton("瀏覽"); b2.clicked.connect(self.choose_out); r2.addWidget(b2)
        fl.addLayout(r2)
        v.addWidget(fc)

        mc, ml = make_card()
        ml.addWidget(section_label("處理模式"))
        mrow = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(["提取 + 去重", "只提取不去重"])
        mrow.addWidget(field_label("模式"))
        mrow.addWidget(self.mode, 1)
        mrow.addWidget(field_label("JPG 品質"))
        self.quality = QSpinBox(); self.quality.setRange(1, 100); self.quality.setValue(100)
        self.quality.setSuffix(" %")
        mrow.addWidget(self.quality)
        ml.addLayout(mrow)
        v.addWidget(mc)

        self.algo = AlgoPanel("去重演算法（僅在「提取+去重」模式生效）")
        v.addWidget(self.algo)

        ar = QHBoxLayout()
        self.start_btn = QPushButton("▶  開始批次"); self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumHeight(36); self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("■  中止"); self.stop_btn.setObjectName("danger")
        self.stop_btn.setMinimumHeight(36); self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        ar.addWidget(self.start_btn); ar.addWidget(self.stop_btn); ar.addStretch(1)
        v.addLayout(ar)

        self.progress = QProgressBar(); self.progress.setFormat("整體 %v / %m 影片  ·  %p%")
        v.addWidget(self.progress)
        self.sub_progress = QProgressBar(); self.sub_progress.setFormat("子任務 %v / %m  ·  %p%")
        v.addWidget(self.sub_progress)

        self.sp = StatsAndPreview(("已處理影片", "保留總計", "重複總計", "—"))
        v.addWidget(self.sp, 1)

    def add_videos(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "選擇多個影片",
            filter="影片 (*.mp4 *.mov *.avi *.mkv *.flv *.wmv *.m4v *.webm)")
        for p in paths:
            self.list_w.addItem(QListWidgetItem(p))

    def add_dir(self):
        d = QFileDialog.getExistingDirectory(self, "選擇影片資料夾")
        if not d: return
        exts = {".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".m4v", ".webm"}
        for p in sorted(Path(d).iterdir()):
            if p.is_file() and p.suffix.lower() in exts:
                self.list_w.addItem(QListWidgetItem(str(p)))

    def remove_sel(self):
        for it in self.list_w.selectedItems():
            self.list_w.takeItem(self.list_w.row(it))

    def choose_out(self):
        d = QFileDialog.getExistingDirectory(self, "選擇輸出根目錄")
        if d: self.out_edit.setText(d)

    def start(self):
        n = self.list_w.count()
        if n == 0:
            QMessageBox.warning(self, "錯誤", "請先加入影片"); return
        out = self.out_edit.text().strip()
        if not out:
            QMessageBox.warning(self, "錯誤", "請選擇輸出根目錄"); return
        paths = [self.list_w.item(i).text() for i in range(n)]

        self.sp.reset(); self.progress.setValue(0); self.sub_progress.setValue(0)
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self.mainwin.set_status("批次處理中…", "#58a6ff")

        mode = "dedup" if self.mode.currentIndex() == 0 else "extract"
        cfg = self.algo.get_config()
        self.worker = BatchWorker(paths, out, cfg,
                                  jpg_quality=self.quality.value(), mode=mode)
        self.worker.progress.connect(lambda c, t: (self.progress.setMaximum(t), self.progress.setValue(c)))
        self.worker.sub_progress.connect(lambda c, t: (self.sub_progress.setMaximum(t), self.sub_progress.setValue(c)))
        self.worker.log.connect(self.sp.append_log)
        self.worker.preview.connect(lambda img, i: self.sp.set_preview(img))
        self.worker.finished_ok.connect(self._done)
        self.worker.error.connect(self._err)
        self.worker.start()

    def _done(self, agg):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.mainwin.set_status("批次完成", "#3fb950")
        self.sp.set_kpi(0, f"{agg['videos']:,}")
        self.sp.set_kpi(1, f"{agg['saved_total']:,}")
        self.sp.set_kpi(2, f"{agg['dup_total']:,}")
        big_info(self, "批次完成", [
            ("處理影片", f"{agg['videos']:,}"),
            ("總幀數", f"{agg.get('frames_total', 0):,}"),
            ("保留總計", f"{agg['saved_total']:,}"),
            ("重複總計", f"{agg['dup_total']:,}"),
            ("執行時間", format_duration(agg.get("elapsed", 0))),
        ], footer=str(self.out_edit.text().strip()))

    def _err(self, msg):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "錯誤", msg)
        self.mainwin.set_status("錯誤", "#f85149")

    def stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()


# ===================== 工具 =====================
def open_folder(path):
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def big_info(parent, title, rows, footer=""):
    """較大的完成對話框。
    rows: [(標籤, 值)] 會排成兩欄表格；footer 為底部備註（例如輸出路徑）。"""
    body = "".join(
        f"<tr>"
        f"<td style='color:#8b949e; padding:4px 20px 4px 0; font-size:14px'>{k}</td>"
        f"<td style='font-size:16px; font-weight:700'>{v}</td>"
        f"</tr>"
        for k, v in rows
    )
    html = (
        f"<div style='font-size:17px; font-weight:700; margin-bottom:10px'>✔ {title}</div>"
        f"<table cellspacing='0'>{body}</table>"
    )
    if footer:
        html += (f"<div style='color:#8b949e; font-size:12px; margin-top:14px'>"
                 f"輸出位置<br><span style='color:#58a6ff'>{footer}</span></div>")
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Information)
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(html)
    # 撐寬撐高：min-width 作用在內部 QLabel，整個對話框會跟著放大
    box.setStyleSheet("QMessageBox QLabel { min-width: 460px; min-height: 120px; }")
    box.exec()


PREF_FILE = Path.home() / ".frameextractor_prefs.json"


# ===================== 主視窗 =====================
class MainWindow(QMainWindow):
    APP_NAME = "FrameExtractor"
    APP_VERSION = "2.0"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{self.APP_NAME} · 影片提取與智慧去重工具")
        self.resize(1180, 820)
        self.setMinimumSize(QSize(1000, 720))
        self.dark_mode = True
        self._build_ui()
        self._build_menubar()
        self._build_statusbar()
        self._load_prefs()

    def _build_ui(self):
        root = QWidget(); root.setObjectName("root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(16, 12, 16, 8); v.setSpacing(10)

        h = QHBoxLayout()
        tbox = QVBoxLayout(); tbox.setSpacing(2)
        title = QLabel(self.APP_NAME); title.setObjectName("title")
        sub = QLabel(f"v{self.APP_VERSION} · 影片提取 · 智慧去重 · 批次處理")
        sub.setObjectName("subtitle")
        tbox.addWidget(title); tbox.addWidget(sub)
        h.addLayout(tbox); h.addStretch(1)
        self.status_badge = QLabel("● 待命")
        self.status_badge.setStyleSheet(
            "background:#21262d;color:#8b949e;border-radius:10px;padding:6px 12px;font-weight:600;")
        h.addWidget(self.status_badge)
        v.addLayout(h)

        self.tabs = QTabWidget()
        self.tab_extract_dedup = TabExtractDedup(self)
        self.tab_extract_only  = TabExtractOnly(self)
        self.tab_folder_dedup  = TabFolderDedup(self)
        self.tab_batch         = TabBatch(self)
        # 每個分頁包進可捲動區，內容超過視窗高度時改用捲軸，避免元件被壓爛
        self.tabs.addTab(self._scrollable(self.tab_extract_dedup), "🎬  提取 + 去重")
        self.tabs.addTab(self._scrollable(self.tab_extract_only),  "📸  只提取")
        self.tabs.addTab(self._scrollable(self.tab_folder_dedup),  "🗂  僅去重資料夾")
        self.tabs.addTab(self._scrollable(self.tab_batch),         "📚  批次處理")
        v.addWidget(self.tabs, 1)

    @staticmethod
    def _scrollable(widget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sa.setWidget(widget)
        return sa

    def _build_menubar(self):
        mb: QMenuBar = self.menuBar()

        m_file = mb.addMenu("檔案(&F)")
        act_open = QAction("開啟影片…", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self._menu_open_video)
        m_file.addAction(act_open)
        act_open_dir = QAction("開啟資料夾去重…", self)
        act_open_dir.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_open_dir.triggered.connect(self._menu_open_dir)
        m_file.addAction(act_open_dir)
        m_file.addSeparator()
        act_export = QAction("匯出本次報表…", self)
        act_export.setShortcut(QKeySequence("Ctrl+E"))
        act_export.triggered.connect(self._menu_export)
        m_file.addAction(act_export)
        m_file.addSeparator()
        act_quit = QAction("離開", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_edit = mb.addMenu("編輯(&E)")
        act_copy = QAction("複製當前輸出路徑", self)
        act_copy.setShortcut(QKeySequence("Ctrl+Shift+C"))
        act_copy.triggered.connect(self._menu_copy_path)
        m_edit.addAction(act_copy)
        act_clear = QAction("清除日誌", self)
        act_clear.setShortcut(QKeySequence("Ctrl+L"))
        act_clear.triggered.connect(self._menu_clear_log)
        m_edit.addAction(act_clear)
        m_edit.addSeparator()
        act_pref = QAction("偏好設定…", self)
        act_pref.setShortcut(QKeySequence("Ctrl+,"))
        act_pref.triggered.connect(self._menu_prefs)
        m_edit.addAction(act_pref)

        m_view = mb.addMenu("檢視(&V)")
        self.act_theme = QAction("切換明暗主題", self)
        self.act_theme.setShortcut(QKeySequence("Ctrl+T"))
        self.act_theme.triggered.connect(self.toggle_theme)
        m_view.addAction(self.act_theme)
        self.act_full = QAction("全螢幕", self, checkable=True)
        self.act_full.setShortcut(QKeySequence("F11"))
        self.act_full.toggled.connect(self._toggle_fullscreen)
        m_view.addAction(self.act_full)
        self.act_statusbar = QAction("顯示狀態列", self, checkable=True)
        self.act_statusbar.setChecked(True)
        self.act_statusbar.toggled.connect(lambda on: self.statusBar().setVisible(on))
        m_view.addAction(self.act_statusbar)

        m_help = mb.addMenu("說明(&H)")
        act_usage = QAction("使用說明", self)
        act_usage.setShortcut(QKeySequence("F1"))
        act_usage.triggered.connect(self._menu_usage)
        m_help.addAction(act_usage)
        act_update = QAction("檢查更新", self)
        act_update.triggered.connect(self._menu_check_update)
        m_help.addAction(act_update)
        m_help.addSeparator()
        act_about = QAction("關於 FrameExtractor", self)
        act_about.triggered.connect(self._menu_about)
        m_help.addAction(act_about)

    def _build_statusbar(self):
        sb: QStatusBar = self.statusBar()
        self.status_msg = QLabel("就緒")
        sb.addWidget(self.status_msg)
        self.status_right = QLabel("v" + self.APP_VERSION)
        sb.addPermanentWidget(self.status_right)

    def set_status(self, text, color="#8b949e"):
        self.status_badge.setText(f"● {text}")
        self.status_badge.setStyleSheet(
            f"background:#21262d;color:{color};border-radius:10px;padding:6px 12px;font-weight:600;")
        self.status_msg.setText(text)

    def _current_out_lineedit(self):
        idx = self.tabs.currentIndex()
        return [self.tab_extract_dedup.out_edit,
                self.tab_extract_only.out_edit,
                self.tab_folder_dedup.in_edit,
                self.tab_batch.out_edit][idx]

    def _menu_open_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "開啟影片",
            filter="影片 (*.mp4 *.mov *.avi *.mkv *.flv *.wmv *.m4v *.webm)")
        if path:
            self.tabs.setCurrentIndex(0)
            self.tab_extract_dedup.video_edit.setText(path)
            if not self.tab_extract_dedup.out_edit.text().strip():
                p = Path(path)
                self.tab_extract_dedup.out_edit.setText(str(p.parent / f"{p.stem}_frames"))

    def _menu_open_dir(self):
        d = QFileDialog.getExistingDirectory(self, "選擇圖片資料夾")
        if d:
            self.tabs.setCurrentIndex(2)
            self.tab_folder_dedup.in_edit.setText(d)

    def _menu_export(self):
        out = self._current_out_lineedit().text().strip()
        if not out or not Path(out).exists():
            QMessageBox.information(self, "匯出", "尚無輸出資料夾可匯出"); return
        target, _ = QFileDialog.getSaveFileName(
            self, "匯出報表為",
            str(Path(out) / "frames_report_copy.csv"),
            "CSV 檔 (*.csv)")
        if not target: return
        src = Path(out) / "frames_report.csv"
        if not src.exists():
            QMessageBox.warning(self, "錯誤", "找不到 frames_report.csv")
            return
        import shutil
        shutil.copy2(src, target)
        QMessageBox.information(self, "完成", f"已匯出至 {target}")

    def _menu_copy_path(self):
        le = self._current_out_lineedit()
        QApplication.clipboard().setText(le.text())
        self.status_msg.setText(f"已複製：{le.text()}")

    def _menu_clear_log(self):
        idx = self.tabs.currentIndex()
        sp = [self.tab_extract_dedup.sp, self.tab_extract_only.sp,
              self.tab_folder_dedup.sp, self.tab_batch.sp][idx]
        sp.log.clear()

    def _menu_prefs(self):
        QMessageBox.information(self, "偏好設定",
            f"偏好設定儲存於：\n{PREF_FILE}\n\n"
            "包含：主題、視窗大小\n自動於關閉時儲存。")

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        QApplication.instance().setStyleSheet(DARK_QSS if self.dark_mode else LIGHT_QSS)

    def _toggle_fullscreen(self, on):
        if on: self.showFullScreen()
        else: self.showNormal()

    def _menu_usage(self):
        msg = (
            "<b>FrameExtractor 使用說明</b><hr>"
            "<b>🎬 提取 + 去重</b>：影片逐幀提取 JPG，同步去除相似畫面。<br><br>"
            "<b>📸 只提取</b>：完整保留所有幀（或指定間隔），不做去重。<br><br>"
            "<b>🗂 僅去重資料夾</b>：對既有圖片資料夾去重（移動／刪除／僅報表）。<br><br>"
            "<b>📚 批次處理</b>：一次處理多個影片，自動建立子資料夾。<br><br>"
            "<b>演算法等級</b>：<br>"
            "&nbsp;• <b>快速</b>：dHash<br>"
            "&nbsp;• <b>標準</b>：dHash + pHash（推薦）<br>"
            "&nbsp;• <b>精準</b>：+ 直方圖 + SSIM<br>"
            "&nbsp;• <b>最精準</b>：+ CLIP 語意（需 PyTorch）<br>"
        )
        box = QMessageBox(self)
        box.setWindowTitle("使用說明")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(msg)
        box.exec()

    def _menu_check_update(self):
        QMessageBox.information(self, "檢查更新",
            f"目前版本：v{self.APP_VERSION}\n\n本程式為離線工具，無自動更新機制。")

    def _menu_about(self):
        QMessageBox.about(self, f"關於 {self.APP_NAME}",
            f"<h3>{self.APP_NAME}</h3>"
            f"<p>版本：v{self.APP_VERSION}</p>"
            "<p>影片逐幀提取與智慧去重工具</p>"
            "<p>核心：OpenCV · imagehash · PyQt6</p>"
            "<p>多演算法分層比對：dHash / pHash / 直方圖 / SSIM / CLIP</p>")

    def _load_prefs(self):
        try:
            if PREF_FILE.exists():
                p = json.loads(PREF_FILE.read_text(encoding="utf-8"))
                if "dark_mode" in p:
                    self.dark_mode = p["dark_mode"]
                    QApplication.instance().setStyleSheet(DARK_QSS if self.dark_mode else LIGHT_QSS)
                if "geometry" in p:
                    w, h = p["geometry"]; self.resize(w, h)
        except Exception:
            pass

    def _save_prefs(self):
        try:
            PREF_FILE.write_text(json.dumps({
                "dark_mode": self.dark_mode,
                "geometry": [self.width(), self.height()],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def closeEvent(self, e):
        self._save_prefs()
        for tab in [self.tab_extract_dedup, self.tab_extract_only,
                    self.tab_folder_dedup, self.tab_batch]:
            w = getattr(tab, "worker", None)
            if w and w.isRunning():
                w.stop(); w.wait(2000)
        e.accept()


def apply_palette(app):
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
    apply_palette(app)
    app.setStyleSheet(DARK_QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
