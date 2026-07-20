"""Perform one guarded truck purchase on the disposable ETS2 profile."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

from ets2_truck_ui_dry_run import load_truck_references, patch_distance
from ets2_ui_dealer_pan_probe import capture_analyze
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR, GARAGE_OK
from ets2_ui_fleet_config_probe import center
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


TRUCK_IDENTITY_BOX = (587, 713, 1018, 829)
GARAGE_IDENTITY_BOX = (1026, 713, 1336, 829)
MAX_IDENTITY_DISTANCE = 0.16


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity-reference", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--post-click-settle", type=float, default=1.2)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--result-attempts", type=int, default=4)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-confirm-truck-purchase-probe",
    )
    args = parser.parse_args()
    if not args.identity_reference.is_file():
        print(f"TRUCK_CONFIRM_ABORTED: missing identity reference {args.identity_reference}")
        return 2

    references = load_truck_references()
    identity_reference = Image.open(args.identity_reference).convert("RGB")
    output_dir = args.output_dir.resolve()
    print(
        f"Guarded truck confirmation in {args.delay:.1f} seconds. Return to ETS2. "
        "One OK click is possible only after every dialog, identity, and slot check passes."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if before["state"] != "truck_garage_selection" or not before.get("safe_to_act"):
        print(f"TRUCK_CONFIRM_ABORTED: unsafe starting screen: {before}")
        return 3
    states = [slot["state"] for slot in before.get("slots", [])]
    if (
        len(states) != 5
        or states.count("selected_free") != 1
        or any(
            state not in {"selected_free", "free", "occupied", "truck_present"}
            for state in states
        )
    ):
        print(
            "TRUCK_CONFIRM_ABORTED: expected exactly one selected destination and "
            f"no locked/unknown slots; got {states}"
        )
        return 4

    truck_distance = patch_distance(
        before_image, TRUCK_IDENTITY_BOX, identity_reference, TRUCK_IDENTITY_BOX
    )
    garage_distance = patch_distance(
        before_image, GARAGE_IDENTITY_BOX, identity_reference, GARAGE_IDENTITY_BOX
    )
    identity_distances = {
        "truck_and_arrow_patch": round(truck_distance, 4),
        "garage_patch": round(garage_distance, 4),
    }
    if (
        truck_distance > MAX_IDENTITY_DISTANCE
        or garage_distance > MAX_IDENTITY_DISTANCE
    ):
        print(
            "TRUCK_CONFIRM_ABORTED: truck or garage identity changed from the "
            f"verified pre-confirmation reference: {identity_distances}"
        )
        return 5

    target = center(GARAGE_OK)
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(args.post_click_settle)

    result_observations = []
    final = None
    for attempt in range(1, args.result_attempts + 1):
        shot, image, analysis, annotated, report = capture_analyze(
            args.screenshot_dir, args.capture_timeout, output_dir, references
        )
        observation = {
            "attempt": attempt,
            "screenshot": str(shot),
            "annotated": str(annotated),
            "report": str(report),
            "state": analysis.get("state"),
            "safe_to_act": analysis.get("safe_to_act"),
            "visual_integrity": analysis.get("visual_integrity"),
        }
        result_observations.append(observation)
        if analysis["state"] == "truck_purchase_success_prompt" and analysis.get(
            "safe_to_act"
        ):
            final = observation
            break
        time.sleep(0.8)

    summary = {
        "gameplay_transactions": 1,
        "transaction": "purchase_truck",
        "expected_truck": "Scania Streamline Topline",
        "expected_price_eur": 248485,
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
        "result_observations": result_observations,
        "final": final,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"confirm-truck-purchase-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"CONFIRM_TRUCK_PURCHASE_REPORT: {summary_path}")
    if not final:
        print(
            "TRUCK_CONFIRM_UNCERTAIN: OK was clicked, but the purchase-success "
            "prompt was not recognized; no further input was sent"
        )
        return 6
    print("TRUCK_CONFIRM_SUCCEEDED: one truck purchased; success prompt recognized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
