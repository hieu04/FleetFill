from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from fleetfill.runner import (  # noqa: E402
    RunHistoryRecord,
    RunnerState,
    SupervisedRun,
    write_history_record,
)
from fleetfill.ui import MainWindow  # noqa: E402


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = MainWindow(Path.cwd())

    def tearDown(self) -> None:
        self.window.close()

    def test_has_final_navigation_structure(self) -> None:
        self.assertEqual(
            [button.text() for button in self.window.nav_buttons],
            ["Setup", "History", "Settings"],
        )
        self.assertEqual(self.window.stack.count(), 3)

    def test_default_plan_is_five_trucks_and_drivers(self) -> None:
        page = self.window.setup_page
        self.assertEqual(page.slots_combo.currentData(), 5)
        self.assertEqual(page.review_values["trucks"].text(), "5 identical")
        self.assertEqual(page.review_values["drivers"].text(), "5")
        self.assertEqual(page.total_value.text(), "€1,249,925")

    def test_setup_exposes_active_profile_preflight_and_transient_status(self) -> None:
        page = self.window.setup_page
        self.assertIn("Active ETS2 career", page.active_profile_check.text())
        self.assertTrue(page.run_status_card.isHidden())

        page.show_run_status(RunnerState.COUNTDOWN, "Return to ETS2 now")

        self.assertFalse(page.run_status_card.isHidden())
        self.assertEqual(page.run_status_title.text(), "Return to ETS2")
        self.assertEqual(page.run_status_message.text(), "Return to ETS2 now")
        self.assertFalse(page.cancel_button.isHidden())

    def test_history_page_loads_durable_simulation_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "research" / "output" / "desktop-runs" / "run-1"
            run_dir.mkdir(parents=True)
            run = SupervisedRun(requested_transactions=2)
            run.accept_output_line("BATCH_SUCCEEDED: complete")
            write_history_record(
                RunHistoryRecord.from_run(
                    run,
                    run_id="run-1",
                    profile_name="Test profile",
                    slots=1,
                    simulated=True,
                ),
                run_dir,
            )
            window = MainWindow(root)
            try:
                self.assertEqual(
                    window.history_page.history_title.text(), "Simulation: Succeeded"
                )
                self.assertIn(
                    "Test profile", window.history_page.history_details.text()
                )
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()
