"""Read-only ETS2 1.60 truck-purchase workflow recognizer.

Recognizes the truck-dealer map, online truck purchase, and truck-delivery
garage modal at 1920x1080.  This module contains no input-control code.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ets2_ui_dry_run import (
    DEFAULT_NVIDIA_SCREENSHOT_DIR,
    EXPECTED_SIZE,
    GARAGE_MAP,
    GARAGE_OK,
    GARAGE_SLOTS,
    classify_slots,
    capture_with_nvidia,
    feature,
    garage_visual_integrity,
    load_references as load_hire_references,
)


DEALER_TITLE = (740, 60, 1180, 106)
PURCHASE_BREADCRUMB = (470, 10, 755, 57)
TRUCK_GARAGE_QUESTION = (655, 65, 1265, 142)
DEALER_MAP = (480, 107, 1791, 925)
BUY_ONLINE = (678, 936, 1039, 973)
VISIT_DEALER = (1050, 936, 1412, 973)
BRAND_BUTTONS = {
    "all": (128, 108, 275, 179),
    "volvo": (128, 186, 275, 257),
    "iveco": (128, 264, 275, 335),
    "daf": (128, 342, 275, 413),
    "man": (128, 420, 275, 491),
    "mercedes_benz": (128, 498, 275, 569),
    "renault": (128, 576, 275, 647),
    "scania": (128, 654, 275, 725),
}
TRUCK_CARDS = (
    (230, 168, 948, 496),
    (972, 168, 1690, 496),
    (230, 520, 948, 846),
    (972, 520, 1690, 846),
)
CUSTOMIZE = (589, 958, 949, 994)
PURCHASE = (970, 958, 1330, 994)
PURCHASE_SUCCESS_MODAL = (588, 344, 1332, 734)
PURCHASE_SUCCESS_TITLE = (790, 356, 1130, 397)
PURCHASE_SUCCESS_MESSAGE = (670, 500, 1250, 565)
PURCHASE_SUCCESS_OK = (900, 674, 1020, 711)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def truck_reference_paths() -> dict[str, Path]:
    frames = project_root() / "research" / "output" / "video-020129" / "frames"
    return {
        "dealer_map": frames / "frame-0027-000013.500s.jpg",
        "truck_purchase": frames / "frame-0042-000021.000s.jpg",
        "truck_garage_locked": frames / "frame-0058-000029.000s.jpg",
        "truck_garage_selected": frames / "frame-0062-000031.000s.jpg",
    }


def load_truck_references() -> dict[str, Image.Image]:
    result = {}
    for name, path in truck_reference_paths().items():
        if not path.is_file():
            raise FileNotFoundError(f"Missing truck recording reference: {path}")
        result[name] = Image.open(path).convert("RGB")
    return result


def patch_distance(
    image: Image.Image,
    image_box: tuple[int, int, int, int],
    reference: Image.Image,
    reference_box: tuple[int, int, int, int],
) -> float:
    return float(np.mean(np.abs(feature(image, image_box) - feature(reference, reference_box))))


def selected_brand(image: Image.Image) -> str | None:
    scores = {}
    for name, box in BRAND_BUTTONS.items():
        rgb = np.asarray(image.crop(box).convert("RGB"), dtype=np.int16)
        yellow = (
            (rgb[:, :, 0] > 135)
            & (rgb[:, :, 1] > 75)
            & (rgb[:, :, 1] < 195)
            & (rgb[:, :, 2] < 75)
            & ((rgb[:, :, 0] - rgb[:, :, 1]) > 25)
        )
        scores[name] = int(yellow.sum())
    best = max(scores, key=scores.get)
    return best if scores[best] >= 400 else None


def dealer_integrity(image: Image.Image) -> dict:
    map_std = float(np.asarray(image.crop(DEALER_MAP).convert("L"), dtype=np.float32).std())
    brand_std = float(
        np.asarray(image.crop((128, 108, 275, 725)).convert("L"), dtype=np.float32).std()
    )
    return {
        "complete": map_std >= 17.5 and brand_std >= 20.0,
        "map_standard_deviation": round(map_std, 2),
        "brand_rail_standard_deviation": round(brand_std, 2),
    }


def purchase_integrity(image: Image.Image) -> dict:
    card_stds = []
    for left, top, right, bottom in TRUCK_CARDS:
        # Exclude the card header and outer margins. Loading cards have a
        # uniform gray interior; rendered trucks create substantial contrast.
        truck_image = (left + 80, top + 50, right - 80, bottom - 20)
        card_stds.append(
            round(
                float(
                    np.asarray(
                        image.crop(truck_image).convert("L"), dtype=np.float32
                    ).std()
                ),
                2,
            )
        )
    return {
        "complete": all(value >= 15.0 for value in card_stds),
        "truck_image_standard_deviation": card_stds,
        "minimum_truck_image_required": 15.0,
    }


def purchase_success_integrity(image: Image.Image) -> dict:
    rgb = np.asarray(image.convert("RGB"), dtype=np.int16)

    def neutral_bright_count(box: tuple[int, int, int, int]) -> int:
        left, top, right, bottom = box
        patch = rgb[top:bottom, left:right]
        chroma = patch.max(axis=2) - patch.min(axis=2)
        return int(((patch.min(axis=2) >= 185) & (chroma <= 28)).sum())

    corner_points = ((610, 360), (1310, 360), (610, 720), (1310, 720))
    corner_luma = [int(rgb[y, x].mean()) for x, y in corner_points]
    left, top, right, bottom = PURCHASE_SUCCESS_OK
    button = rgb[top:bottom, left:right].astype(np.float32)
    button_blue_minus_red = float(np.mean(button[:, :, 2] - button[:, :, 0]))
    title_bright = neutral_bright_count(PURCHASE_SUCCESS_TITLE)
    message_bright = neutral_bright_count(PURCHASE_SUCCESS_MESSAGE)
    complete = (
        max(corner_luma) <= 45
        and title_bright >= 140
        and message_bright >= 260
        and button_blue_minus_red >= 7.0
    )
    return {
        "complete": complete,
        "modal_corner_luma": corner_luma,
        "title_neutral_bright_pixels": title_bright,
        "message_neutral_bright_pixels": message_bright,
        "ok_blue_minus_red": round(button_blue_minus_red, 2),
    }


def recognize(image: Image.Image, references: dict[str, Image.Image]) -> dict:
    if image.size != EXPECTED_SIZE:
        return {
            "state": "unsupported_resolution",
            "resolution": list(image.size),
            "safe_to_act": False,
        }

    success_prompt = purchase_success_integrity(image)
    if success_prompt["complete"]:
        return {
            "state": "truck_purchase_success_prompt",
            "resolution": list(image.size),
            "read_only": True,
            "input_actions_performed": 0,
            "visual_integrity": success_prompt,
            "safe_to_act": True,
            "next_safe_observation": "Acknowledge the purchase-success OK only",
        }

    distances = {
        "dealer_map": patch_distance(
            image, DEALER_TITLE, references["dealer_map"], DEALER_TITLE
        ),
        "truck_purchase": patch_distance(
            image,
            PURCHASE_BREADCRUMB,
            references["truck_purchase"],
            PURCHASE_BREADCRUMB,
        ),
        "truck_garage_selection": patch_distance(
            image,
            TRUCK_GARAGE_QUESTION,
            references["truck_garage_locked"],
            TRUCK_GARAGE_QUESTION,
        ),
    }
    ordered = sorted(distances.items(), key=lambda item: item[1])
    best_name, best_distance = ordered[0]
    margin = ordered[1][1] - best_distance
    state = best_name if best_distance <= 0.44 and margin >= 0.06 else "unknown"
    result = {
        "state": state,
        "resolution": list(image.size),
        "read_only": True,
        "input_actions_performed": 0,
        "distances": {name: round(value, 4) for name, value in distances.items()},
    }

    if state == "dealer_map":
        result["selected_brand"] = selected_brand(image)
        result["visual_integrity"] = dealer_integrity(image)
        result["next_safe_observation"] = "Detect dealer markers; do not click Buy online"
    elif state == "truck_purchase":
        result["visual_integrity"] = purchase_integrity(image)
        result["next_safe_observation"] = "Review truck cards; do not click Purchase"
    elif state == "truck_garage_selection":
        result["slots"] = classify_slots(image, load_hire_references())
        result["visual_integrity"] = garage_visual_integrity(image)
        result["next_safe_observation"] = "Review garage and truck slot; do not press OK"
    else:
        result["visual_integrity"] = {"complete": False}
        result["next_safe_observation"] = "Navigate manually to a supported truck screen"
    result["safe_to_act"] = bool(result["visual_integrity"]["complete"])
    return result


def annotate(image: Image.Image, result: dict) -> Image.Image:
    output = image.copy()
    draw = ImageDraw.Draw(output)
    font = ImageFont.load_default(size=18)
    state = result["state"]
    if state == "dealer_map":
        draw.rectangle(DEALER_MAP, outline="#4cc9f0", width=3)
        for name, box in BRAND_BUTTONS.items():
            color = "#ffae00" if name == result.get("selected_brand") else "#8d99ae"
            draw.rectangle(box, outline=color, width=3)
        draw.rectangle(BUY_ONLINE, outline="#ff5555", width=4)
        draw.text((BUY_ONLINE[0], BUY_ONLINE[1] - 24), "Not clicked", fill="#ff5555", font=font)
    elif state == "truck_purchase":
        for index, box in enumerate(TRUCK_CARDS, start=1):
            draw.rectangle(box, outline="#4cc9f0", width=3)
            draw.text((box[0] + 8, box[1] + 8), f"Truck card {index}", fill="#4cc9f0", font=font)
        draw.rectangle(PURCHASE, outline="#ff5555", width=4)
        draw.text((PURCHASE[0], PURCHASE[1] - 24), "Purchase: not clicked", fill="#ff5555", font=font)
    elif state == "truck_purchase_success_prompt":
        draw.rectangle(PURCHASE_SUCCESS_MODAL, outline="#ffae00", width=4)
        draw.rectangle(PURCHASE_SUCCESS_OK, outline="#50fa7b", width=4)
        draw.text(
            (PURCHASE_SUCCESS_OK[0], PURCHASE_SUCCESS_OK[1] - 24),
            "Purchase acknowledged: not clicked",
            fill="#50fa7b",
            font=font,
        )
    elif state == "truck_garage_selection":
        draw.rectangle(GARAGE_MAP, outline="#4cc9f0", width=3)
        for slot in result.get("slots", []):
            box = GARAGE_SLOTS[slot["slot"] - 1]
            color = {
                "locked": "#8d99ae",
                "free": "#50fa7b",
                "selected_free": "#ffae00",
                "occupied": "#bd93f9",
                "truck_present": "#4cc9f0",
                "unknown": "#ff5555",
            }[slot["state"]]
            draw.rectangle(box, outline=color, width=3)
        draw.rectangle(GARAGE_OK, outline="#ff5555", width=4)
    return output


def validate_recording(references: dict[str, Image.Image]) -> int:
    frames = project_root() / "research" / "output" / "video-020129" / "frames"
    cases = {
        "dealer_map": (27, 30, 32, 34, 36, 38),
        "truck_purchase": (42, 44, 48, 52, 54, 72),
        "truck_garage_selection": (58, 59, 62, 66, 70),
        "unknown": (0, 10, 20, 25, 78, 81),
    }
    failures = []
    for expected, indices in cases.items():
        for index in indices:
            matches = sorted(frames.glob(f"frame-{index:04d}-*.jpg"))
            if len(matches) != 1:
                failures.append(f"frame {index}: reference lookup failed")
                continue
            result = recognize(Image.open(matches[0]).convert("RGB"), references)
            actual = result["state"]
            print(
                f"frame {index:02d}: expected={expected:24s} actual={actual:24s} "
                f"safe={result.get('safe_to_act')} distances={result.get('distances')}"
            )
            if actual != expected:
                failures.append(f"frame {index}: expected {expected}, got {actual}")
    if failures:
        print("TRUCK_VALIDATION_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    # Transitions may still resemble the outgoing state, but must never pass
    # the integrity gate and therefore can never authorize a click.
    for index in (25, 40, 41, 56, 73):
        match = next(frames.glob(f"frame-{index:04d}-*.jpg"))
        transition = recognize(Image.open(match).convert("RGB"), references)
        print(
            f"transition {index:02d}: state={transition['state']:24s} "
            f"safe={transition.get('safe_to_act')}"
        )
        if transition.get("safe_to_act"):
            print("TRUCK_VALIDATION_FAILED")
            print(f"- transition frame {index} incorrectly passed integrity")
            return 1
    print("TRUCK_VALIDATION_OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--image", type=Path)
    source.add_argument("--nvidia-capture", action="store_true")
    parser.add_argument("--validate-recording", action="store_true")
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root() / "research" / "output" / "truck-dry-run",
    )
    args = parser.parse_args()
    references = load_truck_references()
    if args.validate_recording:
        return validate_recording(references)
    source_screenshot = None
    if args.nvidia_capture:
        print(
            f"Read-only truck NVIDIA capture in {args.delay:.1f} seconds. "
            "Return to ETS2; only Alt+F1 will be sent."
        )
        time.sleep(args.delay)
        try:
            source_screenshot = capture_with_nvidia(
                args.screenshot_dir, args.capture_timeout
            )
        except (FileNotFoundError, RuntimeError, TimeoutError) as error:
            print(f"TRUCK_NVIDIA_CAPTURE_FAILED: {error}")
            return 5
        image = Image.open(source_screenshot).convert("RGB")
    elif args.image:
        image = Image.open(args.image).convert("RGB")
    else:
        parser.error("Use --image, --nvidia-capture, or --validate-recording")
    result = recognize(image, references)
    result["capture_hotkeys_performed"] = 1 if source_screenshot else 0
    if source_screenshot:
        result["source_screenshot"] = str(source_screenshot)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    annotated_path = args.output_dir / f"truck-dry-run-{stamp}.png"
    report_path = args.output_dir / f"truck-dry-run-{stamp}.json"
    annotate(image, result).save(annotated_path)
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"ANNOTATED={annotated_path.resolve()}")
    print(f"REPORT={report_path.resolve()}")
    return 0 if result["state"] != "unknown" else 1


if __name__ == "__main__":
    raise SystemExit(main())
