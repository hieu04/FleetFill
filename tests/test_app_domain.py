from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fleetfill.domain import (
    FillRequest,
    ProfileInfo,
    controller_arguments,
    decode_profile_folder_name,
    discover_local_profiles,
    validate_request,
    validate_graduated_live_request,
    validate_live_validation_request,
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

            self.assertEqual([(item.name, item.path) for item in found], [("Test", profile)])


class FillRequestTests(unittest.TestCase):
    def make_profile(self, root: Path) -> Path:
        profile = root / "profile"
        (profile / "save" / "autosave").mkdir(parents=True)
        (profile / "profile.sii").write_text("profile", encoding="utf-8")
        return profile

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
