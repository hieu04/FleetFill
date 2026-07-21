"""Open ETS2 Online Truck Purchase without selecting or purchasing a truck."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_dealer_icon_detector import detect_dealer_markers
from ets2_truck_ui_dry_run import BUY_ONLINE, load_truck_references
from ets2_ui_dealer_marker_probe import button_metrics
from ets2_ui_dealer_pan_probe import capture_analyze
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


def center(box: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = box
    return ((left + right) // 2, (top + bottom) // 2)


def wait_for_loaded_purchase(
    capture,
    timeout: float,
    poll_interval: float = 0.5,
    clock=time.monotonic,
    sleeper=time.sleep,
) -> tuple[tuple, list[dict]]:
    """Poll a recognized loading screen without sending any additional input."""
    deadline = clock() + timeout
    observations: list[dict] = []
    while True:
        result = capture()
        state = result[2]
        observations.append(
            {
                "state": state.get("state"),
                "safe_to_act": bool(state.get("safe_to_act")),
                "visual_integrity": state.get("visual_integrity"),
            }
        )
        if state.get("state") == "truck_purchase" and state.get("safe_to_act"):
            return result, observations
        if state.get("state") not in {"dealer_map", "truck_purchase"}:
            return result, observations
        if clock() >= deadline:
            return result, observations
        sleeper(poll_interval)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-open-online-purchase-probe",
    )
    args = parser.parse_args()
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Open-online-purchase probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It can click Buy online only; no truck card or Purchase target exists."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if (
        before["state"] != "dealer_map"
        or not before.get("safe_to_act")
        or before.get("selected_brand") != "scania"
    ):
        print(f"OPEN_ONLINE_ABORTED: unsafe starting screen: {before}")
        return 2
    selected = [
        marker
        for marker in detect_dealer_markers(before_image)
        if marker["state"] == "selected"
    ]
    button = button_metrics(before_image)
    if len(selected) != 1 or not button["enabled"]:
        print(
            "OPEN_ONLINE_ABORTED: expected one selected dealer and enabled Buy "
            f"online; selected={len(selected)}, button={button}"
        )
        return 3

    target = center(BUY_ONLINE)
    set_pointer(target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(1.5)

    after_result, load_observations = wait_for_loaded_purchase(
        lambda: capture_analyze(
            args.screenshot_dir, args.capture_timeout, output_dir, references
        ),
        timeout=args.capture_timeout,
    )
    after_shot, _after_image, after, after_annotated, after_report = after_result
    if after["state"] != "truck_purchase" or not after.get("safe_to_act"):
        print(
            "OPEN_ONLINE_FAILED: fully loaded Online Truck Purchase was not safely "
            f"recognized after {len(load_observations)} observation(s): {after}"
        )
        return 4

    summary = {
        "gameplay_transactions": 0,
        "buy_online_clicks": 1,
        "truck_card_clicks": 0,
        "purchase_clicks": 0,
        "buy_online_target": list(target),
        "load_observations": load_observations,
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "selected_dealer": selected[0],
            "buy_online_button": button,
        },
        "after": {
            "screenshot": str(after_shot),
            "annotated": str(after_annotated),
            "report": str(after_report),
            "state": after["state"],
            "visual_integrity": after.get("visual_integrity"),
        },
    }
    summary_path = output_dir / (
        f"open-online-purchase-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"OPEN_ONLINE_PURCHASE_REPORT: {summary_path}")
    print("OPEN_ONLINE_SUCCEEDED: truck cards loaded; no truck selected or purchased")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
