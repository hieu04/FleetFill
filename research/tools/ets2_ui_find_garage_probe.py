"""Guarded dynamic-map probe that locates a garage by its slot pattern.

This probe may click detected garage markers, which only changes the selected
garage in the modal.  It has no slot or OK target and therefore cannot complete
a hire.  For the disposable test profile, Lyon is identified by one occupied
driver slot plus four free slots.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

from ets2_garage_icon_detector import detect_garage_markers
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR, load_references
from ets2_ui_pointer_probe import SAFE_POINTER, capture_analyze_save, set_pointer
from ets2_ui_select_probe import click_left_once


def is_one_occupied_four_free(slot_states: list[str]) -> bool:
    return (
        len(slot_states) == 5
        and slot_states.count("occupied") == 1
        and slot_states.count("free") == 4
        and slot_states.count("selected_free") == 0
        and slot_states.count("locked") == 0
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=12.0)
    parser.add_argument("--focus-settle", type=float, default=2.0)
    parser.add_argument("--between-markers", type=float, default=0.8)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--integrity-attempts", type=int, default=4)
    parser.add_argument("--max-markers", type=int, default=20)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-find-garage-probe",
    )
    args = parser.parse_args()

    references = load_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Dynamic-garage probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It can click garage map markers only; it has no slot or OK target."
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
        print(f"FIND_ABORTED: unsafe starting screen: {before}")
        return 2
    initial_slot_states = [slot["state"] for slot in before.get("slots", [])]
    allowed_initial_states = {"locked", "free", "occupied"}
    if (
        len(initial_slot_states) != 5
        or any(state not in allowed_initial_states for state in initial_slot_states)
    ):
        print(
            "FIND_ABORTED: starting state must have no selected destination slot; got "
            f"{initial_slot_states}"
        )
        return 3

    if is_one_occupied_four_free(initial_slot_states):
        print("FIND_SUCCEEDED: matching garage was already selected; no click needed")
        return 0

    source_image = Image.open(before_shot).convert("RGB")
    candidates = detect_garage_markers(source_image)
    if not candidates:
        print("FIND_ABORTED: no safe garage-marker candidates detected")
        return 4
    if len(candidates) > args.max_markers:
        print(
            f"FIND_ABORTED: detected {len(candidates)} markers, exceeding the "
            f"guard limit of {args.max_markers}"
        )
        return 5

    attempts = []
    found = None
    for candidate in candidates:
        target = tuple(candidate["center"])
        set_pointer(target)
        click_left_once()
        set_pointer(SAFE_POINTER)
        time.sleep(args.between_markers)

        shot, analysis, annotated, report = capture_analyze_save(
            args.screenshot_dir,
            args.capture_timeout,
            output_dir,
            references,
            args.integrity_attempts,
        )
        if analysis["state"] != "garage_selection" or not analysis.get("safe_to_act"):
            print(
                "FIND_ABORTED: UI left the safely recognized garage modal after "
                f"candidate {candidate['candidate']}: {analysis}"
            )
            return 6
        slot_states = [slot["state"] for slot in analysis.get("slots", [])]
        attempt = {
            "candidate": candidate["candidate"],
            "target_position": list(target),
            "slot_states": slot_states,
            "screenshot": str(shot),
            "annotated": str(annotated),
            "report": str(report),
        }
        attempts.append(attempt)
        print(
            f"candidate {candidate['candidate']} at {target}: slots={slot_states}"
        )
        if is_one_occupied_four_free(slot_states):
            found = attempt
            break

    set_pointer(SAFE_POINTER)
    summary = {
        "gameplay_transactions": 0,
        "garage_marker_clicks": len(attempts),
        "slot_clicks": 0,
        "confirmation_clicks": 0,
        "target_pattern": ["one occupied", "four free"],
        "detected_candidate_count": len(candidates),
        "initial": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "slot_states": initial_slot_states,
        },
        "attempts": attempts,
        "found": found,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"find-garage-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"FIND_GARAGE_PROBE_REPORT: {summary_path}")
    if not found:
        print("FIND_NOT_FOUND: no marker produced one occupied plus four free slots")
        return 7
    print(
        "FIND_SUCCEEDED: matching garage is selected, but no slot or OK was clicked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
