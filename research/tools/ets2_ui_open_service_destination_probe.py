"""Navigate from ETS2 home to Truck Dealers or Recruitment Agency."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from ets2_truck_ui_dry_run import load_truck_references, recognize as recognize_truck
from ets2_ui_dry_run import analyze as analyze_hire
from ets2_ui_dry_run import capture_direct, feature, load_references as load_hire_references
from ets2_ui_open_services_probe import (
    SERVICES_TARGET,
    load_home_reference,
    recognize_home,
)
from ets2_ui_pointer_probe import SAFE_POINTER, send_relative_move, set_pointer
from ets2_ui_select_probe import click_left_once
from ets2_ui_open_hire_driver_probe import (
    load_recruitment_map_reference,
    recognize_recruitment_map,
)


SERVICES_FLYOUT = (881, 607, 1379, 913)
FLYOUT_REFERENCE = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "live-hover-services-test"
    / "direct-capture-20260721-005945-220477.png"
)
DESTINATIONS = {
    "truck_dealers": {
        "target": (1040, 868),
        "expected_state": "dealer_map",
    },
    "recruitment_agency": {
        "target": (1260, 722),
        "expected_state": "recruitment_map",
    },
}


def load_flyout_reference() -> Image.Image:
    if not FLYOUT_REFERENCE.is_file():
        raise FileNotFoundError(f"Missing Services fly-out reference: {FLYOUT_REFERENCE}")
    return Image.open(FLYOUT_REFERENCE).convert("RGB")


def recognize_services_flyout(image: Image.Image, reference: Image.Image) -> dict:
    distance = float(
        np.mean(
            np.abs(feature(image, SERVICES_FLYOUT) - feature(reference, SERVICES_FLYOUT))
        )
    )
    patch = np.asarray(image.crop(SERVICES_FLYOUT).convert("L"), dtype=np.float32)
    deviation = float(patch.std())
    safe = distance <= 0.38 and deviation >= 30.0
    return {
        "state": "services_flyout" if safe else "unknown",
        "flyout_distance": round(distance, 4),
        "flyout_standard_deviation": round(deviation, 2),
        "safe_to_select_destination": safe,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", choices=tuple(DESTINATIONS), required=True)
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--wake-settle", type=float, default=0.8)
    parser.add_argument("--hover-settle", type=float, default=0.8)
    parser.add_argument("--after-settle", type=float, default=1.2)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-open-service-destination",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    home_reference = load_home_reference()
    flyout_reference = load_flyout_reference()
    destination = DESTINATIONS[args.destination]
    target = destination["target"]
    print(
        f"Open {args.destination} probe in {args.delay:.1f} seconds. Return to "
        "ETS2. It may wake and hover the menu, then clicks only that destination."
    )
    time.sleep(args.delay)

    set_pointer(SAFE_POINTER)
    time.sleep(args.wake_settle)
    home_shot, home_image, home_ms = capture_direct(output_dir)
    home = recognize_home(home_image, home_reference)
    if not home["safe_to_open_services"]:
        print(f"OPEN_DESTINATION_ABORTED: home UI not recognized: {home}")
        return 2

    set_pointer(SERVICES_TARGET)
    time.sleep(args.hover_settle)
    flyout_shot, flyout_image, flyout_ms = capture_direct(output_dir)
    flyout = recognize_services_flyout(flyout_image, flyout_reference)
    if not flyout["safe_to_select_destination"]:
        print(f"OPEN_DESTINATION_ABORTED: Services fly-out not recognized: {flyout}")
        return 3

    # Move continuously from the Services tile into its attached fly-out.
    # Resetting to the screen origin here would close the hover menu.
    send_relative_move(target[0] - SERVICES_TARGET[0], target[1] - SERVICES_TARGET[1])
    time.sleep(args.hover_settle)
    click_left_once()
    set_pointer(SAFE_POINTER)
    time.sleep(args.after_settle)
    after_shot, after_image, after_ms = capture_direct(output_dir)
    if args.destination == "truck_dealers":
        result = recognize_truck(after_image, load_truck_references())
    else:
        result = recognize_recruitment_map(
            after_image, load_recruitment_map_reference()
        )
    if (
        result.get("state") != destination["expected_state"]
        or not (
            result.get("safe_to_act")
            if args.destination == "truck_dealers"
            else result.get("safe_to_open_driver_list")
        )
    ):
        print(
            "OPEN_DESTINATION_FAILED: expected "
            f"{destination['expected_state']}, observed={result}"
        )
        return 4

    report = {
        "gameplay_transactions": 0,
        "keyboard_events": 0,
        "mouse_clicks": 1,
        "destination": args.destination,
        "target_position": list(target),
        "home": {
            "screenshot": str(home_shot),
            "capture_duration_ms": round(home_ms, 2),
            "analysis": home,
        },
        "flyout": {
            "screenshot": str(flyout_shot),
            "capture_duration_ms": round(flyout_ms, 2),
            "analysis": flyout,
        },
        "destination_screen": {
            "screenshot": str(after_shot),
            "capture_duration_ms": round(after_ms, 2),
            "analysis": result,
        },
    }
    report_path = output_dir / (
        f"open-{args.destination}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"OPEN_SERVICE_DESTINATION_REPORT: {report_path}")
    print(
        f"OPEN_SERVICE_DESTINATION_SUCCEEDED: {args.destination} opened with "
        "one guarded click"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
