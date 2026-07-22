"""Guarded batch orchestrator for the proven ETS2 truck and driver probes.

This is the integration prototype, not the final desktop UI.  It never sends
input itself; each action is delegated to a narrowly scoped probe with its own
screen recognition and click guard.  The controller adds state transitions,
checkpoints, resumability, and an aggregate audit report.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from fleetfill.domain import STEAM_CLOUD_PROFILE_STORAGE, ProfileInfo
from fleetfill.profile_safety import (
    ProfileSnapshotError,
    create_steam_cloud_snapshot,
    rehearse_steam_cloud_restore,
)


TRUCK_PRICE_EUR = 248_485
DRIVER_HIRE_COST_EUR = 1_500


class BatchAbort(RuntimeError):
    """A guarded sub-step stopped or returned unverifiable output."""


class BatchCancelled(BatchAbort):
    """The desktop requested a cooperative stop between guarded probes."""


@dataclass(frozen=True)
class GarageState:
    occupied: int
    truck_present: int
    free: int

    def __post_init__(self) -> None:
        values = (self.occupied, self.truck_present, self.free)
        if any(value < 0 for value in values):
            raise ValueError(f"Garage counts cannot be negative: {values}")
        if sum(values) != 5:
            raise ValueError(f"A large ETS2 garage must contain five slots: {values}")

    def buy_truck(self) -> "GarageState":
        if self.free < 1:
            raise ValueError("Cannot buy another truck: the garage has no free slot")
        return GarageState(
            occupied=self.occupied,
            truck_present=self.truck_present + 1,
            free=self.free - 1,
        )

    def hire_driver(self) -> "GarageState":
        if self.truck_present < 1:
            raise ValueError("Cannot pair another driver: no driverless truck remains")
        return GarageState(
            occupied=self.occupied + 1,
            truck_present=self.truck_present - 1,
            free=self.free,
        )


@dataclass
class StepRecord:
    index: int
    label: str
    script: str
    command: list[str]
    return_code: int
    report_prefix: str
    report_path: str | None
    started_at: str
    finished_at: str


class ProbeRunner:
    def __init__(
        self,
        tools_dir: Path,
        run_dir: Path,
        step_delay: float,
        capture_timeout: float,
        cancel_file: Path | None = None,
    ) -> None:
        self.tools_dir = tools_dir
        self.run_dir = run_dir
        self.step_delay = step_delay
        self.capture_timeout = capture_timeout
        self.steps: list[StepRecord] = []
        self.current_state: GarageState | None = None
        self.cancel_file = cancel_file

    def check_cancelled(self) -> None:
        if self.cancel_file is not None and self.cancel_file.exists():
            raise BatchCancelled(
                f"Cancellation requested; stopped before guarded step {len(self.steps) + 1}"
            )

    def run(
        self,
        label: str,
        script: str,
        arguments: Sequence[str],
        report_prefix: str,
        *,
        supports_delay: bool = True,
        supports_capture_timeout: bool = True,
        accepted_return_codes: Sequence[int] = (0,),
    ) -> dict:
        self.check_cancelled()
        index = len(self.steps) + 1
        step_dir = self.run_dir / "steps" / f"{index:03d}-{label}"
        command = [sys.executable, str(self.tools_dir / script), *arguments]
        if supports_delay:
            command.extend(["--delay", str(self.step_delay)])
        if supports_capture_timeout:
            command.extend(["--capture-timeout", str(self.capture_timeout)])
        command.extend(["--output-dir", str(step_dir)])
        print(f"\n[BATCH {index:03d}] {label}", flush=True)
        started = datetime.now().isoformat(timespec="seconds")
        process = subprocess.Popen(
            command,
            cwd=self.tools_dir.parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        report_path: Path | None = None
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip()
            print(f"  {line}", flush=True)
            marker = f"{report_prefix}:"
            if line.startswith(marker):
                report_path = Path(line[len(marker) :].strip()).resolve()
        return_code = process.wait()
        finished = datetime.now().isoformat(timespec="seconds")
        record = StepRecord(
            index=index,
            label=label,
            script=script,
            command=command,
            return_code=return_code,
            report_prefix=report_prefix,
            report_path=str(report_path) if report_path else None,
            started_at=started,
            finished_at=finished,
        )
        self.steps.append(record)
        if return_code not in accepted_return_codes:
            raise BatchAbort(
                f"Step {index} ({label}) stopped with exit code {return_code}"
            )
        if report_path is None or not report_path.is_file():
            raise BatchAbort(f"Step {index} ({label}) produced no readable report")
        return json.loads(report_path.read_text(encoding="utf-8"))


def discover_dynamic_garage(
    runner: ProbeRunner,
    args: argparse.Namespace,
    state: GarageState,
    context: str,
) -> None:
    """Find capacity in the current view, then use one bounded pan if needed."""
    require_empty = bool(getattr(args, "require_empty_garage", False))
    required = str(state.free if require_empty else args.count)
    visible = runner.run(
        f"{context}-find-visible-capacity-garage",
        "ets2_ui_find_capacity_garage_probe.py",
        ["--context", context, "--required", required],
        "FIND_CAPACITY_GARAGE_REPORT",
        accepted_return_codes=(0, 7),
    )
    discovery = visible
    locator_report: Path | None = None
    if not visible.get("found"):
        discovery = runner.run(
            f"{context}-find-capacity-after-pan",
            "ets2_ui_find_after_pan_probe.py",
            ["--context", context, "--required", required],
            "FIND_AFTER_PAN_REPORT",
        )
        locator = discovery.get("locator")
        if not locator or not locator.get("pan_path"):
            raise BatchAbort("Panned garage discovery omitted its replay locator")
        locator_report = runner.run_dir / f"{context}-garage-pan-locator.json"
        locator_report.write_text(json.dumps(discovery, indent=2), encoding="utf-8")

    found = discovery.get("found")
    if not found:
        raise BatchAbort("Bounded garage search returned no qualifying garage")
    counts = found.get("slot_counts")
    if counts != asdict(state):
        raise BatchAbort(
            "Dynamically selected garage did not match the planned initial "
            f"state; expected={asdict(state)}, observed={counts}"
        )
    target = found.get("target_position")
    if not isinstance(target, list) or len(target) != 2:
        raise BatchAbort("Dynamic garage report omitted its marker position")
    args.garage_x, args.garage_y = int(target[0]), int(target[1])
    args.garage_label = "Dynamically selected garage"
    args.garage_locator_report = str(locator_report) if locator_report else None


def reselect_dynamic_garage(
    runner: ProbeRunner,
    args: argparse.Namespace,
    state: GarageState,
    context: str,
    label: str,
) -> None:
    """Reuse either a stable visible coordinate or a verified pan locator."""
    locator_report = getattr(args, "garage_locator_report", None)
    if locator_report:
        runner.run(
            label,
            "ets2_ui_replay_pan_locator_probe.py",
            [
                "--locator-report",
                locator_report,
                "--context",
                context,
                *expected_state_arguments(state),
            ],
            "REPLAY_PAN_LOCATOR_REPORT",
        )
        return
    script = (
        "ets2_ui_reselect_truck_garage_probe.py"
        if context == "truck"
        else "ets2_ui_reselect_hire_garage_probe.py"
    )
    runner.run(
        label,
        script,
        [
            "--target-x",
            str(args.garage_x),
            "--target-y",
            str(args.garage_y),
            *expected_state_arguments(state),
        ],
        "RESELECT_TRUCK_GARAGE_REPORT"
        if context == "truck"
        else "RESELECT_HIRE_GARAGE_REPORT",
    )


def create_preflight_backup(profile: Path, destination: Path) -> dict:
    autosave = profile / "save" / "autosave"
    profile_sii = profile / "profile.sii"
    if not autosave.is_dir() or not profile_sii.is_file():
        raise BatchAbort(f"Disposable profile backup source is incomplete: {profile}")
    backup = destination / "preflight-backup"
    shutil.copytree(autosave, backup / "autosave")
    shutil.copy2(profile_sii, backup / "profile.sii")
    return {
        "profile": str(profile.resolve()),
        "backup": str(backup.resolve()),
        "autosave": str((backup / "autosave").resolve()),
        "autosave_files": sorted(path.name for path in (backup / "autosave").iterdir()),
    }


def is_steam_cloud_profile_path(profile: Path) -> bool:
    """Recognize cloud storage so this local-only controller fails closed."""

    resolved = profile.resolve()
    parent = resolved.parent.name.casefold()
    grandparent = resolved.parent.parent.name.casefold()
    return parent == "steam_profiles" or (
        parent == "profiles" and grandparent == "remote"
    )


def create_steam_cloud_preflight_backup(
    profile: Path,
    profile_name: str,
    documents_companion: Path,
    steam_metadata: Path,
    destination: Path,
) -> dict:
    """Create and rehearse the complete cloud recovery set before UI input."""

    snapshot = destination / "preflight-recovery-snapshot"
    profile_info = ProfileInfo(
        profile_name,
        profile,
        storage=STEAM_CLOUD_PROFILE_STORAGE,
        companion_path=documents_companion,
        steam_metadata_path=steam_metadata,
    )
    snapshot_report = create_steam_cloud_snapshot(profile_info, snapshot)
    rehearsal = destination / "preflight-restore-rehearsal"
    rehearsal_report = rehearse_steam_cloud_restore(snapshot, rehearsal)
    cloud_backup = snapshot / "steam-cloud-profile"
    return {
        "profile": str(profile.resolve()),
        "backup": str(cloud_backup.resolve()),
        "autosave": str((cloud_backup / "save" / "autosave").resolve()),
        "recovery_snapshot": str(snapshot.resolve()),
        "restore_rehearsal": str(rehearsal.resolve()),
        "snapshot_verified": snapshot_report["verified"],
        "restore_rehearsal_verified": rehearsal_report["verified"],
        "autosave_files": sorted(
            path.name for path in (cloud_backup / "save" / "autosave").iterdir()
        ),
    }


def validate_company_preflight(company: dict, count: int) -> dict:
    """Prove the backed-up company can afford and place the requested batch."""

    planned_cost = count * (TRUCK_PRICE_EUR + DRIVER_HIRE_COST_EUR)
    balance = int(company.get("money_eur", -1))
    empty_large_garages = [
        garage["id"]
        for garage in company.get("large_garages", [])
        if garage.get("occupied") == 0
        and garage.get("truck_present") == 0
        and garage.get("free") == 5
        and garage.get("invalid_driver_only") == 0
    ]
    if balance < planned_cost:
        raise BatchAbort(
            f"Insufficient company balance: EUR {balance:,} available, "
            f"EUR {planned_cost:,} required"
        )
    if not empty_large_garages:
        raise BatchAbort("The backed-up save contains no completely empty large garage")
    return {
        "money_eur": balance,
        "planned_cost_eur": planned_cost,
        "remaining_balance_eur": balance - planned_cost,
        "empty_large_garages": empty_large_garages,
    }


def inspect_preflight_company(
    backup: dict, tools_dir: Path, run_dir: Path, count: int
) -> dict:
    """Decode only the backup copy and record a read-only company summary."""

    inspector = tools_dir / "save-inspector"
    autosave = Path(backup.get("autosave", Path(backup["backup"]) / "autosave"))
    source = autosave / "game.sii"
    decoded = run_dir / "preflight-company-game.txt"
    report = run_dir / "preflight-company.json"
    commands = [
        (["node", str(inspector / "decrypt-save.mjs"), str(source), str(decoded)], inspector),
        ([sys.executable, str(tools_dir / "inspect_company_save.py"), str(decoded), "--output", str(report)], tools_dir),
    ]
    for command, cwd in commands:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode:
            detail = completed.stdout.strip().splitlines()[-1:]
            raise BatchAbort(
                "Company preflight inspection failed"
                + (f": {detail[0]}" if detail else "")
            )
    company = json.loads(report.read_text(encoding="utf-8"))
    return validate_company_preflight(company, count)


def initial_state(args: argparse.Namespace) -> GarageState:
    return GarageState(
        occupied=args.occupied,
        truck_present=args.truck_present,
        free=args.free,
    )


def expected_state_arguments(state: GarageState) -> list[str]:
    return [
        "--expected-occupied",
        str(state.occupied),
        "--expected-truck-present",
        str(state.truck_present),
        "--expected-free",
        str(state.free),
    ]


def run_truck_phase(
    runner: ProbeRunner, args: argparse.Namespace, state: GarageState
) -> GarageState:
    runner.current_state = state
    stages = (
        "home",
        "dealer-map",
        "scania-selected",
        "dealer-selected",
        "online-purchase-stock",
        "fleet-configurations",
    )
    start_index = stages.index(args.start_stage)
    dealer_selected_by_fallback = False
    if start_index <= stages.index("home"):
        runner.run(
            "open-truck-dealers-from-home",
            "ets2_ui_open_service_destination_probe.py",
            ["--destination", "truck_dealers"],
            "OPEN_SERVICE_DESTINATION_REPORT",
        )
    if start_index <= stages.index("dealer-map"):
        brand = runner.run(
            "select-scania",
            "ets2_ui_dealer_brand_probe.py",
            [],
            "DEALER_BRAND_PROBE_REPORT",
        )
        if not brand.get("detected_available_dealers"):
            runner.run(
                "find-scania-dealer-after-pan",
                "ets2_ui_dealer_filtered_pan_probe.py",
                ["--brand", "scania"],
                "DEALER_FILTERED_PAN_REPORT",
            )
            dealer_selected_by_fallback = True
    if (
        start_index <= stages.index("scania-selected")
        and not dealer_selected_by_fallback
    ):
        runner.run(
            "select-scania-dealer",
            "ets2_ui_dealer_marker_probe.py",
            [],
            "DEALER_MARKER_PROBE_REPORT",
        )
    if start_index <= stages.index("dealer-selected"):
        runner.run(
            "open-online-purchase",
            "ets2_ui_open_online_purchase_probe.py",
            [],
            "OPEN_ONLINE_PURCHASE_REPORT",
        )
    if start_index <= stages.index("online-purchase-stock"):
        runner.run(
            "open-fleet-configurations",
            "ets2_ui_fleet_config_probe.py",
            [],
            "FLEET_CONFIG_PROBE_REPORT",
        )

    card_selected = args.initial_card_selected
    dynamic_pending = args.dynamic_garage
    for iteration in range(1, args.count + 1):
        print(
            f"\n[TRUCK {iteration}/{args.count}] expected garage state: {state}",
            flush=True,
        )
        if card_selected:
            runner.run(
                f"truck-{iteration}-verify-selected-card",
                "ets2_ui_verify_selected_fleet_truck.py",
                ["--card", str(args.card)],
                "VERIFY_SELECTED_FLEET_TRUCK_REPORT",
            )
        else:
            runner.run(
                f"truck-{iteration}-select-card",
                "ets2_ui_fleet_truck_select_probe.py",
                ["--card", str(args.card)],
                "FLEET_TRUCK_SELECT_REPORT",
            )
        runner.run(
            f"truck-{iteration}-open-garage",
            "ets2_ui_open_truck_garage_probe.py",
            [],
            "OPEN_TRUCK_GARAGE_REPORT",
        )
        if dynamic_pending:
            discover_dynamic_garage(runner, args, state, "truck")
            dynamic_pending = False
            write_checkpoint(runner, "running", "trucks", state, args)
        else:
            reselect_dynamic_garage(
                runner,
                args,
                state,
                "truck",
                f"truck-{iteration}-reselect-garage",
            )
        slot = runner.run(
            f"truck-{iteration}-select-slot",
            "ets2_ui_truck_slot_probe.py",
            [],
            "TRUCK_SLOT_PROBE_REPORT",
        )
        identity_reference = slot.get("after", {}).get("screenshot")
        if not identity_reference:
            raise BatchAbort("Truck slot report omitted the confirmation identity image")
        runner.run(
            f"truck-{iteration}-confirm",
            "ets2_ui_confirm_truck_purchase_probe.py",
            ["--identity-reference", str(identity_reference)],
            "CONFIRM_TRUCK_PURCHASE_REPORT",
        )
        # The gameplay transaction is complete once the success prompt is
        # recognized.  Persist the new garage state before acknowledging that
        # prompt so a later acknowledgement failure cannot undercount a truck.
        state = state.buy_truck()
        runner.current_state = state
        write_checkpoint(runner, "running", "trucks", state, args)
        runner.run(
            f"truck-{iteration}-ack-success",
            "ets2_ui_ack_purchase_prompt_probe.py",
            [],
            "ACK_PURCHASE_PROMPT_REPORT",
        )
        # ETS2 1.60 returns to the fleet list with the purchased card still
        # selected.  Subsequent iterations verify that state without clicking.
        card_selected = True
        write_checkpoint(runner, "running", "trucks", state, args)
    return state


def run_driver_phase(
    runner: ProbeRunner, args: argparse.Namespace, state: GarageState
) -> GarageState:
    runner.current_state = state
    stages = ("home", "recruitment-map", "driver-list")
    start_index = stages.index(args.start_stage)
    if start_index <= stages.index("home"):
        runner.run(
            "open-recruitment-from-home",
            "ets2_ui_open_service_destination_probe.py",
            ["--destination", "recruitment_agency"],
            "OPEN_SERVICE_DESTINATION_REPORT",
        )
    if start_index <= stages.index("recruitment-map"):
        runner.run(
            "open-driver-list",
            "ets2_ui_open_hire_driver_probe.py",
            [],
            "OPEN_HIRE_DRIVER_REPORT",
        )
    dynamic_pending = args.dynamic_garage
    for iteration in range(1, args.count + 1):
        print(
            f"\n[DRIVER {iteration}/{args.count}] expected garage state: {state}",
            flush=True,
        )
        runner.run(
            f"driver-{iteration}-select-card",
            "ets2_ui_select_probe.py",
            ["--focus-settle", "0.2"],
            "SELECT_PROBE_REPORT",
        )
        runner.run(
            f"driver-{iteration}-open-garage",
            "ets2_ui_open_garage_probe.py",
            ["--focus-settle", "0.2"],
            "OPEN_GARAGE_PROBE_REPORT",
        )
        if dynamic_pending:
            discover_dynamic_garage(runner, args, state, "hire")
            dynamic_pending = False
            write_checkpoint(runner, "running", "drivers", state, args)
        else:
            reselect_dynamic_garage(
                runner,
                args,
                state,
                "hire",
                f"driver-{iteration}-reselect-garage",
            )
        slot = runner.run(
            f"driver-{iteration}-select-waiting-truck",
            "ets2_ui_driver_to_truck_slot_probe.py",
            [],
            "DRIVER_TO_TRUCK_SLOT_REPORT",
        )
        identity_reference = slot.get("after", {}).get("screenshot")
        if not identity_reference:
            raise BatchAbort("Driver slot report omitted the confirmation identity image")
        runner.run(
            f"driver-{iteration}-confirm",
            "ets2_ui_confirm_driver_to_truck_probe.py",
            [
                "--identity-reference",
                str(identity_reference),
                "--expected-driver",
                f"selected card 1, iteration {iteration}",
                "--expected-garage",
                args.garage_label,
            ],
            "CONFIRM_DRIVER_TO_TRUCK_REPORT",
        )
        state = state.hire_driver()
        runner.current_state = state
        write_checkpoint(runner, "running", "drivers", state, args)
    return state


def run_fill_phase(
    runner: ProbeRunner, args: argparse.Namespace, state: GarageState
) -> GarageState:
    """Buy trucks and hire the same number of drivers into the same garage."""
    original_dynamic = args.dynamic_garage
    args.start_stage = "home"
    state = run_truck_phase(runner, args, state)
    runner.run(
        "return-home-after-trucks",
        "ets2_ui_return_home_probe.py",
        [],
        "RETURN_HOME_REPORT",
    )
    # Truck discovery has now persisted either a fixed coordinate or a pan
    # locator. The driver phase must reuse it instead of finding another garage.
    args.dynamic_garage = False
    args.start_stage = "home"
    try:
        state = run_driver_phase(runner, args, state)
    finally:
        args.dynamic_garage = original_dynamic
    return state


def summary_payload(
    runner: ProbeRunner,
    status: str,
    phase: str,
    state: GarageState,
    args: argparse.Namespace,
    *,
    error: str | None = None,
) -> dict:
    completed_trucks = sum(
        1
        for step in runner.steps
        if step.return_code == 0
        and step.script == "ets2_ui_confirm_truck_purchase_probe.py"
    )
    completed_drivers = sum(
        1
        for step in runner.steps
        if step.return_code == 0
        and step.script == "ets2_ui_confirm_driver_to_truck_probe.py"
    )
    if phase == "trucks":
        requested_transactions = args.count
        transactions = completed_trucks
    elif phase == "drivers":
        requested_transactions = args.count
        transactions = completed_drivers
    else:
        requested_transactions = args.count * 2
        transactions = completed_trucks + completed_drivers
    return {
        "status": status,
        "phase": phase,
        "error": error,
        "garage": {
            "label": args.garage_label,
            "marker": [args.garage_x, args.garage_y]
            if args.garage_x is not None and args.garage_y is not None
            else None,
            "state": asdict(state),
            "pan_locator_report": getattr(args, "garage_locator_report", None),
        },
        "requested_transactions": requested_transactions,
        "completed_transactions": transactions,
        "transaction_breakdown": {
            "trucks": completed_trucks,
            "drivers": completed_drivers,
        },
        "expected_spend_eur": completed_trucks * TRUCK_PRICE_EUR
        + completed_drivers * DRIVER_HIRE_COST_EUR,
        "fleet_card": getattr(args, "card", None),
        "steps": [asdict(step) for step in runner.steps],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def write_checkpoint(
    runner: ProbeRunner,
    status: str,
    phase: str,
    state: GarageState,
    args: argparse.Namespace,
    *,
    error: str | None = None,
) -> Path:
    path = runner.run_dir / "batch-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            summary_payload(runner, status, phase, state, args, error=error),
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def add_common_live_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Complete recovery and company checks, then exit before countdown or input",
    )
    parser.add_argument("--garage-label", default="Reims")
    parser.add_argument("--garage-x", type=int)
    parser.add_argument("--garage-y", type=int)
    parser.add_argument("--occupied", type=int, required=True)
    parser.add_argument("--truck-present", type=int, required=True)
    parser.add_argument("--free", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--start-delay", type=float, default=10.0)
    parser.add_argument("--step-delay", type=float, default=0.4)
    parser.add_argument("--capture-timeout", type=float, default=20.0)
    parser.add_argument(
        "--require-empty-garage",
        action="store_true",
        help="Only discover a garage whose free-slot count matches the planned state",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        help="Path to the disposable local ETS2 profile used for the safety backup",
    )
    cloud_validation = parser.add_mutually_exclusive_group()
    cloud_validation.add_argument("--allow-steam-cloud-validation", action="store_true")
    cloud_validation.add_argument(
        "--allow-steam-cloud-two-validation",
        action="store_true",
    )
    parser.add_argument("--profile-name")
    parser.add_argument("--documents-companion", type=Path)
    parser.add_argument("--steam-metadata", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--cancel-file",
        type=Path,
        help="Cooperative cancellation marker checked before each guarded probe",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="phase", required=True)
    plan = subparsers.add_parser("plan", help="Validate transitions without UI input")
    plan.add_argument("--occupied", type=int, required=True)
    plan.add_argument("--truck-present", type=int, required=True)
    plan.add_argument("--free", type=int, required=True)
    plan.add_argument("--trucks", type=int, default=0)
    plan.add_argument("--drivers", type=int, default=0)
    trucks = subparsers.add_parser("trucks", help="Run the guarded truck phase")
    add_common_live_arguments(trucks)
    # Price and identity evidence are currently calibrated for the first saved
    # Scania Streamline Topline configuration only.
    trucks.add_argument("--card", type=int, default=1, choices=[1])
    trucks.add_argument(
        "--start-stage",
        choices=[
            "home",
            "dealer-map",
            "scania-selected",
            "dealer-selected",
            "online-purchase-stock",
            "fleet-configurations",
        ],
        default="dealer-map",
        help="Resume only from a manually/previously verified truck-workflow stage",
    )
    trucks.add_argument(
        "--initial-card-selected",
        action="store_true",
        help="Verify an already-selected fleet card instead of clicking it first",
    )
    trucks.add_argument(
        "--dynamic-garage",
        action="store_true",
        help="Discover the first visible garage with capacity on iteration one",
    )
    drivers = subparsers.add_parser("drivers", help="Run the guarded driver phase")
    add_common_live_arguments(drivers)
    drivers.add_argument(
        "--start-stage",
        choices=["home", "recruitment-map", "driver-list"],
        default="driver-list",
        help="Start from home or resume from a verified recruitment workflow stage",
    )
    drivers.add_argument(
        "--dynamic-garage",
        action="store_true",
        help="Discover the first visible garage with enough driverless trucks",
    )
    fill = subparsers.add_parser(
        "fill", help="Buy trucks and hire drivers into one dynamically chosen garage"
    )
    add_common_live_arguments(fill)
    fill.add_argument("--card", type=int, default=1, choices=[1])
    fill.add_argument(
        "--start-stage",
        choices=["home"],
        default="home",
        help="The unified workflow starts from the normal ETS2 home screen",
    )
    fill.add_argument(
        "--initial-card-selected",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    fill.add_argument(
        "--dynamic-garage",
        action="store_true",
        help="Discover a garage with enough free slots, then reuse it for hiring",
    )
    return parser


def run_plan(args: argparse.Namespace) -> int:
    initial = initial_state(args)
    state = initial
    transitions = [{"action": "start", "state": asdict(state)}]
    for index in range(1, args.trucks + 1):
        state = state.buy_truck()
        transitions.append({"action": f"buy_truck_{index}", "state": asdict(state)})
    for index in range(1, args.drivers + 1):
        state = state.hire_driver()
        transitions.append({"action": f"hire_driver_{index}", "state": asdict(state)})
    payload = {
        "valid": True,
        "initial": asdict(initial),
        "trucks": args.trucks,
        "drivers": args.drivers,
        "expected_spend_eur": args.trucks * TRUCK_PRICE_EUR
        + args.drivers * DRIVER_HIRE_COST_EUR,
        "transitions": transitions,
        "final": asdict(state),
    }
    print(json.dumps(payload, indent=2))
    return 0


def run_live(args: argparse.Namespace) -> int:
    if not args.execute:
        print("BATCH_REFUSED: live phases require the explicit --execute flag")
        return 2
    if args.profile is None:
        print("BATCH_REFUSED: live phases require an explicit --profile path")
        return 2
    cloud_profile = is_steam_cloud_profile_path(args.profile)
    cloud_one_allowed = bool(getattr(args, "allow_steam_cloud_validation", False))
    cloud_two_allowed = bool(
        getattr(args, "allow_steam_cloud_two_validation", False)
    )
    cloud_expected_count = 1 if cloud_one_allowed else 2 if cloud_two_allowed else None
    cloud_allowed = cloud_expected_count is not None
    if cloud_profile and not cloud_allowed:
        print(
            "BATCH_REFUSED: Steam Cloud profiles require the separate "
            "main-profile safety boundary"
        )
        return 2
    if cloud_allowed and not cloud_profile:
        print("BATCH_REFUSED: the Steam Cloud validation flag requires a cloud profile")
        return 2
    if cloud_profile:
        if args.phase != "fill" or args.count != cloud_expected_count:
            print(
                "BATCH_REFUSED: Steam Cloud validation is limited to one "
                f"{cloud_expected_count}+{cloud_expected_count} fill"
            )
            return 2
        missing_cloud_args = [
            name
            for name in ("profile_name", "documents_companion", "steam_metadata")
            if getattr(args, name, None) in (None, "")
        ]
        if missing_cloud_args:
            print(
                "BATCH_REFUSED: Steam Cloud validation is missing "
                + ", ".join(missing_cloud_args)
            )
            return 2
    if args.count < 1:
        print("BATCH_REFUSED: --count must be at least one")
        return 2
    dynamic = bool(getattr(args, "dynamic_garage", False))
    if not dynamic and (args.garage_x is None or args.garage_y is None):
        print(
            "BATCH_REFUSED: fixed-garage runs require --garage-x and --garage-y"
        )
        return 2
    state = initial_state(args)
    # Validate the entire requested transition sequence before any UI action.
    preview = state
    if args.phase == "fill":
        for _ in range(args.count):
            preview = preview.buy_truck()
        for _ in range(args.count):
            preview = preview.hire_driver()
    else:
        for _ in range(args.count):
            preview = (
                preview.buy_truck()
                if args.phase == "trucks"
                else preview.hire_driver()
            )
    tools_dir = Path(__file__).resolve().parent
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else tools_dir.parents[0] / "output" / "batch-controller" / f"{stamp}-{args.phase}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    allowed_existing = {"cancel.requested"}
    unexpected = [path for path in run_dir.iterdir() if path.name not in allowed_existing]
    if unexpected:
        print(f"BATCH_REFUSED: output directory is not empty: {run_dir}")
        return 2
    cancel_file = (
        args.cancel_file.resolve()
        if args.cancel_file is not None
        else run_dir / "cancel.requested"
    )
    runner = ProbeRunner(
        tools_dir=tools_dir,
        run_dir=run_dir,
        step_delay=args.step_delay,
        capture_timeout=args.capture_timeout,
        cancel_file=cancel_file,
    )
    runner.current_state = state
    try:
        runner.check_cancelled()
    except BatchCancelled as error:
        print(f"BATCH_CANCELLED: {error}")
        return 2
    try:
        if cloud_profile:
            backup = create_steam_cloud_preflight_backup(
                args.profile.resolve(),
                args.profile_name,
                args.documents_companion.resolve(),
                args.steam_metadata.resolve(),
                run_dir,
            )
        else:
            backup = create_preflight_backup(args.profile.resolve(), run_dir)
    except (BatchAbort, ProfileSnapshotError, OSError) as error:
        print(f"BATCH_ABORTED: recovery backup failed before input: {error}")
        return 1
    preflight_payload = {
        "phase": args.phase,
        "initial_state": asdict(state),
        "planned_final_state": asdict(preview),
        "count": args.count,
        "garage_marker": [args.garage_x, args.garage_y]
        if args.garage_x is not None and args.garage_y is not None
        else None,
        "dynamic_garage": dynamic,
        "require_empty_garage": args.require_empty_garage,
        "start_stage": getattr(args, "start_stage", None),
        "backup": backup,
    }
    if args.phase == "fill":
        try:
            preflight_payload["company"] = inspect_preflight_company(
                backup, tools_dir, run_dir, args.count
            )
        except (BatchAbort, OSError, ValueError, json.JSONDecodeError) as error:
            preflight_payload["company_preflight_error"] = str(error)
            (run_dir / "preflight.json").write_text(
                json.dumps(preflight_payload, indent=2), encoding="utf-8"
            )
            report = write_checkpoint(
                runner, "aborted", args.phase, state, args, error=str(error)
            )
            print(f"BATCH_ABORTED: {error}")
            print(f"BATCH_REPORT: {report.resolve()}")
            return 1
    (run_dir / "preflight.json").write_text(
        json.dumps(preflight_payload, indent=2), encoding="utf-8"
    )
    if args.preflight_only:
        report = write_checkpoint(runner, "preflight_completed", args.phase, state, args)
        print("BATCH_PREFLIGHT_SUCCEEDED: recovery and company checks passed; no input sent")
        print(f"BATCH_REPORT: {report.resolve()}")
        return 0
    write_checkpoint(runner, "ready", args.phase, state, args)
    print(
        f"BATCH_READY: {args.phase} phase begins in {args.start_delay:.1f}s; "
        f"planned state {state} -> {preview}. Return to ETS2.",
        flush=True,
    )
    deadline = time.monotonic() + args.start_delay
    try:
        while time.monotonic() < deadline:
            runner.check_cancelled()
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
        if args.phase == "trucks":
            state = run_truck_phase(runner, args, state)
        elif args.phase == "drivers":
            state = run_driver_phase(runner, args, state)
        else:
            state = run_fill_phase(runner, args, state)
        runner.check_cancelled()
    except BatchCancelled as error:
        state = runner.current_state or state
        report = write_checkpoint(
            runner, "cancelled", args.phase, state, args, error=str(error)
        )
        print(f"BATCH_CANCELLED: {error}")
        print(f"BATCH_REPORT: {report.resolve()}")
        return 2
    except (BatchAbort, ValueError) as error:
        state = runner.current_state or state
        report = write_checkpoint(
            runner, "aborted", args.phase, state, args, error=str(error)
        )
        print(f"BATCH_ABORTED: {error}")
        print(f"BATCH_REPORT: {report.resolve()}")
        return 1
    report = write_checkpoint(runner, "completed", args.phase, state, args)
    print(f"BATCH_SUCCEEDED: {args.phase} phase completed; state={state}")
    print(f"BATCH_REPORT: {report.resolve()}")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.phase == "plan":
        return run_plan(args)
    return run_live(args)


if __name__ == "__main__":
    raise SystemExit(main())
