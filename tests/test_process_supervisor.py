from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from fleetfill.domain import FillRequest, simulator_arguments  # noqa: E402
from fleetfill.process import ControllerProcessSupervisor  # noqa: E402
from fleetfill.runner import LiveExecutionLocked, RunnerState  # noqa: E402


class ProcessSupervisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def run_until_finished(self, supervisor: ControllerProcessSupervisor, timeout_ms: int = 5000):
        loop = QEventLoop()
        results = []
        supervisor.run_finished.connect(lambda model: (results.append(model), loop.quit()))
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()
        self.assertTrue(results, "supervised process timed out")
        return results[0]

    def test_simulator_streams_checkpoints_to_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "success"
            supervisor = ControllerProcessSupervisor()
            checkpoints = []
            supervisor.checkpoint_changed.connect(checkpoints.append)
            supervisor.start(
                simulator_arguments(
                    FillRequest(profile=None, slots=2),
                    run_dir,
                    countdown=0.05,
                    step_delay=0.03,
                ),
                run_dir,
                4,
                simulated=True,
            )
            model = self.run_until_finished(supervisor)

        self.assertEqual(model.state, RunnerState.SUCCEEDED)
        self.assertEqual(model.completed_transactions, 4)
        self.assertTrue(checkpoints)

    def test_simulator_cancels_cooperatively_during_countdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "cancelled"
            supervisor = ControllerProcessSupervisor()
            supervisor.start(
                simulator_arguments(
                    FillRequest(profile=None, slots=1),
                    run_dir,
                    countdown=1.0,
                    step_delay=0.05,
                ),
                run_dir,
                2,
                simulated=True,
            )
            QTimer.singleShot(150, supervisor.request_cancel)
            model = self.run_until_finished(supervisor)

        self.assertEqual(model.state, RunnerState.CANCELLED)
        self.assertEqual(model.completed_transactions, 0)

    def test_real_controller_stays_locked(self) -> None:
        supervisor = ControllerProcessSupervisor()
        with self.assertRaises(LiveExecutionLocked):
            supervisor.start(
                ["never-runs"],
                Path("run"),
                2,
                simulated=False,
                live_enabled=False,
            )


if __name__ == "__main__":
    unittest.main()
