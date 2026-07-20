"""Acknowledge ETS2's purchase-success prompt and no other control."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_truck_ui_dry_run import PURCHASE_SUCCESS_OK, load_truck_references
from ets2_ui_dealer_pan_probe import capture_analyze
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR
from ets2_ui_fleet_config_probe import center
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=8.0)
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
        / "live-ack-purchase-prompt-probe",
    )
    args = parser.parse_args()
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Purchase-prompt acknowledgement in {args.delay:.1f} seconds. Return to "
        "ETS2. It can click the success popup OK only."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if (
        before["state"] != "truck_purchase_success_prompt"
        or not before.get("safe_to_act")
    ):
        print(f"ACK_PURCHASE_ABORTED: success prompt was not verified: {before}")
        return 2

    target = center(PURCHASE_SUCCESS_OK)
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(0.8)

    observations = []
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
        observations.append(observation)
        if analysis["state"] == "truck_purchase" and analysis.get("safe_to_act"):
            final = observation
            break
        time.sleep(0.8)

    summary = {
        "gameplay_transactions": 0,
        "success_prompt_ok_clicks": 1,
        "other_clicks": 0,
        "target_position": list(target),
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "state": before["state"],
        },
        "result_observations": observations,
        "final": final,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"ack-purchase-prompt-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"ACK_PURCHASE_PROMPT_REPORT: {summary_path}")
    if not final:
        print(
            "ACK_PURCHASE_UNCERTAIN: popup OK was clicked, but the normal truck "
            "list was not verified; no further input was sent"
        )
        return 3
    print("ACK_PURCHASE_SUCCEEDED: success prompt closed; truck list recognized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
