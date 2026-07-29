"""Return from a recognized ETS2 workflow screen to the verified home UI."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_truck_ui_dry_run import load_truck_references, recognize as recognize_truck
from ets2_ui_dry_run import analyze as recognize_recruitment
from ets2_ui_dry_run import capture_direct, load_references as load_recruitment_references
from ets2_ui_open_services_probe import load_home_reference, recognize_home
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


HOME_TARGET = (201, 34)
ALLOWED_TRUCK_STATES = {"dealer_map", "truck_purchase"}


def recognize_supported_source(image) -> dict:
    """Recognize only workflow screens whose Home control is calibrated."""

    recruitment = recognize_recruitment(image, load_recruitment_references())
    if recruitment.get("state") == "recruitment_agency" and recruitment.get(
        "safe_to_act"
    ):
        return {**recruitment, "workflow": "recruitment"}
    truck = recognize_truck(image, load_truck_references())
    if truck.get("state") in ALLOWED_TRUCK_STATES and truck.get("safe_to_act"):
        return {**truck, "workflow": "truck"}
    return {
        "state": "unknown",
        "safe_to_act": False,
        "recruitment_analysis": recruitment,
        "truck_analysis": truck,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--after-settle", type=float, default=1.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-return-home",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    print(
        f"Return-home probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It clicks the top Home icon only from a recognized workflow screen."
    )
    time.sleep(args.delay)
    before_shot, before_image, before_ms = capture_direct(output_dir)
    before = recognize_supported_source(before_image)
    if not before.get("safe_to_act"):
        print(f"RETURN_HOME_ABORTED: unsupported starting screen: {before}")
        return 2
    set_pointer(HOME_TARGET)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(args.after_settle)
    after_shot, after_image, after_ms = capture_direct(output_dir)
    after = recognize_home(after_image, load_home_reference())
    if not after["safe_to_open_services"]:
        print(f"RETURN_HOME_FAILED: home UI not recognized afterward: {after}")
        return 3
    report = {
        "gameplay_transactions": 0,
        "keyboard_events": 0,
        "mouse_clicks": 1,
        "click_target": "Home",
        "target_position": list(HOME_TARGET),
        "before": {
            "screenshot": str(before_shot),
            "capture_duration_ms": round(before_ms, 2),
            "analysis": before,
        },
        "after": {
            "screenshot": str(after_shot),
            "capture_duration_ms": round(after_ms, 2),
            "analysis": after,
        },
    }
    report_path = output_dir / (
        f"return-home-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"RETURN_HOME_REPORT: {report_path}")
    print("RETURN_HOME_SUCCEEDED: verified home UI restored with one guarded click")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
