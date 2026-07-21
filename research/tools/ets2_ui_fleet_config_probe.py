"""Switch Online Truck Purchase to My Fleet Configurations without buying."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, TypeVar

from PIL import Image

from ets2_truck_ui_dry_run import (
    load_truck_references,
    patch_distance,
    project_root,
)
from ets2_ui_dealer_pan_probe import capture_analyze
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR
from ets2_ui_pointer_probe import SAFE_POINTER, set_pointer
from ets2_ui_select_probe import click_left_once


MODE_BOX = (230, 118, 583, 154)
MODE_TEXT_BOX = (230, 118, 546, 154)
DROPDOWN_ARROW = (547, 118, 583, 154)
DROPDOWN_MENU = (230, 155, 583, 232)
FLEET_OPTION = (230, 193, 583, 232)
CaptureResult = TypeVar("CaptureResult")


def center(box: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = box
    return ((left + right) // 2, (top + bottom) // 2)


def dropdown_is_open(image: Image.Image) -> bool:
    """Recognize the two-row menu by its stable flat background colors.

    The truck cards behind this menu vary by dealer and save.  Comparing the
    whole menu rectangle to a video frame therefore produces false negatives.
    These samples sit in blank portions of the two menu rows, away from text.
    """
    upper = image.getpixel((575, 174))
    lower = image.getpixel((575, 213))
    upper_is_blue_grey = upper[1] - upper[0] >= 8 and upper[2] - upper[0] >= 12
    lower_is_dark_grey = max(lower) - min(lower) <= 4 and 45 <= lower[0] <= 70
    return upper_is_blue_grey and lower_is_dark_grey


def wait_for_loaded_fleet_cards(
    capture: Callable[[], CaptureResult],
    result_from: Callable[[CaptureResult], dict],
    *,
    timeout: float,
    interval: float = 0.5,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[CaptureResult, int]:
    """Poll captures until rendered fleet cards pass the read-only integrity gate."""

    deadline = clock() + timeout
    attempts = 0
    while True:
        sample = capture()
        attempts += 1
        result = result_from(sample)
        if result.get("state") == "truck_purchase" and result.get("safe_to_act"):
            return sample, attempts
        remaining = deadline - clock()
        if remaining <= 0:
            return sample, attempts
        sleep(min(interval, remaining))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--load-timeout", type=float, default=10.0)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-fleet-config-probe",
    )
    args = parser.parse_args()
    frames = project_root() / "research" / "output" / "video-020129" / "frames"
    stock_reference = Image.open(frames / "frame-0042-000021.000s.jpg").convert("RGB")
    menu_reference = Image.open(frames / "frame-0043-000021.500s.jpg").convert("RGB")
    fleet_reference = Image.open(frames / "frame-0045-000022.500s.jpg").convert("RGB")
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Fleet-configuration probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It can open the source dropdown and choose My Fleet Configurations only."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if before["state"] != "truck_purchase" or not before.get("safe_to_act"):
        print(f"FLEET_ABORTED: unsafe starting screen: {before}")
        return 2
    stock_distance = patch_distance(
        before_image, MODE_TEXT_BOX, stock_reference, MODE_TEXT_BOX
    )
    if stock_distance > 0.20:
        if not dropdown_is_open(before_image):
            print(
                f"FLEET_ABORTED: Stock Offers mode/menu was not verified: "
                f"{stock_distance:.4f}"
            )
            return 3

    if dropdown_is_open(before_image):
        menu_shot, menu_image, menu = before_shot, before_image, before
        menu_annotated, menu_report = before_annotated, before_report
        dropdown_clicks = 0
    else:
        arrow_target = center(DROPDOWN_ARROW)
        set_pointer(arrow_target)
        click_left_once()
        set_pointer(SAFE_POINTER)
        time.sleep(0.6)
        menu_shot, menu_image, menu, menu_annotated, menu_report = capture_analyze(
            args.screenshot_dir, args.capture_timeout, output_dir, references
        )
        dropdown_clicks = 1
    menu_open = dropdown_is_open(menu_image)
    if menu["state"] != "truck_purchase" or not menu_open:
        print(
            "FLEET_FAILED: source dropdown menu was not verified; "
            f"state={menu['state']}, structural_match={menu_open}"
        )
        return 4

    option_target = center(FLEET_OPTION)
    set_pointer(option_target)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(0.5)

    def capture_fleet_cards():
        return capture_analyze(
            args.screenshot_dir, args.capture_timeout, output_dir, references
        )

    after_sample, load_attempts = wait_for_loaded_fleet_cards(
        capture_fleet_cards,
        lambda sample: sample[2],
        timeout=args.load_timeout,
    )
    after_shot, after_image, after, after_annotated, after_report = after_sample
    if after["state"] != "truck_purchase" or not after.get("safe_to_act"):
        print(f"FLEET_FAILED: fleet cards were not fully loaded: {after}")
        return 5
    fleet_distance = patch_distance(
        after_image, MODE_TEXT_BOX, fleet_reference, MODE_TEXT_BOX
    )
    after_stock_distance = patch_distance(
        after_image, MODE_TEXT_BOX, stock_reference, MODE_TEXT_BOX
    )
    if fleet_distance > 0.20 or fleet_distance + 0.08 >= after_stock_distance:
        print(
            "FLEET_FAILED: My Fleet Configurations mode identity was not verified; "
            f"fleet={fleet_distance:.4f}, stock={after_stock_distance:.4f}"
        )
        return 6

    summary = {
        "gameplay_transactions": 0,
        "dropdown_clicks": dropdown_clicks,
        "fleet_option_clicks": 1,
        "fleet_card_load_attempts": load_attempts,
        "truck_card_clicks": 0,
        "purchase_clicks": 0,
        "mode_distances": {
            "initial_stock": round(stock_distance, 4),
            "open_menu_structural_match": menu_open,
            "final_fleet": round(fleet_distance, 4),
            "final_stock": round(after_stock_distance, 4),
        },
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
        },
        "menu": {
            "screenshot": str(menu_shot),
            "annotated": str(menu_annotated),
            "report": str(menu_report),
        },
        "after": {
            "screenshot": str(after_shot),
            "annotated": str(after_annotated),
            "report": str(after_report),
            "visual_integrity": after.get("visual_integrity"),
        },
    }
    summary_path = output_dir / (
        f"fleet-config-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"FLEET_CONFIG_PROBE_REPORT: {summary_path}")
    print("FLEET_SUCCEEDED: fleet configurations loaded; no truck selected or purchased")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
