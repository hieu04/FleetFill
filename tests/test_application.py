from __future__ import annotations

import unittest

from fleetfill.application import build_parser


class ApplicationArgumentsTests(unittest.TestCase):
    def test_normal_mode_does_not_arm_live_validation(self) -> None:
        self.assertFalse(build_parser().parse_args([]).live_validation)

    def test_validation_launcher_requires_explicit_flag(self) -> None:
        self.assertTrue(
            build_parser().parse_args(["--live-validation"]).live_validation
        )

    def test_graduated_live_test_has_a_separate_flag(self) -> None:
        args = build_parser().parse_args(["--live-test"])
        self.assertTrue(args.live_test)
        self.assertFalse(args.live_validation)

    def test_live_development_modes_are_mutually_exclusive(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["--live-test", "--live-validation"])


if __name__ == "__main__":
    unittest.main()
