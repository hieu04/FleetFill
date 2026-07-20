from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PIL import Image


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from ets2_ui_open_services_probe import (  # noqa: E402
    HOME_REFERENCE,
    recognize_home,
)
from ets2_ui_open_service_destination_probe import (  # noqa: E402
    FLYOUT_REFERENCE,
    recognize_services_flyout,
)
from ets2_ui_open_hire_driver_probe import (  # noqa: E402
    RECRUITMENT_MAP_REFERENCE,
    load_recruitment_map_reference,
    recognize_recruitment_map,
)


class HomeUiTests(unittest.TestCase):
    def test_recognizes_visible_home_navigation(self):
        reference = Image.open(HOME_REFERENCE).convert("RGB")
        result = recognize_home(reference, reference)
        self.assertEqual(result["state"], "home")
        self.assertTrue(result["safe_to_open_services"])

    def test_rejects_faded_idle_background(self):
        idle = (
            Path(__file__).resolve().parents[1]
            / "output"
            / "live-home-screen-direct-capture"
            / "direct-capture-20260721-005602-528055.png"
        )
        reference = Image.open(HOME_REFERENCE).convert("RGB")
        result = recognize_home(Image.open(idle).convert("RGB"), reference)
        self.assertEqual(result["state"], "unknown")
        self.assertFalse(result["safe_to_open_services"])

    def test_recognizes_services_flyout(self):
        reference = Image.open(FLYOUT_REFERENCE).convert("RGB")
        result = recognize_services_flyout(reference, reference)
        self.assertEqual(result["state"], "services_flyout")
        self.assertTrue(result["safe_to_select_destination"])

    def test_rejects_home_without_services_flyout(self):
        reference = Image.open(FLYOUT_REFERENCE).convert("RGB")
        home = Image.open(HOME_REFERENCE).convert("RGB")
        result = recognize_services_flyout(home, reference)
        self.assertEqual(result["state"], "unknown")
        self.assertFalse(result["safe_to_select_destination"])

    def test_recognizes_recruitment_map(self):
        reference = load_recruitment_map_reference()
        result = recognize_recruitment_map(reference, reference)
        self.assertEqual(result["state"], "recruitment_map")
        self.assertTrue(result["safe_to_open_driver_list"])

    def test_recruitment_map_rejects_home(self):
        reference = Image.open(RECRUITMENT_MAP_REFERENCE).convert("RGB")
        home = Image.open(HOME_REFERENCE).convert("RGB")
        result = recognize_recruitment_map(home, reference)
        self.assertEqual(result["state"], "unknown")
        self.assertFalse(result["safe_to_open_driver_list"])


if __name__ == "__main__":
    unittest.main()
