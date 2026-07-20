"""Read-only detector for dynamic truck-dealer markers in ETS2 1.60."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ets2_garage_icon_detector import connected_components
from ets2_truck_ui_dry_run import DEALER_MAP


def marker_components(mask: np.ndarray, map_left: int, map_top: int, state: str) -> list[dict]:
    markers = []
    for component in connected_components(mask):
        width = component["right"] - component["left"]
        height = component["bottom"] - component["top"]
        area = component["area"]
        # Dealer diamonds are approximately 30x31 at 1080p.  The narrower,
        # taller white mouse cursor is the main false positive in this map.
        if not (28 <= width <= 36 and 28 <= height <= 36 and 300 <= area <= 600):
            continue
        left = component["left"] + map_left
        top = component["top"] + map_top
        right = component["right"] + map_left
        bottom = component["bottom"] + map_top
        markers.append(
            {
                "state": state,
                "bounds": [left, top, right, bottom],
                "center": [(left + right) // 2, (top + bottom) // 2],
                "colored_area": area,
                "width": width,
                "height": height,
            }
        )
    return markers


def detect_dealer_markers(image: Image.Image) -> list[dict]:
    map_left, map_top, _right, _bottom = DEALER_MAP
    rgb = np.asarray(image.crop(DEALER_MAP).convert("RGB"), dtype=np.int16)
    minimum = rgb.min(axis=2)
    chroma = rgb.max(axis=2) - minimum
    neutral = (minimum >= 170) & (chroma <= 20)
    yellow = (
        (rgb[:, :, 0] > 155)
        & (rgb[:, :, 1] > 85)
        & (rgb[:, :, 1] < 215)
        & (rgb[:, :, 2] < 85)
        & ((rgb[:, :, 0] - rgb[:, :, 1]) > 25)
    )
    markers = marker_components(neutral, map_left, map_top, "available")
    markers.extend(marker_components(yellow, map_left, map_top, "selected"))
    markers.sort(key=lambda marker: (marker["center"][1], marker["center"][0]))
    for index, marker in enumerate(markers, start=1):
        marker["candidate"] = index
    return markers


def annotate(image: Image.Image, markers: list[dict]) -> Image.Image:
    output = image.copy()
    draw = ImageDraw.Draw(output)
    font = ImageFont.load_default(size=18)
    draw.rectangle(DEALER_MAP, outline="#4cc9f0", width=3)
    for marker in markers:
        left, top, right, bottom = marker["bounds"]
        color = "#ffae00" if marker["state"] == "selected" else "#50fa7b"
        draw.rectangle((left - 4, top - 4, right + 4, bottom + 4), outline=color, width=3)
        draw.text((right + 6, top), str(marker["candidate"]), fill=color, font=font)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/dealer-icon-detection"),
    )
    args = parser.parse_args()
    image = Image.open(args.image).convert("RGB")
    if image.size != (1920, 1080):
        raise ValueError(f"Expected 1920x1080 screenshot, received {image.size}")
    markers = detect_dealer_markers(image)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.image.stem
    annotated_path = args.output_dir / f"{stem}-dealer-candidates.png"
    report_path = args.output_dir / f"{stem}-dealer-candidates.json"
    annotate(image, markers).save(annotated_path)
    report = {
        "source": str(args.image.resolve()),
        "map_bounds": list(DEALER_MAP),
        "candidate_count": len(markers),
        "markers": markers,
        "gameplay_input_events": 0,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"ANNOTATED={annotated_path.resolve()}")
    print(f"REPORT={report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
