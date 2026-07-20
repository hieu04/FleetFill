from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fleetfill.preflight import ProfilePreflight
from fleetfill.runner import (
    LiveExecutionLocked,
    RunnerState,
    SupervisedRun,
    read_checkpoint,
    require_live_execution_enabled,
)


class SupervisedRunTests(unittest.TestCase):
    def test_passed_preflight_arms_countdown(self) -> None:
        run = SupervisedRun(requested_transactions=10)
        run.begin_preflight()
        run.accept_preflight(ProfilePreflight(True, "Active test profile verified"))
        self.assertEqual(run.state, RunnerState.COUNTDOWN)

    def test_failed_preflight_stops_before_countdown(self) -> None:
        run = SupervisedRun(requested_transactions=10)
        run.begin_preflight()
        run.accept_preflight(
            ProfilePreflight(False, "Not verified", ("Main profile is active.",))
        )
        self.assertEqual(run.state, RunnerState.FAILED)
        self.assertEqual(run.error, "Main profile is active.")

    def test_checkpoint_updates_visible_progress(self) -> None:
        run = SupervisedRun(requested_transactions=10)
        run.begin_preflight()
        run.accept_preflight(ProfilePreflight(True, "Verified"))
        run.accept_checkpoint(
            {"status": "running", "phase": "trucks", "completed_transactions": 3}
        )
        self.assertEqual(run.state, RunnerState.RUNNING)
        self.assertEqual(run.phase, "trucks")
        self.assertEqual(run.completed_transactions, 3)
        self.assertIn("3 of 10", run.events[-1].message)

    def test_abort_checkpoint_preserves_error_and_report(self) -> None:
        run = SupervisedRun(requested_transactions=10)
        run.begin_preflight()
        run.accept_preflight(ProfilePreflight(True, "Verified"))
        report = Path("run/batch-report.json")
        run.accept_checkpoint(
            {"status": "aborted", "phase": "drivers", "error": "screen mismatch"},
            report_path=report,
        )
        self.assertEqual(run.state, RunnerState.FAILED)
        self.assertEqual(run.error, "screen mismatch")
        self.assertEqual(run.report_path, report)

    def test_output_protocol_records_success_and_report(self) -> None:
        run = SupervisedRun(requested_transactions=10)
        run.accept_output_line("BATCH_READY: begins in 10 seconds")
        run.accept_output_line("BATCH_REPORT: C:/run/batch-report.json")
        run.accept_output_line("BATCH_SUCCEEDED: fill phase completed")
        self.assertEqual(run.state, RunnerState.SUCCEEDED)
        self.assertEqual(run.report_path, Path("C:/run/batch-report.json"))

    def test_cancellation_is_only_available_during_an_active_run(self) -> None:
        run = SupervisedRun(requested_transactions=10)
        with self.assertRaisesRegex(ValueError, "only be cancelled"):
            run.request_cancel()
        run.accept_output_line("BATCH_READY: ready")
        run.request_cancel()
        self.assertEqual(run.state, RunnerState.CANCEL_REQUESTED)

    def test_checkpoint_reader_rejects_non_object_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "batch-report.json"
            path.write_text(json.dumps(["wrong"]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON object"):
                read_checkpoint(path)

    def test_live_execution_remains_centrally_locked(self) -> None:
        with self.assertRaises(LiveExecutionLocked):
            require_live_execution_enabled(enabled=False)
        require_live_execution_enabled(enabled=True)


if __name__ == "__main__":
    unittest.main()
