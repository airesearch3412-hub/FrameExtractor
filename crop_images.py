# -*- coding: utf-8 -*-
"""
批次裁剪圖像 - 命令列版
對一批（建議相同尺寸）的圖片套用同一個裁剪框，輸出成統一格式。
GUI 版（可在預覽上框選）請執行 extract_frames_gui.py 的「✂ 批次裁剪」分頁。

源自 crop_ebook_colab.ipynb，改為純本地、支援中文路徑、無需 Google Drive。

用法：
    python crop_images.py <資料夾或圖片...> --crop 左,上,右,下 [-o 輸出資料夾]
    python crop_images.py 截圖資料夾 --crop 300,121,1620,1040 -o output
    python crop_images.py a.png b.png --crop 0,0,1320,919 --format png
    python crop_images.py 截圖 --crop 300,121,1620,1040 --resize 1320x919
"""

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

from deduper import imread_unicode, imwrite_unicode
import cv2

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}

# Windows 主控台預設多為 cp950（無法編碼 ✓ → ⚠ × 等符號），
# 先盡量切到 UTF-8；切不過去時 _out() 仍會以 replace 模式安全輸出。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _out(msg=""):
    """安全列印：遇到主控台編碼不支援的字元時以 replace 取代，不讓程式崩潰。"""
    line = f"{msg}\n"
    try:
        sys.stdout.write(line)
    except UnicodeEncodeError:
        enc = (sys.stdout.encoding or "utf-8")
        sys.stdout.write(line.encode(enc, errors="replace").decode(enc))


def collect_images(inputs):
    """把資料夾展開成其中的圖片；單一圖片檔則直接收錄。依路徑排序。"""
    paths = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            paths.extend(sorted(q for q in p.iterdir()
                                if q.is_file() and q.suffix.lower() in IMAGE_EXTS))
        elif p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            paths.append(p)
        else:
            _out(f"[略過] 非圖片或不存在：{p}")
    return paths


def _path_key(p):
    """正規化路徑成可比較的鍵（解析符號連結 + 小寫），用來偵測同檔。"""
    try:
        return str(Path(p).resolve()).lower()
    except Exception:
        return str(p).lower()


def _unique_out(base_out, src_path, ext, input_keys, produced):
    """輸出檔若會撞到別的來源檔或本次已輸出檔，改名為 stem__2/__3…避免覆蓋。
    回傳 (最終路徑, 註記)。"""
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
            return cand, f"renamed->{cand.name}"
        k += 1


def parse_crop(text):
    parts = [int(x) for x in text.replace("，", ",").split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--crop 需為「左,上,右,下」四個整數")
    left, top, right, bottom = parts
    if right <= left or bottom <= top:
        raise argparse.ArgumentTypeError("裁剪框無效：右須大於左、下須大於上")
    return left, top, right, bottom


def parse_resize(text):
    if not text:
        return None
    t = text.lower().replace("×", "x")
    parts = t.split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("--resize 需為「寬x高」，例如 1320x919")
    try:
        w, h = int(parts[0]), int(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError("--resize 寬高需為整數，例如 1320x919")
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("--resize 寬高須為正整數")
    return w, h


def crop_images(inputs, crop_box, output_dir=None, out_format="jpg",
                jpg_quality=95, resize_to=None):
    t0 = time.perf_counter()
    images = collect_images(inputs)
    total = len(images)
    if total == 0:
        _out("[錯誤] 找不到任何圖片"); sys.exit(1)

    left, top, right, bottom = crop_box
    out_format = out_format.lower().lstrip(".")
    ext = ".png" if out_format == "png" else ".jpg"
    crop_w, crop_h = right - left, bottom - top
    out_w, out_h = resize_to if resize_to else (crop_w, crop_h)

    if output_dir is None:
        base = images[0].parent
        output_dir = base / "cropped"
    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _out(f"[錯誤] 無法建立輸出資料夾：{output_dir}（{e}）"); sys.exit(1)

    _out(f"[資訊] 圖片總數：{total}")
    _out(f"[資訊] 裁剪框 (左,上,右,下)：{crop_box} → {crop_w}×{crop_h}")
    if resize_to:
        _out(f"[資訊] 統一縮放輸出：{out_w}×{out_h}")
    _out(f"[資訊] 輸出格式：{ext}"
          + (f"（品質 {jpg_quality}）" if ext == ".jpg" else "（PNG 無損）"))
    _out(f"[資訊] 輸出資料夾：{output_dir}")

    report_path = output_dir / "_crop_report.csv"
    try:
        rep_file = open(report_path, "w", newline="", encoding="utf-8-sig")
    except OSError as e:
        _out(f"[錯誤] 無法建立報表檔：{report_path}（{e}）"); sys.exit(1)

    params = ([cv2.IMWRITE_JPEG_QUALITY, jpg_quality] if ext == ".jpg"
              else [cv2.IMWRITE_PNG_COMPRESSION, 3])
    done = failed = skipped = 0
    base_size = None
    input_keys = {_path_key(p) for p in images}
    produced = set()
    try:
        rep_w = csv.writer(rep_file)
        rep_w.writerow(["index", "filename", "src_size",
                        "out_size", "status", "note"])
        for i, path in enumerate(images):
            img = imread_unicode(str(path))
            if img is None:
                failed += 1
                rep_w.writerow([i, path.name, "", "", "read_failed", ""])
                _out(f"  [{i+1}/{total}] ⚠ 無法讀取 {path.name}")
                continue
            h, w = img.shape[:2]
            src_size = f"{w}x{h}"
            if base_size is None:
                base_size = (w, h)
            elif (w, h) != base_size:
                _out(f"  [{i+1}/{total}] ⚠ 尺寸不一致 {path.name} = {w}x{h}"
                     f"（首張 {base_size[0]}x{base_size[1]}，仍套用同一裁剪框）")

            base_out = output_dir / (path.stem + ext)
            # 防呆1：略過會覆蓋「正在處理的原檔」者
            if _path_key(base_out) == _path_key(path):
                skipped += 1
                rep_w.writerow([i, path.name, src_size, "",
                                "skipped_overwrite_source", ""])
                _out(f"  [{i+1}/{total}] ⚠ 略過（會覆蓋原檔）{path.name}")
                continue
            # 防呆2：撞到別的來源檔或已輸出檔 → 改名避免覆蓋
            out_path, rename_note = _unique_out(
                base_out, path, ext, input_keys, produced)

            l = max(0, min(left, w)); r = max(0, min(right, w))
            tp = max(0, min(top, h)); b = max(0, min(bottom, h))
            if r <= l or b <= tp:
                failed += 1
                rep_w.writerow([i, path.name, src_size, "",
                                "crop_out_of_bounds", ""])
                _out(f"  [{i+1}/{total}] ⚠ 裁剪框超出範圍 {path.name}")
                continue

            cropped = img[tp:b, l:r]
            notes = []
            if (l, tp, r, b) != (left, top, right, bottom):
                notes.append(f"clamped->({l},{tp},{r},{b})")
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
                _out(f"  [{i+1}/{total}] ✓ {path.name} → {out_path.name}")
            else:
                failed += 1
                rep_w.writerow([i, path.name, src_size, "",
                                "write_failed", "; ".join(notes)])
                _out(f"  [{i+1}/{total}] ✖ 寫入失敗 {out_path.name}")
    finally:
        rep_file.close()
    elapsed = time.perf_counter() - t0
    summary = (f"批次裁剪摘要\n==================\n"
               f"處理時間  : {datetime.now():%Y-%m-%d %H:%M:%S}\n"
               f"圖片總數  : {total}\n成功裁剪  : {done}\n"
               f"失敗      : {failed}\n略過      : {skipped}\n"
               f"裁剪框    : (左{left}, 上{top}, 右{right}, 下{bottom})\n"
               f"裁剪尺寸  : {crop_w}×{crop_h}\n輸出尺寸  : {out_w}×{out_h}\n"
               f"輸出格式  : {ext}\n輸出資料夾: {output_dir}\n")
    with open(output_dir / "_crop_summary.txt", "w", encoding="utf-8") as f:
        f.write(summary)
    _out("\n" + summary)


def main():
    p = argparse.ArgumentParser(description="批次裁剪圖像（同一裁剪框 → 統一格式）")
    p.add_argument("inputs", nargs="+", help="圖片檔或含圖片的資料夾（可多個）")
    p.add_argument("--crop", required=True, type=parse_crop,
                   help="裁剪框「左,上,右,下」，例如 300,121,1620,1040")
    p.add_argument("-o", "--output", default=None,
                   help="輸出資料夾（預設：第一張圖所在資料夾下的 cropped/）")
    p.add_argument("-f", "--format", default="jpg", choices=["jpg", "png"],
                   help="輸出格式（預設 jpg）")
    p.add_argument("-q", "--quality", type=int, default=95,
                   help="JPG 品質 1-100（預設 95；PNG 無效）")
    p.add_argument("--resize", default=None, type=parse_resize,
                   help="統一輸出尺寸 WxH，例如 1320x919（預設依裁剪框）")
    a = p.parse_args()
    crop_images(a.inputs, a.crop, output_dir=a.output, out_format=a.format,
                jpg_quality=a.quality, resize_to=a.resize)


if __name__ == "__main__":
    main()
