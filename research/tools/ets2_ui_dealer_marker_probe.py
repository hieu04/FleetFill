"""Select one dynamically detected Scania dealer without opening Buy online."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from ets2_dealer_icon_detector import detect_dealer_markers
from ets2_truck_ui_dry_run import BUY_ONLINE, load_truck_references
from ets2_ui_dealer_pan_probe import capture_analyze
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


def yellow_pixels(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    rgb = np.asarray(image.crop(box).convert("RGB"), dtype=np.int16)
    mask = (
        (rgb[:, :, 0] > 135)
        & (rgb[:, :, 1] > 75)
        & (rgb[:, :, 1] < 200)
        & (rgb[:, :, 2] < 80)
        & ((rgb[:, :, 0] - rgb[:, :, 1]) > 25)
    )
    return int(mask.sum())


def button_metrics(image: Image.Image) -> dict:
    rgb = np.asarray(image.crop(BUY_ONLINE).convert("RGB"), dtype=np.float32)
    means = rgb.mean(axis=(0, 1))
    yellow = yellow_pixels(image, BUY_ONLINE)
    blue_minus_red = float(means[2] - means[0])
    return {
        "yellow_pixels": yellow,
        "blue_minus_red": round(blue_minus_red, 2),
        "enabled": bool(yellow >= 300 or blue_minus_red >= 5.0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-dealer-marker-probe",
    )
    args = parser.parse_args()
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Scania-dealer marker probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It can click one detected dealer marker only; Buy online is unreachable."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if (
        before["state"] != "dealer_map"
        or not before.get("safe_to_act")
        or before.get("selected_brand") != "scania"
    ):
        print(f"MARKER_ABORTED: unsafe starting screen: {before}")
        return 2
    before_markers = detect_dealer_markers(before_image)
    available = [marker for marker in before_markers if marker["state"] == "available"]
    selected = [marker for marker in before_markers if marker["state"] == "selected"]
    before_button = button_metrics(before_image)
    if len(available) != 1 or selected or before_button["enabled"]:
        print(
            "MARKER_ABORTED: expected exactly one available dealer, no selected "
            f"dealer, and disabled Buy online; available={len(available)}, "
            f"selected={len(selected)}, button={before_button}"
        )
        return 3

    target = tuple(available[0]["center"])
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(1.0)

    after_shot, after_image, after, after_annotated, after_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if (
        after["state"] != "dealer_map"
        or not after.get("safe_to_act")
        or after.get("selected_brand") != "scania"
    ):
        print(f"MARKER_FAILED: dealer screen was not safely recognized: {after}")
        return 4
    after_markers = detect_dealer_markers(after_image)
    after_selected = [marker for marker in after_markers if marker["state"] == "selected"]
    after_button = button_metrics(after_image)
    if len(after_selected) != 1 or not after_button["enabled"]:
        print(
            "MARKER_FAILED: selected marker or enabled Buy online not verified; "
            f"selected={len(after_selected)}, button={after_button}"
        )
        return 5

    summary = {
        "gameplay_transactions": 0,
        "dealer_marker_clicks": 1,
        "buy_online_clicks": 0,
        "marker_target": list(target),
        "buy_online_button": {
            "before": before_button,
            "after": after_button,
        },
        "selected_marker": after_selected[0],
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
        },
        "after": {
            "screenshot": str(after_shot),
            "annotated": str(after_annotated),
            "report": str(after_report),
        },
    }
    summary_path = output_dir / (
        f"dealer-marker-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"DEALER_MARKER_PROBE_REPORT: {summary_path}")
    print("MARKER_SUCCEEDED: dealer selected and Buy online enabled, not clicked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
