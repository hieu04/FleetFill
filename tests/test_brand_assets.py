from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image


class BrandAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_primary_icon_has_release_quality_dimensions_and_transparency(self) -> None:
        with Image.open(self.root / "assets" / "fleetfill-app.png") as image:
            self.assertEqual(image.size, (512, 512))
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.assertGreater(image.getpixel((256, 256))[3], 0)

    def test_windows_icon_contains_multiple_sizes(self) -> None:
        with Image.open(self.root / "assets" / "fleetfill-app.ico") as image:
            self.assertEqual(image.format, "ICO")
            sizes = {width for width, _height in image.info["sizes"]}
            self.assertTrue({16, 32, 48, 64, 128, 256}.issubset(sizes))


if __name__ == "__main__":
    unittest.main()
