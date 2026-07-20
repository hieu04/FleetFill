"""Replay a recorded garage-map pan locator without making a transaction.

The probe requires a freshly opened, unselected garage map. It verifies the
screen, replays the recorded right-drag, confirms coherent map motion, finds
the recorded marker again within a bounded tolerance, clicks only that marker,
and verifies the expected unselected slot layout. It never clicks a slot or OK.
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
from ets2_ui_find_after_pan_probe import marker_is_action_safe
from ets2_ui_find_capacity_garage_probe import (
    capture_for_context,
    is_resolved_unselected,
    slot_counts,
)
from ets2_ui_garage_pan_probe import drag_map
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


def nearest_marker(
    markers: list[dict], target: tuple[int, int], tolerance: float
) -> tuple[dict | None, float | None]:
    """Return the closest action-safe marker when it is within tolerance."""
    candidates = [marker for marker in markers if marker_is_action_safe(marker)]
    if not candidates:
        return None, None
    marker = min(
        candidates,
        key=lambda item: (item["center"][0] - target[0]) ** 2
        + (item["center"][1] - target[1]) ** 2,
    )
    distance = (
        (marker["center"][0] - target[0]) ** 2
        + (marker["center"][1] - target[1]) ** 2
    ) ** 0.5
    if distance > tolerance:
        return None, distance
    return marker, distance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locator-report", type=Path, required=True)
    parser.add_argument("--context", choices=("truck", "hire"), required=True)
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--between-actions", type=float, default=0.8)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--integrity-attempts", type=int, default=4)
    parser.add_argument("--marker-tolerance", type=float, default=18.0)
    parser.add_argument("--translation-tolerance", type=int, default=18)
    parser.add_argument("--expected-occupied", type=int)
    parser.add_argument("--expected-truck-present", type=int)
    parser.add_argument("--expected-free", type=int)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-replay-pan-locator",
    )
    args = parser.parse_args()

    source = json.loads(args.locator_report.resolve().read_text(encoding="utf-8"))
    locator = source.get("locator")
    if not locator or len(locator.get("pan_path", [])) != 1:
        print("REPLAY_ABORTED: report has no single-step pan locator")
        return 2
    pan = locator["pan_path"][0]
    if pan.get("button") != "right":
        print("REPLAY_ABORTED: only a recorded right-drag is accepted")
        return 3
    start = tuple(pan["start"])
    end = tuple(pan["end"])
    recorded_position = tuple(locator["marker_position"])
    override_values = (
        args.expected_occupied,
        args.expected_truck_present,
        args.expected_free,
    )
    if any(value is not None for value in override_values):
        if any(value is None for value in override_values):
            parser.error("all three --expected-* slot counts must be supplied together")
        expected_counts = {
            "occupied": args.expected_occupied,
            "truck_present": args.expected_truck_present,
            "free": args.expected_free,
        }
    else:
        expected_counts = locator["slot_counts"]

    references = load_truck_references() if args.context == "truck" else load_references()
    expected_state = "truck_garage_selection" if args.context == "truck" else "garage_selection"
    output_dir = args.output_dir.resolve()
    print(
        f"Pan-locator replay in {args.delay:.1f} seconds. Return to ETS2. "
        "It replays one verified drag and one garage-marker click only."
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
    if (
        before.get("state") != expected_state
        or not before.get("safe_to_act")
        or [slot["state"] for slot in before.get("slots", [])] != ["locked"] * 5
    ):
        print(f"REPLAY_ABORTED: unsafe starting screen: {before}")
        return 4
    before_markers = detect_garage_markers(before_image)
    if len(before_markers) < 2:
        print(f"REPLAY_ABORTED: need two initial markers, got {len(before_markers)}")
        return 5

    drag_map(start, end, "right")
    set_pointer(SAFE_POINTER)
    shifted_shot, shifted_image, shifted, shifted_annotated, shifted_report = capture_for_context(
        args.context,
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    if (
        shifted.get("state") != expected_state
        or not shifted.get("safe_to_act")
        or [slot["state"] for slot in shifted.get("slots", [])] != ["locked"] * 5
    ):
        print(f"REPLAY_FAILED: unsafe shifted screen: {shifted}")
        return 6
    shifted_markers = detect_garage_markers(shifted_image)
    translation = dominant_marker_translation(before_markers, shifted_markers)
    recorded_translation = pan["observed_translation"]
    if (
        translation["matched_markers"] < 2
        or abs(translation["dx"] - recorded_translation["dx"])
        > args.translation_tolerance
        or abs(translation["dy"] - recorded_translation["dy"])
        > args.translation_tolerance
    ):
        print(
            "REPLAY_FAILED: current map motion does not match the recorded pan: "
            f"current={translation}, recorded={recorded_translation}"
        )
        return 7

    marker, marker_distance = nearest_marker(
        shifted_markers, recorded_position, args.marker_tolerance
    )
    if marker is None:
        print(
            "REPLAY_FAILED: recorded garage marker was not reproduced; "
            f"nearest distance={marker_distance}"
        )
        return 8
    set_pointer(tuple(marker["center"]))
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(args.between_actions)

    selected_shot, _selected_image, selected, selected_annotated, selected_report = capture_for_context(
        args.context,
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    states = [slot["state"] for slot in selected.get("slots", [])]
    actual_counts = slot_counts(states) if is_resolved_unselected(states) else None
    if (
        selected.get("state") != expected_state
        or not selected.get("safe_to_act")
        or actual_counts != expected_counts
    ):
        print(
            "REPLAY_FAILED: selected garage did not reproduce the recorded slots: "
            f"states={states}, counts={actual_counts}, expected={expected_counts}"
        )
        return 9

    summary = {
        "gameplay_transactions": 0,
        "context": args.context,
        "garage_marker_clicks": 1,
        "slot_clicks": 0,
        "confirmation_clicks": 0,
        "map_drags": 1,
        "source_locator_report": str(args.locator_report.resolve()),
        "recorded_marker_position": list(recorded_position),
        "replayed_marker": marker,
        "marker_distance": marker_distance,
        "expected_slot_counts": expected_counts,
        "actual_slot_counts": actual_counts,
        "translation": translation,
        "before": {
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
        },
        "selected": {
            "screenshot": str(selected_shot),
            "annotated": str(selected_annotated),
            "report": str(selected_report),
            "slot_states": states,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"replay-pan-locator-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"REPLAY_PAN_LOCATOR_REPORT: {summary_path}")
    print(
        "REPLAY_PAN_LOCATOR_SUCCEEDED: recorded garage and slot capacity reproduced; "
        "no slot or confirmation clicked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
