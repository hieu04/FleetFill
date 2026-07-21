"""Pure application models shared by the desktop UI and future runner service."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


TRUCK_PRICE_EUR = 248_485
DRIVER_HIRE_COST_EUR = 1_500
SUPPORTED_GAME_VERSION = "1.60"
SUPPORTED_RESOLUTION = "1920 x 1080"
SUPPORTED_LANGUAGE = "English"


@dataclass(frozen=True)
class ProfileInfo:
    name: str
    path: Path


@dataclass(frozen=True)
class FillRequest:
    profile: Path | None
    slots: int = 5
    garage_policy: str = "automatic"
    truck_template: str = "scania_streamline_topline"
    driver_policy: str = "first_available"

    @property
    def truck_cost_eur(self) -> int:
        return self.slots * TRUCK_PRICE_EUR

    @property
    def driver_cost_eur(self) -> int:
        return self.slots * DRIVER_HIRE_COST_EUR

    @property
    def total_cost_eur(self) -> int:
        return self.truck_cost_eur + self.driver_cost_eur


def decode_profile_folder_name(folder_name: str) -> str:
    """Decode ETS2's hex profile folder convention, falling back safely."""

    try:
        decoded = bytes.fromhex(folder_name).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return folder_name
    return decoded.strip() or folder_name


def candidate_profile_roots(
    *,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[Path]:
    home = (home or Path.home()).resolve()
    if environ is None:
        environ = os.environ
    candidates = [
        home / "Documents" / "Euro Truck Simulator 2" / "profiles",
        home / "OneDrive" / "Documents" / "Euro Truck Simulator 2" / "profiles",
    ]
    one_drive = environ.get("OneDrive")
    if one_drive:
        candidates.append(
            Path(one_drive) / "Documents" / "Euro Truck Simulator 2" / "profiles"
        )

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def discover_local_profiles(
    *,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[ProfileInfo]:
    profiles: list[ProfileInfo] = []
    seen: set[str] = set()
    for root in candidate_profile_roots(home=home, environ=environ):
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if not path.is_dir() or not (path / "profile.sii").is_file():
                continue
            key = os.path.normcase(str(path.resolve()))
            if key in seen:
                continue
            seen.add(key)
            profiles.append(ProfileInfo(decode_profile_folder_name(path.name), path))
    return sorted(profiles, key=lambda profile: profile.name.casefold())


def validate_request(request: FillRequest) -> list[str]:
    errors: list[str] = []
    if not 1 <= request.slots <= 5:
        errors.append("Slots to fill must be between 1 and 5.")
    if request.profile is None:
        errors.append("Choose a disposable local ETS2 profile.")
        return errors
    if not request.profile.is_dir():
        errors.append("The selected profile folder does not exist.")
        return errors
    if not (request.profile / "profile.sii").is_file():
        errors.append("The selected folder is not an ETS2 profile.")
    if not (request.profile / "save" / "autosave").is_dir():
        errors.append("The selected profile does not contain an autosave.")
    return errors


def controller_arguments(
    request: FillRequest,
    project_root: Path,
    output_dir: Path | None = None,
) -> list[str]:
    """Return the currently supported guarded controller invocation."""

    if request.profile is None:
        raise ValueError("A profile is required to build the controller command")
    arguments = [
        sys.executable,
        str(project_root / "research" / "tools" / "ets2_batch_controller.py"),
        "fill",
        "--execute",
        "--profile",
        str(request.profile),
        "--occupied",
        "0",
        "--truck-present",
        "0",
        "--free",
        "5",
        "--count",
        str(request.slots),
        "--card",
        "1",
        "--start-stage",
        "home",
        "--dynamic-garage",
    ]
    if output_dir is not None:
        arguments.extend(
            [
                "--output-dir",
                str(output_dir),
                "--cancel-file",
                str(output_dir / "cancel.requested"),
            ]
        )
    return arguments


def controller_command_preview(request: FillRequest, project_root: Path) -> str:
    return subprocess.list2cmdline(controller_arguments(request, project_root))


def simulator_arguments(
    request: FillRequest,
    output_dir: Path,
    *,
    countdown: float = 1.0,
    step_delay: float = 0.15,
) -> list[str]:
    arguments = [
        sys.executable,
        "-m",
        "fleetfill.simulated_controller",
        "--output-dir",
        str(output_dir),
        "--transactions",
        str(request.slots * 2),
        "--countdown",
        str(countdown),
        "--step-delay",
        str(step_delay),
    ]
    return arguments
