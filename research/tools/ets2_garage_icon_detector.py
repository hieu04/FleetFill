"""Read-only detector for garage markers on ETS2's dynamic garage map.

The map is centered around the player's current location, so marker screen
coordinates cannot be stored.  This utility finds the bright garage-shaped
markers in a fresh screenshot and emits candidate centers.  It never sends
mouse or keyboard input to the game.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ets2_ui_dry_run import GARAGE_MAP


def connected_components(mask: np.ndarray) -> list[dict]:
    """Return 8-connected components for a small boolean map mask."""
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[dict] = []

    for y, x in zip(*np.nonzero(mask)):
        if visited[y, x]:
            continue
        queue = deque([(int(x), int(y))])
        visited[y, x] = True
        pixels: list[tuple[int, int]] = []
        while queue:
            current_x, current_y = queue.popleft()
            pixels.append((current_x, current_y))
            for offset_y in (-1, 0, 1):
                for offset_x in (-1, 0, 1):
                    if not offset_x and not offset_y:
                        continue
                    next_x = current_x + offset_x
                    next_y = current_y + offset_y
                    if (
                        0 <= next_x < width
                        and 0 <= next_y < height
                        and mask[next_y, next_x]
                        and not visited[next_y, next_x]
                    ):
                        visited[next_y, next_x] = True
                        queue.append((next_x, next_y))

        xs = [point[0] for point in pixels]
        ys = [point[1] for point in pixels]
        components.append(
            {
                "left": min(xs),
                "top": min(ys),
                "right": max(xs) + 1,
                "bottom": max(ys) + 1,
                "area": len(pixels),
            }
        )
    return components


def detect_garage_markers(image: Image.Image) -> list[dict]:
    map_left, map_top, _map_right, _map_bottom = GARAGE_MAP
    rgb = np.asarray(image.crop(GARAGE_MAP).convert("RGB"), dtype=np.int16)

    # Garage markers use a nearly neutral light gray.  Roads, borders and city
    # dots are visibly darker; text breaks into much smaller components.
    brightest = rgb.min(axis=2)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    neutral_bright = (brightest >= 174) & (chroma <= 18)

    candidates: list[dict] = []
    for component in connected_components(neutral_bright):
        width = component["right"] - component["left"]
        height = component["bottom"] - component["top"]
        area = component["area"]
        # An unclipped 1080p garage icon is roughly 32x34 pixels.  Slightly
        # broader limits retain antialiased and edge-clipped markers.
        if not (20 <= width <= 42 and 20 <= height <= 42 and 220 <= area <= 950):
            continue
        left = component["left"] + map_left
        top = component["top"] + map_top
        right = component["right"] + map_left
        bottom = component["bottom"] + map_top
        candidates.append(
            {
                "bounds": [left, top, right, bottom],
                "center": [(left + right) // 2, (top + bottom) // 2],
                "bright_area": area,
                "width": width,
                "height": height,
            }
        )

    candidates.sort(key=lambda item: (item["center"][1], item["center"][0]))
    for index, candidate in enumerate(candidates, start=1):
        candidate["candidate"] = index
    return candidates


def annotate(image: Image.Image, candidates: list[dict]) -> Image.Image:
    output = image.copy()
    draw = ImageDraw.Draw(output)
    font = ImageFont.load_default(size=18)
    draw.rectangle(GARAGE_MAP, outline="#4cc9f0", width=3)
    for candidate in candidates:
        left, top, right, bottom = candidate["bounds"]
        center_x, center_y = candidate["center"]
        draw.rectangle((left - 4, top - 4, right + 4, bottom + 4), outline="#50fa7b", width=3)
        draw.ellipse((center_x - 3, center_y - 3, center_x + 3, center_y + 3), fill="#ff5555")
        draw.text(
            (right + 6, top),
            str(candidate["candidate"]),
            fill="#50fa7b",
            font=font,
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("research/output/garage-icon-detection"))
    args = parser.parse_args()

    image = Image.open(args.image).convert("RGB")
    if image.size != (1920, 1080):
        raise ValueError(f"Expected 1920x1080 screenshot, received {image.size}")

    candidates = detect_garage_markers(image)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    annotated_path = args.output_dir / f"{args.image.stem}-garage-candidates.png"
    report_path = args.output_dir / f"{args.image.stem}-garage-candidates.json"
    annotate(image, candidates).save(annotated_path)
    report = {
        "source": str(args.image.resolve()),
        "map_bounds": list(GARAGE_MAP),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "gameplay_input_events": 0,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"ANNOTATED={annotated_path.resolve()}")
    print(f"REPORT={report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
