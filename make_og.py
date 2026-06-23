#!/usr/bin/env python3
"""Generate the static 1200x630 social share image (og-image.png).

Branding only — run once and commit the PNG. Re-run if the brand look changes.
Open Graph / Twitter need a real raster image (PNG/JPG), not SVG, so we bake one.
"""
import os, math
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1200, 630
BG = (10, 14, 20)        # #0a0e14
CARD = (18, 24, 33)      # #121821
GOLD = (231, 185, 78)    # #e7b94e
INK = (233, 237, 244)    # #e9edf4
MUTE = (148, 160, 179)   # #94a0b3


def _font(names, size):
    for n in names:
        for base in (r"C:\Windows\Fonts", "/usr/share/fonts", ""):
            try:
                return ImageFont.truetype(os.path.join(base, n) if base else n, size)
            except Exception:
                continue
    return ImageFont.load_default()


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # subtle latitude grid (market/map motif)
    for y in range(70, H, 70):
        d.line([(0, y), (W, y)], fill=(22, 30, 44), width=1)
    for x in range(70, W, 70):
        d.line([(x, 0), (x, H)], fill=(18, 24, 36), width=1)

    # a gold "great-circle" arc — the Magellan voyage motif
    pts = []
    for i in range(0, 101):
        t = i / 100
        x = 80 + t * (W - 160)
        y = 470 - math.sin(t * math.pi) * 230
        pts.append((x, y))
    d.line(pts, fill=GOLD, width=4, joint="curve")
    # endpoint dots
    d.ellipse([72, 462, 96, 486], fill=INK)
    d.ellipse([W - 96, 462, W - 72, 486], outline=GOLD, width=4)
    # little plane at the apex
    ax, ay = pts[50]
    d.polygon([(ax - 14, ay + 8), (ax + 16, ay), (ax - 14, ay - 8), (ax - 6, ay)],
              fill=GOLD)

    big = _font(["segoeuib.ttf", "Arialbd.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 92)
    mid = _font(["segoeui.ttf", "Arial.ttf", "arial.ttf", "DejaVuSans.ttf"], 38)
    small = _font(["segoeui.ttf", "Arial.ttf", "arial.ttf", "DejaVuSans.ttf"], 30)

    d.text((80, 110), "Magellan Flights", font=big, fill=INK)
    d.text((84, 222), "The cheapest flights from the USA", font=mid, fill=GOLD)
    d.text((84, 540), "magellanflights.com", font=small, fill=MUTE)

    for name in ("og-image.png", os.path.join("site", "og-image.png")):
        p = os.path.join(HERE, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        img.save(p, "PNG")
    print("Wrote og-image.png (1200x630) to root + site/")


if __name__ == "__main__":
    main()
