"""Read-only proof that ETS2 loaded the disposable profile selected in FleetFill."""

from __future__ import annotations

import os
import re
import ctypes
import time
from dataclasses import dataclass, field
from pathlib import Path

from fleetfill.domain import ProfileInfo


SET_PROFILE_RE = re.compile(r"Set profile finished: '([^']+)'\s*$")
PROFILE_TYPE_RE = re.compile(r"Profile type:\s*(\S+)\s*$")
NEW_PROFILE_RE = re.compile(r"New profile selected: '([^']+)'\s*$")
SAVE_PATH_RE = re.compile(
    r"/(home|steam)/profiles/([^/\s]+)/save/([^/\s]+)/game\.sii",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ActiveProfileEvidence:
    """The latest profile-selection attempt found in one ETS2 log session."""

    profile_name: str
    profile_type: str | None = None
    confirmed_name: str | None = None
    storage: str | None = None
    profile_folder_id: str | None = None
    save_slot: str | None = None
    selection_line: int = 0
    confirmation_line: int | None = None
    load_line: int | None = None


@dataclass
class _EvidenceBuilder:
    profile_name: str
    selection_line: int
    profile_type: str | None = None
    confirmed_name: str | None = None
    storage: str | None = None
    profile_folder_id: str | None = None
    save_slot: str | None = None
    confirmation_line: int | None = None
    load_line: int | None = None

    def freeze(self) -> ActiveProfileEvidence:
        return ActiveProfileEvidence(**vars(self))


@dataclass(frozen=True)
class ProfilePreflight:
    passed: bool
    summary: str
    problems: tuple[str, ...] = field(default_factory=tuple)
    evidence: ActiveProfileEvidence | None = None
    log_path: Path | None = None


def parse_latest_profile_evidence(log_text: str) -> ActiveProfileEvidence | None:
    """Parse only the latest selection attempt, never an older matching profile."""

    current: _EvidenceBuilder | None = None
    for line_number, line in enumerate(log_text.splitlines(), start=1):
        selected = SET_PROFILE_RE.search(line)
        if selected:
            current = _EvidenceBuilder(selected.group(1), line_number)
            continue
        if current is None:
            continue

        profile_type = PROFILE_TYPE_RE.search(line)
        if profile_type:
            current.profile_type = profile_type.group(1)
            continue

        confirmed = NEW_PROFILE_RE.search(line)
        if confirmed:
            current.confirmed_name = confirmed.group(1)
            current.confirmation_line = line_number
            continue

        save_path = SAVE_PATH_RE.search(line)
        if save_path and current.confirmation_line is not None:
            current.storage = save_path.group(1).lower()
            current.profile_folder_id = save_path.group(2)
            current.save_slot = save_path.group(3)
            current.load_line = line_number

    return current.freeze() if current else None


def game_log_for_profile(profile: ProfileInfo) -> Path:
    """Resolve game.log.txt from an ETS2 profiles/<id> directory."""

    return profile.path.parent.parent / "game.log.txt"


def _ets2_process_id() -> int | None:
    """Find ETS2 with the read-only Windows process snapshot API."""

    if os.name != "nt":
        return None

    class ProcessEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong),
            ("cntUsage", ctypes.c_ulong),
            ("th32ProcessID", ctypes.c_ulong),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", ctypes.c_ulong),
            ("cntThreads", ctypes.c_ulong),
            ("th32ParentProcessID", ctypes.c_ulong),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_ulong),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessEntry32)]
    kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessEntry32)]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    invalid_handle = ctypes.c_void_p(-1).value
    if snapshot == invalid_handle:
        return None
    entry = ProcessEntry32()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        found = bool(kernel32.Process32FirstW(snapshot, ctypes.byref(entry)))
        while found:
            if entry.szExeFile.casefold() == "eurotrucks2.exe":
                return int(entry.th32ProcessID)
            found = bool(kernel32.Process32NextW(snapshot, ctypes.byref(entry)))
        return None
    finally:
        kernel32.CloseHandle(snapshot)


def _process_started_at(process_id: int) -> float | None:
    class FileTime(ctypes.Structure):
        _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.GetProcessTimes.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
    ]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.OpenProcess(0x1000, False, process_id)
    if not handle:
        return None
    created, exited, kernel, user = (FileTime() for _ in range(4))
    try:
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
        windows_ticks = (created.high << 32) + created.low
        return windows_ticks / 10_000_000 - 11_644_473_600
    finally:
        kernel32.CloseHandle(handle)


def is_ets2_running() -> bool:
    return _ets2_process_id() is not None


def assess_active_profile(
    profile: ProfileInfo,
    *,
    log_path: Path | None = None,
    game_running: bool | None = None,
    process_started_at: float | None = None,
) -> ProfilePreflight:
    """Fail closed unless the latest loaded save exactly matches the local profile."""

    path = log_path or game_log_for_profile(profile)
    problems: list[str] = []
    if game_running is None:
        process_id = _ets2_process_id()
        running = process_id is not None
        if process_id is not None:
            process_started_at = _process_started_at(process_id)
    else:
        running = game_running
    if not running:
        problems.append("ETS2 is not running.")
    if not path.is_file():
        problems.append(f"ETS2 game log was not found: {path}")
        return ProfilePreflight(False, "Active profile not verified", tuple(problems), log_path=path)

    try:
        modified_at = path.stat().st_mtime
    except OSError as error:
        problems.append(f"ETS2 game log metadata could not be read: {error}")
        return ProfilePreflight(False, "Active profile not verified", tuple(problems), log_path=path)
    if process_started_at is not None and modified_at < process_started_at - 5:
        age = max(0, round(time.time() - modified_at))
        problems.append(
            f"The ETS2 log predates the current game process ({age} seconds old)."
        )

    try:
        evidence = parse_latest_profile_evidence(path.read_text(encoding="utf-8", errors="replace"))
    except OSError as error:
        problems.append(f"ETS2 game log could not be read: {error}")
        return ProfilePreflight(False, "Active profile not verified", tuple(problems), log_path=path)

    if evidence is None:
        problems.append("No profile-selection evidence exists in the current ETS2 log.")
        return ProfilePreflight(False, "Active profile not verified", tuple(problems), log_path=path)

    expected_id = profile.path.name
    if evidence.profile_name != profile.name:
        problems.append(
            f"ETS2 most recently selected '{evidence.profile_name}', not '{profile.name}'."
        )
    if evidence.profile_type != "PC_local":
        actual = evidence.profile_type or "unknown"
        problems.append(f"The active career is {actual}; FleetFill requires PC_local.")
    if evidence.confirmed_name != profile.name:
        problems.append("The selected career has not been confirmed by ETS2.")
    if evidence.load_line is None:
        problems.append("That career's save has not been loaded yet.")
    if evidence.storage != "home":
        problems.append("The loaded save is not from ETS2's local profile storage.")
    if (evidence.profile_folder_id or "").casefold() != expected_id.casefold():
        problems.append("The loaded save folder does not match the profile chosen in FleetFill.")

    if problems:
        return ProfilePreflight(
            False,
            "Active profile not verified",
            tuple(problems),
            evidence,
            path,
        )
    return ProfilePreflight(
        True,
        f"Active: {profile.name} (local autosave loaded)",
        evidence=evidence,
        log_path=path,
    )
