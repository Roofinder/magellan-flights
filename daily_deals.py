#!/usr/bin/env python
"""Magellan's Daily Deals — generate ready-to-record short-video scripts from the SAME
live deal data the site and newsletter use (imports buildsite.py, so the deal pick and
the 'below normal' math stay identical — no duplicated logic).

Run:  python daily_deals.py [N] [outdir]
        N       how many deals (default 5)
        outdir  where to write (default ./daily-deals)

Per deal it emits: a ~22-28s voiceover script, the on-screen text overlays, a platform
caption + hashtags, the Aviasales booking link, and a destination photo URL — i.e. a
batch session starts from done scripts instead of a blank page.

Owner tool — run locally; output is not part of the published site.
"""
import os
import sys
from datetime import datetime

import buildsite as B

WPS = 2.7  # ~160 wpm narration, for the rough read-time estimate


def num(n):
    return f"{n:,.0f}"


def script_for(pct, o, p):
    """Build the full script package for one deal: (pct, oneway-row, price)."""
    city = str(o.get("name", o["code"])).split(",")[0].strip()
    country = B.country_from_name(str(o.get("name", "")))
    loc = f"{city}, {country}" if country and country != city else city
    origin = o.get("origin", "")
    link = o.get("link", "")
    pctr = round(pct)
    has_pct = pctr >= 8 and 0 < pct < 90
    normal = p / (1 - pct / 100.0) if has_pct else 0
    img, blurb, coords = B._hero_photo(city)

    # --- voiceover (~50-70 words) ---
    vo = [f"{num(p)} dollars, one-way to {city}."]
    if has_pct and normal > p:
        vo.append(f"That's about {pctr} percent below what this route normally runs "
                  f"— usually around {num(normal)} dollars.")
    else:
        vo.append("One of the best fares on the board right now.")
    if blurb:
        sent = blurb.split(". ")[0].strip().rstrip(".")
        if len(sent) > 115:                       # Wikipedia first "sentence" can run long / cut mid-word
            sent = sent[:115].rsplit(" ", 1)[0].rstrip(",;:")
        vo.append(sent + ".")
    vo.append("Fares like this don't last. The full deal, plus more from your airport, "
              "is free in our newsletter — link in bio.")
    voiceover = " ".join(vo)

    # --- on-screen overlays (drop into the CapCut template) ---
    hook = f"${num(p)}   {city.upper()}" + (f", {country}" if country and country != city else "")
    badge = (f"{pctr}% BELOW NORMAL   (usually ~${num(normal)})" if has_pct and normal > p
             else "RARE FARE ON THE BOARD")
    context = f"one-way from {origin}" + (f"   ·   {coords}" if coords else "")
    overlays = [
        ("0-3s  HOOK", hook),
        ("3-8s  BADGE", badge),
        ("8-18s CONTEXT", context),
        ("18-27s CTA", "magellanflights.com   ·   FREE weekly deals → link in bio"),
    ]

    # --- caption ---
    citytag = "".join(ch for ch in city.lower() if ch.isalnum())
    below = f" — {pctr}% below normal" if has_pct else ""
    caption = (
        f"✈️ ${num(p)} one-way to {loc}{below} right now.\n\n"
        f"Comment your city and I'll tell you the cheapest flight from YOU \U0001f447\n"
        f"Full deal + more, free in our newsletter (link in bio).\n\n"
        f"#cheapflights #flightdeals #traveldeals #budgettravel #travel #{citytag}"
    )

    return {
        "loc": loc, "price": p, "pct": pctr, "has_pct": has_pct, "normal": normal,
        "link": link, "img": img, "voiceover": voiceover, "overlays": overlays,
        "caption": caption, "words": len(voiceover.split()),
    }


def main():
    args = [a for a in sys.argv[1:]]
    n = int(args[0]) if args and args[0].isdigit() else 5
    outdir = (args[1] if len(args) > 1 and not args[1].isdigit()
              else (args[0] if args and not args[0].isdigit() else os.path.join(B.HERE, "daily-deals")))
    os.makedirs(outdir, exist_ok=True)

    market = B.read_snapshot()
    if not market:
        print("No data/market_latest.csv yet. Run 'python market.py' first.")
        return
    oneway = B.read_oneway(kind="6m")

    ranked = B._hm_items(oneway, market)
    items = [it for it in ranked if it[0] >= 12][:n]   # lead with strong below-normal deals
    if len(items) < n:
        seen = {id(it) for it in items}
        items += [it for it in ranked if id(it) not in seen][:n - len(items)]
    if not items:
        print("No deals available from the current data.")
        return

    today = datetime.now()
    path = os.path.join(outdir, f"deals-{today.strftime('%Y%m%d')}.md")
    out = [
        f"# Magellan's Daily Deals — scripts for {today.strftime('%Y-%m-%d')}",
        "",
        f"Auto-generated from live data &middot; {len(items)} deals. Record the voiceover, drop the "
        "photo + overlays into your CapCut template, post to Reels / TikTok / Shorts, one bio link to "
        "the newsletter. Batch the whole week in one sitting.",
        "",
    ]
    for i, (pct, o, p) in enumerate(items, 1):
        d = script_for(pct, o, p)
        head = f"## {i}. {d['loc']} — ${num(d['price'])}"
        if d["has_pct"]:
            head += f"  ({d['pct']}% below normal)"
        out += [
            head,
            "",
            f"- **Photo:** {d['img'] or '(no Wikipedia photo — use your own b-roll)'}",
            f"- **Booking link:** {d['link']}",
            f"- **VO length:** ~{d['words']} words (~{round(d['words'] / WPS)}s read)",
            "",
            "**Voiceover**",
            "",
            f"> {d['voiceover']}",
            "",
            "**On-screen overlays**",
            "",
        ]
        out += [f"- **{label}:**  {text}" for label, text in d["overlays"]]
        out += ["", "**Caption**", "", "```", d["caption"], "```", "", "---", ""]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"Wrote {len(items)} deal scripts -> {path}")


if __name__ == "__main__":
    main()
