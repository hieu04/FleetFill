from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fleetfill.validation import verify_one_plus_one_run


class OnePlusOneValidationTests(unittest.TestCase):
    def make_run(self, root: Path, *, drivers: int = 1) -> Path:
        run_dir = root / "run"
        backup = run_dir / "preflight-backup"
        (backup / "autosave").mkdir(parents=True)
        (backup / "profile.sii").write_text("profile", encoding="utf-8")
        (backup / "autosave" / "game.sii").write_text("save", encoding="utf-8")
        (run_dir / "preflight.json").write_text(
            json.dumps(
                {
                    "phase": "fill",
                    "count": 1,
                    "dynamic_garage": True,
                    "require_empty_garage": True,
                    "backup": {"backup": str(backup)},
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
                    "requested_transactions": 2,
                    "completed_transactions": 2,
                    "transaction_breakdown": {"trucks": 1, "drivers": drivers},
                    "expected_spend_eur": 249985,
                    "steps": [
                        {"return_code": 0, "script": "ets2_ui_confirm_truck_purchase_probe.py"},
                        {"return_code": 0, "script": "ets2_ui_confirm_driver_to_truck_probe.py"},
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
            self.assertIn("one_driver_confirmed", evidence.problems)


if __name__ == "__main__":
    unittest.main()
