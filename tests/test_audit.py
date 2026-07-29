from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication

from fleetfill.audit import SaveAuditProcessSupervisor, save_audit_command


class SaveAuditProcessSupervisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_command_uses_explicit_worker_and_packaged_script(self) -> None:
        command = save_audit_command(
            Path("run"),
            resources=Path("bundle"),
            worker=Path("FleetFillWorker.exe"),
        )
        self.assertEqual(command[0], "FleetFillWorker.exe")
        self.assertEqual(
            Path(command[1]),
            Path("bundle/research/tools/finalize_batch_validation.py"),
        )
        self.assertTrue(Path(command[2]).is_absolute())

    def test_arm_waits_without_starting_a_process_while_ets2_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            statuses: list[tuple[str, str, bool]] = []
            supervisor = SaveAuditProcessSupervisor()
            supervisor.status_changed.connect(
                lambda title, message, terminal: statuses.append(
                    (title, message, terminal)
                )
            )
            with patch("fleetfill.audit.is_ets2_running", return_value=True):
                supervisor.arm(Path(temp))
            self.assertTrue(supervisor.active)
            self.assertTrue(supervisor.poller.isActive())
            self.assertEqual(statuses[-1][0], "Waiting for ETS2 to exit")
            self.assertFalse(statuses[-1][2])
            supervisor.poller.stop()


if __name__ == "__main__":
    unittest.main()
