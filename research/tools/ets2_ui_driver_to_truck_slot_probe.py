"""Select the first truck-without-driver slot without confirming the hire."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR, GARAGE_SLOTS, load_references
from ets2_ui_fleet_config_probe import center
from ets2_ui_pointer_probe import SAFE_POINTER, capture_analyze_save, set_pointer
from ets2_ui_select_probe import click_left_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--integrity-attempts", type=int, default=4)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-driver-to-truck-slot-probe",
    )
    args = parser.parse_args()
    references = load_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Driver-to-truck slot probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It can select the first truck-without-driver slot only; no OK target."
    )
    time.sleep(args.delay)

    before_shot, before, before_annotated, before_report = capture_analyze_save(
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    if before["state"] != "garage_selection" or not before.get("safe_to_act"):
        print(f"DRIVER_TRUCK_SLOT_ABORTED: unsafe starting screen: {before}")
        return 2
    before_states = [slot["state"] for slot in before.get("slots", [])]
    if "selected_free" in before_states or "truck_present" not in before_states:
        print(
            "DRIVER_TRUCK_SLOT_ABORTED: expected at least one unselected waiting "
            f"truck; got {before_states}"
        )
        return 3

    target_index = before_states.index("truck_present")
    target = center(GARAGE_SLOTS[target_index])
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(0.8)
    after_shot, after, after_annotated, after_report = capture_analyze_save(
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    if after["state"] != "garage_selection" or not after.get("safe_to_act"):
        print(f"DRIVER_TRUCK_SLOT_FAILED: result not safely recognized: {after}")
        return 4
    after_states = [slot["state"] for slot in after.get("slots", [])]
    expected_after = before_states.copy()
    expected_after[target_index] = "selected_free"
    if after_states != expected_after:
        print(
            f"DRIVER_TRUCK_SLOT_FAILED: expected {expected_after}, got {after_states}"
        )
        return 5

    summary = {
        "gameplay_transactions": 0,
        "garage_marker_clicks": 0,
        "slot_clicks": 1,
        "ok_clicks": 0,
        "selected_slot": target_index + 1,
        "target_position": list(target),
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "slot_states": before_states,
        },
        "after": {
            "screenshot": str(after_shot),
            "annotated": str(after_annotated),
            "report": str(after_report),
            "slot_states": after_states,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"driver-to-truck-slot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"DRIVER_TO_TRUCK_SLOT_REPORT: {summary_path}")
    print("DRIVER_TRUCK_SLOT_SUCCEEDED: waiting-truck slot selected; OK not clicked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
