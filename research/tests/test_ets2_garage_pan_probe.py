from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from ets2_ui_garage_pan_probe import choose_drag_pair, marker_clearance  # noqa: E402
from ets2_ui_find_after_pan_probe import marker_is_action_safe  # noqa: E402
from ets2_ui_replay_pan_locator_probe import nearest_marker  # noqa: E402


class GaragePanProbeTests(unittest.TestCase):
    def test_rejects_top_edge_clipped_marker(self):
        marker = {
            "bounds": [942, 176, 975, 197],
            "center": [958, 186],
            "width": 33,
            "height": 21,
        }
        self.assertFalse(marker_is_action_safe(marker))

    def test_accepts_fully_visible_lower_marker(self):
        marker = {
            "bounds": [1191, 331, 1224, 364],
            "center": [1207, 347],
            "width": 33,
            "height": 33,
        }
        self.assertTrue(marker_is_action_safe(marker))

    def test_clearance_uses_nearest_marker(self):
        markers = [{"center": [100, 100]}, {"center": [200, 100]}]
        self.assertEqual(marker_clearance((150, 100), markers), 50.0)

    def test_chooses_first_clear_corridor(self):
        markers = [{"center": [1200, 300]}, {"center": [1400, 300]}]
        self.assertEqual(choose_drag_pair(markers), ((1380, 610), (1080, 610)))

    def test_skips_corridor_with_marker_on_endpoint(self):
        markers = [{"center": [1380, 610]}, {"center": [1080, 610]}]
        self.assertEqual(choose_drag_pair(markers), ((1440, 570), (1140, 570)))

    def test_returns_none_when_all_corridors_blocked(self):
        markers = [
            {"center": [1380, 610]},
            {"center": [1440, 570]},
            {"center": [1320, 620]},
            {"center": [1260, 580]},
        ]
        self.assertIsNone(choose_drag_pair(markers))

    def test_replay_locator_accepts_nearby_action_safe_marker(self):
        markers = [
            {
                "bounds": [1410, 245, 1444, 278],
                "center": [1427, 261],
                "width": 34,
                "height": 33,
            }
        ]
        marker, distance = nearest_marker(markers, (1429, 263), tolerance=5)
        self.assertEqual(marker, markers[0])
        self.assertAlmostEqual(distance, 2.828427, places=5)

    def test_replay_locator_rejects_marker_outside_tolerance(self):
        markers = [
            {
                "bounds": [1410, 245, 1444, 278],
                "center": [1427, 261],
                "width": 34,
                "height": 33,
            }
        ]
        marker, distance = nearest_marker(markers, (1400, 240), tolerance=10)
        self.assertIsNone(marker)
        self.assertGreater(distance, 10)


if __name__ == "__main__":
    unittest.main()
