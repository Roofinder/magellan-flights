#!/usr/bin/env python3
"""Generate the brand favicon (the Magellan compass) for browsers + Google Search.

Writes favicon.svg + PNG sizes to the repo root and site/. Static brand assets —
run once, re-run only if the mark changes. Google shows the favicon next to your
search result; it updates a few days/weeks after a re-crawl.
"""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
BG = (10, 14, 20)       # #0a0e14
GOLD = (240, 200, 96)   # #f0c860
GOLD_D = (199, 154, 51)  # #c79a33
RING = (231, 185, 78)   # #e7b94e
LINE = (184, 134, 47)   # #b8862f

# A dark rounded square + the Magellan compass rose (matches LOGO_SVG).
FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<rect width="100" height="100" rx="20" fill="#0a0e14"/>'
    '<circle cx="50" cy="50" r="46" fill="none" stroke="#e7b94e" stroke-width="3"/>'
    '<g stroke="#b8862f" stroke-width="1.6" opacity="0.7">'
    '<line x1="50" y1="50" x2="71" y2="29"/><line x1="50" y1="50" x2="71" y2="71"/>'
    '<line x1="50" y1="50" x2="29" y2="71"/><line x1="50" y1="50" x2="29" y2="29"/></g>'
    '<path d="M50 9 L42 42 L50 50 Z" fill="#f0c860"/><path d="M50 9 L58 42 L50 50 Z" fill="#c79a33"/>'
    '<path d="M91 50 L58 42 L50 50 Z" fill="#f0c860"/><path d="M91 50 L58 58 L50 50 Z" fill="#c79a33"/>'
    '<path d="M50 91 L58 58 L50 50 Z" fill="#f0c860"/><path d="M50 91 L42 58 L50 50 Z" fill="#c79a33"/>'
    '<path d="M9 50 L42 58 L50 50 Z" fill="#f0c860"/><path d="M9 50 L42 42 L50 50 Z" fill="#c79a33"/>'
    '<circle cx="50" cy="50" r="5.5" fill="#0a0e14"/><circle cx="50" cy="50" r="3" fill="#f0c860"/>'
    '</svg>'
)

FACETS = [
    ((50, 9), (42, 42), (50, 50), GOLD), ((50, 9), (58, 42), (50, 50), GOLD_D),
    ((91, 50), (58, 42), (50, 50), GOLD), ((91, 50), (58, 58), (50, 50), GOLD_D),
    ((50, 91), (58, 58), (50, 50), GOLD), ((50, 91), (42, 58), (50, 50), GOLD_D),
    ((9, 50), (42, 58), (50, 50), GOLD), ((9, 50), (42, 42), (50, 50), GOLD_D),
]


def draw_png(size):
    S = size * 4  # supersample for smooth edges
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sc = S / 100.0

    def P(x, y):
        return (x * sc, y * sc)

    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(20 * sc), fill=BG)
    r = 46 * sc
    d.ellipse([S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r], outline=RING, width=max(2, int(3 * sc)))
    for (x2, y2) in [(71, 29), (71, 71), (29, 71), (29, 29)]:
        d.line([P(50, 50), P(x2, y2)], fill=LINE, width=max(1, int(1.6 * sc)))
    for a, b, c, col in FACETS:
        d.polygon([P(*a), P(*b), P(*c)], fill=col)
    cx, cy = P(50, 50)
    d.ellipse([cx - 5.5 * sc, cy - 5.5 * sc, cx + 5.5 * sc, cy + 5.5 * sc], fill=BG)
    d.ellipse([cx - 3 * sc, cy - 3 * sc, cx + 3 * sc, cy + 3 * sc], fill=GOLD)
    return img.resize((size, size), Image.LANCZOS)


def main():
    for base in (HERE, os.path.join(HERE, "site")):
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "favicon.svg"), "w", encoding="utf-8") as f:
            f.write(FAVICON_SVG)
    sizes = {"favicon-32.png": 32, "favicon-48.png": 48, "favicon-96.png": 96, "apple-touch-icon.png": 180}
    for fn, sz in sizes.items():
        img = draw_png(sz)
        if fn == "apple-touch-icon.png":      # iOS wants opaque
            flat = Image.new("RGB", (sz, sz), BG)
            flat.paste(img, (0, 0), img)
            img = flat
        for base in (HERE, os.path.join(HERE, "site")):
            img.save(os.path.join(base, fn))
    print("favicon.svg + favicon-32/48/96.png + apple-touch-icon.png -> root + site/")


if __name__ == "__main__":
    main()
