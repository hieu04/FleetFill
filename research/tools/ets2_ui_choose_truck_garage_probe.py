"""Choose the best visible ETS2 truck garage without selecting a slot or OK."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_garage_icon_detector import detect_garage_markers
from ets2_truck_ui_dry_run import load_truck_references
from ets2_ui_dealer_pan_probe import capture_analyze
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR, GARAGE_MAP
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


def slot_states(analysis: dict) -> list[str]:
    return [slot["state"] for slot in analysis.get("slots", [])]


def free_count(states: list[str]) -> int:
    return states.count("free") + states.count("selected_free")


def is_unclipped(candidate: dict) -> bool:
    left, top, right, bottom = candidate["bounds"]
    map_left, map_top, map_right, map_bottom = GARAGE_MAP
    return (
        left >= map_left + 3
        and top >= map_top + 3
        and right <= map_right - 3
        and bottom <= map_bottom - 3
        and candidate["width"] >= 30
        and candidate["height"] >= 30
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--between-markers", type=float, default=0.6)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--max-markers", type=int, default=15)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-choose-truck-garage-probe",
    )
    args = parser.parse_args()
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Best-visible-garage probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It can click garage markers only; it has no slot or OK target."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if before["state"] != "truck_garage_selection" or not before.get("safe_to_act"):
        print(f"CHOOSE_GARAGE_ABORTED: unsafe starting screen: {before}")
        return 2
    initial_states = slot_states(before)
    if len(initial_states) != 5 or "selected_free" in initial_states:
        print(
            "CHOOSE_GARAGE_ABORTED: a destination slot may already be selected; "
            f"states={initial_states}"
        )
        return 3

    detected = detect_garage_markers(before_image)
    candidates = [candidate for candidate in detected if is_unclipped(candidate)]
    if not candidates:
        print("CHOOSE_GARAGE_ABORTED: no safe unclipped garage markers detected")
        return 4
    if len(candidates) > args.max_markers:
        print(
            f"CHOOSE_GARAGE_ABORTED: {len(candidates)} safe markers exceed guard "
            f"limit {args.max_markers}"
        )
        return 5

    attempts = []
    best = None
    for candidate in candidates:
        target = tuple(candidate["center"])
        set_pointer(target)
        click_left_once()
        set_pointer(SAFE_POINTER)
        time.sleep(args.between_markers)
        shot, image, analysis, annotated, report = capture_analyze(
            args.screenshot_dir, args.capture_timeout, output_dir, references
        )
        if analysis["state"] != "truck_garage_selection" or not analysis.get(
            "safe_to_act"
        ):
            print(
                "CHOOSE_GARAGE_ABORTED: UI was not safely recognized after "
                f"candidate {candidate['candidate']}: {analysis}"
            )
            return 6
        states = slot_states(analysis)
        if len(states) != 5 or any(
            state not in {"free", "occupied", "truck_present", "locked"}
            for state in states
        ):
            print(
                "CHOOSE_GARAGE_ABORTED: unexpected slot state after candidate "
                f"{candidate['candidate']}: {states}"
            )
            return 7
        attempt = {
            "candidate": candidate["candidate"],
            "target_position": list(target),
            "slot_states": states,
            "free_slots": free_count(states),
            "screenshot": str(shot),
            "annotated": str(annotated),
            "report": str(report),
        }
        attempts.append(attempt)
        print(
            f"candidate {candidate['candidate']} at {target}: "
            f"free={attempt['free_slots']} slots={states}"
        )
        if best is None or attempt["free_slots"] > best["free_slots"]:
            best = attempt
        if attempt["free_slots"] == 5:
            break

    if best is None or best["free_slots"] == 0:
        print("CHOOSE_GARAGE_NOT_FOUND: visible markers have no free truck slot")
        return 8

    selected_candidate = attempts[-1]["candidate"]
    reselection = None
    if best["candidate"] != selected_candidate:
        candidate = next(
            item for item in candidates if item["candidate"] == best["candidate"]
        )
        target = tuple(candidate["center"])
        set_pointer(target)
        click_left_once()
        set_pointer(SAFE_POINTER)
        time.sleep(args.between_markers)
        shot, image, analysis, annotated, report = capture_analyze(
            args.screenshot_dir, args.capture_timeout, output_dir, references
        )
        states = slot_states(analysis)
        if (
            analysis["state"] != "truck_garage_selection"
            or not analysis.get("safe_to_act")
            or states != best["slot_states"]
        ):
            print(
                "CHOOSE_GARAGE_ABORTED: best-candidate reselection failed; "
                f"expected={best['slot_states']} actual={states}"
            )
            return 9
        reselection = {
            "target_position": list(target),
            "slot_states": states,
            "screenshot": str(shot),
            "annotated": str(annotated),
            "report": str(report),
        }

    set_pointer(SAFE_POINTER)
    summary = {
        "gameplay_transactions": 0,
        "detected_markers": len(detected),
        "safe_unclipped_markers": len(candidates),
        "garage_marker_clicks": len(attempts) + (1 if reselection else 0),
        "slot_clicks": 0,
        "ok_clicks": 0,
        "policy": "first empty visible garage, otherwise most free slots",
        "initial": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "slot_states": initial_states,
        },
        "attempts": attempts,
        "best": best,
        "reselection": reselection,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"choose-truck-garage-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"CHOOSE_TRUCK_GARAGE_REPORT: {summary_path}")
    print(
        f"CHOOSE_GARAGE_SUCCEEDED: candidate {best['candidate']} selected with "
        f"{best['free_slots']} free slots; no slot or OK clicked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
