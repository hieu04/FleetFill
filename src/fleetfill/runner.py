"""Testable state model for the future guarded controller subprocess."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from fleetfill.preflight import ProfilePreflight


class RunnerState(str, Enum):
    IDLE = "idle"
    PREFLIGHT = "preflight"
    COUNTDOWN = "countdown"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


TERMINAL_STATES = {RunnerState.SUCCEEDED, RunnerState.FAILED}


@dataclass(frozen=True)
class RunnerEvent:
    state: RunnerState
    message: str


@dataclass
class SupervisedRun:
    """Own progress independently of Qt and subprocess implementation details."""

    requested_transactions: int
    state: RunnerState = RunnerState.IDLE
    completed_transactions: int = 0
    phase: str | None = None
    report_path: Path | None = None
    backup_path: Path | None = None
    error: str | None = None
    events: list[RunnerEvent] = field(default_factory=list)

    def begin_preflight(self) -> None:
        self._move(RunnerState.PREFLIGHT, "Checking the active ETS2 profile")

    def accept_preflight(self, result: ProfilePreflight) -> None:
        if self.state != RunnerState.PREFLIGHT:
            raise ValueError("Preflight result arrived outside the preflight state")
        if not result.passed:
            self.error = "; ".join(result.problems) or result.summary
            self._move(RunnerState.FAILED, self.error)
            return
        self._move(RunnerState.COUNTDOWN, result.summary)

    def accept_output_line(self, line: str) -> None:
        line = line.strip()
        if line.startswith("BATCH_READY:"):
            self._move(RunnerState.COUNTDOWN, line.removeprefix("BATCH_READY:").strip())
        elif line.startswith("BATCH_ABORTED:"):
            self.error = line.removeprefix("BATCH_ABORTED:").strip()
            self._move(RunnerState.FAILED, self.error)
        elif line.startswith("BATCH_SUCCEEDED:"):
            self._move(RunnerState.SUCCEEDED, line.removeprefix("BATCH_SUCCEEDED:").strip())
        elif line.startswith("BATCH_REPORT:"):
            self.report_path = Path(line.removeprefix("BATCH_REPORT:").strip())

    def accept_checkpoint(
        self,
        payload: Mapping[str, Any],
        *,
        report_path: Path | None = None,
    ) -> None:
        status = str(payload.get("status", "")).casefold()
        self.phase = str(payload.get("phase")) if payload.get("phase") else self.phase
        self.completed_transactions = int(payload.get("completed_transactions", 0))
        if report_path is not None:
            self.report_path = report_path

        if status == "ready":
            self._move(RunnerState.COUNTDOWN, "Controller is ready; return to ETS2")
        elif status == "running":
            self._move(
                RunnerState.RUNNING,
                f"Completed {self.completed_transactions} of {self.requested_transactions} actions",
            )
        elif status == "completed":
            self._move(RunnerState.SUCCEEDED, "Fleet fill completed")
        elif status == "aborted":
            self.error = str(payload.get("error") or "Controller aborted")
            self._move(RunnerState.FAILED, self.error)

    def request_cancel(self) -> None:
        if self.state not in {RunnerState.COUNTDOWN, RunnerState.RUNNING}:
            raise ValueError("A run can only be cancelled during countdown or execution")
        self._move(RunnerState.CANCEL_REQUESTED, "Cancellation requested")

    def process_exited(self, exit_code: int) -> None:
        if self.state in TERMINAL_STATES:
            return
        if exit_code == 0:
            self._move(RunnerState.SUCCEEDED, "Controller process exited successfully")
        else:
            self.error = self.error or f"Controller process exited with code {exit_code}"
            self._move(RunnerState.FAILED, self.error)

    def _move(self, state: RunnerState, message: str) -> None:
        if self.state in TERMINAL_STATES and state != self.state:
            raise ValueError("A completed run cannot change state")
        self.state = state
        self.events.append(RunnerEvent(state, message))


def read_checkpoint(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Controller checkpoint must contain a JSON object")
    return payload


class LiveExecutionLocked(RuntimeError):
    pass


def require_live_execution_enabled(*, enabled: bool) -> None:
    """Central lock used until the subprocess boundary passes supervised testing."""

    if not enabled:
        raise LiveExecutionLocked("Live controller execution is not enabled in this build")
