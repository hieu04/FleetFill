"""Open ETS2's garage-selection dialog without selecting or confirming anything."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_ui_dry_run import (
    DEFAULT_NVIDIA_SCREENSHOT_DIR,
    HIRE_BUTTON,
    load_references,
)
from ets2_ui_pointer_probe import SAFE_POINTER, capture_analyze_save, set_pointer
from ets2_ui_select_probe import click_left_once


def center(box: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = box
    return ((left + right) // 2, (top + bottom) // 2)


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
        / "live-open-garage-probe",
    )
    args = parser.parse_args()

    references = load_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Open-garage probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It will click Hire Driver only; no garage, slot, or OK click is possible."
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
        print(f"OPEN_ABORTED: unsafe starting screen: {before}")
        return 2
    if before.get("selected_driver_cards") != [1]:
        print(
            "OPEN_ABORTED: driver card 1 must already be selected, got "
            f"{before.get('selected_driver_cards')}"
        )
        return 3

    target = center(HIRE_BUTTON)
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
    if after["state"] != "garage_selection" or not after.get("safe_to_act"):
        print(f"OPEN_FAILED: garage dialog was not safely recognized: {after}")
        return 4
    slot_states = [slot["state"] for slot in after.get("slots", [])]
    if slot_states != ["locked"] * 5:
        print(f"OPEN_FAILED: expected five locked slots before garage selection: {slot_states}")
        return 5

    summary = {
        "gameplay_transactions": 0,
        "mouse_clicks": 1,
        "clicked_control": "hire_driver",
        "garage_clicked": False,
        "slot_clicked": False,
        "confirmation_clicked": False,
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
            "state": after["state"],
            "slot_states": slot_states,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"open-garage-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"OPEN_GARAGE_PROBE_REPORT: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
