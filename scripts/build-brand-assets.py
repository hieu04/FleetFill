"""Build deterministic FleetFill Windows icon assets."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
AMBER = "#F5A800"
CHARCOAL = "#15181A"


def build_icon(size: int = 1024) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scale = size / 1024

    def box(values: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return tuple(round(value * scale) for value in values)

    def points(values: list[tuple[int, int]]) -> list[tuple[int, int]]:
        return [(round(x * scale), round(y * scale)) for x, y in values]

    draw.rounded_rectangle(box((64, 64, 960, 960)), radius=190 * scale, fill=AMBER)

    # A broad garage outline remains legible in Windows' smallest icon slots.
    draw.polygon(
        points([(220, 475), (512, 292), (804, 475), (748, 558), (512, 412), (276, 558)]),
        fill=CHARCOAL,
    )
    draw.rounded_rectangle(box((220, 458, 332, 772)), radius=18 * scale, fill=CHARCOAL)
    draw.rounded_rectangle(box((692, 458, 804, 772)), radius=18 * scale, fill=CHARCOAL)

    # The forward arrow communicates a single guarded action filling the garage.
    draw.polygon(
        points(
            [
                (374, 585),
                (554, 585),
                (554, 518),
                (684, 640),
                (554, 762),
                (554, 695),
                (374, 695),
            ]
        ),
        fill=CHARCOAL,
    )
    return image


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    master = build_icon()
    png = ASSETS / "fleetfill-app.png"
    ico = ASSETS / "fleetfill-app.ico"
    master.resize((512, 512), Image.Resampling.LANCZOS).save(png, optimize=True)
    master.save(
        ico,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"FLEETFILL_ICON_PNG: {png}")
    print(f"FLEETFILL_ICON_ICO: {ico}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
