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
    RunHistoryRecord,
    read_history_records,
    read_checkpoint,
    require_live_execution_enabled,
    write_history_record,
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

    def test_running_checkpoint_does_not_clear_pending_cancellation(self) -> None:
        run = SupervisedRun(requested_transactions=10)
        run.accept_output_line("BATCH_READY: ready")
        run.request_cancel()
        run.accept_checkpoint({"status": "running", "completed_transactions": 4})
        self.assertEqual(run.state, RunnerState.CANCEL_REQUESTED)
        self.assertEqual(run.completed_transactions, 4)

    def test_simulation_completion_uses_no_input_message(self) -> None:
        run = SupervisedRun(requested_transactions=2)
        run.accept_checkpoint(
            {
                "status": "completed",
                "phase": "simulation",
                "completed_transactions": 2,
            }
        )
        self.assertEqual(run.state, RunnerState.SUCCEEDED)
        self.assertEqual(run.events[-1].message, "Simulation completed without game input")

    def test_history_record_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "run-1"
            run_dir.mkdir()
            run = SupervisedRun(requested_transactions=2)
            run.accept_output_line("BATCH_SUCCEEDED: complete")
            record = RunHistoryRecord.from_run(
                run,
                run_id="run-1",
                profile_name="Test",
                slots=1,
                simulated=True,
            )
            write_history_record(record, run_dir)
            loaded = read_history_records(root)
        self.assertEqual(loaded, [record])


if __name__ == "__main__":
    unittest.main()
