"""Guarded one-click ETS2 driver-card selection probe.

The only mouse click in this file selects driver card 1. It never clicks the
Hire Driver button, a garage, a slot, or a confirmation button.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR, load_references
from ets2_ui_pointer_probe import (
    SAFE_POINTER,
    capture_analyze_save,
    card_center,
    set_pointer,
)


MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def click_left_once() -> None:
    user32 = ctypes.windll.user32
    user32.mouse_event.argtypes = (
        ctypes.c_ulong,
        ctypes.c_long,
        ctypes.c_long,
        ctypes.c_ulong,
        ctypes.c_size_t,
    )
    user32.mouse_event.restype = None
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.06)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=15.0)
    parser.add_argument("--focus-settle", type=float, default=2.0)
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
        / "live-select-probe",
    )
    args = parser.parse_args()

    references = load_references()
    output_dir = args.output_dir.resolve()
    print(
        f"One-click selection probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It will select card 1 but will not click Hire Driver."
    )
    time.sleep(args.delay)
    time.sleep(args.focus_settle)

    before_shot, before, before_annotated, before_report = capture_analyze_save(
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    if before["state"] != "recruitment_agency" or not before.get("safe_to_act"):
        print(f"SELECTION_ABORTED: unsafe starting screen: {before}")
        return 2
    if before.get("selected_driver_cards"):
        print(
            "SELECTION_ABORTED: a card already appears selected: "
            f"{before['selected_driver_cards']}"
        )
        return 3

    target = card_center(1)
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(1.5)

    after_shot, after, after_annotated, after_report = capture_analyze_save(
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    if after["state"] != "recruitment_agency" or not after.get("safe_to_act"):
        print(f"SELECTION_FAILED: unsafe resulting screen: {after}")
        return 4
    if after.get("selected_driver_cards") != [1]:
        print(
            "SELECTION_FAILED: card 1 did not remain selected after moving away: "
            f"{after.get('selected_driver_cards')}"
        )
        return 5

    summary = {
        "gameplay_transactions": 0,
        "mouse_clicks": 1,
        "clicked_control": "driver_card_1",
        "hire_driver_clicked": False,
        "target_position": list(target),
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "selected_driver_cards": before.get("selected_driver_cards", []),
        },
        "after": {
            "screenshot": str(after_shot),
            "annotated": str(after_annotated),
            "report": str(after_report),
            "selected_driver_cards": after.get("selected_driver_cards", []),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"select-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"SELECT_PROBE_REPORT: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
