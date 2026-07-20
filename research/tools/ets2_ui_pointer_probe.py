"""Guarded ETS2 pointer-position probe with no mouse clicks."""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

from ets2_ui_dry_run import (
    DEFAULT_NVIDIA_SCREENSHOT_DIR,
    DRIVER_CARDS,
    analyze,
    capture_direct,
    foreground_window_title,
    load_references,
    save_result,
)


SAFE_POINTER = (12, 540)
MOUSEEVENTF_MOVE = 0x0001


def send_relative_move(delta_x: int, delta_y: int) -> None:
    user32 = ctypes.windll.user32
    user32.mouse_event.argtypes = (
        ctypes.c_ulong,
        ctypes.c_long,
        ctypes.c_long,
        ctypes.c_ulong,
        ctypes.c_size_t,
    )
    user32.mouse_event.restype = None
    user32.mouse_event(MOUSEEVENTF_MOVE, delta_x, delta_y, 0, 0)


def set_pointer(position: tuple[int, int]) -> tuple[int, int]:
    if "Euro Truck Simulator 2" not in foreground_window_title():
        raise RuntimeError("Refusing pointer movement because ETS2 is not foreground")
    # Exclusive fullscreen locks the Windows cursor at (960, 540). ETS2's own
    # UI cursor consumes relative mouse deltas. A large negative move clamps the
    # in-game cursor to the top-left boundary, producing a deterministic origin.
    send_relative_move(-32768, -32768)
    time.sleep(0.15)
    send_relative_move(position[0], position[1])
    time.sleep(0.25)
    return position


def card_center(card_number: int) -> tuple[int, int]:
    left, top, right, bottom = DRIVER_CARDS[card_number - 1]
    return ((left + right) // 2, (top + bottom) // 2)


def capture_analyze_save(
    screenshot_dir: Path,
    timeout: float,
    output_dir: Path,
    references,
    integrity_attempts: int,
) -> tuple[Path, dict, Path, Path]:
    last = None
    for attempt in range(1, integrity_attempts + 1):
        screenshot, image, capture_ms = capture_direct(output_dir)
        result = analyze(image, references)
        result["source_screenshot"] = str(screenshot)
        result["capture_hotkeys_performed"] = 0
        result["capture_method"] = "PIL.ImageGrab"
        result["capture_duration_ms"] = round(capture_ms, 2)
        result["integrity_attempt"] = attempt
        annotated, report = save_result(image, result, output_dir)
        last = (screenshot, result, annotated, report)
        if result.get("safe_to_act"):
            return last
        print(
            f"INCOMPLETE_CAPTURE_RETRY: attempt {attempt}/{integrity_attempts}, "
            f"integrity={result.get('visual_integrity')}"
        )
        time.sleep(1.0)
    assert last is not None
    return last


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=15.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--focus-settle", type=float, default=2.0)
    parser.add_argument("--integrity-attempts", type=int, default=4)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-pointer-probe",
    )
    args = parser.parse_args()

    references = load_references()
    output_dir = args.output_dir.resolve()
    print(
        f"Pointer-only probe in {args.delay:.1f} seconds. Return to ETS2 now. "
        "No mouse button will be pressed."
    )
    time.sleep(args.delay)
    if "Euro Truck Simulator 2" not in foreground_window_title():
        print("PROBE_ABORTED: ETS2 is not the foreground window")
        return 5
    time.sleep(args.focus_settle)

    before_shot, before, before_annotated, before_report = capture_analyze_save(
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    if before["state"] != "recruitment_agency":
        print(f"PROBE_ABORTED: expected recruitment_agency, got {before['state']}")
        return 2
    if before.get("selected_driver_cards"):
        print(
            "PROBE_ABORTED: a driver card already appears selected; "
            "the no-selection starting state is required"
        )
        return 3
    if not before.get("safe_to_act"):
        print("PROBE_ABORTED: recruitment UI did not pass the visual-integrity gate")
        return 6

    target = card_center(1)
    observed_target = set_pointer(target)
    time.sleep(1.25)
    hover_shot, hover, hover_annotated, hover_report = capture_analyze_save(
        args.screenshot_dir,
        args.capture_timeout,
        output_dir,
        references,
        args.integrity_attempts,
    )
    observed_safe = set_pointer(SAFE_POINTER)

    if hover["state"] != "recruitment_agency":
        print(f"PROBE_FAILED: screen changed unexpectedly to {hover['state']}")
        return 4
    if not hover.get("safe_to_act"):
        print("PROBE_FAILED: hovered UI did not pass the visual-integrity gate")
        return 7

    summary = {
        "read_only": True,
        "gameplay_transactions": 0,
        "mouse_clicks": 0,
        "pointer_moves": 2,
        "capture_hotkeys": 2,
        "target_card": 1,
        "target_position": list(target),
        "observed_target_position": list(observed_target),
        "safe_return_position": list(SAFE_POINTER),
        "observed_safe_return_position": list(observed_safe),
        "before": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "selected_driver_cards": before.get("selected_driver_cards", []),
        },
        "hover": {
            "screenshot": str(hover_shot),
            "annotated": str(hover_annotated),
            "report": str(hover_report),
            "highlighted_driver_cards": hover.get("selected_driver_cards", []),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"pointer-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"POINTER_PROBE_REPORT: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
