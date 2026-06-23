#!/usr/bin/env python3
"""Generate a ready-to-paste social caption kit from the city-guide data.

Writes social/captions.md — per-city captions for X, Instagram/TikTok, Reddit and
Pinterest, plus a "deal of the day" template and a hashtag bank. Captions are
price-agnostic on purpose (they promote the evergreen guide + video, so they never
go stale); drop the live price into the deal-of-the-day template when you post.

Re-run after adding cities: `python make_social.py`.
"""
import os
import buildsite as bs

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "social")

HASHTAGS = {
    "core": "#cheapflights #flightdeals #traveldeals #budgettravel #travelhacks",
    "wander": "#travel #wanderlust #traveltips #vacation #explore",
}

# Per-country flavor hashtags for a little reach beyond the generic set.
COUNTRY_TAGS = {
    "Mexico": "#mexico #visitmexico", "Puerto Rico": "#puertorico #discoverpuertorico",
    "Dominican Republic": "#dominicanrepublic #puntacana", "Jamaica": "#jamaica #visitjamaica",
    "Aruba": "#aruba #onehappyisland", "Colombia": "#colombia #visitcolombia",
    "Portugal": "#portugal #visitportugal", "Iceland": "#iceland #visiticeland",
    "Ireland": "#ireland #loveireland", "Thailand": "#thailand #amazingthailand",
    "Greece": "#greece #visitgreece", "Turkey": "#turkey #goturkiye",
    "United Arab Emirates": "#dubai #visitdubai", "Morocco": "#morocco #visitmorocco",
    "Egypt": "#egypt #thisisegypt", "Spain": "#spain #visitspain",
}


def caption_block(g):
    code, city, country = g["code"], g["city"], g["country"]
    url = bs.BASE_URL + "/" + g["fname"]
    cg = bs.CITY_GUIDE.get(code, {})
    todo = cg.get("todo", [])
    best = bs.BEST_TIME.get(code, "year-round")
    t1 = todo[0] if todo else "explore the old town"
    t2 = todo[1] if len(todo) > 1 else "eat your way through the markets"
    t3 = todo[2] if len(todo) > 2 else "catch the sunset"
    ctags = COUNTRY_TAGS.get(country, "")

    x = (f"Thinking about {city}? Here's the cheap-flights-from-the-USA + a 2-min "
         f"guide to what to actually do there ✈️\n{url}\n{HASHTAGS['core']} {ctags}")

    ig = (f"\U0001f4cd {city.upper()}, {country}\n\n"
          f"We track the cheapest flights to {city} from the USA every day — and put "
          f"the whole trip in one place: when to go, what it costs, and the stuff worth "
          f"your time.\n\nTop 3 to do:\n• {t1}\n• {t2}\n• {t3}\n\n"
          f"Best time to go: {best}.\n\nFull guide + today's fare → link in bio "
          f"(or {url})\n\n{HASHTAGS['core']} {HASHTAGS['wander']} {ctags}")

    reddit_title = (f"Put together a no-fluff {city} guide — cheapest flights from the US, "
                    f"best time to go, and what's actually worth doing")
    reddit_body = (f"Been tracking fares to {city} ({code}) and wrote up the trip in one page: "
                   f"the current cheapest round-trip from the US, when fares tend to dip, and a "
                   f"short list of what to do ({t1.lower()}, {t2.lower()}, {t3.lower()}). "
                   f"No signup, no fluff — sharing in case it's useful: {url}")

    pin = (f"Cheap flights to {city}, {country} + a complete travel guide: best time to visit "
           f"({best}), top things to do, safety and culture. {ctags}")

    return (f"### {city}, {country}  \n`{url}`\n\n"
            f"**X / Twitter**\n```\n{x}\n```\n\n"
            f"**Instagram / TikTok caption**\n```\n{ig}\n```\n\n"
            f"**Reddit** (r/travel, r/TravelHacks, r/Shoestring — post genuinely, don't spam)\n"
            f"Title:\n```\n{reddit_title}\n```\nBody:\n```\n{reddit_body}\n```\n\n"
            f"**Pinterest description**\n```\n{pin}\n```\n")


PLAYBOOK = f"""# Magellan Flights — social caption kit

Copy-paste captions for every city guide. They promote the **evergreen guide + video**,
so they don't go stale — post them any time. For the daily winner, use the
**deal of the day** template below and drop in the live price.

## The daily routine (the flywheel)
1. Check today's winner on the **Daily Guide** ({bs.BASE_URL}/blog.html).
2. Film/post a short video about that city (what to do, tips, safety, culture).
3. Put the YouTube link in the matching city guide (send it to your dev / drop it in
   `YT_VIDEOS` in buildsite.py).
4. Post the **deal of the day** caption (below) on X / IG / TikTok / Facebook, link to
   the city guide. In the YouTube description, link back to the city guide.
5. That's the loop: video → guide → socials → traffic → back to the video.

## Posting cadence that works for deal accounts
- **1 deal-of-the-day** post across X + IG/TikTok + Facebook (the winner).
- **2–3 evergreen city posts** a week (rotate the cities below) to Pinterest + IG.
- **Reddit**: 1–2 genuinely helpful posts a week, in different subs, no link-spam.

## Deal of the day — fill in the blanks
```
✈️ Deal of the day: {{CITY}} for ${{PRICE}} round-trip from the US

{{ONE_LINE_WHY_IT_RULES}}. Full guide + how to book → {{URL}}

{HASHTAGS['core']}
```

## Hashtag bank
- Core: {HASHTAGS['core']}
- Wander: {HASHTAGS['wander']}
- Add 1–2 country tags from each city's block below.

---

"""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    blocks = "\n---\n\n".join(caption_block(g) for g in bs.CITY_GUIDES)
    md = PLAYBOOK + blocks + "\n"
    with open(os.path.join(OUT_DIR, "captions.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(f"social/captions.md — {len(bs.CITY_GUIDES)} cities × 4 platforms + playbook")


if __name__ == "__main__":
    main()
