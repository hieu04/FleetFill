"""Pan a filtered dealer map, verify map-art motion, and select one dealer.

Unlike marker-only translation checks, this probe compares the map artwork, so
it can prove motion even when the selected brand has fewer than two visible
dealer icons. It can click one dynamically detected dealer after the verified
pan, but it has no Buy Online or transaction click target.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from ets2_dealer_icon_detector import detect_dealer_markers
from ets2_truck_ui_dry_run import DEALER_MAP, load_truck_references
from ets2_ui_dealer_marker_probe import button_metrics
from ets2_ui_dealer_pan_probe import (
    PAN_END,
    PAN_START,
    capture_analyze,
    distance_squared,
    drag_map,
)
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


MAP_ART = (500, 130, 1770, 850)


def estimate_horizontal_translation(
    before: Image.Image,
    after: Image.Image,
    *,
    box: tuple[int, int, int, int] = MAP_ART,
    scale: float = 0.5,
    max_shift: int = 360,
) -> dict:
    """Estimate full-resolution horizontal map motion by overlap matching."""
    width = max(2, round((box[2] - box[0]) * scale))
    height = max(2, round((box[3] - box[1]) * scale))
    size = (width, height)
    left = np.asarray(
        before.crop(box).convert("L").resize(size, Image.Resampling.BILINEAR),
        dtype=np.float32,
    )
    right = np.asarray(
        after.crop(box).convert("L").resize(size, Image.Resampling.BILINEAR),
        dtype=np.float32,
    )
    scaled_limit = min(round(max_shift * scale), width // 2)
    scores: list[tuple[float, int]] = []
    for dx in range(-scaled_limit, scaled_limit + 1):
        if dx < 0:
            old, new = left[:, -dx:], right[:, :dx]
        elif dx > 0:
            old, new = left[:, :-dx], right[:, dx:]
        else:
            old, new = left, right
        old = (old - old.mean()) / (old.std() + 1e-6)
        new = (new - new.mean()) / (new.std() + 1e-6)
        scores.append((float(np.mean((old - new) ** 2)), dx))
    scores.sort()
    best_score, best_dx = scores[0]
    second_score = scores[1][0] if len(scores) > 1 else best_score
    return {
        "dx": round(best_dx / scale),
        "normalized_error": round(best_score, 6),
        "next_best_error": round(second_score, 6),
        "confidence_gap": round(second_score - best_score, 6),
    }


def action_safe_dealer(marker: dict) -> bool:
    left, top, right, bottom = marker["bounds"]
    x, y = marker["center"]
    return (
        marker["state"] == "available"
        and 500 <= left
        and right <= 1770
        and 130 <= top
        and bottom <= 850
        and 515 <= x <= 1755
        and 145 <= y <= 835
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", default="scania", choices=("scania",))
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--translation-tolerance", type=int, default=14)
    parser.add_argument("--maximum-match-error", type=float, default=0.08)
    parser.add_argument("--minimum-confidence-gap", type=float, default=0.05)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-dealer-filtered-pan",
    )
    args = parser.parse_args()
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    requested_dx = PAN_END[0] - PAN_START[0]
    print(
        f"Filtered dealer pan probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It performs one verified right-drag and may click one dealer marker; "
        "Buy Online is unreachable."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    before_markers = detect_dealer_markers(before_image)
    before_button = button_metrics(before_image)
    if (
        before.get("state") != "dealer_map"
        or not before.get("safe_to_act")
        or before.get("selected_brand") != args.brand
        or any(marker["state"] == "selected" for marker in before_markers)
        or before_button["enabled"]
    ):
        print(f"FILTERED_PAN_ABORTED: unsafe starting screen: {before}")
        return 2
    for name, point in (("start", PAN_START), ("end", PAN_END)):
        if before_markers:
            clearance = min(
                distance_squared(tuple(marker["center"]), point)
                for marker in before_markers
            ) ** 0.5
            if clearance < 90:
                print(
                    f"FILTERED_PAN_ABORTED: {name} point is only "
                    f"{clearance:.1f}px from a dealer marker"
                )
                return 3

    drag_map(PAN_START, PAN_END)
    set_pointer(SAFE_POINTER)
    time.sleep(0.8)
    shifted_shot, shifted_image, shifted, shifted_annotated, shifted_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if (
        shifted.get("state") != "dealer_map"
        or not shifted.get("safe_to_act")
        or shifted.get("selected_brand") != args.brand
    ):
        print(f"FILTERED_PAN_FAILED: unsafe shifted screen: {shifted}")
        return 4
    artwork_motion = estimate_horizontal_translation(before_image, shifted_image)
    if (
        abs(artwork_motion["dx"] - requested_dx) > args.translation_tolerance
        or artwork_motion["normalized_error"] > args.maximum_match_error
        or artwork_motion["confidence_gap"] < args.minimum_confidence_gap
    ):
        print(
            "FILTERED_PAN_FAILED: map artwork did not prove the requested motion: "
            f"requested={requested_dx}, observed={artwork_motion}"
        )
        return 5

    shifted_markers = detect_dealer_markers(shifted_image)
    actionable = [marker for marker in shifted_markers if action_safe_dealer(marker)]
    if not actionable:
        print("FILTERED_PAN_NOT_FOUND: verified pan revealed no safe dealer marker")
        return 6
    target_marker = actionable[0]
    set_pointer(tuple(target_marker["center"]))
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(1.0)
    selected_shot, selected_image, selected, selected_annotated, selected_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    selected_markers = detect_dealer_markers(selected_image)
    selected_dealers = [m for m in selected_markers if m["state"] == "selected"]
    selected_button = button_metrics(selected_image)
    if (
        selected.get("state") != "dealer_map"
        or not selected.get("safe_to_act")
        or selected.get("selected_brand") != args.brand
        or len(selected_dealers) != 1
        or not selected_button["enabled"]
    ):
        print(
            "FILTERED_PAN_FAILED: dealer selection or Buy Online enablement was "
            f"not verified: selected={selected_dealers}, button={selected_button}"
        )
        return 7

    locator = {
        "brand": args.brand,
        "pan_path": [
            {
                "button": "right",
                "start": list(PAN_START),
                "end": list(PAN_END),
                "requested_dx": requested_dx,
                "observed_artwork_translation": artwork_motion,
            }
        ],
        "marker_position": target_marker["center"],
    }
    summary = {
        "gameplay_transactions": 0,
        "brand_clicks": 0,
        "dealer_marker_clicks": 1,
        "buy_online_clicks": 0,
        "map_drags": 1,
        "before_marker_count": len(before_markers),
        "shifted_marker_count": len(shifted_markers),
        "artwork_motion": artwork_motion,
        "selected_dealer": selected_dealers[0],
        "buy_online_button": {"before": before_button, "after": selected_button},
        "locator": locator,
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
        },
        "shifted": {
            "screenshot": str(shifted_shot),
            "annotated": str(shifted_annotated),
            "report": str(shifted_report),
        },
        "selected": {
            "screenshot": str(selected_shot),
            "annotated": str(selected_annotated),
            "report": str(selected_report),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"dealer-filtered-pan-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"DEALER_FILTERED_PAN_REPORT: {summary_path}")
    print(
        "FILTERED_PAN_SUCCEEDED: map-art motion verified and one dealer selected; "
        "Buy Online not clicked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
