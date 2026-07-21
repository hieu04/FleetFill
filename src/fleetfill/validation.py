"""Evidence checks for the validation-only one-truck/one-driver run."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fleetfill.domain import DRIVER_HIRE_COST_EUR, TRUCK_PRICE_EUR


@dataclass(frozen=True)
class ValidationEvidence:
    passed: bool
    checks: dict[str, bool]
    report_path: Path
    problems: tuple[str, ...]


def verify_batch_run(run_dir: Path, *, expected_count: int) -> ValidationEvidence:
    if not 1 <= expected_count <= 5:
        raise ValueError("Runtime validation count must be between one and five")
    preflight_path = run_dir / "preflight.json"
    batch_path = run_dir / "batch-report.json"
    output_path = run_dir / "validation-report.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    backup_payload = preflight.get("backup", {})
    backup = Path(backup_payload.get("backup", ""))
    backup_autosave = Path(backup_payload.get("autosave", backup / "autosave"))
    company = preflight.get("company", {})
    breakdown = batch.get("transaction_breakdown", {})
    steps = batch.get("steps", [])
    scripts = [step.get("script") for step in steps if step.get("return_code") == 0]
    checks = {
        "phase_is_unified_fill": preflight.get("phase") == "fill" and batch.get("phase") == "fill",
        "requested_slot_count_matches": preflight.get("count") == expected_count,
        "dynamic_garage_required": preflight.get("dynamic_garage") is True,
        "empty_garage_required": preflight.get("require_empty_garage") is True,
        "backup_directory_exists": backup.is_dir(),
        "backup_profile_exists": (backup / "profile.sii").is_file(),
        "backup_autosave_exists": (backup_autosave / "game.sii").is_file(),
        "company_balance_preflight_passed": company.get("money_eur", -1)
        >= expected_count * (TRUCK_PRICE_EUR + DRIVER_HIRE_COST_EUR)
        and company.get("planned_cost_eur")
        == expected_count * (TRUCK_PRICE_EUR + DRIVER_HIRE_COST_EUR),
        "empty_garage_exists_in_backup": bool(company.get("empty_large_garages")),
        "controller_completed": batch.get("status") == "completed" and not batch.get("error"),
        "all_actions_completed": batch.get("requested_transactions")
        == expected_count * 2
        and batch.get("completed_transactions") == expected_count * 2,
        "all_trucks_confirmed": breakdown.get("trucks") == expected_count
        and scripts.count("ets2_ui_confirm_truck_purchase_probe.py")
        == expected_count,
        "all_drivers_confirmed": breakdown.get("drivers") == expected_count
        and scripts.count("ets2_ui_confirm_driver_to_truck_probe.py")
        == expected_count,
        "expected_spend_matches": batch.get("expected_spend_eur")
        == expected_count * (TRUCK_PRICE_EUR + DRIVER_HIRE_COST_EUR),
    }
    problems = tuple(name for name, passed in checks.items() if not passed)
    payload = {
        "passed": not problems,
        "checks": checks,
        "problems": problems,
        "preflight": str(preflight_path.resolve()),
        "batch_report": str(batch_path.resolve()),
        "deep_save_verification": "pending_clean_game_exit",
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return ValidationEvidence(not problems, checks, output_path, problems)


def verify_one_plus_one_run(run_dir: Path) -> ValidationEvidence:
    """Compatibility wrapper for the completed first live validation."""

    return verify_batch_run(run_dir, expected_count=1)
