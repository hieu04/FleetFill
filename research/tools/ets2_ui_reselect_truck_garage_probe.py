"""Reselect a remembered garage marker and verify its expected truck slots."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_garage_icon_detector import detect_garage_markers
from ets2_truck_ui_dry_run import load_truck_references
from ets2_ui_dealer_pan_probe import capture_analyze
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-x", type=int, required=True)
    parser.add_argument("--target-y", type=int, required=True)
    parser.add_argument("--tolerance", type=int, default=5)
    parser.add_argument("--expected-occupied", type=int, required=True)
    parser.add_argument("--expected-truck-present", type=int, default=0)
    parser.add_argument("--expected-free", type=int, required=True)
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
        / "live-reselect-truck-garage-probe",
    )
    args = parser.parse_args()
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    remembered = (args.target_x, args.target_y)
    print(
        f"Remembered-garage probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It can click one freshly detected garage marker only; no slot or OK."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if before["state"] != "truck_garage_selection" or not before.get("safe_to_act"):
        print(f"RESELECT_GARAGE_ABORTED: unsafe starting screen: {before}")
        return 2
    before_states = [slot["state"] for slot in before.get("slots", [])]
    if before_states != ["locked"] * 5:
        print(
            "RESELECT_GARAGE_ABORTED: expected no garage selected yet; "
            f"got {before_states}"
        )
        return 3

    markers = detect_garage_markers(before_image)
    matches = [
        marker
        for marker in markers
        if abs(marker["center"][0] - remembered[0]) <= args.tolerance
        and abs(marker["center"][1] - remembered[1]) <= args.tolerance
    ]
    if len(matches) != 1:
        print(
            "RESELECT_GARAGE_ABORTED: remembered target did not uniquely match a "
            f"fresh marker; target={remembered}, matches={matches}"
        )
        return 4

    marker = matches[0]
    target = tuple(marker["center"])
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(0.7)
    after_shot, after_image, after, after_annotated, after_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if after["state"] != "truck_garage_selection" or not after.get("safe_to_act"):
        print(f"RESELECT_GARAGE_FAILED: result was not safely recognized: {after}")
        return 5
    states = [slot["state"] for slot in after.get("slots", [])]
    if (
        len(states) != 5
        or states.count("occupied") != args.expected_occupied
        or states.count("truck_present") != args.expected_truck_present
        or states.count("free") != args.expected_free
        or states.count("selected_free") != 0
        or states.count("locked") != 0
    ):
        print(
            "RESELECT_GARAGE_FAILED: remembered garage slot fingerprint changed; "
            f"got {states}"
        )
        return 6

    summary = {
        "gameplay_transactions": 0,
        "remembered_target": list(remembered),
        "fresh_marker": marker,
        "garage_marker_clicks": 1,
        "slot_clicks": 0,
        "ok_clicks": 0,
        "slot_states": states,
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
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"reselect-truck-garage-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"RESELECT_TRUCK_GARAGE_REPORT: {summary_path}")
    print("RESELECT_GARAGE_SUCCEEDED: remembered garage selected; no slot or OK clicked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
