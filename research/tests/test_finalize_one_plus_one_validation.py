from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from finalize_one_plus_one_validation import load_run_paths, record_save_audit


class FinalizeValidationTests(unittest.TestCase):
    def test_resolves_profile_and_before_copy_from_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "run"
            profile = root / "profile"
            before = run_dir / "preflight-backup" / "autosave" / "game.sii"
            profile.mkdir()
            before.parent.mkdir(parents=True)
            before.write_text("save", encoding="utf-8")
            (run_dir / "preflight.json").write_text(
                json.dumps(
                    {
                        "phase": "fill",
                        "count": 1,
                        "backup": {
                            "profile": str(profile),
                            "backup": str(run_dir / "preflight-backup"),
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_run_paths(run_dir), (profile, before))

    def test_rejects_non_validation_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            (run_dir / "preflight.json").write_text(
                json.dumps({"phase": "fill", "count": 5}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "one-plus-one"):
                load_run_paths(run_dir)

    def test_records_passed_audit_in_runtime_and_history_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            report = run_dir / "save-audit.json"
            report.write_text("{}", encoding="utf-8")
            (run_dir / "validation-report.json").write_text(
                json.dumps({"deep_save_verification": "pending_clean_game_exit"}),
                encoding="utf-8",
            )
            (run_dir / "desktop-run.json").write_text(
                json.dumps({"save_audit_passed": None}), encoding="utf-8"
            )
            record_save_audit(run_dir, passed=True, report=report)
            runtime = json.loads(
                (run_dir / "validation-report.json").read_text(encoding="utf-8")
            )
            history = json.loads(
                (run_dir / "desktop-run.json").read_text(encoding="utf-8")
            )
            self.assertEqual(runtime["deep_save_verification"], "passed")
            self.assertTrue(history["save_audit_passed"])
            self.assertEqual(history["save_audit_report"], str(report.resolve()))


if __name__ == "__main__":
    unittest.main()
