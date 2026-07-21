from __future__ import annotations

import unittest

from verify_fill_batch_save import changed_slot_indexes


class FillBatchSlotDiffTests(unittest.TestCase):
    def test_one_plus_one_in_five_slot_garage_changes_one_paired_index(self) -> None:
        before = {
            "vehicles": ["null"] * 5,
            "drivers": ["null"] * 5,
        }
        after = {
            "vehicles": ["vehicle.1", "null", "null", "null", "null"],
            "drivers": ["driver.1", "null", "null", "null", "null"],
        }
        self.assertEqual(changed_slot_indexes(before, after), [0])

    def test_shape_mismatch_fails_closed(self) -> None:
        before = {"vehicles": ["null"] * 5, "drivers": ["null"] * 5}
        after = {"vehicles": ["vehicle.1"], "drivers": ["driver.1"]}
        self.assertEqual(changed_slot_indexes(before, after), [])


if __name__ == "__main__":
    unittest.main()
