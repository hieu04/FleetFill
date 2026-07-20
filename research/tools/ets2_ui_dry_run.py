"""Read-only ETS2 1.60 Recruitment Agency UI recognizer.

This first prototype contains no mouse or keyboard control. It recognizes a
1920x1080 screenshot, annotates known controls, and records what a later state
machine would consider. It never confirms a hire or purchase.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageGrab


EXPECTED_SIZE = (1920, 1080)
DEFAULT_NVIDIA_SCREENSHOT_DIR = (
    Path.home() / "Videos" / "Euro Truck Simulator 2"
)

# Screen-space bounds derived from ETS2's 1440x900 UI definitions and verified
# against the user's 1920x1080, 100%-scale recordings.
RECRUIT_TITLE = (530, 12, 745, 56)
GARAGE_TITLE = (830, 10, 1090, 64)
DRIVER_CARDS = (
    (322, 207, 962, 533),
    (973, 207, 1613, 533),
    (322, 545, 962, 871),
    (973, 545, 1613, 871),
)
HIRE_BUTTON = (589, 982, 1331, 1018)
GARAGE_DIALOG = (322, 10, 1598, 1070)
GARAGE_MAP = (624, 176, 1558, 675)
GARAGE_SLOTS = (
    (642, 880, 750, 988),
    (774, 880, 882, 988),
    (906, 880, 1014, 988),
    (1038, 880, 1146, 988),
    (1170, 880, 1278, 988),
)
GARAGE_OK = (862, 1008, 1059, 1043)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def reference_paths() -> dict[str, Path]:
    frames = project_root() / "research" / "output" / "video-020357" / "frames"
    return {
        "recruitment": frames / "frame-0010-000005.000s.jpg",
        "garage_locked": frames / "frame-0014-000007.000s.jpg",
        "garage_free": frames / "frame-0018-000009.000s.jpg",
        "garage_selected": frames / "frame-0019-000009.500s.jpg",
    }


def feature(image: Image.Image, box: tuple[int, int, int, int]) -> np.ndarray:
    crop = image.crop(box).convert("L").resize((96, 32), Image.Resampling.BILINEAR)
    values = np.asarray(crop, dtype=np.float32) / 255.0
    # Standardization makes the title comparison robust to the dimming layer
    # that ETS2 applies behind its garage-selection modal.
    deviation = float(values.std())
    if deviation < 0.01:
        return values - float(values.mean())
    return (values - float(values.mean())) / deviation


def patch_distance(
    image: Image.Image,
    image_box: tuple[int, int, int, int],
    reference: Image.Image,
    reference_box: tuple[int, int, int, int],
) -> float:
    left = feature(image, image_box)
    right = feature(reference, reference_box)
    return float(np.mean(np.abs(left - right)))


def slot_feature(image: Image.Image, box: tuple[int, int, int, int]) -> np.ndarray:
    # Focus on the central icon and exclude most of the selection border.
    left, top, right, bottom = box
    inset = (left + 10, top + 8, right - 9, bottom - 6)
    crop = image.crop(inset).convert("L").resize((64, 64), Image.Resampling.BILINEAR)
    values = np.asarray(crop, dtype=np.float32) / 255.0
    return values


def slot_distance(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.mean(np.abs(left - right)))


def is_occupied_portrait(strongly_colored_pixels: int, yellow_pixels: int) -> bool:
    """Separate a colorful driver portrait from ETS2's yellow slot selection.

    Some portraits contain a small amount of skin/clothing color that falls in
    the broad yellow mask.  A selected slot, by contrast, is almost entirely
    yellow, so its yellow-to-color ratio is much higher.
    """
    return (
        strongly_colored_pixels >= 200
        and yellow_pixels < strongly_colored_pixels * 0.65
    )


def load_references() -> dict[str, Image.Image]:
    references = {}
    for name, path in reference_paths().items():
        if not path.exists():
            raise FileNotFoundError(
                f"Missing recording reference {path}. Preserve research/output/video-020357."
            )
        references[name] = Image.open(path).convert("RGB")
    return references


def recognize_screen(image: Image.Image, references: dict[str, Image.Image]) -> dict:
    recruit_distance = patch_distance(
        image, RECRUIT_TITLE, references["recruitment"], RECRUIT_TITLE
    )
    garage_distance = patch_distance(
        image, GARAGE_TITLE, references["garage_free"], GARAGE_TITLE
    )

    # Distances are calibrated below by --validate-recordings. Smaller is better.
    if recruit_distance <= 0.42 and recruit_distance + 0.08 < garage_distance:
        state = "recruitment_agency"
    elif garage_distance <= 0.42 and garage_distance + 0.08 < recruit_distance:
        state = "garage_selection"
    else:
        state = "unknown"

    return {
        "state": state,
        "distances": {
            "recruitment_title": round(recruit_distance, 4),
            "garage_title": round(garage_distance, 4),
        },
    }


def selected_driver_cards(image: Image.Image) -> list[int]:
    selected = []
    for index, (left, top, right, _bottom) in enumerate(DRIVER_CARDS, start=1):
        # This patch contains only the card background in the recorded layout.
        patch = np.asarray(
            image.crop((right - 80, top + 12, right - 12, top + 38)).convert("RGB"),
            dtype=np.float32,
        )
        red, _green, blue = patch.mean(axis=(0, 1))
        if blue - red >= 9.0:
            selected.append(index)
    return selected


def recruitment_visual_integrity(image: Image.Image) -> dict:
    portrait_variance = []
    for left, top, _right, _bottom in DRIVER_CARDS:
        portrait = np.asarray(
            image.crop((left + 24, top + 23, left + 132, top + 132)).convert("RGB"),
            dtype=np.float32,
        )
        portrait_variance.append(round(float(portrait.std()), 2))
    return {
        "complete": all(value >= 18.0 for value in portrait_variance),
        "portrait_standard_deviation": portrait_variance,
        "minimum_required": 18.0,
    }


def garage_visual_integrity(image: Image.Image) -> dict:
    map_pixels = np.asarray(image.crop(GARAGE_MAP).convert("L"), dtype=np.float32)
    slot_variance = [
        round(float(np.asarray(image.crop(box).convert("L"), dtype=np.float32).std()), 2)
        for box in GARAGE_SLOTS
    ]
    map_variance = round(float(map_pixels.std()), 2)
    return {
        "complete": map_variance >= 18.0 and all(value >= 12.0 for value in slot_variance),
        "map_standard_deviation": map_variance,
        "slot_standard_deviation": slot_variance,
        "minimum_map_required": 18.0,
        "minimum_slot_required": 12.0,
    }


def classify_slots(image: Image.Image, references: dict[str, Image.Image]) -> list[dict]:
    templates = {
        "locked": slot_feature(references["garage_locked"], GARAGE_SLOTS[0]),
        "free": slot_feature(references["garage_free"], GARAGE_SLOTS[0]),
    }
    results = []
    for index, box in enumerate(GARAGE_SLOTS, start=1):
        current = slot_feature(image, box)
        distances = {
            name: slot_distance(current, template) for name, template in templates.items()
        }
        best_name = min(distances, key=distances.get)
        best_distance = distances[best_name]
        rgb = np.asarray(image.crop(box).convert("RGB"), dtype=np.int16)
        yellow_pixels = int(
            (
                (rgb[:, :, 0] > 150)
                & (rgb[:, :, 1] > 90)
                & (rgb[:, :, 1] < 210)
                & (rgb[:, :, 2] < 90)
                & ((rgb[:, :, 0] - rgb[:, :, 1]) > 25)
            ).sum()
        )
        chroma = rgb.max(axis=2) - rgb.min(axis=2)
        strongly_colored_pixels = int((chroma > 40).sum())
        # An occupied driver slot contains a color portrait over the otherwise
        # gray truck/person symbol.  A selected free slot is also colorful, but
        # overwhelmingly ETS2-yellow, so keep the yellow state separate.  A
        # purchased truck without a driver is rendered as a detailed dim truck
        # image: neutral in color, but noticeably farther from the simple free
        # truck/person template.
        if is_occupied_portrait(strongly_colored_pixels, yellow_pixels):
            best_name = "occupied"
        elif yellow_pixels >= 80 and best_name == "free":
            best_name = "selected_free"
        elif (
            best_name == "free"
            and yellow_pixels < 80
            and strongly_colored_pixels < 200
            and 0.07 <= best_distance <= 0.16
        ):
            best_name = "truck_present"
        elif best_distance > 0.16:
            best_name = "unknown"
        results.append(
            {
                "slot": index,
                "state": best_name,
                "distance": round(best_distance, 4),
                "yellow_pixels": yellow_pixels,
                "strongly_colored_pixels": strongly_colored_pixels,
            }
        )
    return results


def annotate(image: Image.Image, analysis: dict) -> Image.Image:
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    font = ImageFont.load_default(size=18)
    state = analysis["state"]

    if state == "recruitment_agency":
        selected = set(analysis["selected_driver_cards"])
        for index, box in enumerate(DRIVER_CARDS, start=1):
            color = "#ffae00" if index in selected else "#4cc9f0"
            draw.rectangle(box, outline=color, width=4)
            draw.text((box[0] + 8, box[1] + 8), f"Driver card {index}", fill=color, font=font)
        draw.rectangle(HIRE_BUTTON, outline="#ffae00", width=4)
        draw.text(
            (HIRE_BUTTON[0], HIRE_BUTTON[1] - 25),
            "Hire Driver control (not clicked)",
            fill="#ffae00",
            font=font,
        )
    elif state == "garage_selection":
        draw.rectangle(GARAGE_DIALOG, outline="#4cc9f0", width=4)
        draw.rectangle(GARAGE_MAP, outline="#4cc9f0", width=3)
        draw.text(
            (GARAGE_MAP[0], GARAGE_MAP[1] - 25),
            "Dynamic map: never use a fixed garage coordinate",
            fill="#4cc9f0",
            font=font,
        )
        for slot in analysis["slots"]:
            box = GARAGE_SLOTS[slot["slot"] - 1]
            color = {
                "free": "#50fa7b",
                "selected_free": "#ffae00",
                "occupied": "#bd93f9",
                "truck_present": "#4cc9f0",
                "locked": "#8d99ae",
                "unknown": "#ff5555",
            }[slot["state"]]
            draw.rectangle(box, outline=color, width=4)
            draw.text(
                (box[0], box[1] - 24),
                f"{slot['slot']}: {slot['state']}",
                fill=color,
                font=font,
            )
        draw.rectangle(GARAGE_OK, outline="#ff5555", width=5)
        draw.text(
            (GARAGE_OK[0] - 25, GARAGE_OK[1] - 27),
            "STOP: final OK is never clicked in dry-run mode",
            fill="#ff5555",
            font=font,
        )

    banner = (104, 65, 690, 112)
    draw.rectangle(banner, fill="#101318", outline="#ffffff", width=2)
    draw.text(
        (banner[0] + 12, banner[1] + 12),
        f"ETS2 DRY RUN - recognized: {state}",
        fill="#ffffff",
        font=font,
    )
    return annotated


def analyze(image: Image.Image, references: dict[str, Image.Image]) -> dict:
    result = {
        "resolution": list(image.size),
        "read_only": True,
        "input_actions_performed": 0,
        "gameplay_input_actions_performed": 0,
        "capture_hotkeys_performed": 0,
    }
    if image.size != EXPECTED_SIZE:
        result.update(
            {
                "state": "unsupported_resolution",
                "error": f"Expected {EXPECTED_SIZE[0]}x{EXPECTED_SIZE[1]}",
            }
        )
        return result

    result.update(recognize_screen(image, references))
    if result["state"] == "recruitment_agency":
        result["selected_driver_cards"] = selected_driver_cards(image)
        result["visual_integrity"] = recruitment_visual_integrity(image)
        result["next_safe_observation"] = "Review the four driver-card regions"
    elif result["state"] == "garage_selection":
        result["slots"] = classify_slots(image, references)
        result["visual_integrity"] = garage_visual_integrity(image)
        result["next_safe_observation"] = "Review slot states; do not press OK"
    else:
        result["visual_integrity"] = {"complete": False}
        result["next_safe_observation"] = "Navigate manually to Recruitment Agency"
    result["safe_to_act"] = bool(result["visual_integrity"]["complete"])
    return result


def foreground_window_title() -> str:
    user32 = ctypes.windll.user32
    window = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(window)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(window, buffer, len(buffer))
    return buffer.value


def send_nvidia_screenshot_hotkey() -> None:
    # keybd_event is sufficient for this capture-only prototype. No mouse or
    # gameplay key is sent. VK_MENU is Alt and VK_F1 is F1.
    user32 = ctypes.windll.user32
    key_up = 0x0002
    vk_alt = 0x12
    vk_f1 = 0x70
    user32.keybd_event(vk_alt, 0, 0, 0)
    user32.keybd_event(vk_f1, 0, 0, 0)
    user32.keybd_event(vk_f1, 0, key_up, 0)
    user32.keybd_event(vk_alt, 0, key_up, 0)


def latest_pngs(directory: Path) -> dict[Path, int]:
    return {path.resolve(): path.stat().st_mtime_ns for path in directory.glob("*.png")}


def wait_for_new_stable_png(
    directory: Path,
    before: dict[Path, int],
    timeout_seconds: float,
) -> Path:
    deadline = time.monotonic() + timeout_seconds
    candidate: Path | None = None
    previous_size = -1
    stable_polls = 0

    while time.monotonic() < deadline:
        current = latest_pngs(directory)
        changed = [
            path
            for path, modified in current.items()
            if path not in before or modified > before[path]
        ]
        if changed:
            newest = max(changed, key=lambda path: current[path])
            size = newest.stat().st_size
            if newest == candidate and size > 0 and size == previous_size:
                stable_polls += 1
                if stable_polls >= 2:
                    return newest
            else:
                candidate = newest
                previous_size = size
                stable_polls = 0
        time.sleep(0.25)

    raise TimeoutError(
        f"No new stable NVIDIA PNG appeared in {directory} within "
        f"{timeout_seconds:.1f} seconds"
    )


def capture_with_nvidia(directory: Path, timeout_seconds: float) -> Path:
    directory = directory.resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"NVIDIA screenshot directory not found: {directory}")
    title = foreground_window_title()
    if "Euro Truck Simulator 2" not in title:
        raise RuntimeError(
            "Refusing Alt+F1 because ETS2 is not the foreground window "
            f"(foreground title: {title!r})"
        )
    before = latest_pngs(directory)
    send_nvidia_screenshot_hotkey()
    return wait_for_new_stable_png(directory, before, timeout_seconds)


def capture_direct(output_dir: Path) -> tuple[Path, Image.Image, float]:
    """Capture foreground ETS2 through Windows without a hotkey.

    A raw evidence image is kept inside the current run directory because
    later confirmation probes use it as an identity reference. Nothing is
    written to the user's NVIDIA screenshot folder.
    """
    title_before = foreground_window_title()
    if "Euro Truck Simulator 2" not in title_before:
        raise RuntimeError(
            "Refusing direct capture because ETS2 is not the foreground window "
            f"(foreground title: {title_before!r})"
        )
    started = time.perf_counter()
    image = ImageGrab.grab(all_screens=False).convert("RGB")
    capture_ms = (time.perf_counter() - started) * 1000
    title_after = foreground_window_title()
    if "Euro Truck Simulator 2" not in title_after:
        raise RuntimeError("ETS2 lost foreground during direct capture")
    if image.size != EXPECTED_SIZE:
        raise RuntimeError(
            f"Direct capture returned {image.size}; expected {EXPECTED_SIZE}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path = output_dir / f"direct-capture-{stamp}.png"
    image.save(path)
    return path, image, capture_ms


def save_result(image: Image.Image, analysis: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    annotated_path = output_dir / f"dry-run-{stamp}.png"
    report_path = output_dir / f"dry-run-{stamp}.json"
    annotate(image, analysis).save(annotated_path)
    report_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    return annotated_path, report_path


def validate_recordings(references: dict[str, Image.Image]) -> int:
    frames = project_root() / "research" / "output" / "video-020357" / "frames"
    cases = {
        "recruitment_agency": (*range(10, 14), 22, 23),
        "garage_selection": range(14, 22),
        "unknown": (0, 4, 6, 8, 26, 29),
    }
    failures = []
    for expected, indices in cases.items():
        for index in indices:
            matches = sorted(frames.glob(f"frame-{index:04d}-*.jpg"))
            if len(matches) != 1:
                failures.append(f"frame {index}: reference lookup failed")
                continue
            image = Image.open(matches[0]).convert("RGB")
            result = analyze(image, references)
            actual = result["state"]
            print(
                f"frame {index:02d}: expected={expected:19s} actual={actual:19s} "
                f"distances={result.get('distances')}"
            )
            if actual != expected:
                failures.append(f"frame {index}: expected {expected}, got {actual}")
    if failures:
        print("VALIDATION_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    driver_check = analyze(references["recruitment"], references)
    if driver_check.get("selected_driver_cards") != [1]:
        print("VALIDATION_FAILED")
        print(f"- selected driver detection: {driver_check.get('selected_driver_cards')}")
        return 1

    slot_expectations = {
        "garage_locked": ["locked"] * 5,
        "garage_free": ["free"] * 5,
        "garage_selected": ["selected_free", "free", "free", "free", "free"],
    }
    for reference_name, expected_states in slot_expectations.items():
        slot_check = analyze(references[reference_name], references)
        actual_states = [slot["state"] for slot in slot_check.get("slots", [])]
        if actual_states != expected_states:
            print("VALIDATION_FAILED")
            print(
                f"- {reference_name} slots: expected {expected_states}, got {actual_states}"
            )
            return 1
    print("VALIDATION_OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--image", type=Path)
    source.add_argument("--capture", action="store_true")
    source.add_argument("--nvidia-capture", action="store_true")
    parser.add_argument("--delay", type=float, default=5.0)
    parser.add_argument("--capture-timeout", type=float, default=15.0)
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        default=DEFAULT_NVIDIA_SCREENSHOT_DIR,
    )
    parser.add_argument("--expected", choices=("recruitment_agency", "garage_selection"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root() / "research" / "output" / "live-dry-run",
    )
    parser.add_argument("--validate-recordings", action="store_true")
    args = parser.parse_args()

    references = load_references()
    if args.validate_recordings:
        return validate_recordings(references)

    capture_hotkeys = 0
    source_screenshot: Path | None = None
    if args.capture:
        print(f"Read-only capture in {args.delay:.1f} seconds. Return to ETS2 now.")
        time.sleep(args.delay)
        try:
            image = ImageGrab.grab(all_screens=False).convert("RGB")
        except OSError as error:
            print(
                "CAPTURE_BLOCKED: Windows could not capture the exclusive-fullscreen "
                f"surface ({error}). Use an NVIDIA/game screenshot with --image instead."
            )
            return 4
    elif args.nvidia_capture:
        print(
            f"NVIDIA capture in {args.delay:.1f} seconds. Return to ETS2 now; "
            "only Alt+F1 will be sent."
        )
        time.sleep(args.delay)
        try:
            source_screenshot = capture_with_nvidia(
                args.screenshot_dir, args.capture_timeout
            )
        except (FileNotFoundError, RuntimeError, TimeoutError) as error:
            print(f"NVIDIA_CAPTURE_FAILED: {error}")
            return 5
        image = Image.open(source_screenshot).convert("RGB")
        capture_hotkeys = 1
    elif args.image:
        image = Image.open(args.image).convert("RGB")
    else:
        parser.error("Use --image, --capture, or --validate-recordings")

    analysis = analyze(image, references)
    analysis["capture_hotkeys_performed"] = capture_hotkeys
    if source_screenshot:
        analysis["source_screenshot"] = str(source_screenshot)
    annotated_path, report_path = save_result(image, analysis, args.output_dir.resolve())
    print(json.dumps(analysis, indent=2))
    print(f"ANNOTATED_SCREENSHOT: {annotated_path}")
    print(f"REPORT: {report_path}")

    if args.expected and analysis["state"] != args.expected:
        print(f"EXPECTED_STATE_MISMATCH: wanted {args.expected}")
        return 2
    return 0 if analysis["state"] not in ("unknown", "unsupported_resolution") else 3


if __name__ == "__main__":
    raise SystemExit(main())
