"""Automatic post-exit save-audit supervision for completed live runs."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from fleetfill.preflight import is_ets2_running
from fleetfill.runner import read_history_record, record_save_audit_failure
from fleetfill.runtime import python_executable, resource_root


def save_audit_command(
    run_dir: Path,
    *,
    resources: Path | None = None,
    worker: Path | None = None,
) -> list[str]:
    root = resources or resource_root()
    executable = worker or python_executable()
    script = root / "research" / "tools" / "finalize_batch_validation.py"
    return [str(executable), str(script), str(run_dir.resolve())]


class SaveAuditProcessSupervisor(QObject):
    """Wait for ETS2 to exit, then run the packaged semantic save verifier."""

    status_changed = Signal(str, str, bool)
    audit_finished = Signal(object, bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.poller = QTimer(self)
        self.poller.setInterval(1000)
        self.poller.timeout.connect(self._poll_game)
        self.settle_timer = QTimer(self)
        self.settle_timer.setSingleShot(True)
        self.settle_timer.setInterval(1500)
        self.settle_timer.timeout.connect(self._start_audit)
        self.run_dir: Path | None = None
        self._buffer = ""
        self._finishing = False

    @property
    def active(self) -> bool:
        return self.run_dir is not None

    def arm(self, run_dir: Path) -> None:
        resolved = run_dir.resolve()
        if self.active and self.run_dir != resolved:
            raise RuntimeError("Another FleetFill save audit is already pending")
        self.run_dir = resolved
        self._buffer = ""
        self._finishing = False
        self.status_changed.emit(
            "Waiting for ETS2 to exit",
            "The garage fill passed its runtime checks. Exit ETS2 cleanly; FleetFill will verify the saved result automatically.",
            False,
        )
        self.poller.start()
        self._poll_game()

    def _poll_game(self) -> None:
        if self.run_dir is None or is_ets2_running():
            return
        self.poller.stop()
        self.status_changed.emit(
            "Verifying the saved result",
            "ETS2 has closed. FleetFill is decoding and auditing the new autosave.",
            False,
        )
        self.settle_timer.start()

    def _start_audit(self) -> None:
        if self.run_dir is None:
            return
        if is_ets2_running():
            self.poller.start()
            return
        command: Sequence[str] = save_audit_command(self.run_dir)
        self.process.setProgram(command[0])
        self.process.setArguments(list(command[1:]))
        self.process.start()

    def _read_output(self) -> None:
        self._buffer += bytes(self.process.readAllStandardOutput()).decode(
            "utf-8", "replace"
        )

    def _process_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._read_output()
        if self._finishing or self.run_dir is None:
            return
        self._finishing = True
        run_dir = self.run_dir
        if exit_code == 2 and is_ets2_running():
            self.run_dir = None
            self._finishing = False
            self.arm(run_dir)
            return
        try:
            record = read_history_record(run_dir / "desktop-run.json")
        except (OSError, ValueError, TypeError) as error:
            self._fail(run_dir, f"Could not read the completed save audit: {error}")
            return
        if exit_code == 0 and record.save_audit_passed is True:
            garage = record.target_garage or "the filled garage"
            message = f"Save audit passed. FleetFill verified {garage}."
            self.status_changed.emit("Garage fill verified", message, True)
            self.run_dir = None
            self.audit_finished.emit(run_dir, True, message)
            return
        output = self._buffer.strip().splitlines()
        reason = output[-1] if output else f"Save-audit worker exited with code {exit_code}"
        self._fail(run_dir, reason)

    def _process_error(self, _error: QProcess.ProcessError) -> None:
        if (
            self.run_dir is not None
            and self.process.state() == QProcess.ProcessState.NotRunning
            and not self._finishing
        ):
            self._finishing = True
            self._fail(self.run_dir, self.process.errorString())

    def _fail(self, run_dir: Path, reason: str) -> None:
        message = f"Save audit failed: {reason}"
        try:
            record_save_audit_failure(run_dir, message)
        except (OSError, ValueError, TypeError):
            pass
        self.status_changed.emit("Save audit stopped", message, True)
        self.run_dir = None
        self.audit_finished.emit(run_dir, False, message)
