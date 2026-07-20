"""Reveal the ETS2 Services fly-out using pointer movement only."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_ui_dry_run import capture_direct
from ets2_ui_open_services_probe import (
    SERVICES_TARGET,
    load_home_reference,
    recognize_home,
)
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--wake-settle", type=float, default=0.8)
    parser.add_argument("--hover-settle", type=float, default=1.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-hover-services",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    reference = load_home_reference()
    print(
        f"Services-hover probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It moves the pointer only and performs no click."
    )
    time.sleep(args.delay)
    set_pointer(SAFE_POINTER)
    time.sleep(args.wake_settle)
    before_shot, before_image, before_ms = capture_direct(output_dir)
    before = recognize_home(before_image, reference)
    if not before["safe_to_open_services"]:
        print(f"HOVER_SERVICES_ABORTED: home UI not recognized: {before}")
        return 2
    set_pointer(SERVICES_TARGET)
    time.sleep(args.hover_settle)
    after_shot, _after_image, after_ms = capture_direct(output_dir)
    report = {
        "gameplay_transactions": 0,
        "keyboard_events": 0,
        "mouse_clicks": 0,
        "pointer_moves": 2,
        "hover_target": "Services",
        "target_position": list(SERVICES_TARGET),
        "before": {
            "screenshot": str(before_shot),
            "capture_duration_ms": round(before_ms, 2),
            "analysis": before,
        },
        "after": {
            "screenshot": str(after_shot),
            "capture_duration_ms": round(after_ms, 2),
        },
    }
    report_path = output_dir / (
        f"hover-services-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"HOVER_SERVICES_REPORT: {report_path}")
    print("HOVER_SERVICES_SUCCEEDED: Services hovered with zero clicks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
