from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from ets2_truck_ui_dry_run import (  # noqa: E402
    DEALER_TITLE,
    load_truck_references,
    recognize,
)
from ets2_ui_fleet_config_probe import wait_for_loaded_fleet_cards  # noqa: E402


class TruckDealerRecognitionTests(unittest.TestCase):
    def test_translucent_background_change_keeps_dealer_map_safe(self) -> None:
        references = load_truck_references()
        pixels = np.asarray(references["dealer_map"]).copy()
        left, top, right, bottom = DEALER_TITLE
        title = pixels[top:bottom, left:right]
        yellow = (
            (title[:, :, 0] > 135)
            & (title[:, :, 1] > 75)
            & (title[:, :, 1] < 210)
            & (title[:, :, 2] < 90)
            & ((title[:, :, 0].astype(np.int16) - title[:, :, 1]) > 20)
        )
        title[~yellow] = (235, 235, 235)

        result = recognize(Image.fromarray(pixels), references)

        self.assertEqual(result["state"], "dealer_map")
        self.assertTrue(result["safe_to_act"])
        self.assertGreater(result["distances"]["dealer_map"], 0.44)


class FleetCardLoadingTests(unittest.TestCase):
    def test_waits_through_loading_placeholders(self) -> None:
        results = iter(
            [
                {"state": "truck_purchase", "safe_to_act": False},
                {"state": "truck_purchase", "safe_to_act": False},
                {"state": "truck_purchase", "safe_to_act": True},
            ]
        )
        now = [0.0]

        def sleep(seconds: float) -> None:
            now[0] += seconds

        sample, attempts = wait_for_loaded_fleet_cards(
            lambda: next(results),
            lambda result: result,
            timeout=10.0,
            interval=0.5,
            clock=lambda: now[0],
            sleep=sleep,
        )

        self.assertTrue(sample["safe_to_act"])
        self.assertEqual(attempts, 3)
        self.assertEqual(now[0], 1.0)

    def test_times_out_without_authorizing_a_click(self) -> None:
        now = [0.0]

        def sleep(seconds: float) -> None:
            now[0] += seconds

        sample, attempts = wait_for_loaded_fleet_cards(
            lambda: {"state": "truck_purchase", "safe_to_act": False},
            lambda result: result,
            timeout=1.0,
            interval=0.5,
            clock=lambda: now[0],
            sleep=sleep,
        )

        self.assertFalse(sample["safe_to_act"])
        self.assertEqual(attempts, 3)


if __name__ == "__main__":
    unittest.main()
