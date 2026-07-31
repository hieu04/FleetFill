from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fleetfill.simulated_controller import (
    REPORT_REPLACE_ATTEMPTS,
    REPORT_REPLACE_RETRY_DELAY_SECONDS,
    _replace_report,
)


class SimulatedControllerReportTests(unittest.TestCase):
    def test_transient_windows_sharing_lock_is_retried(self) -> None:
        temporary = Mock()
        temporary.replace.side_effect = [PermissionError("sharing lock"), None]
        destination = Path("batch-report.json")

        with patch("fleetfill.simulated_controller.time.sleep") as sleep:
            _replace_report(temporary, destination)

        self.assertEqual(temporary.replace.call_count, 2)
        temporary.replace.assert_called_with(destination)
        sleep.assert_called_once_with(REPORT_REPLACE_RETRY_DELAY_SECONDS)

    def test_persistent_permission_failure_still_fails_closed(self) -> None:
        temporary = Mock()
        temporary.replace.side_effect = PermissionError("persistent denial")

        with patch("fleetfill.simulated_controller.time.sleep") as sleep:
            with self.assertRaises(PermissionError):
                _replace_report(temporary, Path("batch-report.json"))

        self.assertEqual(temporary.replace.call_count, REPORT_REPLACE_ATTEMPTS)
        self.assertEqual(sleep.call_count, REPORT_REPLACE_ATTEMPTS - 1)


if __name__ == "__main__":
    unittest.main()
