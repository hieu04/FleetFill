from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from fleetfill.runner import RunnerState  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
