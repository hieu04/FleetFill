from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fleetfill.domain import (
    FillRequest,
    controller_arguments,
    decode_profile_folder_name,
    discover_local_profiles,
    validate_request,
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
            self.assertEqual(
                arguments[-3:], ["--start-stage", "home", "--dynamic-garage"]
            )


if __name__ == "__main__":
    unittest.main()
