"""Select one visually verified free garage slot without confirming the hire."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_ui_dry_run import (
    DEFAULT_NVIDIA_SCREENSHOT_DIR,
    GARAGE_SLOTS,
    load_references,
)
from ets2_ui_pointer_probe import SAFE_POINTER, capture_analyze_save, set_pointer
from ets2_ui_select_probe import click_left_once


def center(box: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = box
    return ((left + right) // 2, (top + bottom) // 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=10.0)
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
        / "live-slot-probe",
    )
    args = parser.parse_args()

    references = load_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Free-slot probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It can click one verified free slot only; it has no OK target."
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
    if before["state"] != "garage_selection" or not before.get("safe_to_act"):
        print(f"SLOT_ABORTED: unsafe starting screen: {before}")
        return 2
    before_states = [slot["state"] for slot in before.get("slots", [])]
    if before_states != ["occupied", "free", "free", "free", "free"]:
        print(
            "SLOT_ABORTED: expected Lyon's occupied-plus-four-free layout, got "
            f"{before_states}"
        )
        return 3

    free_index = before_states.index("free")
    target = center(GARAGE_SLOTS[free_index])
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(1.0)

    after_shot, after, after_annotated, after_report = capture_analyze_save(
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    if after["state"] != "garage_selection" or not after.get("safe_to_act"):
        print(f"SLOT_FAILED: garage dialog was not safely recognized: {after}")
        return 4
    after_states = [slot["state"] for slot in after.get("slots", [])]
    expected_after = ["occupied", "selected_free", "free", "free", "free"]
    if after_states != expected_after:
        print(f"SLOT_FAILED: expected {expected_after}, got {after_states}")
        return 5

    summary = {
        "gameplay_transactions": 0,
        "garage_marker_clicks": 0,
        "slot_clicks": 1,
        "confirmation_clicks": 0,
        "selected_slot": free_index + 1,
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
        f"slot-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"SLOT_PROBE_REPORT: {summary_path}")
    print("SLOT_SUCCEEDED: free slot selected, but OK was not clicked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
