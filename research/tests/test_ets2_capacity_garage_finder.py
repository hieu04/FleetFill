from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from ets2_ui_find_capacity_garage_probe import (  # noqa: E402
    has_capacity,
    is_resolved_unselected,
    slot_counts,
)
from ets2_ui_dry_run import is_occupied_portrait  # noqa: E402


class CapacityGarageFinderTests(unittest.TestCase):
    def test_portrait_with_some_yellow_is_still_occupied(self):
        self.assertTrue(is_occupied_portrait(963, 96))

    def test_yellow_selected_slot_is_not_a_portrait(self):
        self.assertFalse(is_occupied_portrait(1564, 1564))

    def test_counts_resolved_slot_states(self):
        states = ["occupied", "truck_present", "truck_present", "free", "free"]
        self.assertEqual(
            slot_counts(states),
            {"occupied": 1, "truck_present": 2, "free": 2},
        )

    def test_truck_context_uses_free_slots(self):
        states = ["occupied", "truck_present", "free", "free", "free"]
        self.assertTrue(has_capacity(states, "truck", 3))
        self.assertFalse(has_capacity(states, "truck", 4))

    def test_hire_context_uses_driverless_trucks(self):
        states = ["occupied", "truck_present", "truck_present", "free", "free"]
        self.assertTrue(has_capacity(states, "hire", 2))
        self.assertFalse(has_capacity(states, "hire", 3))

    def test_empty_garage_qualifies_for_five_trucks(self):
        self.assertTrue(has_capacity(["free"] * 5, "truck", 5))

    def test_locked_or_selected_states_never_qualify(self):
        self.assertFalse(has_capacity(["locked"] * 5, "truck", 1))
        self.assertFalse(
            has_capacity(["selected_free", "free", "free", "free", "free"], "truck", 4)
        )

    def test_resolved_requires_exactly_five_known_states(self):
        self.assertTrue(is_resolved_unselected(["occupied"] * 5))
        self.assertFalse(is_resolved_unselected(["occupied"] * 4))
        self.assertFalse(
            is_resolved_unselected(["occupied", "free", "free", "free", "unknown"])
        )


if __name__ == "__main__":
    unittest.main()
