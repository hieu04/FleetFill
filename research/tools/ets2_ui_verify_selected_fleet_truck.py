"""Read-only guard for an already-selected ETS2 fleet truck card.

The only generated input is NVIDIA's screenshot hotkey, via capture_analyze.
No mouse movement or click is performed.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from ets2_truck_ui_dry_run import load_truck_references, patch_distance, project_root
from ets2_ui_dealer_pan_probe import capture_analyze
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR
from ets2_ui_fleet_config_probe import MODE_TEXT_BOX
from ets2_ui_fleet_truck_select_probe import button_blue_minus_red


# Blank portions of the four card headers, away from title and price text.
CARD_HEADER_SAMPLES = (
    (650, 172, 780, 200),
    (1390, 172, 1510, 200),
    (650, 524, 780, 552),
    (1390, 524, 1510, 552),
)


def header_blue_minus_red(image: Image.Image, card: int) -> float:
    patch = np.asarray(
        image.crop(CARD_HEADER_SAMPLES[card - 1]).convert("RGB"), dtype=np.float32
    )
    return float(np.mean(patch[:, :, 2] - patch[:, :, 0]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--card", type=int, default=1, choices=range(1, 5))
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-verify-selected-fleet-truck",
    )
    args = parser.parse_args()
    frames = project_root() / "research" / "output" / "video-020129" / "frames"
    stock_reference = Image.open(frames / "frame-0042-000021.000s.jpg").convert("RGB")
    fleet_reference = Image.open(frames / "frame-0052-000026.000s.jpg").convert("RGB")
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Selected fleet-card guard in {args.delay:.1f} seconds. Return to ETS2. "
        "It captures and verifies only; it never clicks."
    )
    time.sleep(args.delay)

    shot, image, analysis, annotated, analysis_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if analysis["state"] != "truck_purchase" or not analysis.get("safe_to_act"):
        print(f"VERIFY_SELECTED_ABORTED: unsafe screen: {analysis}")
        return 2

    fleet_distance = patch_distance(image, MODE_TEXT_BOX, fleet_reference, MODE_TEXT_BOX)
    stock_distance = patch_distance(image, MODE_TEXT_BOX, stock_reference, MODE_TEXT_BOX)
    if fleet_distance > 0.20 or fleet_distance + 0.08 >= stock_distance:
        print(
            "VERIFY_SELECTED_ABORTED: My Fleet Configurations was not verified; "
            f"fleet={fleet_distance:.4f}, stock={stock_distance:.4f}"
        )
        return 3

    purchase_metric = button_blue_minus_red(image)
    header_metrics = [
        header_blue_minus_red(image, card) for card in range(1, len(CARD_HEADER_SAMPLES) + 1)
    ]
    selected_metric = header_metrics[args.card - 1]
    other_max = max(
        metric for index, metric in enumerate(header_metrics, start=1) if index != args.card
    )
    if purchase_metric < 8.0:
        print(
            "VERIFY_SELECTED_ABORTED: Purchase is not enabled; "
            f"blue_minus_red={purchase_metric:.2f}"
        )
        return 4
    if selected_metric < 12.0 or selected_metric < other_max + 8.0:
        print(
            f"VERIFY_SELECTED_ABORTED: fleet card {args.card} selection was not "
            f"distinct; headers={[round(value, 2) for value in header_metrics]}"
        )
        return 5

    summary = {
        "gameplay_transactions": 0,
        "mouse_clicks": 0,
        "selected_card": args.card,
        "purchase_blue_minus_red": round(purchase_metric, 2),
        "card_header_blue_minus_red": [round(value, 2) for value in header_metrics],
        "mode_distances": {
            "fleet": round(fleet_distance, 4),
            "stock": round(stock_distance, 4),
        },
        "capture": {
            "screenshot": str(shot),
            "annotated": str(annotated),
            "report": str(analysis_report),
            "visual_integrity": analysis.get("visual_integrity"),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"verify-selected-fleet-truck-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"VERIFY_SELECTED_FLEET_TRUCK_REPORT: {summary_path}")
    print(f"VERIFY_SELECTED_SUCCEEDED: fleet card {args.card} is already selected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
