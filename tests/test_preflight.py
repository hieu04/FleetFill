from __future__ import annotations

import tempfile
import os
import unittest
from pathlib import Path

from fleetfill.domain import STEAM_CLOUD_PROFILE_STORAGE, ProfileInfo
from fleetfill.preflight import (
    assess_active_profile,
    newest_session_save,
    parse_latest_profile_evidence,
)


TEST_ID = "45545332204175746F6D6174696F6E2054657374"
MAIN_ID = "5072696D61727920436172656572"


def selection(name: str, profile_type: str, storage: str, folder_id: str) -> str:
    return f"""
00:01:00.000 : Set profile finished: '{name}'
00:01:00.010 : Profile type: {profile_type}
00:01:00.020 : New profile selected: '{name}'
00:01:10.000 : Loading save. Type: 0, slot: 0, path:
<MEMFILE><UFS>/{storage}/profiles/{folder_id}/save/autosave/game.sii
"""


class ActiveProfileParserTests(unittest.TestCase):
    def test_uses_latest_selection_in_mixed_profile_log(self) -> None:
        text = selection("Primary Career", "PC_steam_cloud", "steam", MAIN_ID)
        text += selection("ETS2 Automation Test", "PC_local", "home", TEST_ID)

        evidence = parse_latest_profile_evidence(text)

        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual(evidence.profile_name, "ETS2 Automation Test")
        self.assertEqual(evidence.profile_folder_id, TEST_ID)
        self.assertEqual(evidence.save_slot, "autosave")

    def test_latest_unloaded_selection_does_not_reuse_an_older_save(self) -> None:
        text = selection("ETS2 Automation Test", "PC_local", "home", TEST_ID)
        text += """
00:02:00.000 : Set profile finished: 'Primary Career'
00:02:00.010 : Profile type: PC_steam_cloud
00:02:00.020 : New profile selected: 'Primary Career'
"""

        evidence = parse_latest_profile_evidence(text)

        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual(evidence.profile_name, "Primary Career")
        self.assertIsNone(evidence.load_line)


class ActiveProfilePreflightTests(unittest.TestCase):
    def run_check(self, text: str, *, running: bool = True, folder_id: str = TEST_ID):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile_path = root / "profiles" / folder_id
            profile_path.mkdir(parents=True)
            log_path = root / "game.log.txt"
            log_path.write_text(text, encoding="utf-8")
            return assess_active_profile(
                ProfileInfo("ETS2 Automation Test", profile_path),
                log_path=log_path,
                game_running=running,
            )

    def test_exact_latest_local_profile_passes(self) -> None:
        text = selection("Primary Career", "PC_steam_cloud", "steam", MAIN_ID)
        text += selection("ETS2 Automation Test", "PC_local", "home", TEST_ID)
        result = self.run_check(text)
        self.assertTrue(result.passed)
        self.assertEqual(result.summary, "Active: ETS2 Automation Test (local autosave loaded)")

    def test_test_then_main_fails(self) -> None:
        text = selection("ETS2 Automation Test", "PC_local", "home", TEST_ID)
        text += selection("Primary Career", "PC_steam_cloud", "steam", MAIN_ID)
        result = self.run_check(text)
        self.assertFalse(result.passed)
        self.assertTrue(any("most recently selected" in item for item in result.problems))

    def test_highlighted_profile_without_loaded_save_fails(self) -> None:
        result = self.run_check("""
00:01:00.000 : Set profile finished: 'ETS2 Automation Test'
00:01:00.010 : Profile type: PC_local
00:01:00.020 : New profile selected: 'ETS2 Automation Test'
""")
        self.assertFalse(result.passed)
        self.assertIn("That career's save has not been loaded yet.", result.problems)

    def test_cloud_profile_fails(self) -> None:
        result = self.run_check(
            selection("ETS2 Automation Test", "PC_steam_cloud", "steam", TEST_ID)
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("PC_steam_cloud" in item for item in result.problems))

    def test_exact_latest_cloud_profile_passes_for_cloud_profile_info(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            documents = root / "Euro Truck Simulator 2"
            documents.mkdir()
            log_path = documents / "game.log.txt"
            log_path.write_text(
                selection("Primary Career", "PC_steam_cloud", "steam", MAIN_ID),
                encoding="utf-8",
            )
            profile_path = root / "userdata" / "123" / "227300" / "remote" / "profiles" / MAIN_ID
            profile_path.mkdir(parents=True)

            result = assess_active_profile(
                ProfileInfo(
                    "Primary Career",
                    profile_path,
                    storage=STEAM_CLOUD_PROFILE_STORAGE,
                    documents_root=documents,
                ),
                game_running=True,
            )

        self.assertTrue(result.passed)
        self.assertEqual(
            result.summary,
            "Active: Primary Career (Steam Cloud autosave loaded)",
        )

    def test_cloud_profile_requires_exact_steam_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            documents = root / "Euro Truck Simulator 2"
            documents.mkdir()
            (documents / "game.log.txt").write_text(
                selection("Primary Career", "PC_steam_cloud", "steam", "WRONG"),
                encoding="utf-8",
            )
            profile_path = root / "remote" / "profiles" / MAIN_ID
            profile_path.mkdir(parents=True)

            result = assess_active_profile(
                ProfileInfo(
                    "Primary Career",
                    profile_path,
                    storage=STEAM_CLOUD_PROFILE_STORAGE,
                    documents_root=documents,
                ),
                game_running=True,
            )

        self.assertFalse(result.passed)
        self.assertTrue(any("folder does not match" in item for item in result.problems))

    def test_wrong_folder_fails(self) -> None:
        result = self.run_check(
            selection("ETS2 Automation Test", "PC_local", "home", "WRONG")
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("folder does not match" in item for item in result.problems))

    def test_stale_log_with_no_running_game_fails(self) -> None:
        result = self.run_check(
            selection("ETS2 Automation Test", "PC_local", "home", TEST_ID),
            running=False,
        )
        self.assertFalse(result.passed)
        self.assertIn("ETS2 is not running.", result.problems)

    def test_log_that_predates_current_process_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile_path = root / "profiles" / TEST_ID
            profile_path.mkdir(parents=True)
            log_path = root / "game.log.txt"
            log_path.write_text(
                selection("ETS2 Automation Test", "PC_local", "home", TEST_ID),
                encoding="utf-8",
            )
            os.utime(log_path, (100, 100))

            result = assess_active_profile(
                ProfileInfo("ETS2 Automation Test", profile_path),
                log_path=log_path,
                game_running=True,
                process_started_at=200,
            )

        self.assertFalse(result.passed)
        self.assertTrue(any("predates" in item for item in result.problems))

    def test_cloud_profile_requires_a_save_from_the_current_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            documents = root / "Euro Truck Simulator 2"
            documents.mkdir()
            log_path = documents / "game.log.txt"
            log_path.write_text(
                selection("Primary Career", "PC_steam_cloud", "steam", MAIN_ID),
                encoding="utf-8",
            )
            profile_path = root / "remote" / "profiles" / MAIN_ID
            autosave = profile_path / "save" / "autosave"
            autosave.mkdir(parents=True)
            game = autosave / "game.sii"
            game.write_text("stale", encoding="utf-8")
            os.utime(game, (100, 100))

            result = assess_active_profile(
                ProfileInfo(
                    "Primary Career",
                    profile_path,
                    storage=STEAM_CLOUD_PROFILE_STORAGE,
                    documents_root=documents,
                ),
                log_path=log_path,
                game_running=True,
                process_started_at=200,
            )

        self.assertFalse(result.passed)
        self.assertTrue(any("has not been saved" in item for item in result.problems))

    def test_newest_session_save_selects_a_fresh_manual_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile_path = Path(temp) / "profiles" / MAIN_ID
            autosave = profile_path / "save" / "autosave" / "game.sii"
            manual = profile_path / "save" / "manual" / "game.sii"
            autosave.parent.mkdir(parents=True)
            manual.parent.mkdir(parents=True)
            autosave.write_text("old", encoding="utf-8")
            manual.write_text("fresh", encoding="utf-8")
            os.utime(autosave, (100, 100))
            os.utime(manual, (220, 220))

            evidence = newest_session_save(
                ProfileInfo("Primary Career", profile_path), 200
            )

        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual(evidence.slot, "manual")


if __name__ == "__main__":
    unittest.main()
