"""Build full-bleed app icons from the square logo artwork.

The source (images/ufeed logo 1.png) is a rounded tile with a darker rim on a
grey background. Home-screen icons must be full-bleed squares (iOS/Android
apply their own mask), so: crop inside the rim, then fill the rounded corners
by extending the tile's own gradient outwards (sampled along the same angle
just inside the curve). Run: uvx --with pillow python scripts/make_icons.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "images" / "ufeed logo 1.png"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Frontend" / "static"

# Measured on the 1024px source: tile spans x 89..934, rim ~20px, corner r~137.
CROP = (113, 111, 910, 908)  # inside the rim, square (797px)
RADIUS = 125  # corner zone to rebuild (px in the crop)
SAMPLE = 100  # sample this far from the corner centre (safely inside the fill)


def full_bleed() -> Image.Image:
    tile = Image.open(SRC).convert("RGB").crop(CROP)
    s = tile.size[0]
    px = tile.load()
    centres = [(RADIUS, RADIUS), (s - 1 - RADIUS, RADIUS), (RADIUS, s - 1 - RADIUS),
               (s - 1 - RADIUS, s - 1 - RADIUS)]
    for cx, cy in centres:
        xs = range(0, RADIUS + 1) if cx == RADIUS else range(s - 1 - RADIUS, s)
        ys = range(0, RADIUS + 1) if cy == RADIUS else range(s - 1 - RADIUS, s)
        for y in ys:
            for x in xs:
                dx, dy = x - cx, y - cy
                d = math.hypot(dx, dy)
                if d <= SAMPLE:
                    continue
                sx = round(cx + dx / d * SAMPLE)
                sy = round(cy + dy / d * SAMPLE)
                px[x, y] = px[sx, sy]
    return tile


def padded(img: Image.Image, content: float) -> Image.Image:
    """Maskable variant: shrink the art into the safe zone, extend the edges."""
    size = img.size[0]
    inner = img.resize((round(size * content),) * 2, Image.LANCZOS)
    canvas = img.resize((size, size), Image.LANCZOS)  # background = same art, blurred by scale
    canvas = canvas.resize((8, 8), Image.BILINEAR).resize((size, size), Image.BILINEAR)
    off = (size - inner.size[0]) // 2
    canvas.paste(inner, (off, off))
    return canvas


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    art = full_bleed()
    for name, px in (
        ("apple-touch-icon.png", 180),
        ("icon-192.png", 192),
        ("icon-512.png", 512),
        ("favicon-32.png", 32),
        ("logo.png", 64),
    ):
        art.resize((px, px), Image.LANCZOS).save(OUT / name, optimize=True)
    padded(art.resize((512, 512), Image.LANCZOS), 0.82).save(
        OUT / "icon-maskable-512.png", optimize=True
    )
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
