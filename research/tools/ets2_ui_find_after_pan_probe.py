"""Pan once, then find a qualifying garage in the shifted ETS2 map view.

This research probe exercises the fallback path even when the initial view has
qualifying garages. It clicks garage markers only after a verified coherent
pan and never selects a slot or confirmation button.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_garage_icon_detector import detect_garage_markers
from ets2_truck_ui_dry_run import load_truck_references
from ets2_ui_dealer_pan_probe import dominant_marker_translation
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR, load_references
from ets2_ui_find_capacity_garage_probe import (
    capture_for_context,
    has_capacity,
    is_resolved_unselected,
    slot_counts,
)
from ets2_ui_garage_pan_probe import (
    choose_drag_pair,
    drag_map,
    marker_clearance,
)
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


def marker_is_action_safe(marker: dict, minimum_center_y: int = 250) -> bool:
    """Reject clipped/top-row icons whose city popup can occlude identity text."""
    left, top, right, bottom = marker["bounds"]
    center_x, center_y = marker["center"]
    return (
        marker["width"] >= 28
        and marker["height"] >= 28
        and center_y >= minimum_center_y
        and 650 <= center_x <= 1530
        and top >= 176
        and bottom <= 675
        and left >= 624
        and right <= 1558
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", choices=("truck", "hire"), required=True)
    parser.add_argument("--required", type=int, required=True)
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--between-markers", type=float, default=0.7)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--integrity-attempts", type=int, default=4)
    parser.add_argument("--minimum-clearance", type=float, default=70.0)
    parser.add_argument("--minimum-translation", type=int, default=80)
    parser.add_argument("--max-markers", type=int, default=30)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-find-after-pan",
    )
    args = parser.parse_args()
    if not 1 <= args.required <= 5:
        parser.error("--required must be between 1 and 5")

    references = load_truck_references() if args.context == "truck" else load_references()
    expected_state = "truck_garage_selection" if args.context == "truck" else "garage_selection"
    output_dir = args.output_dir.resolve()
    print(
        f"Pan-then-find probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It performs one verified right-drag, then marker clicks only."
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
    before_states = [slot["state"] for slot in before.get("slots", [])]
    if (
        before.get("state") != expected_state
        or not before.get("safe_to_act")
        or (
            before_states != ["locked"] * 5
            and not is_resolved_unselected(before_states)
        )
    ):
        print(f"PAN_FIND_ABORTED: unsafe starting screen: {before}")
        return 2
    before_markers = detect_garage_markers(before_image)
    if len(before_markers) < 2:
        print(f"PAN_FIND_ABORTED: need two initial markers, got {len(before_markers)}")
        return 3
    pair = choose_drag_pair(before_markers, args.minimum_clearance)
    if pair is None:
        print("PAN_FIND_ABORTED: no marker-free drag corridor")
        return 4
    drag_start, drag_end = pair
    drag_map(drag_start, drag_end, "right")
    set_pointer(SAFE_POINTER)

    shifted_shot, shifted_image, shifted, shifted_annotated, shifted_report = capture_for_context(
        args.context,
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    shifted_states = [slot["state"] for slot in shifted.get("slots", [])]
    if (
        shifted.get("state") != expected_state
        or not shifted.get("safe_to_act")
        or (
            shifted_states != ["locked"] * 5
            and not is_resolved_unselected(shifted_states)
        )
    ):
        print(f"PAN_FIND_FAILED: unsafe shifted view: {shifted}")
        return 5
    shifted_markers = detect_garage_markers(shifted_image)
    translation = dominant_marker_translation(before_markers, shifted_markers)
    if (
        translation["matched_markers"] < 2
        or max(abs(translation["dx"]), abs(translation["dy"]))
        < args.minimum_translation
    ):
        print(f"PAN_FIND_FAILED: incoherent map translation: {translation}")
        return 6
    actionable_markers = [
        marker for marker in shifted_markers if marker_is_action_safe(marker)
    ]
    if len(actionable_markers) > args.max_markers:
        print(
            f"PAN_FIND_ABORTED: {len(shifted_markers)} shifted markers exceed "
            f"the limit of {args.max_markers}"
        )
        return 7

    attempts: list[dict] = []
    found: dict | None = None
    for candidate in actionable_markers:
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
            print(f"PAN_FIND_ABORTED: unsafe result after marker {candidate}: {analysis}")
            return 8
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
            f"shifted candidate {candidate['candidate']} at {target}: "
            f"slots={states}, qualifies={attempt['qualifies']}"
        )
        if attempt["qualifies"]:
            found = attempt
            break

    set_pointer(SAFE_POINTER)
    locator = None
    if found:
        locator = {
            "pan_path": [
                {
                    "button": "right",
                    "start": list(drag_start),
                    "end": list(drag_end),
                    "requested_translation": [
                        drag_end[0] - drag_start[0],
                        drag_end[1] - drag_start[1],
                    ],
                    "observed_translation": translation,
                }
            ],
            "marker_position": found["target_position"],
            "slot_counts": found["slot_counts"],
        }
    summary = {
        "gameplay_transactions": 0,
        "context": args.context,
        "required": args.required,
        "garage_marker_clicks": len(attempts),
        "slot_clicks": 0,
        "confirmation_clicks": 0,
        "map_drags": 1,
        "initial": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "marker_count": len(before_markers),
        },
        "shifted": {
            "screenshot": str(shifted_shot),
            "annotated": str(shifted_annotated),
            "report": str(shifted_report),
            "marker_count": len(shifted_markers),
            "actionable_marker_count": len(actionable_markers),
            "translation": translation,
            "corridor_clearance": {
                "start": round(marker_clearance(drag_start, before_markers), 1),
                "end": round(marker_clearance(drag_end, before_markers), 1),
            },
        },
        "attempts": attempts,
        "found": found,
        "locator": locator,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"find-after-pan-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"FIND_AFTER_PAN_REPORT: {summary_path}")
    if not found:
        print("PAN_FIND_NOT_FOUND: shifted view had no garage with enough capacity")
        return 9
    print("PAN_FIND_SUCCEEDED: qualifying garage selected and replay locator recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
