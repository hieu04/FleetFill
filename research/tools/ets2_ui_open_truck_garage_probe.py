"""Open ETS2 truck garage assignment without selecting a slot or confirming."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_truck_ui_dry_run import PURCHASE, load_truck_references
from ets2_ui_dealer_pan_probe import capture_analyze
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR
from ets2_ui_fleet_config_probe import center
from ets2_ui_fleet_truck_select_probe import button_blue_minus_red
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


def main() -> int:
    parser = argparse.ArgumentParser()
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
        / "live-open-truck-garage-probe",
    )
    args = parser.parse_args()
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Open-garage probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It can click Purchase only; garage markers, slots, and OK are never clicked."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if before["state"] != "truck_purchase" or not before.get("safe_to_act"):
        print(f"OPEN_GARAGE_ABORTED: unsafe starting screen: {before}")
        return 2
    button_metric = button_blue_minus_red(before_image)
    if button_metric < 8.0:
        print(
            "OPEN_GARAGE_ABORTED: Purchase was not verified as enabled; "
            f"blue_minus_red={button_metric:.2f}"
        )
        return 3

    target = center(PURCHASE)
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(1.2)
    after_shot, after_image, after, after_annotated, after_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if after["state"] != "truck_garage_selection" or not after.get("safe_to_act"):
        print(f"OPEN_GARAGE_FAILED: garage assignment was not verified: {after}")
        return 4

    summary = {
        "gameplay_transactions": 0,
        "purchase_button_clicks": 1,
        "garage_marker_clicks": 0,
        "garage_slot_clicks": 0,
        "ok_clicks": 0,
        "purchase_blue_minus_red_before": round(button_metric, 2),
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
        },
        "after": {
            "screenshot": str(after_shot),
            "annotated": str(after_annotated),
            "report": str(after_report),
            "slots": after.get("slots"),
            "visual_integrity": after.get("visual_integrity"),
        },
    }
    summary_path = output_dir / (
        f"open-truck-garage-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"OPEN_TRUCK_GARAGE_REPORT: {summary_path}")
    print("OPEN_GARAGE_SUCCEEDED: garage assignment opened; no slot or OK clicked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
