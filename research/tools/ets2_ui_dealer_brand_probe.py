"""Select the Scania dealer filter without selecting a dealer or buying online."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

from ets2_dealer_icon_detector import detect_dealer_markers
from ets2_truck_ui_dry_run import (
    BRAND_BUTTONS,
    annotate,
    load_truck_references,
    recognize,
)
from ets2_ui_dealer_pan_probe import capture_analyze
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


def center(box: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = box
    return ((left + right) // 2, (top + bottom) // 2)


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
        / "live-dealer-brand-probe",
    )
    args = parser.parse_args()
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Scania-filter probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It can click the Scania brand button only."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if (
        before["state"] != "dealer_map"
        or not before.get("safe_to_act")
        or before.get("selected_brand") != "all"
    ):
        print(f"BRAND_ABORTED: unsafe starting screen: {before}")
        return 2

    target = center(BRAND_BUTTONS["scania"])
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
        print(f"BRAND_FAILED: Scania dealer screen was not safely recognized: {after}")
        return 3
    markers = detect_dealer_markers(after_image)
    available = [marker for marker in markers if marker["state"] == "available"]
    selected = [marker for marker in markers if marker["state"] == "selected"]
    if selected:
        print(
            "BRAND_FAILED: filtering must not leave a dealer selected; "
            f"available={len(available)}, selected={len(selected)}"
        )
        return 4

    summary = {
        "gameplay_transactions": 0,
        "brand_clicks": 1,
        "dealer_marker_clicks": 0,
        "buy_online_clicks": 0,
        "selected_brand": "scania",
        "brand_target": list(target),
        "detected_available_dealers": available,
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
        f"dealer-brand-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"DEALER_BRAND_PROBE_REPORT: {summary_path}")
    if available:
        print("BRAND_SUCCEEDED: Scania selected with a visible dealer; no dealer click")
    else:
        print("BRAND_SUCCEEDED: Scania selected; dealer pan fallback required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
