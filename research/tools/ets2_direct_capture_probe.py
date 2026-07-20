"""Test direct fullscreen capture without NVIDIA hotkeys or gameplay input."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_dealer_icon_detector import detect_dealer_markers
from ets2_truck_ui_dry_run import EXPECTED_SIZE, load_truck_references, recognize
from ets2_ui_dealer_marker_probe import button_metrics
from ets2_ui_dry_run import capture_direct, foreground_window_title


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument(
        "--allow-unknown",
        action="store_true",
        help="Keep a read-only capture of a not-yet-calibrated screen",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-direct-capture",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    print(
        f"Direct capture probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It sends no keyboard or mouse input."
    )
    time.sleep(args.delay)

    title_before = foreground_window_title()
    if "Euro Truck Simulator 2" not in title_before:
        print(f"DIRECT_CAPTURE_ABORTED: ETS2 is not foreground: {title_before!r}")
        return 2
    image_path, image, capture_ms = capture_direct(output_dir)
    title_after = foreground_window_title()
    if "Euro Truck Simulator 2" not in title_after:
        print(f"DIRECT_CAPTURE_ABORTED: ETS2 lost foreground: {title_after!r}")
        return 3
    if image.size != EXPECTED_SIZE:
        print(
            "DIRECT_CAPTURE_FAILED: unexpected image size "
            f"{image.size}; expected {EXPECTED_SIZE}"
        )
        return 4

    references = load_truck_references()
    analysis = recognize(image, references)
    markers = detect_dealer_markers(image) if analysis.get("state") == "dealer_map" else []
    button = button_metrics(image) if analysis.get("state") == "dealer_map" else None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report_path = output_dir / f"direct-capture-{stamp}.json"
    report = {
        "gameplay_input_events": 0,
        "nvidia_capture_hotkeys": 0,
        "capture_method": "PIL.ImageGrab",
        "capture_duration_ms": round(capture_ms, 2),
        "foreground_before": title_before,
        "foreground_after": title_after,
        "resolution": list(image.size),
        "analysis": analysis,
        "dealer_markers": markers,
        "buy_online_button": button,
        "image": str(image_path),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"DIRECT_CAPTURE_REPORT: {report_path}")
    if (
        not args.allow_unknown
        and (analysis.get("state") == "unknown" or not analysis.get("safe_to_act"))
    ):
        print("DIRECT_CAPTURE_FAILED: the direct image was not safely recognizable")
        return 5
    print("DIRECT_CAPTURE_SUCCEEDED: fullscreen ETS2 recognized without Alt+F1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
