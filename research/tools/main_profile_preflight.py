"""Zero-input identity, recovery, and company preflight for a Steam Cloud career."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from fleetfill.domain import discover_steam_cloud_profiles
from fleetfill.preflight import (
    assess_active_profile,
    ets2_process_started_at,
    newest_session_save,
)
from fleetfill.profile_safety import ProfileSnapshotError, create_steam_cloud_snapshot

from ets2_batch_controller import BatchAbort, validate_company_preflight


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prove a Steam Cloud profile without sending any game input"
    )
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--count", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--output-dir", type=Path)
    return parser


def select_exact_profile(profile_name: str):
    matches = [
        profile
        for profile in discover_steam_cloud_profiles()
        if profile.name == profile_name
    ]
    if len(matches) != 1:
        raise ProfileSnapshotError(
            f"Expected exactly one Steam Cloud profile named '{profile_name}', "
            f"found {len(matches)}."
        )
    return matches[0]


def inspect_snapshot(snapshot: Path, tools_dir: Path, save_slot: str = "autosave") -> dict:
    source = snapshot / "steam-cloud-profile" / "save" / save_slot / "game.sii"
    decoded = snapshot / f"decoded-{save_slot}.sii"
    report = snapshot / "company-report.json"
    commands = [
        ["node", str(tools_dir / "save-inspector" / "decrypt-save.mjs"), str(source), str(decoded)],
        [sys.executable, str(tools_dir / "inspect_company_save.py"), str(decoded), "--output", str(report)],
    ]
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=tools_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode:
            detail = completed.stdout.strip().splitlines()[-1:]
            raise ProfileSnapshotError(
                "Copied-save inspection failed" + (f": {detail[0]}" if detail else "")
            )
    return json.loads(report.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tools_dir = Path(__file__).resolve().parent
    output = (
        args.output_dir.resolve()
        if args.output_dir
        else tools_dir.parent / "output" / "main-profile-preflight" / datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    result: dict = {
        "mode": "zero-input-main-profile-preflight",
        "profile_name": args.profile_name,
        "count": args.count,
        "passed": False,
        "input_sent": False,
    }
    try:
        profile = select_exact_profile(args.profile_name)
        active = assess_active_profile(profile)
        result["active_profile"] = {
            "passed": active.passed,
            "summary": active.summary,
            "problems": list(active.problems),
            "evidence": asdict(active.evidence) if active.evidence else None,
        }
        if not active.passed:
            raise ProfileSnapshotError("; ".join(active.problems))
        process_started_at = ets2_process_started_at()
        if process_started_at is None:
            raise ProfileSnapshotError(
                "The current ETS2 process start time could not be verified."
            )
        baseline = newest_session_save(profile, process_started_at)
        if baseline is None:
            raise ProfileSnapshotError(
                "The Steam Cloud career has not been saved during this ETS2 session."
            )
        snapshot = output / "recovery-snapshot"
        result["snapshot"] = create_steam_cloud_snapshot(profile, snapshot)
        result["baseline_save"] = {
            "slot": baseline.slot,
            "modified_at": baseline.modified_at,
        }
        company = inspect_snapshot(snapshot, tools_dir, baseline.slot)
        result["company"] = validate_company_preflight(company, args.count)
        result["passed"] = True
    except (ProfileSnapshotError, BatchAbort, OSError, ValueError, json.JSONDecodeError) as error:
        result["error"] = str(error)

    output.mkdir(parents=True, exist_ok=True)
    report = output / "main-profile-preflight.json"
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"MAIN_PROFILE_PREFLIGHT_REPORT: {report.resolve()}")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
