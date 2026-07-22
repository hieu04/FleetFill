"""Finalize a FleetFill 1-5 test run after ETS2 has exited cleanly.

This tool is read-only with respect to the ETS2 profile. It copies the stable
post-run autosave into the run evidence directory, decodes before/after copies,
and invokes the semantic save verifier.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


PER_SLOT_COST_EUR = 249_985


def load_run_paths(run_dir: Path) -> tuple[Path, Path, int]:
    preflight = json.loads((run_dir / "preflight.json").read_text(encoding="utf-8"))
    count = int(preflight.get("count", 0))
    if preflight.get("phase") != "fill" or not 1 <= count <= 5:
        raise ValueError("Run evidence is not a guarded one-to-five fill batch")
    profile = Path(preflight["backup"]["profile"])
    backup = preflight["backup"]
    before_save = Path(
        backup.get(
            "baseline_save",
            backup.get("autosave", Path(backup["backup"]) / "autosave"),
        )
    )
    before = before_save / "game.sii"
    if not profile.is_dir() or not before.is_file():
        raise ValueError("Run evidence does not contain a usable profile backup")
    return profile, before, count


def run_checked(command: list[str], *, cwd: Path | None = None) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode:
        raise RuntimeError(
            f"Evidence command failed with exit code {completed.returncode}: "
            + subprocess.list2cmdline(command)
        )


def record_save_audit(run_dir: Path, *, passed: bool, report: Path | None) -> None:
    """Persist the deep result into both runtime evidence and app History."""

    target_garage = None
    if report and report.is_file():
        audit = json.loads(report.read_text(encoding="utf-8"))
        target_garage = audit.get("target_garage")
    runtime_report = run_dir / "validation-report.json"
    if runtime_report.is_file():
        payload = json.loads(runtime_report.read_text(encoding="utf-8"))
        payload["deep_save_verification"] = "passed" if passed else "failed"
        payload["save_audit"] = str(report.resolve()) if report else None
        payload["target_garage"] = target_garage
        runtime_report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    desktop_record = run_dir / "desktop-run.json"
    if desktop_record.is_file():
        payload = json.loads(desktop_record.read_text(encoding="utf-8"))
        payload["save_audit_passed"] = passed
        payload["save_audit_report"] = str(report.resolve()) if report else None
        payload["target_garage"] = target_garage
        desktop_record.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()

    from fleetfill.preflight import is_ets2_running

    if is_ets2_running():
        print("VALIDATION_REFUSED: Exit ETS2 cleanly before copying the post-run save.")
        return 2

    run_dir = args.run_dir.resolve()
    profile, before, count = load_run_paths(run_dir)
    current = profile / "save" / "autosave" / "game.sii"
    if not current.is_file():
        print(f"VALIDATION_REFUSED: Current autosave was not found: {current}")
        return 2

    evidence_dir = run_dir / "post-exit-save-audit"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    after = evidence_dir / "after-game.sii"
    shutil.copy2(current, after)

    tools_dir = Path(__file__).resolve().parent
    inspector = tools_dir / "save-inspector"
    decoder = inspector / "decrypt-save.mjs"
    before_text = evidence_dir / "before-game.txt"
    after_text = evidence_dir / "after-game.txt"
    report = evidence_dir / "save-audit.json"
    try:
        run_checked(["node", str(decoder), str(before), str(before_text)], cwd=inspector)
        run_checked(["node", str(decoder), str(after), str(after_text)], cwd=inspector)
    except (OSError, RuntimeError, ValueError) as error:
        record_save_audit(run_dir, passed=False, report=None)
        print(f"VALIDATION_FAILED: {error}")
        return 1
    verification = subprocess.run(
        [
            sys.executable,
            str(tools_dir / "verify_fill_batch_save.py"),
            str(before_text),
            str(after_text),
            "--count",
            str(count),
            "--expected-cost",
            str(count * PER_SLOT_COST_EUR),
            "--output",
            str(report),
        ],
        cwd=tools_dir,
        check=False,
    )
    passed = verification.returncode == 0
    record_save_audit(run_dir, passed=passed, report=report if report.is_file() else None)
    if not passed:
        print("VALIDATION_FAILED: The semantic save audit did not pass.")
        return 1
    print(f"FLEETFILL_BATCH_SAVE_AUDIT: {report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
