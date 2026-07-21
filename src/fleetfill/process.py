"""Qt process supervision for simulated and eventually live controllers."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from fleetfill.runner import (
    RunnerState,
    SupervisedRun,
    read_checkpoint,
    require_live_execution_enabled,
)


class ControllerProcessSupervisor(QObject):
    state_changed = Signal(object, str)
    checkpoint_changed = Signal(dict)
    run_finished = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.poller = QTimer(self)
        self.poller.setInterval(75)
        self.poller.timeout.connect(self._poll_checkpoint)
        self.model: SupervisedRun | None = None
        self.run_dir: Path | None = None
        self._buffer = ""
        self._checkpoint_stamp: int | None = None

    @property
    def active(self) -> bool:
        return self.process.state() != QProcess.ProcessState.NotRunning

    def start(
        self,
        command: Sequence[str],
        run_dir: Path,
        requested_transactions: int,
        *,
        simulated: bool,
        live_enabled: bool = False,
    ) -> None:
        if self.active:
            raise RuntimeError("A FleetFill controller is already running")
        if not simulated:
            require_live_execution_enabled(enabled=live_enabled)
        self.model = SupervisedRun(requested_transactions=requested_transactions)
        self.run_dir = run_dir
        self._buffer = ""
        self._checkpoint_stamp = None
        self.process.setProgram(str(command[0]))
        self.process.setArguments([str(item) for item in command[1:]])
        self.process.start()
        self.poller.start()

    def request_cancel(self) -> None:
        if self.model is None or self.run_dir is None:
            return
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "cancel.requested").touch(exist_ok=True)
        if self.model.state in {RunnerState.COUNTDOWN, RunnerState.RUNNING}:
            self.model.request_cancel()
            self._emit_latest()

    def _read_output(self) -> None:
        self._buffer += bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if self.model is not None:
                self.model.accept_output_line(line)
                self._emit_latest()

    def _poll_checkpoint(self) -> None:
        if self.run_dir is None or self.model is None:
            return
        path = self.run_dir / "batch-report.json"
        if not path.is_file():
            return
        stamp = path.stat().st_mtime_ns
        if stamp == self._checkpoint_stamp:
            return
        try:
            payload = read_checkpoint(path)
        except (OSError, ValueError):
            return
        self._checkpoint_stamp = stamp
        self.model.accept_checkpoint(payload, report_path=path)
        self.checkpoint_changed.emit(payload)
        self._emit_latest()

    def _process_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._read_output()
        self._poll_checkpoint()
        self.poller.stop()
        if self.model is not None:
            self.model.process_exited(exit_code)
            self._emit_latest()
            self.run_finished.emit(self.model)

    def _process_error(self, _error: QProcess.ProcessError) -> None:
        if self.model is not None and not self.active:
            self.model.process_exited(-1)
            self._emit_latest()
            self.run_finished.emit(self.model)

    def _emit_latest(self) -> None:
        if self.model is None or not self.model.events:
            return
        event = self.model.events[-1]
        self.state_changed.emit(event.state, event.message)
