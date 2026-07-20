"""Select one saved ETS2 fleet configuration without clicking Purchase."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from ets2_truck_ui_dry_run import (
    PURCHASE,
    TRUCK_CARDS,
    load_truck_references,
    patch_distance,
    project_root,
)
from ets2_ui_dealer_pan_probe import capture_analyze
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR
from ets2_ui_fleet_config_probe import MODE_TEXT_BOX, center
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


def button_blue_minus_red(image: Image.Image) -> float:
    # Blank background strip inside Purchase, away from its centered label.
    patch = np.asarray(image.crop((985, 963, 1060, 989)).convert("RGB"), dtype=np.float32)
    return float(np.mean(patch[:, :, 2] - patch[:, :, 0]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--card", type=int, default=1, choices=range(1, 5))
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-fleet-truck-select-probe",
    )
    args = parser.parse_args()
    frames = project_root() / "research" / "output" / "video-020129" / "frames"
    stock_reference = Image.open(frames / "frame-0042-000021.000s.jpg").convert("RGB")
    fleet_reference = Image.open(frames / "frame-0052-000026.000s.jpg").convert("RGB")
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Fleet truck-selection probe in {args.delay:.1f} seconds. Return to ETS2. "
        f"It can click fleet card {args.card} only; Purchase is never clicked."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if before["state"] != "truck_purchase" or not before.get("safe_to_act"):
        print(f"TRUCK_SELECT_ABORTED: unsafe starting screen: {before}")
        return 2
    fleet_distance = patch_distance(
        before_image, MODE_TEXT_BOX, fleet_reference, MODE_TEXT_BOX
    )
    stock_distance = patch_distance(
        before_image, MODE_TEXT_BOX, stock_reference, MODE_TEXT_BOX
    )
    if fleet_distance > 0.20 or fleet_distance + 0.08 >= stock_distance:
        print(
            "TRUCK_SELECT_ABORTED: My Fleet Configurations was not verified; "
            f"fleet={fleet_distance:.4f}, stock={stock_distance:.4f}"
        )
        return 3

    before_button_metric = button_blue_minus_red(before_image)
    if before_button_metric > 6.0:
        print(
            "TRUCK_SELECT_ABORTED: Purchase already appears enabled; "
            f"blue_minus_red={before_button_metric:.2f}"
        )
        return 4

    target = center(TRUCK_CARDS[args.card - 1])
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(0.8)
    after_shot, after_image, after, after_annotated, after_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    after_button_metric = button_blue_minus_red(after_image)
    if after["state"] != "truck_purchase" or not after.get("safe_to_act"):
        print(f"TRUCK_SELECT_FAILED: unsafe result screen: {after}")
        return 5
    if after_button_metric < 8.0:
        print(
            "TRUCK_SELECT_FAILED: Purchase did not become enabled; "
            f"blue_minus_red={after_button_metric:.2f}"
        )
        return 6

    summary = {
        "gameplay_transactions": 0,
        "fleet_card_clicks": 1,
        "selected_card": args.card,
        "selected_card_center": list(target),
        "purchase_clicks": 0,
        "purchase_blue_minus_red": {
            "before": round(before_button_metric, 2),
            "after": round(after_button_metric, 2),
        },
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
        },
        "after": {
            "screenshot": str(after_shot),
            "annotated": str(after_annotated),
            "report": str(after_report),
            "visual_integrity": after.get("visual_integrity"),
        },
    }
    summary_path = output_dir / (
        f"fleet-truck-select-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"FLEET_TRUCK_SELECT_REPORT: {summary_path}")
    print("TRUCK_SELECT_SUCCEEDED: one fleet card selected; Purchase was not clicked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
