from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fleetfill.domain import (
    FillRequest,
    ProfileInfo,
    STEAM_CLOUD_PROFILE_STORAGE,
    controller_arguments,
    decode_profile_folder_name,
    discover_local_profiles,
    discover_steam_cloud_profiles,
    validate_request,
    validate_graduated_live_request,
    validate_live_validation_request,
    validate_main_profile_validation_request,
)


class ProfileDiscoveryTests(unittest.TestCase):
    def test_decodes_ets2_profile_folder_name(self) -> None:
        self.assertEqual(
            decode_profile_folder_name("45545332204175746F6D6174696F6E2054657374"),
            "ETS2 Automation Test",
        )

    def test_discovers_valid_local_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            profile = (
                home
                / "Documents"
                / "Euro Truck Simulator 2"
                / "profiles"
                / "54657374"
            )
            profile.mkdir(parents=True)
            (profile / "profile.sii").write_text("profile", encoding="utf-8")

            found = discover_local_profiles(home=home, environ={})

            self.assertEqual(
                [(item.name, item.path) for item in found],
                [("Test", profile.resolve())],
            )

    def test_discovers_authoritative_steam_cloud_profile_and_companion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            documents = home / "OneDrive" / "Documents" / "Euro Truck Simulator 2"
            profile_id = "5072696D61727920436172656572"
            companion = documents / "steam_profiles" / profile_id
            companion.mkdir(parents=True)
            (companion / "controls.sii").write_text("controls", encoding="utf-8")
            userdata = root / "Steam" / "userdata"
            app = userdata / "123" / "227300"
            profile = app / "remote" / "profiles" / profile_id
            (profile / "save" / "autosave").mkdir(parents=True)
            (profile / "profile.sii").write_text("profile", encoding="utf-8")
            (app / "remotecache.vdf").write_text("metadata", encoding="utf-8")

            found = discover_steam_cloud_profiles(
                home=home,
                environ={},
                userdata_roots=[userdata],
            )

            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].name, "Primary Career")
            self.assertEqual(found[0].path, profile)
            self.assertEqual(found[0].storage, STEAM_CLOUD_PROFILE_STORAGE)
            self.assertEqual(found[0].documents_root, documents.resolve())
            self.assertEqual(found[0].companion_path, companion.resolve())
            self.assertEqual(found[0].steam_metadata_path, app / "remotecache.vdf")


class FillRequestTests(unittest.TestCase):
    def make_profile(self, root: Path) -> Path:
        profile = root / "profile"
        (profile / "save" / "autosave").mkdir(parents=True)
        (profile / "profile.sii").write_text("profile", encoding="utf-8")
        return profile

    def make_cloud_profile(self, root: Path) -> ProfileInfo:
        profile = root / "227300" / "remote" / "profiles" / "5072696D617279"
        (profile / "save" / "autosave").mkdir(parents=True)
        (profile / "profile.sii").write_text("profile", encoding="utf-8")
        companion = root / "documents" / "steam_profiles" / profile.name
        companion.mkdir(parents=True)
        metadata = root / "227300" / "remotecache.vdf"
        metadata.write_text("metadata", encoding="utf-8")
        return ProfileInfo(
            "Primary",
            profile,
            storage=STEAM_CLOUD_PROFILE_STORAGE,
            documents_root=root / "documents",
            companion_path=companion,
            steam_metadata_path=metadata,
        )

    def test_calculates_exact_five_plus_five_cost(self) -> None:
        request = FillRequest(profile=Path("profile"), slots=5)
        self.assertEqual(request.truck_cost_eur, 1_242_425)
        self.assertEqual(request.driver_cost_eur, 7_500)
        self.assertEqual(request.total_cost_eur, 1_249_925)

    def test_rejects_missing_profile(self) -> None:
        self.assertEqual(
            validate_request(FillRequest(profile=None)),
            ["Choose a disposable local ETS2 profile."],
        )

    def test_accepts_complete_disposable_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_profile(Path(temp))
            self.assertEqual(validate_request(FillRequest(profile=profile)), [])

    def test_controller_arguments_require_explicit_profile(self) -> None:
        with self.assertRaisesRegex(ValueError, "profile is required"):
            controller_arguments(FillRequest(profile=None), Path("project"))

    def test_controller_arguments_use_guarded_home_fill(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_profile(Path(temp))
            arguments = controller_arguments(
                FillRequest(profile=profile, slots=3), Path("project")
            )
            self.assertIn("--execute", arguments)
            self.assertEqual(arguments[arguments.index("--count") + 1], "3")
            self.assertEqual(arguments[arguments.index("--profile") + 1], str(profile))
            self.assertEqual(arguments[-4:], [
                "--start-stage", "home", "--dynamic-garage", "--require-empty-garage"
            ])

    def test_live_validation_accepts_only_exact_disposable_one_plus_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_profile(Path(temp))
            info = ProfileInfo("ETS2 Automation Test", profile)
            self.assertEqual(
                validate_live_validation_request(
                    FillRequest(profile=profile, slots=1), info, enabled=True
                ),
                [],
            )

    def test_live_validation_rejects_normal_mode_larger_batch_and_other_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_profile(Path(temp))
            errors = validate_live_validation_request(
                FillRequest(profile=profile, slots=5),
                ProfileInfo("Main career", profile),
                enabled=False,
            )
            self.assertEqual(len(errors), 3)

    def test_graduated_live_test_allows_five_slots_only_on_test_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_profile(Path(temp))
            request = FillRequest(profile=profile, slots=5)
            self.assertEqual(
                validate_graduated_live_request(
                    request,
                    ProfileInfo("ETS2 Automation Test", profile),
                    enabled=True,
                ),
                [],
            )
            errors = validate_graduated_live_request(
                request, ProfileInfo("Main career", profile), enabled=True
            )
            self.assertEqual(len(errors), 1)

    def test_main_profile_validation_requires_exact_cloud_one_plus_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_cloud_profile(Path(temp))
            request = FillRequest(profile=profile.path, slots=1)

            self.assertEqual(
                validate_main_profile_validation_request(
                    request,
                    profile,
                    enabled=True,
                    expected_profile_name="Primary",
                ),
                [],
            )
            errors = validate_main_profile_validation_request(
                FillRequest(profile=profile.path, slots=5),
                profile,
                enabled=True,
                expected_profile_name="Wrong Career",
            )
            self.assertTrue(any("exactly one" in error for error in errors))
            self.assertTrue(any("Wrong Career" in error for error in errors))

    def test_main_profile_two_validation_requires_exact_cloud_two_plus_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_cloud_profile(Path(temp))
            request = FillRequest(profile=profile.path, slots=2)

            self.assertEqual(
                validate_main_profile_validation_request(
                    request,
                    profile,
                    enabled=True,
                    expected_profile_name="Primary",
                    expected_slots=2,
                ),
                [],
            )
            errors = validate_main_profile_validation_request(
                FillRequest(profile=profile.path, slots=1),
                profile,
                enabled=True,
                expected_profile_name="Primary",
                expected_slots=2,
            )
            self.assertTrue(any("exactly two" in error for error in errors))

    def test_main_profile_three_validation_requires_exact_cloud_three_plus_three(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_cloud_profile(Path(temp))
            request = FillRequest(profile=profile.path, slots=3)

            self.assertEqual(
                validate_main_profile_validation_request(
                    request,
                    profile,
                    enabled=True,
                    expected_profile_name="Primary",
                    expected_slots=3,
                ),
                [],
            )
            errors = validate_main_profile_validation_request(
                FillRequest(profile=profile.path, slots=2),
                profile,
                enabled=True,
                expected_profile_name="Primary",
                expected_slots=3,
            )
            self.assertTrue(any("exactly three" in error for error in errors))

    def test_main_profile_five_validation_requires_exact_cloud_five_plus_five(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_cloud_profile(Path(temp))
            request = FillRequest(profile=profile.path, slots=5)

            self.assertEqual(
                validate_main_profile_validation_request(
                    request,
                    profile,
                    enabled=True,
                    expected_profile_name="Primary",
                    expected_slots=5,
                ),
                [],
            )
            errors = validate_main_profile_validation_request(
                FillRequest(profile=profile.path, slots=3),
                profile,
                enabled=True,
                expected_profile_name="Primary",
                expected_slots=5,
            )
            self.assertTrue(any("exactly five" in error for error in errors))

    def test_main_profile_validation_rejects_an_unapproved_slot_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_cloud_profile(Path(temp))
            errors = validate_main_profile_validation_request(
                FillRequest(profile=profile.path, slots=4),
                profile,
                enabled=True,
                expected_profile_name="Primary",
                expected_slots=4,
            )
        self.assertTrue(any("guarded 5+5" in error for error in errors))

    def test_cloud_controller_arguments_carry_every_recovery_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_cloud_profile(Path(temp))
            arguments = controller_arguments(
                FillRequest(profile=profile.path, slots=1),
                Path("project"),
                steam_cloud_profile=profile,
            )

        self.assertIn("--allow-steam-cloud-validation", arguments)
        self.assertEqual(arguments[arguments.index("--profile-name") + 1], "Primary")
        self.assertEqual(
            arguments[arguments.index("--documents-companion") + 1],
            str(profile.companion_path),
        )
        self.assertEqual(
            arguments[arguments.index("--steam-metadata") + 1],
            str(profile.steam_metadata_path),
        )

    def test_cloud_two_controller_arguments_use_a_distinct_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_cloud_profile(Path(temp))
            arguments = controller_arguments(
                FillRequest(profile=profile.path, slots=2),
                Path("project"),
                steam_cloud_profile=profile,
            )

        self.assertIn("--allow-steam-cloud-two-validation", arguments)
        self.assertNotIn("--allow-steam-cloud-validation", arguments)
        self.assertEqual(arguments[arguments.index("--count") + 1], "2")

    def test_cloud_three_controller_arguments_use_a_distinct_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_cloud_profile(Path(temp))
            arguments = controller_arguments(
                FillRequest(profile=profile.path, slots=3),
                Path("project"),
                steam_cloud_profile=profile,
            )

        self.assertIn("--allow-steam-cloud-three-validation", arguments)
        self.assertNotIn("--allow-steam-cloud-validation", arguments)
        self.assertNotIn("--allow-steam-cloud-two-validation", arguments)
        self.assertEqual(arguments[arguments.index("--count") + 1], "3")

    def test_cloud_five_controller_arguments_use_a_distinct_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_cloud_profile(Path(temp))
            arguments = controller_arguments(
                FillRequest(profile=profile.path, slots=5),
                Path("project"),
                steam_cloud_profile=profile,
            )

        self.assertIn("--allow-steam-cloud-five-validation", arguments)
        self.assertNotIn("--allow-steam-cloud-validation", arguments)
        self.assertNotIn("--allow-steam-cloud-two-validation", arguments)
        self.assertNotIn("--allow-steam-cloud-three-validation", arguments)
        self.assertEqual(arguments[arguments.index("--count") + 1], "5")

    def test_cloud_controller_arguments_reject_uncertified_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = self.make_cloud_profile(Path(temp))
            with self.assertRaisesRegex(ValueError, r"only the 1\+1, 2\+2, 3\+3, and 5\+5"):
                controller_arguments(
                    FillRequest(profile=profile.path, slots=4),
                    Path("project"),
                    steam_cloud_profile=profile,
                )

    def test_supervised_live_arguments_share_output_and_cancel_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = self.make_profile(root)
            run_dir = root / "run"
            arguments = controller_arguments(
                FillRequest(profile=profile, slots=1), Path("project"), run_dir
            )
        self.assertEqual(arguments[arguments.index("--output-dir") + 1], str(run_dir))
        self.assertEqual(
            arguments[arguments.index("--cancel-file") + 1],
            str(run_dir / "cancel.requested"),
        )
        self.assertIn("--require-empty-garage", arguments)


if __name__ == "__main__":
    unittest.main()
