from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from ets2_ui_find_capacity_garage_probe import (  # noqa: E402
    DEFAULT_MAX_MARKERS,
    canonical_garage_name,
    exceeds_marker_guard,
    has_capacity,
    is_resolved_unselected,
    resolve_allowed_garage_id,
    slot_counts,
)
from ets2_ui_dry_run import is_occupied_portrait  # noqa: E402


class CapacityGarageFinderTests(unittest.TestCase):
    def test_dense_map_regression_stays_inside_bounded_marker_guard(self):
        fixture = Path(__file__).parent / "fixtures" / "dense_garage_map_35_markers.json"
        evidence = json.loads(fixture.read_text(encoding="utf-8"))

        self.assertEqual(evidence["detected_candidate_count"], 35)
        self.assertEqual(len(evidence["candidate_centers"]), 35)
        self.assertFalse(exceeds_marker_guard(evidence["detected_candidate_count"]))
        self.assertEqual(DEFAULT_MAX_MARKERS, 60)

    def test_candidate_guard_still_aborts_detector_explosions(self):
        self.assertFalse(exceeds_marker_guard(60))
        self.assertTrue(exceeds_marker_guard(61))

    def test_rendered_city_names_match_preflight_garage_ids(self):
        self.assertEqual(canonical_garage_name("garage.cluj_napoca"), "clujnapoca")
        self.assertEqual(canonical_garage_name("Cluj-Napoca"), "clujnapoca")
        self.assertEqual(canonical_garage_name("København"), "kobenhavn")

    def test_ocr_confusion_resolves_only_an_allowed_owned_garage(self):
        self.assertEqual(
            resolve_allowed_garage_id("la9i", ["garage.iasi", "garage.debrecen"]),
            "garage.iasi",
        )
        self.assertEqual(
            resolve_allowed_garage_id(
                "\ufffdla9i", ["garage.iasi", "garage.debrecen"]
            ),
            "garage.iasi",
        )
        self.assertIsNone(
            resolve_allowed_garage_id("la9i", ["garage.debrecen", "garage.brasov"])
        )

    def test_ambiguous_or_unrelated_ocr_fails_closed(self):
        self.assertIsNone(
            resolve_allowed_garage_id("unknown", ["garage.luga", "garage.lodz"])
        )
        self.assertIsNone(
            resolve_allowed_garage_id("Riga", ["garage.luga", "garage.lodz"])
        )

    def test_unowned_iasi_regression_is_rejected_before_click(self):
        fixture = Path(__file__).parent / "fixtures" / "unowned_garage_activation.json"
        evidence = json.loads(fixture.read_text(encoding="utf-8"))

        self.assertEqual(evidence["preflight_status"], 0)
        self.assertEqual(evidence["unplanned_garage_cost_eur"], 2_800_000)
        self.assertIsNone(
            resolve_allowed_garage_id(
                evidence["rendered_city"], ["garage.debrecen", "garage.brasov"]
            )
        )

    def test_portrait_with_some_yellow_is_still_occupied(self):
        self.assertTrue(is_occupied_portrait(963, 96))

    def test_dark_portrait_regression_is_still_occupied(self):
        fixture = Path(__file__).parent / "fixtures" / "dark_driver_portrait_slot.json"
        evidence = json.loads(fixture.read_text(encoding="utf-8"))

        self.assertEqual(evidence["observed_state_before_fix"], "locked")
        self.assertTrue(
            is_occupied_portrait(
                evidence["strongly_colored_pixels"], evidence["yellow_pixels"]
            )
        )

    def test_neutral_truck_slot_is_not_a_portrait(self):
        self.assertFalse(is_occupied_portrait(1, 0))

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
