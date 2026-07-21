"""No-input controller used to prove FleetFill's desktop process lifecycle."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path


def write_report(path: Path, status: str, completed: int, requested: int, error: str | None = None) -> None:
    payload = {
        "status": status,
        "phase": "simulation",
        "completed_transactions": completed,
        "requested_transactions": requested,
        "error": error,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def cancellable_wait(seconds: float, cancel_file: Path) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if cancel_file.exists():
            return False
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    return not cancel_file.exists()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--transactions", type=int, required=True)
    parser.add_argument("--countdown", type=float, default=1.0)
    parser.add_argument("--step-delay", type=float, default=0.15)
    args = parser.parse_args()

    run_dir = args.output_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    report = run_dir / "batch-report.json"
    cancel_file = run_dir / "cancel.requested"
    write_report(report, "ready", 0, args.transactions)
    print(f"BATCH_REPORT: {report}", flush=True)
    print(f"BATCH_READY: simulation begins in {args.countdown:.1f}s", flush=True)
    if not cancellable_wait(args.countdown, cancel_file):
        write_report(report, "cancelled", 0, args.transactions, "Cancelled during countdown")
        print("BATCH_CANCELLED: Cancelled during countdown", flush=True)
        return 2

    for completed in range(1, args.transactions + 1):
        if not cancellable_wait(args.step_delay, cancel_file):
            write_report(report, "cancelled", completed - 1, args.transactions, "Cancelled between guarded actions")
            print("BATCH_CANCELLED: Cancelled between guarded actions", flush=True)
            return 2
        write_report(report, "running", completed, args.transactions)
        print(f"SIMULATED_STEP: {completed}/{args.transactions}", flush=True)

    write_report(report, "completed", args.transactions, args.transactions)
    print("BATCH_SUCCEEDED: simulation completed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
