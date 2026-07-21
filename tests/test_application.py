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


if __name__ == "__main__":
    unittest.main()
