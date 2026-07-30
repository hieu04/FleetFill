"""Select the first visible ETS2 garage with enough usable capacity.

The live path hovers first, OCRs the city tooltip, and clicks only a garage in
the preflight-approved empty-garage allowlist. This makes target selection
deterministic; the truck-delivery dialog cannot purchase garages. The probe
never clicks a slot or confirmation button.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from PIL import Image

from ets2_garage_icon_detector import detect_garage_markers
from ets2_truck_ui_dry_run import load_truck_references
from ets2_ui_dealer_pan_probe import capture_analyze as capture_truck
from ets2_ui_dry_run import DEFAULT_NVIDIA_SCREENSHOT_DIR, load_references
from ets2_ui_pointer_probe import SAFE_POINTER, capture_analyze_save, set_pointer
from ets2_ui_select_probe import click_left_once


VALID_UNSELECTED_STATES = {"occupied", "truck_present", "free"}
DEFAULT_MAX_MARKERS = 60
GARAGE_TOOLTIP_HALF_WIDTH = 150
GARAGE_TOOLTIP_TOP_OFFSET = 110
GARAGE_TOOLTIP_BOTTOM_OFFSET = 20


def canonical_garage_name(value: str) -> str:
    """Normalize save IDs and rendered city labels for fail-closed matching."""

    value = value.casefold().removeprefix("garage.")
    for source, replacement in {
        "ø": "o",
        "ł": "l",
        "đ": "d",
        "ð": "d",
        "þ": "th",
        "æ": "ae",
        "œ": "oe",
        "ß": "ss",
    }.items():
        value = value.replace(source, replacement)
    value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]", "", value)


def ocr_name_variants(value: str) -> set[str]:
    normalized = canonical_garage_name(value)
    corrected = normalized.translate(str.maketrans({"0": "o", "1": "i", "5": "s", "9": "s"}))
    variants = {normalized, corrected}
    if corrected.startswith("l"):
        variants.add("i" + corrected[1:])
    return {variant for variant in variants if variant}


def resolve_allowed_garage_id(
    observed_name: str, allowed_garage_ids: list[str]
) -> str | None:
    """Resolve OCR text only when it uniquely matches a preflight-owned garage."""

    normalized_allowed = {
        garage_id: canonical_garage_name(garage_id) for garage_id in allowed_garage_ids
    }
    variants = ocr_name_variants(observed_name)
    if not variants:
        return None
    exact = [
        garage_id
        for garage_id, normalized in normalized_allowed.items()
        if normalized in variants
    ]
    if len(exact) == 1:
        return exact[0]
    ranked = sorted(
        (
            max(
                difflib.SequenceMatcher(None, variant, normalized).ratio()
                for variant in variants
            ),
            garage_id,
        )
        for garage_id, normalized in normalized_allowed.items()
    )
    if not ranked:
        return None
    best_score, best_id = ranked[-1]
    second_score = ranked[-2][0] if len(ranked) > 1 else 0.0
    if (
        max(map(len, variants)) >= 5
        and best_score >= 0.82
        and best_score - second_score >= 0.12
    ):
        return best_id
    return None


def identify_hovered_garage(
    image: Image.Image,
    marker: dict,
    output_dir: Path,
) -> tuple[str | None, Path, dict]:
    """OCR the marker tooltip without selecting or purchasing the garage."""

    center_x, center_y = marker["center"]
    left = max(0, center_x - GARAGE_TOOLTIP_HALF_WIDTH)
    right = min(image.width, center_x + GARAGE_TOOLTIP_HALF_WIDTH)
    top = max(0, center_y - GARAGE_TOOLTIP_TOP_OFFSET)
    bottom = max(top + 1, center_y - GARAGE_TOOLTIP_BOTTOM_OFFSET)
    crop = image.crop((left, top, right, bottom)).resize(
        ((right - left) * 3, (bottom - top) * 3), Image.Resampling.BICUBIC
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    crop_path = output_dir / (
        f"garage-tooltip-{marker['candidate']}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.png"
    )
    crop.save(crop_path)
    helper = Path(__file__).resolve().with_name("windows_ocr.ps1")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper),
            "-ImagePath",
            str(crop_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        return None, crop_path, {
            "status": "failed",
            "return_code": completed.returncode,
            "output": completed.stdout.strip(),
        }
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return None, crop_path, {
            "status": "failed",
            "return_code": completed.returncode,
            "output": completed.stdout.strip(),
        }
    lines = [str(line).strip() for line in payload.get("lines", []) if str(line).strip()]
    label = max(lines, key=lambda line: sum(character.isalpha() for character in line), default=None)
    return label, crop_path, {"status": "passed", "text": payload.get("text", ""), "lines": lines}


def exceeds_marker_guard(
    candidate_count: int, max_markers: int = DEFAULT_MAX_MARKERS
) -> bool:
    return candidate_count > max_markers


def slot_counts(states: list[str]) -> dict[str, int]:
    return {
        "occupied": states.count("occupied"),
        "truck_present": states.count("truck_present"),
        "free": states.count("free"),
    }


def is_resolved_unselected(states: list[str]) -> bool:
    return len(states) == 5 and all(state in VALID_UNSELECTED_STATES for state in states)


def has_capacity(states: list[str], context: str, required: int) -> bool:
    if not is_resolved_unselected(states):
        return False
    counts = slot_counts(states)
    available = counts["free"] if context == "truck" else counts["truck_present"]
    return available >= required


def capture_for_context(
    context: str,
    screenshot_dir: Path,
    timeout: float,
    output_dir: Path,
    references,
    integrity_attempts: int,
) -> tuple[Path, Image.Image, dict, Path, Path]:
    if context == "truck":
        return capture_truck(screenshot_dir, timeout, output_dir, references)
    shot, analysis, annotated, report = capture_analyze_save(
        screenshot_dir,
        timeout,
        output_dir,
        references,
        integrity_attempts,
    )
    return shot, Image.open(shot).convert("RGB"), analysis, annotated, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", choices=("truck", "hire"), required=True)
    parser.add_argument("--required", type=int, required=True)
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument("--between-markers", type=float, default=0.7)
    parser.add_argument("--hover-delay", type=float, default=0.35)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument("--integrity-attempts", type=int, default=4)
    parser.add_argument("--max-markers", type=int, default=DEFAULT_MAX_MARKERS)
    parser.add_argument("--allowed-garage-id", action="append", default=[])
    parser.add_argument(
        "--screenshot-dir", type=Path, default=DEFAULT_NVIDIA_SCREENSHOT_DIR
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "output"
        / "live-find-capacity-garage",
    )
    args = parser.parse_args()
    if not 1 <= args.required <= 5:
        parser.error("--required must be between 1 and 5")
    if not args.allowed_garage_id:
        parser.error(
            "at least one --allowed-garage-id from company preflight is required"
        )

    references = load_truck_references() if args.context == "truck" else load_references()
    expected_state = "truck_garage_selection" if args.context == "truck" else "garage_selection"
    output_dir = args.output_dir.resolve()
    capacity_kind = "free slots" if args.context == "truck" else "driverless trucks"
    print(
        f"Capacity-garage finder in {args.delay:.1f} seconds. Return to ETS2. "
        f"It requires {args.required} {capacity_kind}; marker clicks only."
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
    if before.get("state") != expected_state or not before.get("safe_to_act"):
        print(f"FIND_CAPACITY_ABORTED: unsafe starting screen: {before}")
        return 2
    initial_states = [slot["state"] for slot in before.get("slots", [])]
    if initial_states != ["locked"] * 5 and not is_resolved_unselected(initial_states):
        print(
            "FIND_CAPACITY_ABORTED: starting slots were neither locked nor a "
            f"resolved unselected garage: {initial_states}"
        )
        return 3

    candidates = detect_garage_markers(before_image)
    if not candidates:
        print("FIND_CAPACITY_NOT_VISIBLE: no safe garage-marker candidates detected")
    if exceeds_marker_guard(len(candidates), args.max_markers):
        print(
            f"FIND_CAPACITY_ABORTED: {len(candidates)} markers exceed the guard "
            f"limit of {args.max_markers}"
        )
        return 5

    attempts: list[dict] = []
    found: dict | None = None
    for candidate in candidates:
        target = tuple(candidate["center"])
        set_pointer(target)
        identity: dict = {
            "recognized_name": None,
            "garage_id": None,
            "preflight_owned": not args.allowed_garage_id,
        }
        if args.allowed_garage_id:
            time.sleep(args.hover_delay)
            hover_shot, hover_image, hover_analysis, hover_annotated, hover_report = (
                capture_for_context(
                    args.context,
                    args.screenshot_dir,
                    args.capture_timeout,
                    output_dir,
                    references,
                    args.integrity_attempts,
                )
            )
            if (
                hover_analysis.get("state") != expected_state
                or not hover_analysis.get("safe_to_act")
            ):
                print(
                    "FIND_CAPACITY_ABORTED: unsafe screen while identifying "
                    f"candidate {candidate['candidate']}: {hover_analysis}"
                )
                return 6
            recognized_name, tooltip_crop, ocr = identify_hovered_garage(
                hover_image, candidate, output_dir
            )
            garage_id = (
                resolve_allowed_garage_id(recognized_name, args.allowed_garage_id)
                if recognized_name
                else None
            )
            identity = {
                "recognized_name": recognized_name,
                "garage_id": garage_id,
                "preflight_owned": garage_id is not None,
                "hover_screenshot": str(hover_shot),
                "hover_annotated": str(hover_annotated),
                "hover_report": str(hover_report),
                "tooltip_crop": str(tooltip_crop),
                "ocr": ocr,
            }
            if garage_id is None:
                attempts.append(
                    {
                        "candidate": candidate["candidate"],
                        "marker": candidate,
                        "target_position": list(target),
                        "identity": identity,
                        "selected": False,
                        "slot_states": None,
                        "slot_counts": None,
                        "qualifies": False,
                    }
                )
                print(
                    f"candidate {candidate['candidate']} at {target}: "
                    f"hover={recognized_name!a}, not in preflight-owned list; skipped"
                )
                set_pointer(SAFE_POINTER)
                continue
        click_left_once()
        set_pointer(SAFE_POINTER)
        time.sleep(args.between_markers)
        shot, _image, analysis, annotated, report = capture_for_context(
            args.context,
            args.screenshot_dir,
            args.capture_timeout,
            output_dir,
            references,
            args.integrity_attempts,
        )
        if analysis.get("state") != expected_state or not analysis.get("safe_to_act"):
            print(
                "FIND_CAPACITY_ABORTED: UI left the recognized garage dialog "
                f"after candidate {candidate['candidate']}: {analysis}"
            )
            return 6
        states = [slot["state"] for slot in analysis.get("slots", [])]
        attempt = {
            "candidate": candidate["candidate"],
            "marker": candidate,
            "target_position": list(target),
            "identity": identity,
            "selected": True,
            "slot_states": states,
            "slot_counts": slot_counts(states) if is_resolved_unselected(states) else None,
            "qualifies": has_capacity(states, args.context, args.required),
            "screenshot": str(shot),
            "annotated": str(annotated),
            "report": str(report),
        }
        attempts.append(attempt)
        print(
            f"candidate {candidate['candidate']} at {target}: "
            f"slots={states}, qualifies={attempt['qualifies']}"
        )
        if attempt["qualifies"]:
            found = attempt
            break

    set_pointer(SAFE_POINTER)
    summary = {
        "gameplay_transactions": 0,
        "context": args.context,
        "required": args.required,
        "capacity_kind": capacity_kind,
        "garage_marker_hovers": len(attempts) if args.allowed_garage_id else 0,
        "garage_marker_clicks": sum(attempt.get("selected", True) for attempt in attempts),
        "slot_clicks": 0,
        "confirmation_clicks": 0,
        "detected_candidate_count": len(candidates),
        "allowed_garage_ids": args.allowed_garage_id,
        "initial": {
            "screenshot": str(before_shot),
            "annotated": str(before_annotated),
            "report": str(before_report),
            "slot_states": initial_states,
        },
        "attempts": attempts,
        "found": found,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / (
        f"find-capacity-garage-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"FIND_CAPACITY_GARAGE_REPORT: {summary_path}")
    if not found:
        print("FIND_CAPACITY_NOT_VISIBLE: no visible garage had enough capacity")
        return 7
    print(
        "FIND_CAPACITY_SUCCEEDED: a qualifying garage is selected; no slot or "
        "confirmation button was clicked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
