"""Wake ETS2's faded home UI using pointer movement only."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_ui_dry_run import capture_direct, foreground_window_title
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--settle", type=float, default=1.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-wake-home",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    print(
        f"Home wake-up probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It moves the pointer to the far-left edge and performs no click."
    )
    time.sleep(args.delay)
    if "Euro Truck Simulator 2" not in foreground_window_title():
        print("WAKE_HOME_ABORTED: ETS2 is not foreground")
        return 2
    set_pointer(SAFE_POINTER)
    time.sleep(args.settle)
    screenshot, _image, capture_ms = capture_direct(output_dir)
    report = {
        "gameplay_transactions": 0,
        "keyboard_events": 0,
        "mouse_button_events": 0,
        "pointer_moves": 1,
        "pointer_target": list(SAFE_POINTER),
        "capture_method": "PIL.ImageGrab",
        "capture_duration_ms": round(capture_ms, 2),
        "screenshot": str(screenshot),
    }
    report_path = output_dir / (
        f"wake-home-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"WAKE_HOME_REPORT: {report_path}")
    print("WAKE_HOME_SUCCEEDED: pointer moved with zero clicks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
