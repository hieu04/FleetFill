from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from ets2_ui_return_home_probe import recognize_supported_source  # noqa: E402


class ReturnHomeRecognitionTests(unittest.TestCase):
    @patch("ets2_ui_return_home_probe.load_recruitment_references", return_value={})
    @patch("ets2_ui_return_home_probe.recognize_recruitment")
    def test_accepts_action_safe_recruitment_cards(self, recognize, _load) -> None:
        recognize.return_value = {
            "state": "recruitment_agency",
            "safe_to_act": True,
        }
        result = recognize_supported_source(object())
        self.assertEqual(result["workflow"], "recruitment")
        self.assertTrue(result["safe_to_act"])

    @patch("ets2_ui_return_home_probe.load_truck_references", return_value={})
    @patch("ets2_ui_return_home_probe.recognize_truck")
    @patch("ets2_ui_return_home_probe.load_recruitment_references", return_value={})
    @patch("ets2_ui_return_home_probe.recognize_recruitment")
    def test_rejects_unknown_screen(
        self, recognize_recruitment, _load_recruitment, recognize_truck, _load_truck
    ) -> None:
        recognize_recruitment.return_value = {
            "state": "unknown",
            "safe_to_act": False,
        }
        recognize_truck.return_value = {"state": "unknown", "safe_to_act": False}
        result = recognize_supported_source(object())
        self.assertEqual(result["state"], "unknown")
        self.assertFalse(result["safe_to_act"])


if __name__ == "__main__":
    unittest.main()
