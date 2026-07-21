"""Reconstruct a FleetFill cloud snapshot in an isolated sandbox."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fleetfill.profile_safety import ProfileSnapshotError, rehearse_steam_cloud_restore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rehearse Steam Cloud recovery without touching live paths"
    )
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = rehearse_steam_cloud_restore(
            args.snapshot.resolve(),
            args.output_dir.resolve(),
        )
    except (ProfileSnapshotError, OSError, ValueError) as error:
        print(f"RESTORE_REHEARSAL_REFUSED: {error}")
        return 2
    print(f"RESTORE_REHEARSAL_REPORT: {args.output_dir.resolve() / 'restore-rehearsal-report.json'}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
