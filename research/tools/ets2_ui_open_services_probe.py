"""Recognize the ETS2 home UI and open only the Services section."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from ets2_ui_dry_run import capture_direct, feature
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


HOME_NAV = (392, 920, 1528, 1073)
SERVICES_TILE = (1071, 920, 1184, 1073)
SERVICES_TARGET = (1128, 998)
HOME_REFERENCE = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "live-wake-home-test"
    / "direct-capture-20260721-005704-141212.png"
)


def load_home_reference() -> Image.Image:
    if not HOME_REFERENCE.is_file():
        raise FileNotFoundError(f"Missing home UI reference: {HOME_REFERENCE}")
    return Image.open(HOME_REFERENCE).convert("RGB")


def recognize_home(image: Image.Image, reference: Image.Image) -> dict:
    distance = float(
        np.mean(np.abs(feature(image, HOME_NAV) - feature(reference, HOME_NAV)))
    )
    nav_std = float(
        np.asarray(image.crop(HOME_NAV).convert("L"), dtype=np.float32).std()
    )
    return {
        "state": "home" if distance <= 0.34 and nav_std >= 38.0 else "unknown",
        "home_nav_distance": round(distance, 4),
        "home_nav_standard_deviation": round(nav_std, 2),
        "safe_to_open_services": bool(distance <= 0.34 and nav_std >= 38.0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--wake-settle", type=float, default=1.0)
    parser.add_argument("--after-settle", type=float, default=1.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-open-services",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    reference = load_home_reference()
    print(
        f"Open-Services probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It may wake the home UI and click the Services tile only."
    )
    time.sleep(args.delay)

    set_pointer(SAFE_POINTER)
    time.sleep(args.wake_settle)
    before_shot, before_image, before_ms = capture_direct(output_dir)
    before = recognize_home(before_image, reference)
    if not before["safe_to_open_services"]:
        print(f"OPEN_SERVICES_ABORTED: home UI not safely recognized: {before}")
        return 2

    set_pointer(SERVICES_TARGET)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(args.after_settle)
    after_shot, after_image, after_ms = capture_direct(output_dir)
    after_home = recognize_home(after_image, reference)
    # A successful section transition must replace the home navigation strip.
    if after_home["state"] == "home":
        print(f"OPEN_SERVICES_FAILED: home UI remained visible: {after_home}")
        return 3

    report = {
        "gameplay_transactions": 0,
        "keyboard_events": 0,
        "pointer_moves": 3,
        "mouse_clicks": 1,
        "click_target": "Services",
        "target_position": list(SERVICES_TARGET),
        "capture_method": "PIL.ImageGrab",
        "before": {
            "screenshot": str(before_shot),
            "capture_duration_ms": round(before_ms, 2),
            "analysis": before,
        },
        "after": {
            "screenshot": str(after_shot),
            "capture_duration_ms": round(after_ms, 2),
            "home_analysis": after_home,
        },
    }
    report_path = output_dir / (
        f"open-services-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"OPEN_SERVICES_REPORT: {report_path}")
    print("OPEN_SERVICES_SUCCEEDED: Services opened with one guarded click")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
