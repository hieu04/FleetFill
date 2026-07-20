"""Confirm one driver hire into a garage slot that already contains a truck."""

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
from ets2_ui_fleet_config_probe import center
from ets2_ui_pointer_probe import SAFE_POINTER, capture_analyze_save, set_pointer
from ets2_ui_select_probe import click_left_once


DRIVER_IDENTITY_BOX = (587, 713, 1018, 829)
GARAGE_IDENTITY_BOX = (1026, 713, 1336, 829)
MAX_IDENTITY_DISTANCE = 0.16


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity-reference", type=Path, required=True)
    parser.add_argument("--expected-driver", required=True)
    parser.add_argument("--expected-garage", required=True)
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--integrity-attempts", type=int, default=4)
    parser.add_argument("--result-attempts", type=int, default=4)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-confirm-driver-to-truck-probe",
    )
    args = parser.parse_args()
    if not args.identity_reference.is_file():
        print(f"DRIVER_TRUCK_CONFIRM_ABORTED: missing {args.identity_reference}")
        return 2

    references = load_references()
    identity_reference = Image.open(args.identity_reference).convert("RGB")
    output_dir = args.output_dir.resolve()
    print(
        f"Guarded driver-to-truck confirmation in {args.delay:.1f} seconds. "
        "One OK click is possible only after dialog, identity, and slot checks pass."
    )
    time.sleep(args.delay)

    before_shot, before, before_annotated, before_report = capture_analyze_save(
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    if before["state"] != "garage_selection" or not before.get("safe_to_act"):
        print(f"DRIVER_TRUCK_CONFIRM_ABORTED: unsafe starting screen: {before}")
        return 3
    states = [slot["state"] for slot in before.get("slots", [])]
    if (
        len(states) != 5
        or states.count("selected_free") != 1
        or any(
            state not in {"selected_free", "truck_present", "free", "occupied"}
            for state in states
        )
    ):
        print(
            "DRIVER_TRUCK_CONFIRM_ABORTED: expected exactly one selected "
            f"destination and no locked/unknown slots; got {states}"
        )
        return 4

    before_image = Image.open(before_shot).convert("RGB")
    driver_distance = patch_distance(
        before_image, DRIVER_IDENTITY_BOX, identity_reference, DRIVER_IDENTITY_BOX
    )
    garage_distance = patch_distance(
        before_image, GARAGE_IDENTITY_BOX, identity_reference, GARAGE_IDENTITY_BOX
    )
    identity_distances = {
        "driver_and_arrow_patch": round(driver_distance, 4),
        "garage_patch": round(garage_distance, 4),
    }
    if driver_distance > MAX_IDENTITY_DISTANCE or garage_distance > MAX_IDENTITY_DISTANCE:
        print(
            "DRIVER_TRUCK_CONFIRM_ABORTED: driver or garage identity changed from "
            f"the verified reference: {identity_distances}"
        )
        return 5

    target = center(GARAGE_OK)
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(1.0)

    observations = []
    final = None
    for attempt in range(1, args.result_attempts + 1):
        shot, analysis, annotated, report = capture_analyze_save(
            args.screenshot_dir,
            args.capture_timeout,
            output_dir,
            references,
            args.integrity_attempts,
        )
        observation = {
            "attempt": attempt,
            "screenshot": str(shot),
            "annotated": str(annotated),
            "report": str(report),
            "state": analysis.get("state"),
            "safe_to_act": analysis.get("safe_to_act"),
            "selected_driver_cards": analysis.get("selected_driver_cards", []),
        }
        observations.append(observation)
        if analysis["state"] == "recruitment_agency" and analysis.get("safe_to_act"):
            final = observation
            break
        time.sleep(0.8)

    summary = {
        "gameplay_transactions": 1,
        "transaction": "hire_driver_to_existing_truck",
        "expected_driver": args.expected_driver,
        "expected_garage": args.expected_garage,
        "expected_cost_eur": 1500,
        "selected_slot": states.index("selected_free") + 1,
        "mouse_clicks": 1,
        "confirmation_clicks": 1,
        "confirmation_position": list(target),
        "identity_distances": identity_distances,
        "identity_distance_limit": MAX_IDENTITY_DISTANCE,
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "slot_states": states,
        },
        "result_observations": observations,
        "final": final,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"confirm-driver-to-truck-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"CONFIRM_DRIVER_TO_TRUCK_REPORT: {summary_path}")
    if not final:
        print(
            "DRIVER_TRUCK_CONFIRM_UNCERTAIN: OK was clicked, but Recruitment Agency "
            "was not verified; no further input was sent"
        )
        return 6
    print("DRIVER_TRUCK_CONFIRM_SUCCEEDED: hire completed; Recruitment Agency recognized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
