from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fleetfill.domain import STEAM_CLOUD_PROFILE_STORAGE, ProfileInfo
from fleetfill.profile_safety import ProfileSnapshotError, create_steam_cloud_snapshot


class SteamCloudSnapshotTests(unittest.TestCase):
    def make_profile(self, root: Path) -> ProfileInfo:
        profile = root / "userdata" / "123" / "227300" / "remote" / "profiles" / "4D61696E"
        autosave = profile / "save" / "autosave"
        autosave.mkdir(parents=True)
        (profile / "profile.sii").write_text("profile", encoding="utf-8")
        (autosave / "game.sii").write_text("game", encoding="utf-8")
        (autosave / "info.sii").write_text("info", encoding="utf-8")
        (profile / "save" / "manual").mkdir()
        (profile / "save" / "manual" / "game.sii").write_text("manual", encoding="utf-8")
        companion = root / "documents" / "steam_profiles" / "4D61696E"
        companion.mkdir(parents=True)
        (companion / "controls.sii").write_text("controls", encoding="utf-8")
        metadata = root / "userdata" / "123" / "227300" / "remotecache.vdf"
        metadata.write_text("metadata", encoding="utf-8")
        return ProfileInfo(
            "Main",
            profile,
            storage=STEAM_CLOUD_PROFILE_STORAGE,
            companion_path=companion,
            steam_metadata_path=metadata,
        )

    def test_copies_and_hash_verifies_every_recovery_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = self.make_profile(root)
            destination = root / "snapshot"

            report = create_steam_cloud_snapshot(profile, destination)

            self.assertTrue(report["verified"])
            self.assertEqual(report["cloud_files"], 4)
            self.assertEqual(report["companion_files"], 1)
            self.assertEqual(
                (destination / "steam-cloud-profile" / "save" / "autosave" / "game.sii").read_text(),
                "game",
            )
            self.assertEqual(
                (destination / "documents-companion" / "controls.sii").read_text(),
                "controls",
            )
            self.assertEqual(
                (destination / "steam-metadata" / "remotecache.vdf").read_text(),
                "metadata",
            )
            self.assertTrue((destination / "snapshot-report.json").is_file())

    def test_refuses_local_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ProfileSnapshotError, "requires a cloud profile"):
                create_steam_cloud_snapshot(ProfileInfo("Local", root), root / "snapshot")

    def test_refuses_incomplete_cloud_recovery_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = self.make_profile(root)
            assert profile.steam_metadata_path is not None
            profile.steam_metadata_path.unlink()

            with self.assertRaisesRegex(ProfileSnapshotError, "remotecache"):
                create_steam_cloud_snapshot(profile, root / "snapshot")

    def test_refuses_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = self.make_profile(root)
            destination = root / "snapshot"
            destination.mkdir()

            with self.assertRaisesRegex(ProfileSnapshotError, "already exists"):
                create_steam_cloud_snapshot(profile, destination)


if __name__ == "__main__":
    unittest.main()
