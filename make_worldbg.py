#!/usr/bin/env python3
"""Generate world-bg.svg — a faint green world-map silhouette used as the
site-wide page background (Atlas theme). Static asset: run once and commit the
SVG. Source: Natural Earth 110m land (public domain).
"""
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 2000, 1000
SRC = ("https://raw.githubusercontent.com/martynafford/natural-earth-geojson/"
       "master/110m/physical/ne_110m_land.json")


def load():
    cache = os.path.join(HERE, "ne_110m_land.json")
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    data = urllib.request.urlopen(SRC, timeout=30).read().decode("utf-8")
    open(cache, "w", encoding="utf-8").write(data)
    return json.loads(data)


def ring_path(ring):
    pts = []
    for lon, lat in ring:
        x = (lon + 180) / 360 * W
        y = (90 - lat) / 180 * H
        pts.append(f"{x:.0f} {y:.0f}")
    if len(pts) < 4:
        return ""
    return "M" + "L".join(pts) + "Z"


def geom_paths(geom):
    t = geom["type"]
    cs = geom["coordinates"]
    polys = [cs] if t == "Polygon" else cs if t == "MultiPolygon" else []
    out = []
    for poly in polys:
        for ring in poly:
            p = ring_path(ring)
            if p:
                out.append(p)
    return out


def main():
    gj = load()
    paths = []
    for f in gj["features"]:
        paths += geom_paths(f.get("geometry") or {})
    d = "".join(paths)
    grat = []
    for x in range(0, W + 1, 100):
        grat.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}"/>')
    for y in range(0, H + 1, 100):
        grat.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           f'preserveAspectRatio="xMidYMid slice">'
           f'<g stroke="#2f6b46" stroke-width="1" opacity="0.035">{"".join(grat)}</g>'
           f'<path d="{d}" fill="#2f6b46" fill-opacity="0.06" stroke="#2f6b46" '
           f'stroke-opacity="0.10" stroke-width="0.8" fill-rule="evenodd"/></svg>')
    for base in (HERE, os.path.join(HERE, "site")):
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "world-bg.svg"), "w", encoding="utf-8") as fh:
            fh.write(svg)
    print(f"world-bg.svg written ({len(svg)} bytes, {len(paths)} rings)")


if __name__ == "__main__":
    main()
