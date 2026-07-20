from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from ets2_ui_dealer_filtered_pan_probe import (  # noqa: E402
    action_safe_dealer,
    estimate_horizontal_translation,
)


class DealerMapTranslationTests(unittest.TestCase):
    def test_estimates_leftward_artwork_motion_without_markers(self):
        generator = np.random.default_rng(42)
        before = generator.integers(0, 255, size=(120, 400), dtype=np.uint8)
        after = generator.integers(0, 255, size=(120, 400), dtype=np.uint8)
        after[:, :320] = before[:, 80:]
        result = estimate_horizontal_translation(
            Image.fromarray(before).convert("RGB"),
            Image.fromarray(after).convert("RGB"),
            box=(0, 0, 400, 120),
            scale=1.0,
            max_shift=120,
        )
        self.assertEqual(result["dx"], -80)
        self.assertLess(result["normalized_error"], 0.001)
        self.assertGreater(result["confidence_gap"], 1.0)

    def test_dealer_marker_must_be_inside_safe_map_interior(self):
        safe = {
            "state": "available",
            "bounds": [1249, 172, 1280, 203],
            "center": [1264, 187],
        }
        clipped = {
            "state": "available",
            "bounds": [1770, 172, 1801, 203],
            "center": [1785, 187],
        }
        self.assertTrue(action_safe_dealer(safe))
        self.assertFalse(action_safe_dealer(clipped))


if __name__ == "__main__":
    unittest.main()
