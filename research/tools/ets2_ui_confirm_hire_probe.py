"""Perform one guarded hire confirmation on the disposable ETS2 profile."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

from ets2_ui_dry_run import (
    DEFAULT_NVIDIA_SCREENSHOT_DIR,
    GARAGE_OK,
    load_references,
    patch_distance,
)
from ets2_ui_pointer_probe import SAFE_POINTER, capture_analyze_save, set_pointer
from ets2_ui_select_probe import click_left_once


DRIVER_NAME_BOX = (585, 713, 775, 828)
GARAGE_NAME_BOX = (1150, 713, 1325, 828)
MAX_IDENTITY_DISTANCE = 0.20


def center(box: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = box
    return ((left + right) // 2, (top + bottom) // 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument("--focus-settle", type=float, default=2.0)
    parser.add_argument("--post-click-settle", type=float, default=1.5)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--integrity-attempts", type=int, default=4)
    parser.add_argument(
        "--identity-reference",
        type=Path,
        required=True,
        help="Verified pre-confirmation screenshot used to guard driver/garage identity",
    )
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-confirm-hire-probe",
    )
    args = parser.parse_args()

    if not args.identity_reference.is_file():
        print(
            "CONFIRM_ABORTED: missing verified identity reference "
            f"{args.identity_reference}"
        )
        return 2

    references = load_references()
    identity_reference = Image.open(args.identity_reference).convert("RGB")
    output_dir = args.output_dir.resolve()
    print(
        f"Guarded confirmation in {args.delay:.1f} seconds. Return to ETS2. "
        "One OK click is possible only after every Lyon/Ronald/slot check passes."
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
        print(f"CONFIRM_ABORTED: unsafe starting screen: {before}")
        return 3

    before_states = [slot["state"] for slot in before.get("slots", [])]
    expected_states = ["occupied", "selected_free", "free", "free", "free"]
    if before_states != expected_states:
        print(
            f"CONFIRM_ABORTED: expected slots {expected_states}, got {before_states}"
        )
        return 4

    before_image = Image.open(before_shot).convert("RGB")
    driver_distance = patch_distance(
        before_image, DRIVER_NAME_BOX, identity_reference, DRIVER_NAME_BOX
    )
    garage_distance = patch_distance(
        before_image, GARAGE_NAME_BOX, identity_reference, GARAGE_NAME_BOX
    )
    identity_distances = {
        "ronald_driver_patch": round(driver_distance, 4),
        "lyon_garage_patch": round(garage_distance, 4),
    }
    if (
        driver_distance > MAX_IDENTITY_DISTANCE
        or garage_distance > MAX_IDENTITY_DISTANCE
    ):
        print(
            "CONFIRM_ABORTED: driver or garage identity did not match the verified "
            f"Ronald/Lyon reference: {identity_distances}"
        )
        return 5

    target = center(GARAGE_OK)
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(args.post_click_settle)

    after_shot, after, after_annotated, after_report = capture_analyze_save(
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    if after["state"] != "recruitment_agency" or not after.get("safe_to_act"):
        print(
            "CONFIRM_UNCERTAIN: OK was clicked, but the expected Recruitment Agency "
            f"screen was not safely recognized: {after}"
        )
        return 6

    summary = {
        "gameplay_transactions": 1,
        "transaction": "hire_driver",
        "expected_driver": "Ronald R.",
        "expected_garage": "Lyon",
        "expected_slot": 2,
        "mouse_clicks": 1,
        "confirmation_clicks": 1,
        "confirmation_position": list(target),
        "identity_distances": identity_distances,
        "identity_distance_limit": MAX_IDENTITY_DISTANCE,
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
            "state": after["state"],
            "selected_driver_cards": after.get("selected_driver_cards", []),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"confirm-hire-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"CONFIRM_HIRE_PROBE_REPORT: {summary_path}")
    print("CONFIRM_SUCCEEDED: one hire completed and Recruitment Agency recognized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
