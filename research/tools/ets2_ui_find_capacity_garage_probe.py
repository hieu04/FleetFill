"""Select the first visible ETS2 garage with enough usable capacity.

This guarded discovery probe may click garage markers only. It cannot click a
garage slot or the confirmation button, so it cannot purchase or hire.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

from ets2_garage_icon_detector import detect_garage_markers
from ets2_truck_ui_dry_run import load_truck_references
from ets2_ui_dealer_pan_probe import capture_analyze as capture_truck
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR, load_references
from ets2_ui_pointer_probe import SAFE_POINTER, capture_analyze_save, set_pointer
from ets2_ui_select_probe import click_left_once


VALID_UNSELECTED_STATES = {"occupied", "truck_present", "free"}


def slot_counts(states: list[str]) -> dict[str, int]:
    return {
        "occupied": states.count("occupied"),
        "truck_present": states.count("truck_present"),
        "free": states.count("free"),
    }


def is_resolved_unselected(states: list[str]) -> bool:
    return len(states) == 5 and all(state in VALID_UNSELECTED_STATES for state in states)


def has_capacity(states: list[str], context: str, required: int) -> bool:
    if not is_resolved_unselected(states):
        return False
    counts = slot_counts(states)
    available = counts["free"] if context == "truck" else counts["truck_present"]
    return available >= required


def capture_for_context(
    context: str,
    screenshot_dir: Path,
    timeout: float,
    output_dir: Path,
    references,
    integrity_attempts: int,
) -> tuple[Path, Image.Image, dict, Path, Path]:
    if context == "truck":
        return capture_truck(screenshot_dir, timeout, output_dir, references)
    shot, analysis, annotated, report = capture_analyze_save(
        screenshot_dir,
        timeout,
        output_dir,
        references,
        integrity_attempts,
    )
    return shot, Image.open(shot).convert("RGB"), analysis, annotated, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", choices=("truck", "hire"), required=True)
    parser.add_argument("--required", type=int, required=True)
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument("--between-markers", type=float, default=0.7)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--integrity-attempts", type=int, default=4)
    parser.add_argument("--max-markers", type=int, default=30)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-find-capacity-garage",
    )
    args = parser.parse_args()
    if not 1 <= args.required <= 5:
        parser.error("--required must be between 1 and 5")

    references = load_truck_references() if args.context == "truck" else load_references()
    expected_state = "truck_garage_selection" if args.context == "truck" else "garage_selection"
    output_dir = args.output_dir.resolve()
    capacity_kind = "free slots" if args.context == "truck" else "driverless trucks"
    print(
        f"Capacity-garage finder in {args.delay:.1f} seconds. Return to ETS2. "
        f"It requires {args.required} {capacity_kind}; marker clicks only."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_for_context(
        args.context,
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    if before.get("state") != expected_state or not before.get("safe_to_act"):
        print(f"FIND_CAPACITY_ABORTED: unsafe starting screen: {before}")
        return 2
    initial_states = [slot["state"] for slot in before.get("slots", [])]
    if initial_states != ["locked"] * 5 and not is_resolved_unselected(initial_states):
        print(
            "FIND_CAPACITY_ABORTED: starting slots were neither locked nor a "
            f"resolved unselected garage: {initial_states}"
        )
        return 3

    candidates = detect_garage_markers(before_image)
    if not candidates:
        print("FIND_CAPACITY_NOT_VISIBLE: no safe garage-marker candidates detected")
    if len(candidates) > args.max_markers:
        print(
            f"FIND_CAPACITY_ABORTED: {len(candidates)} markers exceed the guard "
            f"limit of {args.max_markers}"
        )
        return 5

    attempts: list[dict] = []
    found: dict | None = None
    for candidate in candidates:
        target = tuple(candidate["center"])
        set_pointer(target)
        click_left_once()
        set_pointer(SAFE_POINTER)
        time.sleep(args.between_markers)
        shot, _image, analysis, annotated, report = capture_for_context(
            args.context,
            args.screenshot_dir,
            args.capture_timeout,
            output_dir,
            references,
            args.integrity_attempts,
        )
        if analysis.get("state") != expected_state or not analysis.get("safe_to_act"):
            print(
                "FIND_CAPACITY_ABORTED: UI left the recognized garage dialog "
                f"after candidate {candidate['candidate']}: {analysis}"
            )
            return 6
        states = [slot["state"] for slot in analysis.get("slots", [])]
        attempt = {
            "candidate": candidate["candidate"],
            "marker": candidate,
            "target_position": list(target),
            "slot_states": states,
            "slot_counts": slot_counts(states) if is_resolved_unselected(states) else None,
            "qualifies": has_capacity(states, args.context, args.required),
            "screenshot": str(shot),
            "annotated": str(annotated),
            "report": str(report),
        }
        attempts.append(attempt)
        print(
            f"candidate {candidate['candidate']} at {target}: "
            f"slots={states}, qualifies={attempt['qualifies']}"
        )
        if attempt["qualifies"]:
            found = attempt
            break

    set_pointer(SAFE_POINTER)
    summary = {
        "gameplay_transactions": 0,
        "context": args.context,
        "required": args.required,
        "capacity_kind": capacity_kind,
        "garage_marker_clicks": len(attempts),
        "slot_clicks": 0,
        "confirmation_clicks": 0,
        "detected_candidate_count": len(candidates),
        "initial": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "slot_states": initial_states,
        },
        "attempts": attempts,
        "found": found,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"find-capacity-garage-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"FIND_CAPACITY_GARAGE_REPORT: {summary_path}")
    if not found:
        print("FIND_CAPACITY_NOT_VISIBLE: no visible garage had enough capacity")
        return 7
    print(
        "FIND_CAPACITY_SUCCEEDED: a qualifying garage is selected; no slot or "
        "confirmation button was clicked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
