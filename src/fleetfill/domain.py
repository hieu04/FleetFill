"""Pure application models shared by the desktop UI and future runner service."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from fleetfill.runtime import python_executable


TRUCK_PRICE_EUR = 248_485
DRIVER_HIRE_COST_EUR = 1_500
SUPPORTED_GAME_VERSION = "1.60"
SUPPORTED_RESOLUTION = "1920 x 1080"
SUPPORTED_LANGUAGE = "English"
VALIDATION_PROFILE_NAME = "ETS2 Automation Test"
LOCAL_PROFILE_STORAGE = "local"
STEAM_CLOUD_PROFILE_STORAGE = "steam_cloud"
MAIN_PROFILE_VALIDATION_BOUNDARIES = (1, 2, 3, 5)


@dataclass(frozen=True)
class ProfileInfo:
    name: str
    path: Path
    storage: str = LOCAL_PROFILE_STORAGE
    documents_root: Path | None = None
    companion_path: Path | None = None
    steam_metadata_path: Path | None = None

    @property
    def is_steam_cloud(self) -> bool:
        return self.storage == STEAM_CLOUD_PROFILE_STORAGE


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


def candidate_steam_userdata_roots(
    *,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[Path]:
    """Return plausible Steam userdata roots without touching the registry."""

    home = (home or Path.home()).resolve()
    if environ is None:
        environ = os.environ
    candidates: list[Path] = []
    explicit = environ.get("FLEETFILL_STEAM_USERDATA")
    if explicit:
        candidates.append(Path(explicit))
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        value = environ.get(variable)
        if value:
            candidates.append(Path(value) / "Steam" / "userdata")
    candidates.extend(
        [
            home / "AppData" / "Local" / "Steam" / "userdata",
            Path("C:/Program Files (x86)/Steam/userdata"),
            Path("C:/Program Files/Steam/userdata"),
        ]
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


def discover_steam_cloud_profiles(
    *,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
    userdata_roots: list[Path] | None = None,
) -> list[ProfileInfo]:
    """Discover authoritative ETS2 Steam Cloud profiles and recovery companions."""

    home = (home or Path.home()).resolve()
    if environ is None:
        environ = os.environ
    documents_roots = [root.parent for root in candidate_profile_roots(home=home, environ=environ)]
    companion_by_id: dict[str, tuple[Path, Path]] = {}
    for documents_root in documents_roots:
        mirror = documents_root / "steam_profiles"
        try:
            mirror_exists = mirror.is_dir()
        except OSError:
            mirror_exists = False
        if not mirror_exists:
            continue
        try:
            mirror_entries = list(mirror.iterdir())
        except OSError:
            continue
        for path in mirror_entries:
            if path.is_dir():
                companion_by_id.setdefault(path.name.casefold(), (path, documents_root))

    roots = userdata_roots or candidate_steam_userdata_roots(home=home, environ=environ)
    profiles: list[ProfileInfo] = []
    seen: set[str] = set()
    for userdata_root in roots:
        try:
            root_exists = userdata_root.is_dir()
        except OSError:
            root_exists = False
        if not root_exists:
            continue
        try:
            accounts = list(userdata_root.iterdir())
        except OSError:
            continue
        for account in accounts:
            app_root = account / "227300"
            profiles_root = app_root / "remote" / "profiles"
            try:
                profiles_root_exists = profiles_root.is_dir()
            except OSError:
                profiles_root_exists = False
            if not profiles_root_exists:
                continue
            metadata = app_root / "remotecache.vdf"
            try:
                profile_entries = list(profiles_root.iterdir())
            except OSError:
                continue
            for path in profile_entries:
                if (
                    not path.is_dir()
                    or not (path / "profile.sii").is_file()
                    or not (path / "save" / "autosave").is_dir()
                ):
                    continue
                key = os.path.normcase(str(path.resolve()))
                if key in seen:
                    continue
                seen.add(key)
                companion, documents_root = companion_by_id.get(
                    path.name.casefold(),
                    (None, None),
                )
                profiles.append(
                    ProfileInfo(
                        decode_profile_folder_name(path.name),
                        path,
                        storage=STEAM_CLOUD_PROFILE_STORAGE,
                        documents_root=documents_root,
                        companion_path=companion,
                        steam_metadata_path=metadata if metadata.is_file() else None,
                    )
                )
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


def validate_live_validation_request(
    request: FillRequest,
    profile: ProfileInfo,
    *,
    enabled: bool,
) -> list[str]:
    """Apply the deliberately narrow gate for the first supervised live run."""

    errors = validate_request(request)
    if not enabled:
        errors.append("The one-plus-one live validation launcher is not armed.")
    if request.slots != 1:
        errors.append("Live validation is limited to exactly one truck and one driver.")
    if profile.name != VALIDATION_PROFILE_NAME:
        errors.append(
            f"Live validation requires the '{VALIDATION_PROFILE_NAME}' career."
        )
    if request.profile is not None and profile.path.resolve() != request.profile.resolve():
        errors.append("The reviewed profile does not match the selected profile folder.")
    return errors


def validate_graduated_live_request(
    request: FillRequest,
    profile: ProfileInfo,
    *,
    enabled: bool,
) -> list[str]:
    """Gate the first desktop-controlled one-to-five test-profile batches."""

    errors = validate_request(request)
    if not enabled:
        errors.append("The graduated live-test launcher is not armed.")
    if profile.name != VALIDATION_PROFILE_NAME:
        errors.append(
            f"Graduated live testing requires the '{VALIDATION_PROFILE_NAME}' career."
        )
    if request.profile is not None and profile.path.resolve() != request.profile.resolve():
        errors.append("The reviewed profile does not match the selected profile folder.")
    return errors


def validate_main_profile_validation_request(
    request: FillRequest,
    profile: ProfileInfo,
    *,
    enabled: bool,
    expected_profile_name: str | None,
    expected_slots: int = 1,
) -> list[str]:
    """Gate one explicitly armed Steam Cloud validation boundary."""

    errors = validate_request(request)
    if not enabled or not expected_profile_name:
        errors.append("The main-profile validation launcher is not armed.")
    if expected_slots not in MAIN_PROFILE_VALIDATION_BOUNDARIES:
        errors.append(
            "Main-profile validation supports only the certified 1+1, 2+2, "
            "and 3+3 boundaries plus the guarded 5+5 boundary."
        )
    elif request.slots != expected_slots:
        quantity = {1: "one", 2: "two", 3: "three", 5: "five"}[expected_slots]
        errors.append(
            f"Main-profile validation is limited to exactly {quantity} "
            f"truck{'s' if expected_slots != 1 else ''} and {quantity} "
            f"driver{'s' if expected_slots != 1 else ''}."
        )
    if not profile.is_steam_cloud:
        errors.append("Main-profile validation requires an authoritative Steam Cloud profile.")
    if expected_profile_name and profile.name != expected_profile_name:
        errors.append(
            f"Main-profile validation requires the '{expected_profile_name}' career."
        )
    if profile.documents_root is None:
        errors.append("The ETS2 Documents root for the cloud career is missing.")
    if profile.companion_path is None or not profile.companion_path.is_dir():
        errors.append("The Documents-side Steam profile companion is missing.")
    if profile.steam_metadata_path is None or not profile.steam_metadata_path.is_file():
        errors.append("Steam remotecache.vdf metadata is missing.")
    if request.profile is not None and profile.path.resolve() != request.profile.resolve():
        errors.append("The reviewed cloud profile does not match the selected folder.")
    return errors


def validate_personal_beta_request(
    request: FillRequest,
    profile: ProfileInfo,
    *,
    enabled: bool,
) -> list[str]:
    """Gate the fixed-scope personal beta to the certified cloud 5+5 path."""

    errors = validate_request(request)
    if not enabled:
        errors.append("The FleetFill personal beta is not armed.")
    if request.slots != 5:
        errors.append(
            "The personal beta is limited to exactly five trucks and five drivers."
        )
    if not profile.is_steam_cloud:
        errors.append("The personal beta requires an authoritative Steam Cloud profile.")
    if profile.documents_root is None:
        errors.append("The ETS2 Documents root for the cloud career is missing.")
    if profile.companion_path is None or not profile.companion_path.is_dir():
        errors.append("The Documents-side Steam profile companion is missing.")
    if profile.steam_metadata_path is None or not profile.steam_metadata_path.is_file():
        errors.append("Steam remotecache.vdf metadata is missing.")
    if request.profile is not None and profile.path.resolve() != request.profile.resolve():
        errors.append("The reviewed cloud profile does not match the selected folder.")
    return errors


def controller_arguments(
    request: FillRequest,
    project_root: Path,
    output_dir: Path | None = None,
    *,
    steam_cloud_profile: ProfileInfo | None = None,
) -> list[str]:
    """Return the currently supported guarded controller invocation."""

    if request.profile is None:
        raise ValueError("A profile is required to build the controller command")
    arguments = [
        str(python_executable()),
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
        "--require-empty-garage",
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
    if steam_cloud_profile is not None:
        if not steam_cloud_profile.is_steam_cloud:
            raise ValueError("Steam Cloud controller arguments require a cloud profile")
        if steam_cloud_profile.path.resolve() != request.profile.resolve():
            raise ValueError("The Steam Cloud profile does not match the request")
        if steam_cloud_profile.companion_path is None:
            raise ValueError("The Steam Cloud Documents companion is required")
        if steam_cloud_profile.steam_metadata_path is None:
            raise ValueError("Steam remotecache.vdf is required")
        if request.slots == 1:
            cloud_validation_flag = "--allow-steam-cloud-validation"
        elif request.slots == 2:
            cloud_validation_flag = "--allow-steam-cloud-two-validation"
        elif request.slots == 3:
            cloud_validation_flag = "--allow-steam-cloud-three-validation"
        elif request.slots == 5:
            cloud_validation_flag = "--allow-steam-cloud-five-validation"
        else:
            raise ValueError(
                "Steam Cloud controller arguments support only the 1+1, 2+2, "
                "3+3, and 5+5 validation boundaries"
            )
        arguments.extend(
            [
                cloud_validation_flag,
                "--profile-name",
                steam_cloud_profile.name,
                "--documents-companion",
                str(steam_cloud_profile.companion_path),
                "--steam-metadata",
                str(steam_cloud_profile.steam_metadata_path),
            ]
        )
    return arguments


def controller_command_preview(
    request: FillRequest,
    project_root: Path,
    *,
    steam_cloud_profile: ProfileInfo | None = None,
) -> str:
    return subprocess.list2cmdline(
        controller_arguments(
            request,
            project_root,
            steam_cloud_profile=steam_cloud_profile,
        )
    )


def simulator_arguments(
    request: FillRequest,
    output_dir: Path,
    *,
    countdown: float = 1.0,
    step_delay: float = 0.15,
) -> list[str]:
    arguments = [
        str(python_executable()),
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
