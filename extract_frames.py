# -*- coding: utf-8 -*-
"""
影片逐幀提取為 JPG (品質 100%) + pHash 去重 - 命令列版
支援中文路徑。GUI 版請執行 extract_frames_gui.py。

用法：
    python extract_frames.py <影片路徑> [--output 輸出資料夾] [--threshold 5]
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import cv2
from PIL import Image
from tqdm import tqdm

from deduper import DedupConfig, Deduper, compute_features, imwrite_unicode
from workers import open_video_capture, format_timestamp


def extract_frames(video_path, output_dir=None, preset="standard",
                   hash_size=8, jpg_quality=100):
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
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cfg = DedupConfig.from_preset(preset)
    cfg.hash_size = hash_size

    print(f"[資訊] 影片：{video_path.name}")
    print(f"[資訊] {w}x{h}  FPS {fps:.2f}  總幀數 {total_frames}")
    print(f"[資訊] 預設等級：{preset}")
    print(f"[資訊] 輸出：{output_dir}")

    csv_path = output_dir / "frames_report.csv"
    dup_path = output_dir / "duplicates.csv"
    summary_path = output_dir / "summary.txt"

    csv_file = open(csv_path, "w", newline="", encoding="utf-8-sig")
    cw = csv.writer(csv_file)
    cw.writerow(["frame_index", "timestamp", "filename", "status",
                 "duplicate_of", "scores"])
    dup_file = open(dup_path, "w", newline="", encoding="utf-8-sig")
    dw = csv.writer(dup_file)
    dw.writerow(["frame_index", "timestamp", "duplicate_of_frame",
                 "duplicate_of_filename", "scores"])

    dedup = Deduper(cfg)
    saved = 0; duplicate = 0; failed = 0; idx = 0
    pbar = tqdm(total=total_frames if total_frames > 0 else None,
                desc="提取", unit="frame")
    try:
        while True:
            ret, frame = cap.read()
            if not ret: break
            ts = format_timestamp(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
            feat = compute_features(frame, cfg, index=idx)
            is_dup, prev, scores = dedup.check(feat)
            if is_dup:
                duplicate += 1
                cw.writerow([idx, ts, "", "duplicate", prev.index, str(scores)])
                dw.writerow([idx, ts, prev.index, prev.filename, str(scores)])
            else:
                filename = f"frame_{idx:08d}.jpg"
                ok = imwrite_unicode(str(output_dir / filename), frame,
                                     [cv2.IMWRITE_JPEG_QUALITY, jpg_quality])
                if ok:
                    feat.filename = filename
                    feat.timestamp = ts
                    dedup.add(feat)
                    saved += 1
                    cw.writerow([idx, ts, filename, "saved", "", ""])
                else:
                    failed += 1
                    cw.writerow([idx, ts, "", "write_failed", "", ""])
            idx += 1
            pbar.update(1)
    finally:
        pbar.close(); cap.release()
        csv_file.close(); dup_file.close()

    rate = (duplicate / idx * 100) if idx else 0
    summary = (f"影片提取統計摘要\n==================\n"
               f"影片檔案    : {video_path.name}\n"
               f"處理時間    : {datetime.now():%Y-%m-%d %H:%M:%S}\n"
               f"解析度      : {w} x {h}\n原始 FPS    : {fps:.2f}\n"
               f"總幀數      : {idx}\n保留幀數    : {saved}\n"
               f"重複幀數    : {duplicate}\n寫入失敗    : {failed}\n"
               f"去重率      : {rate:.2f}%\n預設等級    : {preset}\n"
               f"JPG 品質    : {jpg_quality}\n輸出資料夾  : {output_dir}\n")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)
    print("\n" + summary)


def main():
    p = argparse.ArgumentParser(description="影片逐幀提取 + 多演算法去重")
    p.add_argument("video", help="影片檔案路徑")
    p.add_argument("-o", "--output", default=None, help="輸出資料夾")
    p.add_argument("-p", "--preset", default="standard",
                   choices=["fast", "standard", "precise", "ultra"],
                   help="演算法預設等級")
    p.add_argument("--hash-size", type=int, default=8)
    p.add_argument("--quality", type=int, default=100)
    a = p.parse_args()
    extract_frames(a.video, output_dir=a.output, preset=a.preset,
                   hash_size=a.hash_size, jpg_quality=a.quality)


if __name__ == "__main__":
    main()
