from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create timestamped ETS2 workflow frames and contact sheets."
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--thumbnail-width", type=int, default=480)
    return parser.parse_args()


def timestamp_label(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:05.2f}"


def main() -> int:
    args = parse_args()
    if args.interval <= 0:
        raise ValueError("--interval must be greater than zero")

    video = args.video.resolve()
    output = args.output.resolve()
    frames_dir = output / "frames"
    sheets_dir = output / "sheets"
    frames_dir.mkdir(parents=True, exist_ok=True)
    sheets_dir.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0.0
    sample_count = max(1, int(math.floor(duration / args.interval)) + 1)
    samples: list[dict[str, object]] = []
    thumbnails = []

    for sample_index in range(sample_count):
        seconds = min(sample_index * args.interval, duration)
        capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000.0)
        ok, frame = capture.read()
        if not ok:
            continue

        filename = f"frame-{sample_index:04d}-{seconds:010.3f}s.jpg"
        frame_path = frames_dir / filename
        cv2.imwrite(str(frame_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

        thumb_height = round(frame.shape[0] * args.thumbnail_width / frame.shape[1])
        thumbnail = cv2.resize(
            frame,
            (args.thumbnail_width, thumb_height),
            interpolation=cv2.INTER_AREA,
        )
        label = timestamp_label(seconds)
        cv2.rectangle(thumbnail, (0, 0), (138, 34), (0, 0, 0), thickness=-1)
        cv2.putText(
            thumbnail,
            label,
            (8, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        thumbnails.append(thumbnail)
        samples.append({"index": sample_index, "seconds": seconds, "file": str(frame_path)})

    capture.release()

    per_sheet = args.columns * args.rows
    sheet_files = []
    for sheet_index, start in enumerate(range(0, len(thumbnails), per_sheet)):
        batch = thumbnails[start : start + per_sheet]
        if not batch:
            continue
        cell_height = batch[0].shape[0]
        sheet = cv2.copyMakeBorder(
            batch[0], 0, cell_height * args.rows - cell_height, 0,
            args.thumbnail_width * args.columns - args.thumbnail_width,
            cv2.BORDER_CONSTANT, value=(20, 20, 20)
        )
        sheet[:] = (20, 20, 20)
        for offset, thumbnail in enumerate(batch):
            row, column = divmod(offset, args.columns)
            y = row * cell_height
            x = column * args.thumbnail_width
            sheet[y : y + cell_height, x : x + args.thumbnail_width] = thumbnail
        sheet_path = sheets_dir / f"sheet-{sheet_index:03d}.jpg"
        cv2.imwrite(str(sheet_path), sheet, [int(cv2.IMWRITE_JPEG_QUALITY), 94])
        sheet_files.append(str(sheet_path))

    manifest = {
        "video": str(video),
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": duration,
        "sample_interval_seconds": args.interval,
        "samples": samples,
        "sheets": sheet_files,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in (
        "video", "width", "height", "fps", "frame_count", "duration_seconds"
    )}, indent=2))
    print(f"Wrote {len(samples)} frames and {len(sheet_files)} sheets to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
