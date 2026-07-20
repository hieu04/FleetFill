"""Prove a reversible bounded pan on the ETS2 garage-selection map.

The probe starts with no garage selected, drags only through marker-free map
space, verifies coherent marker translation, replays the inverse drag, and
verifies restoration. It has no marker, slot, or confirmation click target.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from datetime import datetime
from pathlib import Path

from ets2_garage_icon_detector import detect_garage_markers
from ets2_truck_ui_dry_run import load_truck_references
from ets2_ui_dealer_pan_probe import distance_squared, dominant_marker_translation
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR, GARAGE_MAP, load_references
from ets2_ui_find_capacity_garage_probe import capture_for_context
from ets2_ui_pointer_probe import SAFE_POINTER, send_relative_move, set_pointer
from ets2_ui_dry_run import foreground_window_title


MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
VK_LBUTTON = 0x01
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
VK_RBUTTON = 0x02
DRAG_PAIRS = (
    ((1380, 610), (1080, 610)),
    ((1440, 570), (1140, 570)),
    ((1320, 620), (1020, 620)),
    ((1260, 580), (960, 580)),
)


def marker_clearance(point: tuple[int, int], markers: list[dict]) -> float:
    if not markers:
        return float("inf")
    return min(distance_squared(tuple(marker["center"]), point) for marker in markers) ** 0.5


def choose_drag_pair(markers: list[dict], minimum_clearance: float = 70.0):
    left, top, right, bottom = GARAGE_MAP
    for start, end in DRAG_PAIRS:
        if not (
            left <= start[0] < right
            and top <= start[1] < bottom
            and left <= end[0] < right
            and top <= end[1] < bottom
        ):
            continue
        if (
            marker_clearance(start, markers) >= minimum_clearance
            and marker_clearance(end, markers) >= minimum_clearance
        ):
            return start, end
    return None


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


def drag_map(
    start: tuple[int, int],
    end: tuple[int, int],
    button: str,
    steps: int = 30,
) -> None:
    if "Euro Truck Simulator 2" not in foreground_window_title():
        raise RuntimeError("Refusing garage-map drag because ETS2 is not foreground")
    set_pointer(start)
    delta_x = end[0] - start[0]
    delta_y = end[1] - start[1]
    moved_x = 0
    moved_y = 0
    if button == "left":
        down_flag, up_flag, virtual_key = (
            MOUSEEVENTF_LEFTDOWN,
            MOUSEEVENTF_LEFTUP,
            VK_LBUTTON,
        )
    else:
        down_flag, up_flag, virtual_key = (
            MOUSEEVENTF_RIGHTDOWN,
            MOUSEEVENTF_RIGHTUP,
            VK_RBUTTON,
        )
    send_button(down_flag)
    try:
        time.sleep(0.3)
        if not (ctypes.windll.user32.GetAsyncKeyState(virtual_key) & 0x8000):
            raise RuntimeError(
                f"Windows did not report the {button} mouse button as held"
            )
        for step in range(1, steps + 1):
            if "Euro Truck Simulator 2" not in foreground_window_title():
                raise RuntimeError("ETS2 lost foreground during garage-map drag")
            target_x = round(delta_x * step / steps)
            target_y = round(delta_y * step / steps)
            send_relative_move(target_x - moved_x, target_y - moved_y)
            moved_x = target_x
            moved_y = target_y
            time.sleep(0.04)
    finally:
        send_button(up_flag)
    time.sleep(0.7)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", choices=("truck", "hire"), required=True)
    parser.add_argument("--button", choices=("left", "right"), default="right")
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--integrity-attempts", type=int, default=4)
    parser.add_argument("--minimum-clearance", type=float, default=70.0)
    parser.add_argument("--minimum-translation", type=int, default=80)
    parser.add_argument("--restore-tolerance", type=int, default=14)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-garage-pan-probe",
    )
    args = parser.parse_args()

    references = load_truck_references() if args.context == "truck" else load_references()
    expected_state = "truck_garage_selection" if args.context == "truck" else "garage_selection"
    output_dir = args.output_dir.resolve()
    print(
        f"Reversible garage-map pan probe in {args.delay:.1f} seconds. Return to "
        "ETS2. It drags marker-free map space only and has no selection target."
    )
    time.sleep(args.delay)

    before_shot, before_image, before, before_annotated, before_report = capture_for_context(
        args.context,
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    before_states = [slot["state"] for slot in before.get("slots", [])]
    if (
        before.get("state") != expected_state
        or not before.get("safe_to_act")
        or before_states != ["locked"] * 5
    ):
        print(f"GARAGE_PAN_ABORTED: unsafe starting screen: {before}")
        return 2
    before_markers = detect_garage_markers(before_image)
    if len(before_markers) < 2:
        print(f"GARAGE_PAN_ABORTED: need two visible markers, got {len(before_markers)}")
        return 3
    pair = choose_drag_pair(before_markers, args.minimum_clearance)
    if pair is None:
        print("GARAGE_PAN_ABORTED: no predefined drag corridor is marker-free")
        return 4
    drag_start, drag_end = pair

    drag_map(drag_start, drag_end, args.button)
    set_pointer(SAFE_POINTER)
    after_shot, after_image, after, after_annotated, after_report = capture_for_context(
        args.context,
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    after_states = [slot["state"] for slot in after.get("slots", [])]
    if (
        after.get("state") != expected_state
        or not after.get("safe_to_act")
        or after_states != ["locked"] * 5
    ):
        print(f"GARAGE_PAN_FAILED: unsafe state after forward drag: {after}")
        return 5
    after_markers = detect_garage_markers(after_image)
    forward = dominant_marker_translation(before_markers, after_markers)
    if (
        forward["matched_markers"] < 2
        or max(abs(forward["dx"]), abs(forward["dy"])) < args.minimum_translation
    ):
        print(f"GARAGE_PAN_FAILED: no coherent forward translation: {forward}")
        return 6
    if (
        marker_clearance(drag_end, after_markers) < args.minimum_clearance
        or marker_clearance(drag_start, after_markers) < args.minimum_clearance
    ):
        print("GARAGE_PAN_ABORTED: inverse corridor is no longer marker-free")
        return 7

    drag_map(drag_end, drag_start, args.button)
    set_pointer(SAFE_POINTER)
    restored_shot, restored_image, restored, restored_annotated, restored_report = capture_for_context(
        args.context,
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    restored_states = [slot["state"] for slot in restored.get("slots", [])]
    if (
        restored.get("state") != expected_state
        or not restored.get("safe_to_act")
        or restored_states != ["locked"] * 5
    ):
        print(f"GARAGE_PAN_FAILED: unsafe state after inverse drag: {restored}")
        return 8
    restored_markers = detect_garage_markers(restored_image)
    residual = dominant_marker_translation(before_markers, restored_markers)
    if (
        residual["matched_markers"] < 2
        or abs(residual["dx"]) > args.restore_tolerance
        or abs(residual["dy"]) > args.restore_tolerance
    ):
        print(f"GARAGE_PAN_FAILED: inverse drag did not restore the map: {residual}")
        return 9

    summary = {
        "gameplay_transactions": 0,
        "context": args.context,
        "garage_marker_clicks": 0,
        "slot_clicks": 0,
        "confirmation_clicks": 0,
        "map_drags": 2,
        "mouse_button": args.button,
        "drag_start": list(drag_start),
        "drag_end": list(drag_end),
        "requested_translation": [
            drag_end[0] - drag_start[0],
            drag_end[1] - drag_start[1],
        ],
        "observed_forward_translation": forward,
        "observed_restore_residual": residual,
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "marker_count": len(before_markers),
        },
        "after_forward": {
            "screenshot": str(after_shot),
            "annotated": str(after_annotated),
            "report": str(after_report),
            "marker_count": len(after_markers),
        },
        "restored": {
            "screenshot": str(restored_shot),
            "annotated": str(restored_annotated),
            "report": str(restored_report),
            "marker_count": len(restored_markers),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"garage-pan-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"GARAGE_PAN_PROBE_REPORT: {summary_path}")
    print("GARAGE_PAN_SUCCEEDED: coherent forward pan and inverse restoration verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
