from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fleetfill.validation import verify_batch_run, verify_one_plus_one_run


class BatchValidationTests(unittest.TestCase):
    def make_run(self, root: Path, *, drivers: int | None = None, count: int = 1) -> Path:
        if drivers is None:
            drivers = count
        run_dir = root / "run"
        backup = run_dir / "preflight-backup"
        (backup / "autosave").mkdir(parents=True)
        (backup / "profile.sii").write_text("profile", encoding="utf-8")
        (backup / "autosave" / "game.sii").write_text("save", encoding="utf-8")
        (run_dir / "preflight.json").write_text(
            json.dumps(
                {
                    "phase": "fill",
                    "count": count,
                    "dynamic_garage": True,
                    "require_empty_garage": True,
                    "backup": {"backup": str(backup)},
                    "company": {
                        "money_eur": 10_000_000,
                        "planned_cost_eur": count * 249_985,
                        "empty_large_garages": ["garage.test"],
                    },
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "batch-report.json").write_text(
            json.dumps(
                {
                    "status": "completed",
                    "phase": "fill",
                    "error": None,
                    "requested_transactions": count * 2,
                    "completed_transactions": count + drivers,
                    "transaction_breakdown": {"trucks": count, "drivers": drivers},
                    "expected_spend_eur": count * 249985,
                    "steps": [
                        *[
                            {"return_code": 0, "script": "ets2_ui_confirm_truck_purchase_probe.py"}
                            for _ in range(count)
                        ],
                        *[
                            {"return_code": 0, "script": "ets2_ui_confirm_driver_to_truck_probe.py"}
                            for _ in range(drivers)
                        ],
                    ],
                }
            ),
            encoding="utf-8",
        )
        return run_dir

    def test_accepts_exact_one_plus_one_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence = verify_one_plus_one_run(self.make_run(Path(temp)))
            self.assertTrue(evidence.passed)
            self.assertTrue(evidence.report_path.is_file())

    def test_rejects_incomplete_driver_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence = verify_one_plus_one_run(self.make_run(Path(temp), drivers=0))
            self.assertFalse(evidence.passed)
            self.assertIn("all_drivers_confirmed", evidence.problems)

    def test_accepts_complete_five_plus_five_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence = verify_batch_run(
                self.make_run(Path(temp), count=5), expected_count=5
            )
            self.assertTrue(evidence.passed)


if __name__ == "__main__":
    unittest.main()
