"""
影片逐幀提取為 JPG (品質 100%)，使用 pHash 感知雜湊去除重複畫面。
★ 已修正：支援中文路徑（影片讀取與 JPG 寫入）

用法：
    python extract_frames.py <影片路徑> [--output 輸出資料夾] [--threshold 5]

依賴：
    pip install opencv-python Pillow imagehash tqdm numpy
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image
from tqdm import tqdm


def imwrite_unicode(path: str, img, params=None) -> bool:
    """支援中文路徑寫入影像"""
    try:
        ext = os.path.splitext(path)[1]
        ok, buf = cv2.imencode(ext, img, params or [])
        if not ok:
            return False
        buf.tofile(path)
        return True
    except Exception:
        return False


def open_video_capture(video_path: str):
    """支援中文路徑開啟 VideoCapture"""
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


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def extract_frames(video_path, output_dir=None, threshold=5, hash_size=8, jpg_quality=100):
    video_path = Path(video_path)
    if not video_path.exists():
        print(f"[錯誤] 找不到影片：{video_path}")
        sys.exit(1)

    if output_dir is None:
        output_dir = video_path.parent / f"{video_path.stem}_frames"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = open_video_capture(str(video_path))
    if not cap.isOpened():
        print(f"[錯誤] 無法開啟影片：{video_path}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"[資訊] 影片：{video_path.name}")
    print(f"[資訊] 解析度：{width}x{height}，FPS：{fps:.2f}，總幀數：{total_frames}")
    print(f"[資訊] 輸出資料夾：{output_dir}")
    print(f"[資訊] pHash 閾值：{threshold}")

    csv_path = output_dir / "frames_report.csv"
    dup_path = output_dir / "duplicates.csv"
    summary_path = output_dir / "summary.txt"

    csv_file = open(csv_path, "w", newline="", encoding="utf-8-sig")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(["frame_index", "timestamp", "filename", "phash",
                         "status", "duplicate_of", "min_distance"])

    dup_file = open(dup_path, "w", newline="", encoding="utf-8-sig")
    dup_writer = csv.writer(dup_file)
    dup_writer.writerow(["frame_index", "timestamp", "duplicate_of_frame",
                         "duplicate_of_filename", "hamming_distance"])

    seen_hashes = []
    saved_count = 0
    duplicate_count = 0
    write_fail_count = 0
    frame_index = 0

    pbar = tqdm(total=total_frames if total_frames > 0 else None,
                desc="提取幀", unit="frame")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            timestamp_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            timestamp_str = format_timestamp(timestamp_sec)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            phash = imagehash.phash(pil_img, hash_size=hash_size)

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
                if dist <= threshold:
                    is_duplicate = True
                    break

            if is_duplicate:
                duplicate_count += 1
                csv_writer.writerow([frame_index, timestamp_str, "", str(phash),
                                     "duplicate", duplicate_of, min_distance])
                dup_writer.writerow([frame_index, timestamp_str, duplicate_of,
                                     duplicate_filename, min_distance])
            else:
                filename = f"frame_{frame_index:08d}.jpg"
                filepath = output_dir / filename
                ok = imwrite_unicode(str(filepath), frame,
                                     [cv2.IMWRITE_JPEG_QUALITY, jpg_quality])
                if ok:
                    seen_hashes.append((frame_index, phash, filename))
                    saved_count += 1
                    csv_writer.writerow([frame_index, timestamp_str, filename, str(phash),
                                         "saved", "",
                                         min_distance if min_distance is not None else ""])
                else:
                    write_fail_count += 1
                    csv_writer.writerow([frame_index, timestamp_str, "", str(phash),
                                         "write_failed", "", ""])

            frame_index += 1
            pbar.update(1)
    finally:
        pbar.close()
        cap.release()
        csv_file.close()
        dup_file.close()

    total_processed = frame_index
    dedup_rate = (duplicate_count / total_processed * 100) if total_processed else 0

    summary = f"""影片提取統計摘要
==================
影片檔案    : {video_path.name}
處理時間    : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
解析度      : {width} x {height}
原始 FPS    : {fps:.2f}
總幀數      : {total_processed}
保留幀數    : {saved_count}
重複幀數    : {duplicate_count}
寫入失敗    : {write_fail_count}
去重率      : {dedup_rate:.2f}%
pHash 閾值  : {threshold}
JPG 品質    : {jpg_quality}
輸出資料夾  : {output_dir}
"""
    print("\n" + summary)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)

    print(f"[完成] 已輸出 {saved_count} 張圖片，去除 {duplicate_count} 張重複。")
    if write_fail_count > 0:
        print(f"[警告] {write_fail_count} 張寫入失敗")


def main():
    parser = argparse.ArgumentParser(description="影片逐幀提取 + pHash 去重")
    parser.add_argument("video", help="影片檔案路徑")
    parser.add_argument("-o", "--output", default=None, help="輸出資料夾")
    parser.add_argument("-t", "--threshold", type=int, default=5, help="pHash 閾值 (預設 5)")
    parser.add_argument("--hash-size", type=int, default=8, help="Hash 大小")
    parser.add_argument("--quality", type=int, default=100, help="JPG 品質 (預設 100)")
    args = parser.parse_args()

    extract_frames(args.video, output_dir=args.output,
                   threshold=args.threshold, hash_size=args.hash_size,
                   jpg_quality=args.quality)


if __name__ == "__main__":
    main()
