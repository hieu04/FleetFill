"""Guarded ETS2 dealer-map drag probe with no marker or button clicks."""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from PIL import Image

from ets2_dealer_icon_detector import detect_dealer_markers
from ets2_truck_ui_dry_run import annotate, load_truck_references, recognize
from ets2_ui_dry_run import (
    DEFAULT_NVIDIA_SCREENSHOT_DIR,
    capture_direct,
    foreground_window_title,
)
from ets2_ui_pointer_probe import SAFE_POINTER, send_relative_move, set_pointer


PAN_START = (1350, 800)
PAN_END = (1110, 800)
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010


def send_button(flags: int) -> None:
    user32 = ctypes.windll.user32
    user32.mouse_event.argtypes = (
        ctypes.c_ulong,
        ctypes.c_long,
        ctypes.c_long,
        ctypes.c_ulong,
        ctypes.c_size_t,
    )
    user32.mouse_event.restype = None
    user32.mouse_event(flags, 0, 0, 0, 0)


def drag_map(start: tuple[int, int], end: tuple[int, int], steps: int = 24) -> None:
    if "Euro Truck Simulator 2" not in foreground_window_title():
        raise RuntimeError("Refusing map drag because ETS2 is not foreground")
    set_pointer(start)
    delta_x = end[0] - start[0]
    delta_y = end[1] - start[1]
    moved_x = 0
    moved_y = 0
    send_button(MOUSEEVENTF_RIGHTDOWN)
    try:
        time.sleep(0.35)
        if not (ctypes.windll.user32.GetAsyncKeyState(0x02) & 0x8000):
            raise RuntimeError("Windows did not report the right mouse button as held")
        for step in range(1, steps + 1):
            if "Euro Truck Simulator 2" not in foreground_window_title():
                raise RuntimeError("ETS2 lost foreground during map drag")
            target_x = round(delta_x * step / steps)
            target_y = round(delta_y * step / steps)
            send_relative_move(target_x - moved_x, target_y - moved_y)
            moved_x = target_x
            moved_y = target_y
            time.sleep(0.055)
    finally:
        # Never allow an interrupted probe to leave the mouse button held.
        send_button(MOUSEEVENTF_RIGHTUP)
    time.sleep(0.5)


def capture_analyze(
    screenshot_dir: Path,
    timeout: float,
    output_dir: Path,
    references,
) -> tuple[Path, Image.Image, dict, Path, Path]:
    screenshot, image, capture_ms = capture_direct(output_dir)
    analysis = recognize(image, references)
    analysis["source_screenshot"] = str(screenshot)
    analysis["capture_hotkeys_performed"] = 0
    analysis["capture_method"] = "PIL.ImageGrab"
    analysis["capture_duration_ms"] = round(capture_ms, 2)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output_dir.mkdir(parents=True, exist_ok=True)
    annotated_path = output_dir / f"dealer-pan-{stamp}.png"
    report_path = output_dir / f"dealer-pan-{stamp}.json"
    annotate(image, analysis).save(annotated_path)
    report_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    return screenshot, image, analysis, annotated_path, report_path


def distance_squared(left: tuple[int, int], right: tuple[int, int]) -> int:
    return (left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2


def dominant_marker_translation(before: list[dict], after: list[dict]) -> dict:
    differences = Counter()
    for old in before:
        old_x, old_y = old["center"]
        for new in after:
            new_x, new_y = new["center"]
            # Two-pixel bins absorb capture antialiasing and rounding.
            dx = round((new_x - old_x) / 2) * 2
            dy = round((new_y - old_y) / 2) * 2
            differences[(dx, dy)] += 1
    if not differences:
        return {"dx": 0, "dy": 0, "matched_markers": 0}
    (dx, dy), _raw_count = differences.most_common(1)[0]
    matched = 0
    used_after = set()
    for old in before:
        expected = (old["center"][0] + dx, old["center"][1] + dy)
        choices = [
            (index, marker)
            for index, marker in enumerate(after)
            if index not in used_after
            and distance_squared(tuple(marker["center"]), expected) <= 25
        ]
        if choices:
            best_index, _best = min(
                choices,
                key=lambda item: distance_squared(tuple(item[1]["center"]), expected),
            )
            used_after.add(best_index)
            matched += 1
    return {"dx": dx, "dy": dy, "matched_markers": matched}


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
        / "live-dealer-pan-probe",
    )
    args = parser.parse_args()
    references = load_truck_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Dealer-map drag probe in {args.delay:.1f} seconds. Return to ETS2. "
        "It has no marker, brand, Buy online, or transaction click target."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if (
        before["state"] != "dealer_map"
        or not before.get("safe_to_act")
        or before.get("selected_brand") != "all"
    ):
        print(f"PAN_ABORTED: unsafe starting screen: {before}")
        return 2
    before_markers = detect_dealer_markers(before_image)
    if len(before_markers) < 2:
        print(f"PAN_ABORTED: need at least two visible markers, got {len(before_markers)}")
        return 3
    for point_name, point in (("start", PAN_START), ("end", PAN_END)):
        nearest = min(
            distance_squared(tuple(marker["center"]), point) for marker in before_markers
        ) ** 0.5
        if nearest < 90:
            print(f"PAN_ABORTED: {point_name} point is only {nearest:.1f}px from a marker")
            return 4

    drag_map(PAN_START, PAN_END)
    set_pointer(SAFE_POINTER)
    time.sleep(0.8)
    after_shot, after_image, after, after_annotated, after_report = capture_analyze(
        args.screenshot_dir, args.capture_timeout, output_dir, references
    )
    if after["state"] != "dealer_map" or not after.get("safe_to_act"):
        print(f"PAN_FAILED: dealer screen was not safely recognized afterward: {after}")
        return 5
    after_markers = detect_dealer_markers(after_image)
    translation = dominant_marker_translation(before_markers, after_markers)
    moved_far_enough = abs(translation["dx"]) >= 80 or abs(translation["dy"]) >= 80
    if translation["matched_markers"] < 2 or not moved_far_enough:
        print(
            "PAN_FAILED: marker motion did not prove a coherent map translation: "
            f"{translation}"
        )
        return 6

    summary = {
        "gameplay_transactions": 0,
        "marker_clicks": 0,
        "brand_clicks": 0,
        "buy_online_clicks": 0,
        "map_drags": 1,
        "drag_start": list(PAN_START),
        "drag_end": list(PAN_END),
        "requested_drag": [PAN_END[0] - PAN_START[0], PAN_END[1] - PAN_START[1]],
        "observed_marker_translation": translation,
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "marker_count": len(before_markers),
        },
        "after": {
            "screenshot": str(after_shot),
            "annotated": str(after_annotated),
            "report": str(after_report),
            "marker_count": len(after_markers),
        },
    }
    summary_path = output_dir / (
        f"dealer-pan-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"DEALER_PAN_PROBE_REPORT: {summary_path}")
    print("PAN_SUCCEEDED: dealer map moved coherently with zero selections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
