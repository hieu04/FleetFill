from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from ets2_ui_dealer_marker_probe import choose_available_marker  # noqa: E402
from ets2_ui_open_online_purchase_probe import (  # noqa: E402
    wait_for_loaded_purchase,
)


class DealerMarkerProbeTests(unittest.TestCase):
    def test_accepts_single_available_marker(self):
        marker = {"state": "available", "center": [700, 500]}
        self.assertIs(choose_available_marker([marker]), marker)

    def test_chooses_topmost_then_leftmost_available_marker(self):
        markers = [
            {"state": "available", "center": [900, 600]},
            {"state": "selected", "center": [400, 100]},
            {"state": "available", "center": [800, 300]},
            {"state": "available", "center": [700, 300]},
        ]
        self.assertIs(choose_available_marker(markers), markers[3])

    def test_returns_none_without_available_markers(self):
        markers = [{"state": "selected", "center": [700, 500]}]
        self.assertIsNone(choose_available_marker(markers))


class OnlinePurchaseLoadingTests(unittest.TestCase):
    @staticmethod
    def capture_result(state: str, safe_to_act: bool) -> tuple:
        analysis = {
            "state": state,
            "safe_to_act": safe_to_act,
            "visual_integrity": {"complete": safe_to_act},
        }
        return ("shot", "image", analysis, "annotated", "report")

    def test_waits_through_blank_cards_until_loaded(self):
        captures = iter(
            [
                self.capture_result("truck_purchase", False),
                self.capture_result("truck_purchase", False),
                self.capture_result("truck_purchase", True),
            ]
        )
        result, observations = wait_for_loaded_purchase(
            lambda: next(captures),
            timeout=20.0,
            clock=lambda: 0.0,
            sleeper=lambda _delay: None,
        )
        self.assertTrue(result[2]["safe_to_act"])
        self.assertEqual(len(observations), 3)

    def test_allows_dealer_map_during_initial_transition(self):
        captures = iter(
            [
                self.capture_result("dealer_map", True),
                self.capture_result("truck_purchase", True),
            ]
        )
        result, observations = wait_for_loaded_purchase(
            lambda: next(captures),
            timeout=20.0,
            clock=lambda: 0.0,
            sleeper=lambda _delay: None,
        )
        self.assertEqual(result[2]["state"], "truck_purchase")
        self.assertEqual(len(observations), 2)

    def test_stops_immediately_on_unexpected_screen(self):
        result, observations = wait_for_loaded_purchase(
            lambda: self.capture_result("truck_garage_selection", False),
            timeout=20.0,
            clock=lambda: 0.0,
            sleeper=lambda _delay: None,
        )
        self.assertEqual(result[2]["state"], "truck_garage_selection")
        self.assertEqual(len(observations), 1)

    def test_stops_when_blank_cards_outlast_timeout(self):
        clock_values = iter([0.0, 0.5, 21.0])
        result, observations = wait_for_loaded_purchase(
            lambda: self.capture_result("truck_purchase", False),
            timeout=20.0,
            clock=lambda: next(clock_values),
            sleeper=lambda _delay: None,
        )
        self.assertFalse(result[2]["safe_to_act"])
        self.assertEqual(len(observations), 2)


if __name__ == "__main__":
    unittest.main()
