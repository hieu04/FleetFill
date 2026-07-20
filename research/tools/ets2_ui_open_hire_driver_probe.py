"""Recognize the recruitment-agencies map and open the driver list."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from ets2_ui_dry_run import analyze, capture_direct, feature, load_references
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


RECRUITMENT_MAP_REFERENCE = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "live-open-recruitment-from-home-test"
    / "direct-capture-20260721-010250-822667.png"
)
RECRUITMENT_HEADER = (235, 10, 540, 57)
RECRUITMENT_MAP = (430, 122, 1803, 900)
HIRE_DRIVER_BUTTON = (780, 924, 1140, 960)
HIRE_DRIVER_TARGET = (960, 942)


def load_recruitment_map_reference() -> Image.Image:
    if not RECRUITMENT_MAP_REFERENCE.is_file():
        raise FileNotFoundError(
            f"Missing recruitment map reference: {RECRUITMENT_MAP_REFERENCE}"
        )
    return Image.open(RECRUITMENT_MAP_REFERENCE).convert("RGB")


def recognize_recruitment_map(image: Image.Image, reference: Image.Image) -> dict:
    header_distance = float(
        np.mean(
            np.abs(
                feature(image, RECRUITMENT_HEADER)
                - feature(reference, RECRUITMENT_HEADER)
            )
        )
    )
    button_distance = float(
        np.mean(
            np.abs(
                feature(image, HIRE_DRIVER_BUTTON)
                - feature(reference, HIRE_DRIVER_BUTTON)
            )
        )
    )
    map_std = float(
        np.asarray(image.crop(RECRUITMENT_MAP).convert("L"), dtype=np.float32).std()
    )
    safe = header_distance <= 0.3 and button_distance <= 0.3 and map_std >= 17.0
    return {
        "state": "recruitment_map" if safe else "unknown",
        "header_distance": round(header_distance, 4),
        "hire_button_distance": round(button_distance, 4),
        "map_standard_deviation": round(map_std, 2),
        "safe_to_open_driver_list": safe,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--after-settle", type=float, default=1.2)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-open-hire-driver",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    map_reference = load_recruitment_map_reference()
    print(
        f"Open-driver-list probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It clicks the Hire a driver button only and cannot select a driver."
    )
    time.sleep(args.delay)
    before_shot, before_image, before_ms = capture_direct(output_dir)
    before = recognize_recruitment_map(before_image, map_reference)
    if not before["safe_to_open_driver_list"]:
        print(f"OPEN_HIRE_DRIVER_ABORTED: recruitment map not recognized: {before}")
        return 2
    set_pointer(HIRE_DRIVER_TARGET)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(args.after_settle)
    after_shot, after_image, after_ms = capture_direct(output_dir)
    after = analyze(after_image, load_references())
    if after.get("state") != "recruitment_agency" or not after.get("safe_to_act"):
        print(f"OPEN_HIRE_DRIVER_FAILED: driver list not recognized: {after}")
        return 3
    report = {
        "gameplay_transactions": 0,
        "driver_card_clicks": 0,
        "hire_confirmations": 0,
        "mouse_clicks": 1,
        "click_target": "Hire a driver",
        "target_position": list(HIRE_DRIVER_TARGET),
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
        f"open-hire-driver-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"OPEN_HIRE_DRIVER_REPORT: {report_path}")
    print("OPEN_HIRE_DRIVER_SUCCEEDED: driver list opened; no driver selected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
