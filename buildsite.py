#!/usr/bin/env python3
"""
BuildSite - generates a multi-page, CNBC-style flight website into site/.

Pages (shared header, tickers, nav and footer on every one):
  index.html       Home - tickers, market summary, top deals, email signup
  market.html      Region indices + movers board + all deal cards
  explore.html     Region-selectable ticker + one-way escapes abroad
  lastminute.html  Cheapest round-trip getaways this week
  airports.html    "My airports" - personalized deals from your home airport(s)
  watchlist.html   Your starred destinations + followed airlines

Each page is self-contained HTML; upload the whole site/ folder to any host.

Reads:  data/market_latest.csv, data/pricehistory.csv, explore_oneway_*.csv,
        lastminute_*.csv, data/homebase.json

Run:  py buildsite.py     (also runs automatically twice a day)
Uses only the Python standard library.
"""

import csv
import glob
import html
import json
import os
from collections import defaultdict
from datetime import datetime

import dealsgen as dg

HERE = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(HERE, "site")
DATA_DIR = os.path.join(HERE, "data")
SNAP = os.path.join(DATA_DIR, "market_latest.csv")
HISTORY = os.path.join(DATA_DIR, "pricehistory.csv")
HOMEBASE = os.path.join(DATA_DIR, "homebase.json")

EMOJI = {code: emoji for code, name, emoji, bench in dg.DESTINATIONS}
BEST_TIME = dg.BEST_TIME
DEST_INFO = dg.DEST_INFO

CODE_COUNTRY = {
    "BKK": "th", "DPS": "id", "HKT": "th", "SGN": "vn", "HAN": "vn", "NRT": "jp",
    "KIX": "jp", "ICN": "kr", "SIN": "sg", "KUL": "my", "MNL": "ph", "DEL": "in",
    "BOM": "in", "HKG": "hk", "TPE": "tw", "KTM": "np",
    "DXB": "ae", "DOH": "qa", "IST": "tr", "TLV": "il",
    "LHR": "gb", "CDG": "fr", "FCO": "it", "BCN": "es", "MAD": "es", "LIS": "pt",
    "AMS": "nl", "FRA": "de", "ATH": "gr", "DUB": "ie", "KEF": "is", "PRG": "cz", "CPH": "dk",
    "MEX": "mx", "CUN": "mx", "SJD": "mx", "PTY": "pa", "SJO": "cr", "SJU": "pr",
    "PUJ": "do", "NAS": "bs", "BOG": "co", "LIM": "pe", "GRU": "br", "EZE": "ar", "SCL": "cl",
    "SYD": "au", "MEL": "au", "AKL": "nz", "NAN": "fj",
    "CAI": "eg", "CMN": "ma", "JNB": "za", "NBO": "ke",
}

AIRLINES = {
    "SQ": "Singapore Airlines", "EY": "Etihad", "QR": "Qatar Airways", "EK": "Emirates",
    "AA": "American", "UA": "United", "DL": "Delta", "BA": "British Airways",
    "AF": "Air France", "KL": "KLM", "LH": "Lufthansa", "TK": "Turkish Airlines",
    "JL": "Japan Airlines", "NH": "ANA", "KE": "Korean Air", "OZ": "Asiana",
    "CX": "Cathay Pacific", "TG": "Thai Airways", "AV": "Avianca", "CM": "Copa",
    "AC": "Air Canada", "IB": "Iberia", "TP": "TAP Portugal", "AY": "Finnair",
    "VS": "Virgin Atlantic", "SV": "Saudia", "ET": "Ethiopian", "GF": "Gulf Air",
    "WY": "Oman Air", "MH": "Malaysia Airlines", "GA": "Garuda", "VN": "Vietnam Airlines",
    "BR": "EVA Air", "CA": "Air China", "MU": "China Eastern", "CZ": "China Southern",
    "FI": "Icelandair", "AI": "Air India",
}

REGIONS = {
    "Asia": ["BKK", "DPS", "HKT", "SGN", "HAN", "NRT", "KIX", "ICN", "SIN", "KUL",
             "MNL", "DEL", "BOM", "HKG", "TPE", "KTM"],
    "Europe": ["LHR", "CDG", "FCO", "BCN", "MAD", "LIS", "AMS", "FRA", "ATH", "DUB",
               "KEF", "PRG", "CPH"],
    "Middle East": ["DXB", "DOH", "IST", "TLV"],
    "Americas": ["MEX", "CUN", "SJD", "PTY", "SJO", "SJU", "PUJ", "NAS", "BOG", "LIM",
                 "GRU", "EZE", "SCL"],
    "Oceania": ["SYD", "MEL", "AKL", "NAN"],
    "Africa": ["CAI", "CMN", "JNB", "NBO"],
}

_GROUPS = {
    "SE Asia": "TH VN ID SG MY PH KH LA MM BN TL".split(),
    "E Asia": "JP KR CN TW HK MO MN".split(),
    "S Asia": "IN LK NP PK BD MV BT AF".split(),
    "C Asia": "KZ UZ KG TJ TM".split(),
    "W Europe": "FR GB DE NL BE IE ES PT IT CH AT LU MC AD LI MT".split(),
    "Nordic": "SE NO DK FI IS".split(),
    "E Europe": "PL CZ HU RO BG GR HR RS SK SI UA EE LV LT AL BA MK ME MD BY RU CY".split(),
    "S America": "BR AR CL CO PE EC UY PY BO VE GF SR GY".split(),
    "C America": "MX GT BZ SV HN NI CR PA".split(),
    "Caribbean": "DO JM BS CU HT PR TT BB AW CW GP MQ KY BM AG LC GD VC DM KN TC VG AI MS SX BQ".split(),
    "Oceania": "AU NZ FJ PF NC WS TO VU PG CK GU".split(),
    "Middle East": "AE QA SA IL JO TR LB KW BH OM IR IQ YE SY".split(),
    "Africa": "ZA EG MA KE ET NG GH TZ SN CI TN DZ UG RW MU SC NA BW ZW MZ AO CM GA".split(),
    "Canada": "CA".split(),
}
REGION_BTNS = ["all", "USA", "Abroad", "Asia", "SE Asia", "E Asia", "S Asia",
               "W Europe", "E Europe", "Nordic", "S America", "C America",
               "Caribbean", "Oceania", "Middle East", "Africa", "Canada"]

NAV = [("index.html", "Home"), ("market.html", "Market"), ("explore.html", "Explore"),
       ("trip.html", "Journey"), ("blog.html", "Daily Guide"), ("guides.html", "Guides"),
       ("watchlist.html", "My Bucket List Flights"), ("essentials.html", "Travel kit")]


def regions_for(cc):
    cc = (cc or "").upper()
    for grp, codes in _GROUPS.items():
        if cc in codes:
            tags = [grp]
            if grp in ("SE Asia", "E Asia", "S Asia", "C Asia"):
                tags.append("Asia")
            if grp in ("W Europe", "Nordic", "E Europe"):
                tags.append("Europe")
            return tags
    return []


# All chip bars share one comprehensive region list; empty ones are hidden in JS.
LM_BTNS = REGION_BTNS


def lm_tags(cc):
    cc = (cc or "").upper()
    if cc == "US":
        return ["USA"]
    return regions_for(cc)


# ---- Connect these later (see HOSTING.md) -------------------------------- #
FORM_ACTION = "https://formspree.io/f/mojoqrgn"
BRAND = "Magellan Flights"
TAGLINE = "The cheapest flights from the USA, tracked like a market - every day."

# --------------------------------------------------------------------------- #
# SEO: per-page titles + descriptions, social cards, schema, sitemap.
# All booking links stay Aviasales/Travelpayouts (marker 741311) — SEO only
# touches the <head> and a couple of static text files; it never changes links.
# --------------------------------------------------------------------------- #
BASE_URL = "https://www.magellanflights.com"      # canonical home (served domain; apex 308s here)
OG_IMAGE = BASE_URL + "/og-image.png"             # 1200x630 social share image

# Unique, keyword-targeted <title> + meta description per page. Keep titles
# ~55-60 chars and descriptions ~150-160 so Google shows them in full.
SEO = {
    "index.html": (
        "Cheap Flights from the USA — Tracked Daily | Magellan Flights",
        "Find today's cheapest flights from the USA to anywhere. Real fares "
        "refreshed several times a day and tracked like a stock market, so you "
        "book at the low. Round-trip and one-way deals."),
    "market.html": (
        "Cheap Flight Deals Today — Live Fare Tracker | Magellan Flights",
        "A live board of the cheapest round-trip flights from the USA, with "
        "price history and how far below normal each fare is. Updated daily."),
    "world.html": (
        "Cheapest Flights Anywhere to Anywhere | Magellan Flights",
        "Explore the cheapest flights between 50 global hubs — anywhere to "
        "anywhere. Compare live fares and find the best-value route today."),
    "explore.html": (
        "Cheap One-Way Flights from the USA (Next 6 Months) | Magellan Flights",
        "The cheapest one-way flights from the USA over the next six months. "
        "Filter by region and home airport to find your next trip for less."),
    "lastminute.html": (
        "Cheap Last-Minute Flights from the USA | Magellan Flights",
        "Today's cheapest last-minute flights from the USA, domestic and "
        "international. Real, bookable fares for travelers who can leave soon."),
    "blog.html": (
        "Today's Cheapest Flight from the USA — Daily Guide | Magellan Flights",
        "Our daily guide to the single best flight deal from the USA right now: "
        "the price, the dates, why it's a deal, and how to book it."),
    "airports.html": (
        "Cheap Flights from Your Home Airport | Magellan Flights",
        "See the cheapest flights leaving your home airport right now. Pick "
        "your airports and track fares to everywhere they fly."),
    "trip.html": (
        "Plan a Trip — Cheapest Dates & Fares | Magellan Flights",
        "Plan your journey around the cheapest dates and fares from the USA, "
        "with trip-cost and best-time-to-go guidance."),
    "watchlist.html": (
        "Your Flight Watchlist — Track Fare Drops | Magellan Flights",
        "Track the routes you care about and watch for price drops. Your "
        "personal watchlist of the cheapest flights from the USA."),
    "essentials.html": (
        "Travel Essentials — Gear & Tips for Cheap Trips | Magellan Flights",
        "Hand-picked travel essentials and tips to make your cheap flight a "
        "great trip — from carry-ons to currency know-how."),
    "guides.html": (
        "Flight Deal Guides — When to Book & Where to Go | Magellan Flights",
        "Straight answers on when to book flights, the cheapest time to fly, "
        "and how to catch a cheap fare — backed by fares we track daily."),
}

# Questions AI assistants and Google's "People also ask" love to answer.
# Rendered as a FAQPage schema so ChatGPT/Gemini/Claude/Google can quote us.
SEO_FAQ = [
    ("How does Magellan Flights find the cheapest flights from the USA?",
     "Magellan Flights scans live airfare data several times a day and tracks "
     "each route's price history like a stock market. That lets it flag when a "
     "fare is unusually low — well below its normal range — so you book at the "
     "right moment instead of guessing."),
    ("Are the flight prices on Magellan Flights real and bookable?",
     "Yes. Every fare is re-checked against live airline pricing before it is "
     "shown, and obvious phantom prices are removed. Clicking a deal takes you "
     "to a secure booking page for that exact flight."),
    ("What's the difference between a round-trip and a one-way deal here?",
     "Round-trip deals cover a there-and-back journey from a US airport. "
     "One-way deals are single legs — useful for open-jaw trips, long stays, or "
     "pairing two cheap one-ways into a cheaper round-trip."),
    ("How often are the deals updated?",
     "The whole board refreshes several times every day, so the prices you see "
     "reflect what's available right now, not last week."),
    ("Is Magellan Flights free to use?",
     "Yes, it's completely free. When you book through a deal link we may earn "
     "a small commission from the travel partner, at no extra cost to you."),
]


def _seo_for(active, fallback_title):
    """(full <title>, meta description) for a page — unique where defined."""
    art = globals().get("ARTICLE_BY_FILE", {})
    if active in art:
        return (art[active]["title"], art[active]["description"])
    if active in SEO:
        return SEO[active]
    return (f"{fallback_title} | {BRAND}", TAGLINE)


def _esc_attr(s):
    return (str(s).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def head_seo(active, full_title, description, market=None):
    """Canonical + Open Graph + Twitter + JSON-LD schema for one page."""
    url = BASE_URL + "/" + ("" if active == "index.html" else active)
    t, d = _esc_attr(full_title), _esc_attr(description)
    tags = [
        f'<link rel="canonical" href="{url}">',
        '<meta name="robots" content="index, follow, max-image-preview:large">',
        '<meta name="theme-color" content="#0a0e14">',
        f'<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{BRAND}">',
        f'<meta property="og:title" content="{t}">',
        f'<meta property="og:description" content="{d}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{OG_IMAGE}">',
        f'<meta property="og:image:alt" content="{_esc_attr(BRAND)} — the cheapest flights from the USA">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{t}">',
        f'<meta name="twitter:description" content="{d}">',
        f'<meta name="twitter:image" content="{OG_IMAGE}">',
        f'<meta name="twitter:image:alt" content="{_esc_attr(BRAND)} — the cheapest flights from the USA">',
    ]
    # ---- JSON-LD schema graph ------------------------------------------ #
    graph = [
        {"@type": "Organization", "@id": BASE_URL + "/#org", "name": BRAND,
         "url": BASE_URL, "logo": OG_IMAGE,
         "description": TAGLINE},
        {"@type": "WebSite", "@id": BASE_URL + "/#website", "name": BRAND,
         "url": BASE_URL, "publisher": {"@id": BASE_URL + "/#org"},
         "potentialAction": {
             "@type": "SearchAction",
             "target": {"@type": "EntryPoint",
                        "urlTemplate": BASE_URL + "/world.html?q={search_term_string}"},
             "query-input": "required name=search_term_string"}},
        {"@type": "WebPage", "@id": url + "#webpage", "url": url,
         "name": full_title, "description": description,
         "isPartOf": {"@id": BASE_URL + "/#website"}},
    ]
    # Home + market: list the live deals so search engines see structured offers.
    if active in ("index.html", "market.html") and market:
        items = []
        for i, m in enumerate(sorted(market, key=lambda x: _to_int(x.get("price")))[:10], 1):
            try:
                price = _to_int(m.get("price"))
            except Exception:
                continue
            if not price:
                continue
            items.append({
                "@type": "ListItem", "position": i,
                "name": f"{m.get('origin','USA')} to {m.get('name', m.get('code',''))}",
                "url": url})
        if items:
            graph.append({"@type": "ItemList", "name": "Cheapest flight deals today",
                          "numberOfItems": len(items), "itemListElement": items})
    # Home: add the FAQ so AI assistants can quote concrete answers (GEO).
    if active == "index.html":
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in SEO_FAQ]})
    # Blog article: add Article + breadcrumb + (optional) FAQ schema.
    art = globals().get("ARTICLE_BY_FILE", {})
    if active in art:
        a = art[active]
        graph.append({
            "@type": "Article", "headline": a["h1"], "description": a["description"],
            "datePublished": a["published"], "dateModified": a["updated"],
            "author": {"@id": BASE_URL + "/#org"},
            "publisher": {"@id": BASE_URL + "/#org"},
            "image": OG_IMAGE, "mainEntityOfPage": {"@id": url + "#webpage"}})
        graph.append({
            "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Guides",
                 "item": BASE_URL + "/guides.html"},
                {"@type": "ListItem", "position": 2, "name": a["h1"], "item": url}]})
        if a.get("faqs"):
            graph.append({"@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": ans}}
                for q, ans in a["faqs"]]})
    blob = json.dumps({"@context": "https://schema.org", "@graph": graph},
                      ensure_ascii=False)
    tags.append(f'<script type="application/ld+json">{blob}</script>')
    return "\n".join(tags)


def _to_int(v):
    try:
        return int(float(v))
    except Exception:
        return 0


def _marker():
    try:
        with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
            return json.load(f).get("marker", "")
    except Exception:  # noqa: BLE001
        return ""


MARKER = _marker()


def _load_coords():
    try:
        with open(os.path.join(HERE, "airport_coords.json"), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:  # noqa: BLE001
        return "{}"


MAP_COORDS = _load_coords()

# Cross-sell affiliate widgets ("Plan the rest of your trip"). Hotels works now via
# Hotellook + your marker. For the others, paste your Travelpayouts program links
# here once approved (see HOSTING.md). "#" = not connected yet.
AFFILIATE = [
    ("Hotels", "hotel", "https://search.hotellook.com/?marker=" + MARKER,
     "Compare hotels worldwide. You earn on every booking."),
    ("eSIM data", "esim", "https://airalo.tp.st/k719ywOV",
     "Instant mobile data abroad — no roaming fees."),
    ("Travel insurance", "insurance", "https://ektatraveling.tp.st/edRJZE4n",
     "Medical, trip-cancellation and baggage cover."),
    ("Car rental", "car", "https://getrentacar.tp.st/1iKjA1x6",
     "Rent a car when you land at your destination."),
    ("Airport transfer", "van", "https://kiwitaxi.tp.st/7aDORbmz",
     "Pre-booked rides from the airport to your hotel."),
    ("Tours & activities", "tours", "#",
     "Skip-the-line tickets, tours and experiences."),
]
# -------------------------------------------------------------------------- #


def airline_name(code):
    return AIRLINES.get(code, code or "")


def signal_for(price, benchmark):
    pct = (benchmark - price) / benchmark * 100 if benchmark else 0
    if pct >= 20:
        return "BOOK", pct
    if pct >= 8:
        return "WATCH", pct
    return "WAIT", pct


# Per-night hotel estimates by region (rough averages) for the trip-cost estimator.
HOTEL_NIGHT = {"SE Asia": 40, "E Asia": 110, "S Asia": 35, "W Europe": 140,
               "E Europe": 75, "Nordic": 170, "S America": 55, "C America": 75,
               "Caribbean": 160, "Oceania": 140, "Middle East": 120, "Africa": 85,
               "USA": 140, "Canada": 130}
ESIM_COST = 15
HIST_SERIES = {}  # {code: [price per day, oldest..newest]} — filled in main()
FEATURED_VERIFIED = {}  # {code: True} — featured deals cross-checked vs Skyscanner


def hotel_night(code):
    for t in lm_tags(CODE_COUNTRY.get(code, "").upper()):
        if t in HOTEL_NIGHT:
            return HOTEL_NIGHT[t]
    return 100


def week_cost(code, flight_price):
    return round(flight_price + 7 * hotel_night(code) + ESIM_COST)


# Destination country -> currency, + rough USD exchange rates (live-updated in JS).
COUNTRY_CURRENCY = {
    "th": "THB", "id": "IDR", "vn": "VND", "jp": "JPY", "kr": "KRW", "sg": "SGD",
    "my": "MYR", "ph": "PHP", "in": "INR", "hk": "HKD", "tw": "TWD", "np": "NPR",
    "ae": "AED", "qa": "QAR", "tr": "TRY", "il": "ILS", "gb": "GBP", "fr": "EUR",
    "it": "EUR", "es": "EUR", "pt": "EUR", "nl": "EUR", "de": "EUR", "gr": "EUR",
    "ie": "EUR", "is": "ISK", "cz": "CZK", "dk": "DKK", "mx": "MXN", "pa": "USD",
    "cr": "CRC", "pr": "USD", "do": "DOP", "bs": "BSD", "co": "COP", "pe": "PEN",
    "br": "BRL", "ar": "ARS", "cl": "CLP", "au": "AUD", "nz": "NZD", "fj": "FJD",
    "eg": "EGP", "ma": "MAD", "za": "ZAR", "ke": "KES",
}
FX_STATIC = {  # approx units per 1 USD; JS refreshes these live on load
    "THB": 36, "IDR": 16300, "VND": 25400, "JPY": 157, "KRW": 1380, "SGD": 1.35,
    "MYR": 4.6, "PHP": 58, "INR": 84, "HKD": 7.8, "TWD": 32, "NPR": 134, "AED": 3.67,
    "QAR": 3.64, "TRY": 33, "ILS": 3.7, "GBP": 0.79, "EUR": 0.92, "ISK": 138,
    "CZK": 23, "DKK": 6.9, "MXN": 18.5, "CRC": 515, "DOP": 59, "BSD": 1, "COP": 4000,
    "PEN": 3.75, "BRL": 5.4, "ARS": 950, "CLP": 950, "AUD": 1.5, "NZD": 1.65,
    "FJD": 2.25, "EGP": 48, "MAD": 9.9, "ZAR": 18.5, "KES": 130, "USD": 1,
}


def dest_currency(code):
    return COUNTRY_CURRENCY.get(CODE_COUNTRY.get(code, ""), "")


def fmt_rate(r):
    if r >= 100:
        return f"{r:,.0f}"
    if r >= 10:
        return f"{r:.1f}"
    return f"{r:.2f}"


def fx_line(code):
    cur = dest_currency(code)
    if not cur:
        return ""
    if cur == "USD":
        return '<p class="trip">&#128178; Uses the US dollar</p>'
    rate = FX_STATIC.get(cur)
    if not rate:
        return ""
    return (f'<p class="trip">&#128178; <span data-cur="{cur}">'
            f'$1 &asymp; {fmt_rate(rate)} {cur}</span></p>')


def hist_signal(code, price, benchmark):
    """Book/Watch/Wait using real price history once we have enough days; else
    falls back to the benchmark signal. Returns (label, css_class)."""
    series = HIST_SERIES.get(code, [])
    if len(series) >= 4:
        lo, avg = min(series), sum(series) / len(series)
        if price <= lo * 1.02:
            return ("BOOK · lowest in " + str(len(series)) + "d", "s-book")
        if price <= avg * 0.96:
            return ("Good price", "s-book")
        if price >= avg * 1.06:
            return ("Wait · above avg", "s-wait")
        return ("Fair price", "s-watch")
    sig, _ = signal_for(price, benchmark)
    return ({"BOOK": "BOOK", "WATCH": "WATCH", "WAIT": "WAIT"}[sig],
            {"BOOK": "s-book", "WATCH": "s-watch", "WAIT": "s-wait"}[sig])


def is_flash(code, price, benchmark):
    """A 'flash deal' = price far below normal (and below its own history low)."""
    pct = (benchmark - price) / benchmark * 100 if benchmark else 0
    series = HIST_SERIES.get(code, [])
    if len(series) >= 5 and price <= min(series) and pct >= 30:
        return True
    return pct >= 42


def corroborated(code, price):
    """Is this price trustworthy enough to FEATURE (winner / top deals)?
    Once we have a few days of history, reject a price that sits far below the
    route's own recent typical UNLESS that low has shown up on >=2 recent
    snapshots (i.e. it's a real trend, not a lone phantom). Lenient until history
    matures so we never blank the page early on."""
    series = HIST_SERIES.get(code, [])
    if len(series) < 3:
        return True
    s = sorted(series)
    median = s[len(s) // 2]
    if not median or price >= 0.65 * median:
        return True
    near = sum(1 for v in series if v <= price * 1.20)
    return near >= 2


def price_range(code, price):
    """A believable recent range to show alongside a fare, e.g. ($340, $410).
    Uses the route's recent history (15th-85th percentile) + today's price."""
    series = sorted(list(HIST_SERIES.get(code, [])) + [price])
    if len(series) < 3:
        return None
    lo = series[int(len(series) * 0.15)]
    hi = series[min(len(series) - 1, int(len(series) * 0.85))]
    if hi <= lo * 1.05:
        return None
    return (lo, hi)


def sparkline_svg(series, w=84, h=22):
    if not series:
        return ""
    if len(series) < 2:
        return ('<svg class="spark" width="%d" height="%d" viewBox="0 0 %d %d" '
                'role="img" aria-label="Not enough price history yet">'
                '<circle cx="%d" cy="%d" r="2.5" fill="#888"/></svg>'
                % (w, h, w, h, w // 2, h // 2))
    lo, hi = min(series), max(series)
    rng = (hi - lo) or 1
    n = len(series)
    pts = []
    for i, v in enumerate(series):
        x = i * (w - 4) / (n - 1) + 2
        y = h - 2 - (v - lo) / rng * (h - 4)
        pts.append("%.1f,%.1f" % (x, y))
    falling = series[-1] <= series[0]
    color = "#27d07a" if falling else "#ff5e5e"
    label = ("Price trend over %d days: %s, from $%d to $%d, now $%d"
             % (n, "falling" if falling else "rising", lo, hi, series[-1]))
    return ('<svg class="spark" width="%d" height="%d" viewBox="0 0 %d %d" '
            'role="img" aria-label="%s">'
            '<polyline fill="none" stroke="%s" stroke-width="1.5" points="%s"/></svg>'
            % (w, h, w, h, html.escape(label, quote=True), color, " ".join(pts)))


_FLAG_NA_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
                'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/>'
                '<path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg>')

def _flag_cc(code):
    # Hand map first, then the comprehensive code_cc.json; flagcdn wants lowercase.
    return (CODE_COUNTRY.get(code) or CODE_CC_MAP.get(code) or "").lower()

def flag_img(code, cls="flag"):
    cc = _flag_cc(code)
    if cc:
        return f'<img class="{cls}" src="https://flagcdn.com/{cc}.svg" alt="" loading="lazy">'
    return f'<span class="{cls} flag-na" aria-hidden="true">{_FLAG_NA_SVG}</span>'


# Clean minimal line icons (outline, currentColor) — no emoji/clip-art.
ICONS = {
    "plane": '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/>',
    "hotel": '<rect x="4" y="3" width="16" height="18" rx="1.5"/><path d="M9.5 21v-4h5v4"/><path d="M8 7h1M11.5 7h1M15 7h1M8 11h1M11.5 11h1M15 11h1"/>',
    "esim": '<rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M10 18.5h4"/>',
    "insurance": '<path d="M12 3 5 6v5c0 4.6 7 8.5 7 8.5s7-3.9 7-8.5V6z"/><path d="m9 11.5 2 2 4-4"/>',
    "car": '<path d="M4 12l2-5.2A2 2 0 0 1 7.9 5.5h8.2A2 2 0 0 1 18 6.8L20 12"/><rect x="3" y="12" width="18" height="5" rx="1.2"/><circle cx="7.5" cy="18.5" r="1.4"/><circle cx="16.5" cy="18.5" r="1.4"/>',
    "van": '<rect x="2.5" y="6.5" width="12.5" height="9" rx="1.2"/><path d="M15 9.5h3.2l2.8 3v3H18"/><circle cx="6.5" cy="17" r="1.5"/><circle cx="17" cy="17" r="1.5"/>',
    "tours": '<path d="M12 21s-6.5-5.6-6.5-10.5a6.5 6.5 0 1 1 13 0C18.5 15.4 12 21 12 21z"/><circle cx="12" cy="10.5" r="2.3"/>',
    "chat": '<path d="M21 14.5a2 2 0 0 1-2 2H9l-4 4V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2z"/>',
}


def icon(name, cls="ic"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(name, "")}</svg>')


# --------------------------------------------------------------------------- #
# Data readers
# --------------------------------------------------------------------------- #
def read_snapshot():
    if not os.path.exists(SNAP):
        return []
    out = []
    with open(SNAP, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out.append({"code": r["code"], "name": r["name"], "origin": r["origin"],
                            "price": float(r["price"]), "benchmark": float(r["benchmark"]),
                            "airline": r.get("airline", ""), "depart": r.get("depart", ""),
                            "return": r.get("return", ""), "link": r.get("booking_link", "")})
            except (ValueError, KeyError):
                continue
    return out


def _latest(pattern):
    files = sorted(glob.glob(os.path.join(HERE, pattern)))
    return files[-1] if files else None


def read_oneway(limit=600, kind="6m"):
    path = _latest(f"explore_oneway_{kind}_*.csv")
    if not path:
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"price": float(r["price"]), "origin": r["origin"],
                             "code": r["destination_code"], "name": r["destination_name"],
                             "cc": r.get("country_code", ""), "depart": r["depart"],
                             "link": r["booking_link"]})
            except (ValueError, KeyError):
                continue
    rows.sort(key=lambda x: x["price"])
    return rows[:limit]


def read_lastminute(limit=40, kind="all"):
    path = _latest(f"lastminute_{kind}_*.csv")
    if not path:
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"price": float(r["price"]), "origin": r["origin"],
                             "code": r["destination_code"], "name": r["destination_name"],
                             "cc": r.get("country_code", ""), "depart": r["depart"],
                             "return": r["return"], "link": r["booking_link"]})
            except (ValueError, KeyError):
                continue
    rows.sort(key=lambda x: x["price"])
    return rows[:limit]


def read_history_series():
    """{code: [price oldest..newest]} from pricehistory.csv (one point per day)."""
    if not os.path.exists(HISTORY):
        return {}
    per_date = defaultdict(dict)  # date -> {code: price}
    with open(HISTORY, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                per_date[r["date"]][r["code"]] = float(r["price"])
            except (ValueError, KeyError):
                continue
    series = defaultdict(list)
    for d in sorted(per_date):
        for code, price in per_date[d].items():
            series[code].append(price)
    return series


def read_world(limit=30000, kind="any"):
    path = _latest(f"world_{kind}_*.csv")
    if not path:
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"o": r["origin"], "on": r["origin_name"], "c": r["destination_code"],
                             "n": r["destination_name"], "cc": r.get("country_code", ""),
                             "price": float(r["price"]), "depart": r["depart"], "link": r["booking_link"]})
            except (ValueError, KeyError):
                continue
    rows.sort(key=lambda x: x["price"])
    return rows[:limit]


def read_homebase():
    if not os.path.exists(HOMEBASE):
        return {}
    with open(HOMEBASE, encoding="utf-8") as f:
        return json.load(f)


def index_history():
    if not os.path.exists(HISTORY):
        return {}
    per_date = defaultdict(dict)
    with open(HISTORY, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                per_date[r["date"]][r["code"]] = float(r["price"])
            except (ValueError, KeyError):
                continue
    series = defaultdict(list)
    for d in sorted(per_date):
        codes = per_date[d]
        for reg, rcodes in REGIONS.items():
            vals = [codes[c] for c in rcodes if c in codes]
            if vals:
                series[reg].append((d, sum(vals) / len(vals)))
    return series


# --------------------------------------------------------------------------- #
# Section builders
# --------------------------------------------------------------------------- #
def ticker_rt(market):
    items = []
    for m in sorted(market, key=lambda x: signal_for(x["price"], x["benchmark"])[1], reverse=True):
        _, pct = signal_for(m["price"], m["benchmark"])
        arrow, cls = ("&#9660;", "down") if pct > 0 else ("&#9650;", "up")
        link = html.escape(m["link"], quote=True)
        items.append(f'<a class="ti-item" href="{link}" target="_blank" rel="noopener">'
                     f'{flag_img(m["code"], "ti-flag")}<span class="ti-code">{m["code"]}</span>'
                     f'<span class="ti-price">${m["price"]:,.0f}</span>'
                     f'<span class="{cls}">{arrow}{abs(pct):.0f}%</span></a>')
    row = "".join(items)
    return row + row


def region_buttons():
    out = []
    for r in REGION_BTNS:
        label = "All" if r == "all" else r
        active = " on" if r == "all" else ""
        out.append(f'<button class="regchip{active}" data-region="{r}" '
                   f'onclick="selRegion(\'{r}\')">{label}</button>')
    return "".join(out)


def ow_arr(rows):
    return [{"o": d["origin"], "c": d["code"], "n": d["name"], "p": round(d["price"]),
             "dep": d.get("depart", ""), "l": d["link"], "t": lm_tags(d["cc"])} for d in rows]


def world_arr(world):
    return [{"o": w["o"], "on": w["on"], "c": w["c"], "n": w["n"], "p": round(w["price"]),
             "dep": w["depart"], "l": w["link"], "t": lm_tags(w["cc"])} for w in world]


def lm_buttons():
    out = []
    for r in LM_BTNS:
        label = "All" if r == "all" else r
        active = " on" if r == "all" else ""
        out.append(f'<button class="airchip{active}" data-lmr="{r}" '
                   f'onclick="toggleLMR(\'{r}\')">{label}</button>')
    return "".join(out)


def lm_js(lm):
    arr = [{"o": d["origin"], "c": d["code"], "n": d["name"], "p": round(d["price"]),
            "dep": d["depart"], "ret": d["return"], "l": d["link"], "t": lm_tags(d["cc"])}
           for d in lm]
    return "var LM = " + json.dumps(arr) + ";"


def region_chip_bar(attr, toggle):
    out = []
    for r in LM_BTNS:
        label = "All" if r == "all" else r
        active = " on" if r == "all" else ""
        out.append(f'<button class="airchip{active}" {attr}="{r}" '
                   f'onclick="{toggle}(\'{r}\')">{label}</button>')
    return "".join(out)


def market_pulse(market):
    """Overall: are fares cheaper or pricier than normal right now?"""
    if not market:
        return "Tracking fares…"
    avg = sum(signal_for(m["price"], m["benchmark"])[1] for m in market) / len(market)
    if avg >= 3:
        return f"&#9660; Fares are running ~{avg:.0f}% BELOW normal across {len(market)} routes"
    if avg <= -3:
        return f"&#9650; Fares are running ~{abs(avg):.0f}% ABOVE normal across {len(market)} routes"
    return f"Fares are about normal right now across {len(market)} routes"


def widgets_html():
    cards = []
    for label, ic, url, blurb in AFFILIATE:
        live = url and url != "#"
        href = url if live else "essentials.html"
        tag = "" if live else '<span class="soon">soon</span>'
        cards.append(
            f'<a class="xcard" href="{href}"' + (' target="_blank" rel="noopener"' if live else '') +
            f'><span class="xi">{icon(ic)}</span><span>{label}</span>{tag}</a>')
    return "".join(cards)


def essentials_cards():
    out = []
    for label, ic, url, blurb in AFFILIATE:
        live = url and url != "#"
        if live:
            btn = f'<a class="book" href="{url}" target="_blank" rel="noopener">Search {label.lower()}</a>'
        else:
            btn = '<a class="book" style="background:#9aa0aa;cursor:default;pointer-events:none;">Coming soon</a>'
        out.append(f'<article class="card"><div class="card-top">{icon(ic, "ic-lg")}</div>'
                   f'<h3 class="dest">{label}</h3><p class="route">{html.escape(blurb)}</p>'
                   f'<div style="margin-top:auto;padding-top:14px">{btn}</div></article>')
    return "".join(out)


def market_summary(market):
    if not market:
        return "Tracking fares now - check back soon."
    reg_pct = {}
    for reg, codes in REGIONS.items():
        ps = [signal_for(m["price"], m["benchmark"])[1] for m in market if m["code"] in codes]
        if ps:
            reg_pct[reg] = sum(ps) / len(ps)
    lead = max(reg_pct, key=reg_pct.get) if reg_pct else "The market"
    top = max(market, key=lambda m: signal_for(m["price"], m["benchmark"])[1])
    _, toppct = signal_for(top["price"], top["benchmark"])
    nbook = sum(1 for m in market if signal_for(m["price"], m["benchmark"])[0] == "BOOK")
    lead_avg = sum(m["price"] for m in market if m["code"] in REGIONS.get(lead, [])) / \
        max(1, sum(1 for m in market if m["code"] in REGIONS.get(lead, [])))
    return (f"{lead} leads today, averaging ${lead_avg:,.0f} "
            f"(~{reg_pct.get(lead, 0):.0f}% below typical). Biggest mover: "
            f"{html.escape(top['name'])}, down {toppct:.0f}%. {nbook} routes flagging BOOK.")


def index_cards(market, hist):
    cards = []
    for reg, codes in REGIONS.items():
        prices = [m["price"] for m in market if m["code"] in codes]
        if not prices:
            continue
        avg = sum(prices) / len(prices)
        move = '<span class="idx-move new">today</span>'
        series = hist.get(reg, [])
        if len(series) >= 2:
            diff = avg - series[-2][1]
            if abs(diff) >= 1:
                ar, cl = ("&#9660;", "down") if diff < 0 else ("&#9650;", "up")
                move = f'<span class="idx-move {cl}">{ar}${abs(diff):,.0f} vs yest</span>'
            else:
                move = '<span class="idx-move flat">flat</span>'
        cards.append(f'<div class="idx"><p class="idx-name">{reg} index</p>'
                     f'<p class="idx-val">${avg:,.0f}</p>'
                     f'<p class="idx-sub">avg of {len(prices)} routes &middot; {move}</p></div>')
    return "".join(cards)


_MOVER_REGIONS = {
    "Asia": ["BKK","DPS","HKT","SGN","HAN","NRT","KIX","ICN","SIN","KUL","MNL","DEL","BOM","HKG","TPE","KTM","PEK","PVG","CAN","CTU","CGK","REP","PNH","CMB","MLE","BLR","MAA","FUK","CEB","KHH", "CTS", "OKA", "CNX", "DAD", "USM", "GOI", "COK", "PEN", "SUB"],
    "Middle East": ["DXB","DOH","IST","TLV","AUH","RUH","JED","AMM","BEY","MCT", "KWI", "BAH", "GYD", "TBS", "EVN"],
    "Europe": ["LHR","CDG","FCO","BCN","MAD","LIS","AMS","FRA","ATH","DUB","KEF","PRG","CPH","MUC","ZRH","VIE","BRU","MXP","VCE","NCE","EDI","MAN","GVA","OSL","ARN","HEL","WAW","BUD","KRK","OPO", "HAM", "DUS", "BER", "STR", "CGN", "SOF", "OTP", "BEG", "ZAG", "SPU", "DBV", "TLL", "RIX", "VNO", "BLQ", "FLR", "NAP", "CTA", "AGP", "SVQ", "VLC", "FAO", "LYS", "MRS", "GLA", "BHX"],
    "Americas": ["MEX","CUN","SJD","PTY","SJO","SJU","PUJ","NAS","BOG","LIM","GRU","EZE","SCL","GIG","UIO","CTG","MDE","GUA","MBJ","AUA","CUR","BGI","KIN","GCM","BZE","SDQ","STT","LIR", "YYZ", "YVR", "YUL", "YYC", "SAL", "TGU", "MGA", "GYE", "FOR", "REC", "SSA", "FLN", "SXM", "ANU", "UVF", "GND", "POS", "PLS", "FPO"],
    "Oceania": ["SYD","MEL","AKL","NAN","BNE","PER","CHC","PPT", "CNS", "ADL", "WLG", "ZQN"],
    "Africa": ["CAI","CMN","JNB","NBO","RAK","ACC","LOS","ADD","CPT","DKR", "TUN", "AGA", "HRG", "SSH", "MBA", "ZNZ", "JRO", "MRU"],
}
CODE_CONT = {c: r for r, cs in _MOVER_REGIONS.items() for c in cs}


def _loadj(fn):
    try:
        with open(os.path.join(HERE, fn), encoding="utf-8") as _f:
            return json.load(_f)
    except Exception:
        return {}


CONTINENT_CC = _loadj("continent_cc.json")
CODE_CC_MAP = _loadj("code_cc.json")


def continent_of(code):
    if code in CODE_CONT:
        return CODE_CONT[code]
    return CONTINENT_CC.get(CODE_CC_MAP.get(code, ""), "Other")


def movers_html(market, limit=14):
    rows = []
    ranked = sorted(market, key=lambda x: signal_for(x["price"], x["benchmark"])[1], reverse=True)
    sig_cls = {"BOOK": "s-book", "WATCH": "s-watch", "WAIT": "s-wait"}
    for m in ranked:
        sig, pct = signal_for(m["price"], m["benchmark"])
        link = html.escape(m["link"], quote=True)
        rows.append(
            f'<div class="mv-row" data-region="{continent_of(m["code"])}" data-lp data-o="{m["origin"]}" data-d="{m["code"]}" data-b="{m["benchmark"]}" data-ow="0"><button class="star" data-code="{m["code"]}" aria-label="watch">&#9734;</button>'
            f'<div class="mv-dest">{flag_img(m["code"])}<div><div class="mv-name">{html.escape(m["name"])}</div>'
            f'<div class="mv-air">{html.escape(airline_name(m["airline"]))} &middot; from {html.escape(m["origin"])}</div></div></div>'
            f'<div class="mv-right"><span class="mv-price">${m["price"]:,.0f}</span>'
            f'<span class="down">&#9660;{pct:.0f}%</span><span class="sig {sig_cls[sig]}">{sig}</span>'
            f'<a class="mini-book" href="{link}" target="_blank" rel="noopener">Book</a></div></div>')
    return "".join(rows)


def lastminute_html(rows, limit=40):
    out = []
    for o in rows[:limit]:
        link = html.escape(o["link"], quote=True)
        out.append(f'<div class="mv-row" data-lp data-o="{o["origin"]}" data-d="{o["code"]}" data-ow="0"><div class="mv-dest">{flag_img(o["code"])}'
                   f'<div><div class="mv-name">{html.escape(o["name"])}</div>'
                   f'<div class="mv-air">round-trip from {html.escape(o["origin"])} &middot; '
                   f'{html.escape(o["depart"])} &rarr; {html.escape(o["return"])}</div></div></div>'
                   f'<div class="mv-right"><span class="mv-price">${o["price"]:,.0f}</span>'
                   f'<a class="mini-book" href="{link}" target="_blank" rel="noopener">Book</a></div></div>')
    return "".join(out)


def oneway_html(rows, limit=12):
    out = []
    for o in rows[:limit]:
        link = html.escape(o["link"], quote=True)
        out.append(f'<div class="mv-row" data-lp data-o="{o["origin"]}" data-d="{o["code"]}" data-ow="1"><div class="mv-dest">{flag_img(o["code"])}'
                   f'<div><div class="mv-name">{html.escape(o["name"])}</div>'
                   f'<div class="mv-air">one-way from {html.escape(o["origin"])} &middot; {html.escape(o["depart"])}</div></div></div>'
                   f'<div class="mv-right"><span class="mv-price">${o["price"]:,.0f}</span>'
                   f'<a class="mini-book" href="{link}" target="_blank" rel="noopener">Book</a></div></div>')
    return "".join(out)


def airlines_chips(market):
    seen = []
    for m in market:
        if m["airline"] and m["airline"] not in seen:
            seen.append(m["airline"])
    return "".join(f'<button class="airchip" data-air="{a}" onclick="toggleAir(\'{a}\')">'
                   f'{html.escape(airline_name(a))}</button>' for a in seen)


def city_options(home):
    opts = ['<option value="">Choose your home airport…</option>']
    for code in sorted(home, key=lambda c: home[c]["name"]):
        opts.append(f'<option value="{code}">{html.escape(home[code]["name"])} ({code})</option>')
    return "".join(opts)


def card_html(m):
    code = m["code"]
    _, pct = signal_for(m["price"], m["benchmark"])
    flash = is_flash(code, m["price"], m["benchmark"])
    hlabel, hcls = hist_signal(code, m["price"], m["benchmark"])
    badge = ('<span class="badge flash">&#128293; FLASH</span>' if flash
             else (f'<span class="badge">Save {pct:.0f}%</span>' if pct > 0 else ""))
    dates = f'{html.escape(m.get("depart", ""))} &rarr; {html.escape(m.get("return", ""))}' if m.get("return") else html.escape(m.get("depart", ""))
    link = html.escape(m["link"], quote=True)
    spark = sparkline_svg(HIST_SERIES.get(code, []))
    hn = hotel_night(code)
    wk = week_cost(code, m["price"])
    fx = fx_line(code)
    info = DEST_INFO.get(code, {"lang": "—", "eng": "—", "visa": "Check requirements",
                                "safe": "Check advisories", "note": "Verify before booking"})
    back = (f'<p class="binfo"><b>Language:</b> {html.escape(info["lang"])}</p>'
            f'<p class="binfo"><b>English:</b> {html.escape(info["eng"])}</p>'
            f'<p class="binfo"><b>Visa (US passport):</b> {html.escape(info["visa"])}</p>'
            f'<p class="binfo"><b>Safety:</b> {html.escape(info["safe"])}</p>'
            f'<p class="binfo"><b>Good to know:</b> {html.escape(info["note"])}</p>')
    return f"""
      <div class="flip"><div class="flip-inner">
      <article class="card flip-front" data-lp data-b="{m['benchmark']}" data-o="{html.escape(m['origin'], quote=True)}" data-c="{code}" data-dep="{html.escape(m.get('depart', ''), quote=True)}" data-ret="{html.escape(m.get('return', ''), quote=True)}" data-ow="0">
        <div class="card-top">{flag_img(code)}
          <div class="card-top-right">{badge}
            <button class="star" data-code="{code}" aria-label="watch">&#9734;</button></div></div>
        <h3 class="dest">{html.escape(m["name"])}</h3>
        <p class="route">{html.escape(airline_name(m['airline']))} &middot; round-trip from {html.escape(m["origin"])}</p>
        <p class="dates">{dates}</p>
        <p class="dates">&#9728; Best time: {html.escape(BEST_TIME.get(code, "year-round"))}</p>
        <p class="price">${m['price']:,.0f} <span class="was" title="The Standard Meridian — this route's historical baseline fare">${m['benchmark']:,.0f}</span></p>
        <p style="font-size:11px;color:var(--muted);margin:-11px 0 8px;letter-spacing:.03em">&#9678; vs. the <b style="color:var(--gold);font-weight:600">Standard Meridian</b> &middot; historical baseline</p>
        <button class="live-btn" onclick="liveCard(this)">&#8635; check live price</button>
        <div class="cardmeta"><span class="sig {hcls}">{hlabel}</span>{spark}</div>
        <p class="trip">A week here &asymp; <b>${wk:,}</b> <span>(flight ${m['price']:,.0f} &middot; hotel ~${hn}/nt &times;7 &middot; eSIM ${ESIM_COST})</span></p>
        {fx}
        <a class="book" href="{link}" target="_blank" rel="noopener">See live price &rarr;</a>
        <button class="flipbtn" onclick="flipCard(this)">&#9432; Things to know &rarr;</button>
      </article>
      <article class="card flip-back">
        <h3 class="dest">{html.escape(m["name"])}</h3>
        <p class="binfo-h">&#127757; Things to know before you go</p>
        {back}
        <p class="finehint">General guidance for US travelers — verify official sources before booking.</p>
        <button class="flipbtn" onclick="flipCard(this)">&#8592; Back to the deal</button>
      </article>
      </div></div>"""


def market_js(market):
    arr = []
    for m in market:
        sig, pct = signal_for(m["price"], m["benchmark"])
        arr.append({"c": m["code"], "n": m["name"], "cc": CODE_COUNTRY.get(m["code"], ""),
                    "o": m["origin"], "p": round(m["price"]), "pct": round(pct),
                    "s": sig, "a": m["airline"], "an": airline_name(m["airline"]), "l": m["link"],
                    "dep": m.get("depart", ""), "ret": m.get("return", ""),
                    "wk": week_cost(m["code"], m["price"])})
    return "var MARKET = " + json.dumps(arr) + ";"


SIGNUP = """
<section class="signup" id="alerts">
  <div class="signup-inner">
    <h2>Never miss a deal</h2>
    <p>Get the best flight deals from the USA sent to your inbox. Free to join.</p>
    <form class="form" action="__FORM_ACTION__" method="POST" onsubmit="return fakeSubmit(event)">
      <input type="email" name="email" placeholder="you@email.com" required>
      <button type="submit">Get free alerts</button>
    </form>
    <div class="ok" id="ok">&#10003; You're on the list! Check your inbox to confirm.</div>
  </div>
</section>"""

CHAT_HTML = f"""
<button id="chatbtn" onclick="chatToggle()" aria-label="Ask {BRAND}">{icon('chat', 'chat-ic')}</button>
<div id="chatpanel">
  <div class="cp-head">Ask {BRAND}<span onclick="chatToggle()" style="cursor:pointer;float:right">&times;</span></div>
  <div class="cp-msgs" id="cpmsgs"></div>
  <div class="cp-in"><input id="cpinput" placeholder="e.g. cheapest one-way to Asia" onkeydown="if(event.key==='Enter')chatSend()"><button onclick="chatSend()">Send</button></div>
</div>"""

# Digital astrolabe — thin-line gold loader (rotating rete over a graduated ring).
ASTRO_SVG = (
    '<svg viewBox="0 0 100 100" fill="none" stroke="#e7b94e" stroke-width="1.4" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<circle cx="50" cy="50" r="47" stroke-opacity=".9"/>'
    '<circle cx="50" cy="50" r="43" stroke-width="1" stroke-opacity=".5"/>'
    '<path d="M44 6 h12 v4 a6 6 0 0 1 -12 0 z" stroke-width="1"/>'
    '<g class="a-slow">'
    '<circle cx="50" cy="50" r="39" stroke-width="1" stroke-dasharray="0.6 5.1" stroke-opacity=".85"/>'
    '<circle cx="50" cy="50" r="31" stroke-width="1" stroke-opacity=".35"/>'
    '</g>'
    '<g class="a-fast">'
    '<circle cx="58" cy="44" r="19" stroke-width="1.2" stroke-opacity=".9"/>'
    '<line x1="50" y1="50" x2="74" y2="30"/>'
    '<line x1="50" y1="50" x2="26" y2="70"/>'
    '<line x1="50" y1="50" x2="30" y2="34"/>'
    '<circle cx="74" cy="30" r="1.8" fill="#e7b94e" stroke="none"/>'
    '<circle cx="26" cy="70" r="1.8" fill="#e7b94e" stroke="none"/>'
    '<circle cx="30" cy="34" r="1.6" fill="#e7b94e" stroke="none"/>'
    '</g>'
    '<line x1="50" y1="3" x2="50" y2="97" stroke-width="1" stroke-opacity=".4"/>'
    '<line x1="3" y1="50" x2="97" y2="50" stroke-width="1" stroke-opacity=".4"/>'
    '<circle cx="50" cy="50" r="3.4" fill="#0a0e14"/>'
    '<circle cx="50" cy="50" r="2.2" fill="#e7b94e" stroke="none"/>'
    '</svg>'
)

LOGO_SVG = (
    '<svg viewBox="0 0 100 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<circle cx="50" cy="50" r="47" fill="none" stroke="#e7b94e" stroke-width="2"/>'
    '<circle cx="50" cy="50" r="39" fill="none" stroke="#e7b94e" stroke-width="1" opacity="0.4"/>'
    '<g stroke="#b8862f" stroke-width="1.4" opacity="0.7">'
    '<line x1="50" y1="50" x2="71" y2="29"/><line x1="50" y1="50" x2="71" y2="71"/>'
    '<line x1="50" y1="50" x2="29" y2="71"/><line x1="50" y1="50" x2="29" y2="29"/></g>'
    '<path d="M50 7 L42 42 L50 50 Z" fill="#f0c860"/><path d="M50 7 L58 42 L50 50 Z" fill="#c79a33"/>'
    '<path d="M93 50 L58 42 L50 50 Z" fill="#f0c860"/><path d="M93 50 L58 58 L50 50 Z" fill="#c79a33"/>'
    '<path d="M50 93 L58 58 L50 50 Z" fill="#f0c860"/><path d="M50 93 L42 58 L50 50 Z" fill="#c79a33"/>'
    '<path d="M7 50 L42 58 L50 50 Z" fill="#f0c860"/><path d="M7 50 L42 42 L50 50 Z" fill="#c79a33"/>'
    '<circle cx="50" cy="50" r="5.5" fill="#0a0e14"/><circle cx="50" cy="50" r="3" fill="#f0c860"/>'
    '</svg>'
)

CSS = r"""<style>
  :root{ --bg:#0a0e14; --card:#121821; --ink:#e9edf4; --muted:#94a0b3; --line:#222b38;
         --blue:#e7b94e; --blue-d:#d2a23a; --green:#27d07a; --green-bg:rgba(39,208,122,.14);
         --red:#ff5e5e; --amber:#e7b94e; --amber-bg:rgba(231,185,78,.14); --ink2:#070a10; --gold:#e7b94e; }
  *{ box-sizing:border-box; }
  body{ margin:0; background:var(--bg); color:var(--ink);
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; line-height:1.6; }
  a{ color:inherit; }
  .ticker{ overflow:hidden; background:var(--ink2); border-bottom:1px solid #1d2941; }
  .ticker.ow{ background:#0e1a2e; }
  .ticker-track{ display:inline-flex; white-space:nowrap; animation:scrollL 70s linear infinite; }
  .ticker.ow .ticker-track{ animation:scrollR 90s linear infinite; }
  .ticker:hover .ticker-track{ animation-play-state:paused; }
  .ti-item{ display:inline-flex; align-items:center; gap:7px; padding:8px 18px; text-decoration:none;
            font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13.5px; color:#cdd5e3; border-right:1px solid #1d2941; }
  .ti-item:hover{ background:#16223c; }
  .ti-flag{ width:18px; height:13px; object-fit:cover; border-radius:2px; }
  .ti-code{ color:#fff; font-weight:600; }  .ti-price{ color:#fff; }
  .down{ color:#36d36b; } .up{ color:#ff6b6b; } .ow{ color:#7fb0ff; }
  @keyframes scrollL{ from{ transform:translateX(0);} to{ transform:translateX(-50%);} }
  @keyframes scrollR{ from{ transform:translateX(-50%);} to{ transform:translateX(0);} }
  .regionbar{ background:#0e1a2e; border-bottom:1px solid #1d2941; padding:8px 14px; overflow-x:auto; white-space:nowrap; }
  .regchip{ background:transparent; border:1px solid #2a3a5a; color:#cdd5e3; font-size:12.5px;
            padding:5px 13px; border-radius:20px; cursor:pointer; margin-right:7px; }
  .regchip.on{ background:#fff; color:#0b1320; border-color:#fff; font-weight:600; }
  .topbar{ position:sticky; top:0; z-index:60; }
  .blog-wrap{ max-width:760px; }
  .blog-eyebrow{ color:var(--gold); font-size:12.5px; letter-spacing:.05em; text-transform:uppercase; margin-bottom:6px; }
  .blog-title{ font-size:40px; margin:0 0 16px; }
  .blog-deal{ display:flex; flex-wrap:wrap; gap:14px; justify-content:space-between; align-items:center; background:#0e141d; border:1px solid var(--line); border-radius:14px; padding:16px 18px; margin-bottom:22px; }
  .blog-deal-label{ font-weight:700; } .blog-deal-dates{ color:var(--muted); font-size:13px; }
  .blog-deal-right{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  .blog-price{ font-size:26px; font-weight:800; color:var(--gold); } .blog-was{ color:var(--muted); font-size:13px; }
  .blog-sec{ margin:0 0 22px; } .blog-sec h2{ font-size:21px; margin:0 0 8px; } .blog-sec p{ color:var(--ink); line-height:1.7; }
  .blog-list{ margin:0; padding-left:20px; line-height:1.9; } .blog-list li{ color:var(--ink); }
  .blog-sec a, .art-lede a{ color:var(--gold); }
  .crumbs{ font-size:12.5px; color:var(--muted); margin-bottom:10px; } .crumbs a{ color:var(--gold); text-decoration:none; }
  .art-meta{ font-size:12.5px; color:var(--muted); margin:-8px 0 18px; }
  .art-lede{ font-size:18px; line-height:1.75; color:var(--ink); margin:0 0 22px; }
  .art-cta{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:14px;
            background:#0e141d; border:1px solid var(--line); border-left:3px solid var(--gold);
            border-radius:12px; padding:16px 18px; margin:0 0 24px; }
  .art-cta-txt{ color:var(--ink); font-size:14.5px; max-width:62ch; }
  .art-q{ border-bottom:1px solid var(--line); padding:12px 0; }
  .art-q summary{ cursor:pointer; font-weight:600; color:var(--ink); list-style:none; }
  .art-q summary::-webkit-details-marker{ display:none; }
  .art-q summary::before{ content:"+"; color:var(--gold); margin-right:9px; font-weight:700; }
  .art-q[open] summary::before{ content:"\2013"; }
  .art-q p{ color:var(--ink); line-height:1.7; margin:10px 0 2px; }
  .guide-grid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; }
  .guide-card{ display:flex; flex-direction:column; gap:8px; background:var(--card); border:1px solid var(--line);
               border-radius:14px; padding:18px 18px 16px; text-decoration:none; transition:border-color .15s,transform .15s; }
  .guide-card:hover{ border-color:var(--gold); transform:translateY(-2px); }
  .gc-kick{ font-size:11.5px; letter-spacing:.05em; text-transform:uppercase; color:var(--gold); }
  .gc-title{ font-size:18px; font-weight:700; color:var(--ink); line-height:1.3; }
  .gc-desc{ font-size:13.5px; color:var(--muted); line-height:1.55; flex:1; }
  .gc-more{ font-size:13px; color:var(--gold); font-weight:600; }
  .blog-lang{ font-size:13.5px; color:var(--muted); margin-top:8px; }
  .blog-video{ display:flex; align-items:center; gap:14px; background:linear-gradient(135deg,#1a2330,#0e141d); border:1px solid var(--line); border-radius:12px; padding:18px 20px; text-decoration:none; color:var(--ink); transition:border-color .15s; }
  .blog-video:hover{ border-color:var(--gold); }
  .bv-play{ display:inline-flex; align-items:center; justify-content:center; width:46px; height:46px; border-radius:50%; background:var(--gold); color:#0b1118; font-size:18px; flex:0 0 auto; }
  .bv-text{ font-size:15px; }
  .blog-soon{ display:flex; align-items:center; gap:10px; background:#0e141d; border:1px dashed var(--line); border-radius:12px; padding:18px 20px; color:var(--muted); font-size:14px; }
  .blog-embed{ position:relative; padding-bottom:56.25%; height:0; border-radius:12px; overflow:hidden; border:1px solid var(--line); }
  .blog-embed iframe{ position:absolute; top:0; left:0; width:100%; height:100%; }
  .yt-sub{ display:inline-flex; align-items:center; gap:7px; margin-top:12px; background:#ff0000; color:#fff; border-radius:9px; padding:9px 16px; text-decoration:none; font-weight:600; font-size:14px; }
  .yt-sub:hover{ filter:brightness(1.08); }
  .blog-spark{ background:#0e141d; border:1px solid var(--line); border-radius:12px; padding:14px 16px; margin-bottom:10px; }
  .blog-spark svg{ width:100%; height:auto; }
    .blog-cta{ display:flex; gap:12px; flex-wrap:wrap; justify-content:center; margin-top:8px; }
  .mv-more{ display:block; margin:10px auto 2px; background:#0e141d; color:var(--gold); border:1px solid var(--line); border-radius:9px; padding:9px 18px; font-size:13px; cursor:pointer; }
  .mv-more:hover{ border-color:var(--gold); }
  .mv-head{ display:flex; align-items:center; gap:16px; margin:2px 8px 8px; }
  .mv-sortbtn{ background:none; border:0; color:var(--muted); cursor:pointer; font-size:12.5px; display:inline-flex; align-items:center; gap:5px; padding:2px 0; }
  .mv-sortbtn:hover{ color:var(--ink); }
  .mv-sortbtn.on{ color:var(--gold); font-weight:600; }
  .mv-ar{ font-size:10px; }
  .lp-dot{ display:inline-block; width:7px; height:7px; border-radius:50%; background:#27d07a; margin-right:6px; vertical-align:middle; animation:lppulse 1.8s infinite; }
  @keyframes lppulse{ 0%{box-shadow:0 0 0 0 rgba(39,208,122,.5)} 70%{box-shadow:0 0 0 6px rgba(39,208,122,0)} 100%{box-shadow:0 0 0 0 rgba(39,208,122,0)} }
  .ticker-toggle{ background:#0e141d; color:var(--gold); border:1px solid var(--line); border-radius:8px; padding:6px 9px; font-size:12px; cursor:pointer; display:inline-flex; align-items:center; gap:5px; line-height:1; }
  .ticker-toggle:hover{ border-color:var(--gold); }
  body.tickers-off .topbar .ticker, body.tickers-off .topbar .regionbar{ display:none !important; }
  header{ background:rgba(255,255,255,.96); backdrop-filter:blur(8px);
          border-bottom:1px solid var(--line); }
  .bar{ max-width:1080px; margin:0 auto; padding:13px 20px; display:flex; align-items:center; justify-content:space-between; gap:12px; }
  .logo{ display:flex; align-items:center; gap:9px; font-weight:700; font-size:19px; text-decoration:none; }
  .logo .mark{ width:34px; height:34px; display:flex; align-items:center; justify-content:center; }
  .logo .mark svg{ width:34px; height:34px; display:block; }
  .nav{ display:flex; align-items:center; gap:15px; flex-wrap:wrap; }
  .nav a.link{ font-size:14px; color:var(--muted); text-decoration:none; }
  .nav a.link.active{ color:var(--ink); font-weight:500; }
  .nav-cta{ background:var(--blue); color:#fff; text-decoration:none; padding:9px 16px; border-radius:8px; font-weight:600; font-size:14px; }
  .wrap{ max-width:1080px; margin:0 auto; padding:0 20px; }
  .hero{ text-align:center; padding:30px 20px 4px; }
  .hero h1{ font-size:29px; line-height:1.2; margin:0 0 8px; }
  .hero p{ font-size:16px; color:var(--muted); margin:0 auto; max-width:600px; }
  .summary{ max-width:920px; margin:14px auto 0; background:var(--card); border:1px solid var(--line);
            border-left:4px solid var(--blue); border-radius:0 10px 10px 0; padding:11px 16px; font-size:14.5px; text-align:left; }
  .updated{ font-size:13px; color:var(--muted); margin-top:12px; text-align:center; }
  .cust-btn{ margin-top:12px; background:transparent; border:1px solid var(--line); color:var(--muted); padding:7px 14px; border-radius:8px; cursor:pointer; font-size:13px; }
  .customizer{ max-width:540px; margin:14px auto 0; background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 18px; text-align:left; }
  .customizer p{ margin:0 0 10px; font-size:13px; color:var(--muted); }
  .customizer label{ display:inline-flex; align-items:center; gap:7px; font-size:14px; margin:4px 16px 4px 0; cursor:pointer; }
  .pagehead{ padding:26px 0 2px; } .pagehead h1{ font-size:26px; margin:0 0 4px; } .pagehead p{ margin:0; color:var(--muted); }
  .sec-head{ display:flex; align-items:baseline; justify-content:space-between; margin:26px 0 12px; gap:10px; flex-wrap:wrap; }
  .sec-head h2{ font-size:20px; margin:0; } .sec-head span{ font-size:13px; color:var(--muted); }
  .indices{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; }
  .idx{ background:var(--ink2); border-radius:12px; padding:14px 16px; color:#fff; }
  .idx-name{ margin:0; font-size:13px; color:#9fb0cc; } .idx-val{ margin:4px 0 0; font-size:24px; font-weight:700; }
  .idx-sub{ margin:2px 0 0; font-size:12px; color:#7e90ad; }
  .idx-move.down{ color:#36d36b; } .idx-move.up{ color:#ff6b6b; } .idx-move.new,.idx-move.flat{ color:#7e90ad; }
  .panel{ background:var(--card); border:1px solid var(--line); border-radius:14px; overflow:hidden; }
  .mv-row{ display:flex; align-items:center; gap:10px; padding:11px 16px; border-top:1px solid var(--line); }
  .mv-row:first-child{ border-top:0; }
  .mv-dest{ display:flex; align-items:center; gap:11px; min-width:0; flex:1; }
  .mv-name{ font-size:15px; } .mv-air{ font-size:12px; color:var(--muted); }
  .mv-right{ display:flex; align-items:center; gap:13px; }
  .mv-price{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:15px; }
  .flag{ width:30px; height:21px; object-fit:cover; border-radius:3px; border:1px solid var(--line); }
  .flag-na{ display:inline-flex; align-items:center; justify-content:center; color:var(--muted); background:#0e141d; }
  .flag-na svg{ width:62%; height:62%; }
  .emoji{ font-size:24px; }
  .sig{ font-size:12px; font-weight:700; padding:3px 10px; border-radius:7px; }
  .s-book{ background:var(--green-bg); color:var(--green); } .s-watch{ background:var(--amber-bg); color:var(--amber); }
  .s-wait{ background:#eef0f3; color:var(--muted); }
  .star{ background:none; border:0; cursor:pointer; font-size:19px; color:#b9bec7; line-height:1; padding:0; }
  .star.on{ color:var(--gold); }
  .mini-book{ background:var(--blue); color:#fff; text-decoration:none; font-size:13px; font-weight:600; padding:6px 13px; border-radius:7px; }
  .mini-book:hover{ background:var(--blue-d); }
  .citybar{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
  .citybar select{ padding:10px 12px; border:1px solid var(--line); border-radius:9px; font-size:14px; min-width:240px; }
  .citybar button{ background:var(--blue); color:#fff; border:0; padding:10px 16px; border-radius:9px; font-weight:600; cursor:pointer; }
  .citychips{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
  .citychip{ background:var(--ink2); color:#fff; font-size:13px; padding:6px 12px; border-radius:20px; display:inline-flex; gap:8px; align-items:center; }
  .citychip b{ cursor:pointer; color:#9fb0cc; }
  .airchips{ display:flex; flex-wrap:wrap; gap:8px; }
  .airchip{ background:var(--card); border:1px solid var(--line); color:var(--ink); font-size:13px; padding:6px 13px; border-radius:20px; cursor:pointer; }
  .airchip.on{ background:var(--ink2); color:#fff; border-color:var(--ink2); }
  .my-line{ font-size:14px; color:var(--muted); margin:10px 0 0; }
  .wl-hint{ color:var(--muted); font-size:14px; padding:16px; text-align:center; }
  .grouphdr{ font-size:13px; font-weight:600; color:var(--muted); padding:10px 16px 4px; }
  .two-col{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  @media(max-width:760px){ .two-col{ grid-template-columns:1fr; } }
  .grid{ display:grid; grid-template-columns:repeat(auto-fill,minmax(244px,1fr)); gap:16px; }
  .flip{ perspective:1200px; }
  .flip-inner{ position:relative; transition:transform .55s; transform-style:preserve-3d; height:100%; }
  .flip.flipped .flip-inner{ transform:rotateY(180deg); }
  .flip-front{ -webkit-backface-visibility:hidden; backface-visibility:hidden; }
  .flip-back{ position:absolute; inset:0; transform:rotateY(180deg); -webkit-backface-visibility:hidden; backface-visibility:hidden; }
  .flipbtn{ margin-top:12px; background:none; border:0; color:var(--muted); font-size:12.5px; cursor:pointer; width:100%; text-align:center; }
  .flipbtn:hover{ color:var(--blue); }
  .binfo-h{ font-weight:600; font-size:14px; margin:8px 0 10px; }
  .binfo{ font-size:13px; margin:5px 0; line-height:1.5; } .binfo b{ font-weight:600; }
  .finehint{ font-size:11px; color:var(--muted); margin:12px 0 0; }
  .card{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px; display:flex; flex-direction:column; }
  .card-top{ display:flex; align-items:center; justify-content:space-between; min-height:34px; }
  .card-top-right{ display:flex; align-items:center; gap:8px; }
  .badge{ background:var(--green-bg); color:var(--green); font-weight:600; font-size:12px; padding:4px 10px; border-radius:20px; }
  .badge.flash{ background:#fdecec; color:#c0392b; }
  .cardmeta{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin:0 0 10px; }
  .spark{ vertical-align:middle; }
  .trip{ font-size:12.5px; color:var(--muted); margin:0 0 12px; } .trip b{ color:var(--ink); font-weight:600; }
  .dest{ font-size:19px; margin:12px 0 2px; } .route{ color:var(--muted); font-size:13.5px; margin:0; }
  .dates{ color:var(--muted); font-size:13px; margin:2px 0 0; }
  .price{ font-size:27px; font-weight:700; margin:14px 0 16px; }
  .price .was{ font-size:15px; font-weight:400; color:var(--muted); text-decoration:line-through; margin-left:6px; }
  .book{ margin-top:auto; text-align:center; background:var(--blue); color:#fff; text-decoration:none; padding:12px; border-radius:9px; font-weight:600; }
  .book:hover{ background:var(--blue-d); }
  .signup{ max-width:680px; margin:34px auto 0; }
  .signup-inner{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:30px 26px; text-align:center; }
  .signup h2{ margin:0 0 8px; font-size:23px; } .signup p{ color:var(--muted); margin:0 auto 18px; max-width:460px; }
  .form{ display:flex; gap:10px; max-width:440px; margin:0 auto; flex-wrap:wrap; }
  .form input{ flex:1; min-width:200px; padding:13px 14px; border:1px solid var(--line); border-radius:9px; font-size:15px; }
  .form button{ background:var(--blue); color:#fff; border:0; padding:13px 22px; border-radius:9px; font-weight:600; font-size:15px; cursor:pointer; }
  .ok{ color:var(--green); font-weight:600; margin-top:14px; display:none; }
  footer{ max-width:1080px; margin:34px auto 0; padding:24px 20px 50px; color:var(--muted); font-size:13px; text-align:center; border-top:1px solid var(--line); }
  @media(max-width:540px){ .hero h1{ font-size:24px; } }
  .xcards{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; }
  .xcard{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; text-decoration:none; color:var(--ink); display:flex; flex-direction:column; align-items:center; gap:6px; text-align:center; position:relative; }
  .xcard:hover{ border-color:var(--blue); }
  .xcard .xi{ display:flex; } .xcard span{ font-size:14px; }
  .ic{ width:22px; height:22px; } .ic-lg{ width:30px; height:30px; color:var(--blue); }
  .xcard .xi .ic{ width:26px; height:26px; color:var(--blue); }
  .logo .mark .logo-ic{ width:18px; height:18px; }
  #chatbtn .chat-ic{ width:24px; height:24px; }
  .xcard .soon{ position:absolute; top:8px; right:8px; font-size:10px; color:var(--muted); background:var(--bg); padding:2px 6px; border-radius:10px; }
  #chatbtn{ position:fixed; bottom:20px; right:20px; width:56px; height:56px; border-radius:50%; background:var(--blue); color:#fff; border:0; font-size:24px; cursor:pointer; box-shadow:0 4px 14px rgba(0,0,0,.25); z-index:50; }
  #chatpanel{ position:fixed; bottom:86px; right:20px; width:340px; max-width:92vw; height:460px; max-height:70vh; background:var(--card); border:1px solid var(--line); border-radius:14px; display:none; flex-direction:column; overflow:hidden; box-shadow:0 8px 30px rgba(0,0,0,.2); z-index:50; }
  #chatpanel.open{ display:flex; }
  .cp-head{ background:var(--ink2); color:#fff; padding:12px 14px; font-weight:600; }
  .cp-msgs{ flex:1; overflow-y:auto; padding:12px; font-size:14px; }
  .cp-msg{ margin:0 0 10px; } .cp-msg.you{ text-align:right; }
  .cp-msg .bub{ display:inline-block; padding:8px 11px; border-radius:10px; background:var(--bg); max-width:88%; text-align:left; }
  .cp-msg.you .bub{ background:var(--blue); color:#fff; }
  .cp-msg .bub a{ color:var(--blue); } .cp-msg.you .bub a{ color:#fff; }
  .cp-in{ display:flex; gap:6px; padding:10px; border-top:1px solid var(--line); }
  .cp-in input{ flex:1; padding:9px 10px; border:1px solid var(--line); border-radius:8px; font-size:14px; }
  .cp-in button{ background:var(--blue); color:#fff; border:0; padding:9px 14px; border-radius:8px; cursor:pointer; }

  /* ====================  Dark charcoal + compass gold  ==================== */
  header{ background:rgba(10,14,20,.92); backdrop-filter:blur(8px); border-bottom:1px solid var(--line); }
  .logo .mark{ background:none; }
  .nav a.link.active{ color:var(--gold); }
  /* dark text on gold buttons */
  .nav-cta, .book, .mini-book, .form button, .citybar button, .cp-in button{ color:var(--ink2); font-weight:700; }
  .nav-cta:hover{ filter:brightness(1.07); }
  #chatbtn{ color:var(--ink2); box-shadow:0 6px 20px rgba(0,0,0,.55); }
  .cp-msg.you .bub, .cp-msg.you .bub a{ color:var(--ink2); }
  .regchip.on{ background:var(--gold); color:var(--ink2); border-color:var(--gold); }
  .ticker, .ticker.ow, .regionbar{ background:var(--ink2); border-bottom:1px solid var(--line); }
  .ti-item{ color:#aeb9c9; border-right:1px solid var(--line); }
  .ti-item:hover{ background:#10161f; }
  .regchip{ border-color:#2a3442; color:#aeb9c9; }
  .idx{ background:#0c121b; border:1px solid var(--line); }
  .badge.flash{ background:rgba(255,94,94,.15); color:#ff7a7a; }
  .s-wait{ background:rgba(148,160,179,.13); color:var(--muted); }
  .airchip.on{ background:var(--gold); color:var(--ink2); border-color:var(--gold); font-weight:600; }
  .citychip{ background:var(--gold); color:var(--ink2); } .citychip b{ color:var(--ink2); }
  .summary{ background:var(--card); border-color:var(--line); border-left:4px solid var(--gold); }
  input, select, textarea{ background:#0e141d; color:var(--ink); border-color:var(--line); }
  .citybar select, .form input, .cp-in input{ background:#0e141d; color:var(--ink); }
  ::placeholder{ color:#5f6b7d; }
  .star{ color:#46505f; }
  .cust-btn{ color:var(--muted); }
  .cp-msg .bub{ background:#0e141d; }

  /* ====================  Fleet Tracker label  ==================== */
  .ticker{ display:flex; align-items:stretch; }
  .ticker{ position:relative; }
  .ticker .ticker-track{ flex:1 1 auto; min-width:0; position:relative; z-index:1; }
  .ti-label{ flex:0 0 auto; position:relative; z-index:3; display:inline-flex; align-items:center; gap:6px; padding:8px 14px;
             background:var(--gold); color:var(--ink2); font-family:ui-monospace,Menlo,Consolas,monospace;
             font-size:11.5px; font-weight:700; letter-spacing:.10em; text-transform:uppercase; white-space:nowrap; }
  .ticker.ow .ti-label{ background:transparent; color:var(--gold); border-right:1px solid var(--line); }

  /* ====================  Historical context banners  ==================== */
  .context-banner{ display:flex; gap:10px; align-items:flex-start; margin:0 0 14px;
                   background:linear-gradient(90deg, rgba(231,185,78,.09), rgba(231,185,78,0));
                   border-left:2px solid var(--gold); border-radius:0 8px 8px 0; padding:10px 15px; }
  .context-banner .cb-ic{ flex:0 0 auto; width:16px; height:16px; color:var(--gold); margin-top:2px; }
  .context-banner p{ margin:0; font-size:12.5px; line-height:1.55; color:var(--muted); font-style:italic; }
  .context-banner .cb-em{ color:var(--ink); font-style:normal; }

  /* ====================  Digital astrolabe loader  ==================== */
  .astro{ display:inline-block; line-height:0; }
  .astro.lg{ width:84px; } .astro.sm{ width:22px; }
  .astro svg{ width:100%; height:auto; display:block; overflow:visible; }
  .astro .a-slow{ transform-origin:50px 50px; animation:astroSpin 9s linear infinite; }
  .astro .a-fast{ transform-origin:50px 50px; animation:astroSpinR 5.5s linear infinite; }
  @keyframes astroSpin{ to{ transform:rotate(360deg); } }
  @keyframes astroSpinR{ to{ transform:rotate(-360deg); } }
  @media(prefers-reduced-motion:reduce){ .astro .a-slow, .astro .a-fast{ animation:none; } }
  .bub.think{ padding:6px 10px; }
  #astro-splash{ position:fixed; inset:0; z-index:200; background:var(--bg);
                 display:flex; align-items:center; justify-content:center;
                 transition:opacity .6s ease; }
  #astro-splash.hide{ opacity:0; pointer-events:none; }
  .intro-stage{ width:min(760px,90vw); }
  .intro-svg{ width:100%; height:auto; display:block; overflow:visible; }
  .intro-grid line{ stroke:#16202c; stroke-width:1; }
  .intro-arc{ fill:none; stroke:var(--gold); stroke-width:4; stroke-linecap:round;
              stroke-dasharray:1300; stroke-dashoffset:1300;
              animation:mfArc 2.2s cubic-bezier(.45,0,.25,1) .25s forwards; }
  .intro-dot-a{ fill:var(--ink); opacity:0; animation:mfFade .4s ease .15s forwards; }
  .intro-dot-b{ fill:none; stroke:var(--gold); stroke-width:4; opacity:0;
                animation:mfFade .5s ease 2.15s forwards; }
  .intro-plane{ opacity:0; animation:mfFade .3s ease .25s forwards; }
  .intro-plane path{ fill:var(--gold); }
  .intro-ttl{ font:800 96px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
              fill:var(--ink); opacity:0; animation:mfFade .7s ease .9s forwards; }
  .intro-sub{ font:600 40px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
              fill:var(--gold); opacity:0; animation:mfFade .7s ease 1.25s forwards; }
  .intro-url{ font:500 30px ui-monospace,Menlo,Consolas,monospace;
              fill:var(--muted); opacity:0; animation:mfFade .6s ease 1.9s forwards; }
  @keyframes mfArc{ to{ stroke-dashoffset:0; } }
  @keyframes mfFade{ from{ opacity:0; } to{ opacity:1; } }
  @media(prefers-reduced-motion:reduce){
    .intro-arc{ animation:none; stroke-dashoffset:0; }
    .intro-plane,.intro-ttl,.intro-sub,.intro-url,.intro-dot-a,.intro-dot-b{
      animation:none; opacity:1; }
  }

  /* ====================  Landing hero  ==================== */
  .lander{ position:relative; overflow:hidden; text-align:center; padding:62px 20px 26px; }
  .lander-glow{ position:absolute; top:-170px; left:50%; transform:translateX(-50%); width:820px; height:440px;
                background:radial-gradient(ellipse at center, rgba(231,185,78,.15), rgba(231,185,78,0) 70%);
                pointer-events:none; z-index:0; }
  .lander-inner{ position:relative; z-index:1; max-width:780px; margin:0 auto; }
  .eyebrow{ display:inline-block; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11px;
            letter-spacing:.22em; text-transform:uppercase; color:var(--gold);
            border:1px solid rgba(231,185,78,.4); border-radius:30px; padding:7px 15px; margin-bottom:20px; }
  .lander h1{ font-size:47px; line-height:1.07; margin:0 0 16px; letter-spacing:-.015em; }
  .lander h1 .g{ color:var(--gold); }
  .lander .lead{ font-size:17.5px; color:var(--muted); max-width:630px; margin:0 auto 26px; line-height:1.6; }
  .lander .lead .buy{ color:var(--green); font-weight:700; }
  .cta-row{ display:flex; gap:12px; justify-content:center; flex-wrap:wrap; }
  .btn-primary{ background:var(--gold); color:var(--ink2); font-weight:700; text-decoration:none;
                padding:13px 26px; border-radius:10px; font-size:15px; }
  .btn-primary:hover{ filter:brightness(1.07); }
  .btn-ghost{ background:#161d28; color:var(--ink); border:1px solid #2c3744; text-decoration:none;
              padding:13px 24px; border-radius:10px; font-size:15px; font-weight:600; }
  .btn-ghost:hover{ border-color:var(--gold); color:var(--gold); background:#1b2330; }
  .trust{ margin:24px 0 0; font-size:12.5px; color:var(--muted); letter-spacing:.02em; }
  .trust b{ color:var(--ink); }
  .statbar{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:24px 0 4px; }
  .stat{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; text-align:center; }
  .stat .n{ font-size:26px; font-weight:700; color:var(--gold); font-family:ui-monospace,Menlo,Consolas,monospace; }
  .stat .l{ font-size:12px; color:var(--muted); margin-top:3px; }
  .winner{ display:flex; flex-wrap:wrap; align-items:center; gap:14px 22px; margin:20px 0 4px; padding:20px 24px 18px; border-radius:18px; text-decoration:none; color:var(--ink);
    background:linear-gradient(120deg,#1d1708 0%,#0e141d 58%); border:1px solid rgba(212,175,90,.45); position:relative; overflow:hidden; transition:border-color .15s, transform .15s; }
  .winner:hover{ border-color:var(--gold); transform:translateY(-2px); }
  .winner-badge{ position:absolute; top:0; left:0; background:var(--gold); color:#1a1205; font-size:11px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; padding:5px 12px; border-bottom-right-radius:12px; }
  .winner-main{ flex:1 1 240px; min-width:190px; padding-top:12px; }
  .winner-city{ font-size:27px; font-weight:800; line-height:1.15; }
  .winner-route{ color:var(--muted); font-size:13.5px; margin-top:4px; }
  .winner-right{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; padding-top:12px; }
  .winner-price{ font-size:30px; font-weight:800; color:var(--gold); }
  .winner-was{ color:var(--muted); font-size:13px; text-decoration:line-through; }
  .winner-off{ background:rgba(78,208,138,.15); color:#4ed08a; font-weight:700; font-size:12.5px; padding:4px 10px; border-radius:999px; }
  .winner-cta{ flex:0 0 auto; color:var(--gold); font-weight:700; font-size:14px; padding-top:12px; }
  @media(max-width:560px){ .winner-city{ font-size:22px; } .winner-price{ font-size:25px; } }
  .why{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin:32px 0 6px; }
  .why-card{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:22px; }
  .why-card .wi{ width:30px; height:30px; color:var(--gold); margin-bottom:12px; }
  .why-card h3{ margin:0 0 7px; font-size:17px; }
  .why-card p{ margin:0; font-size:13.5px; color:var(--muted); line-height:1.6; }
  @media(max-width:760px){ .why{ grid-template-columns:1fr; } }
  @media(max-width:680px){ .statbar{ grid-template-columns:repeat(2,1fr); } .lander h1{ font-size:33px; } .lander{ padding-top:44px; } }

  /* ====================  Promise strip  ==================== */
  .promise{ margin:46px 0 6px; border:1px solid var(--line); border-radius:16px; padding:26px 24px;
            background:linear-gradient(180deg, rgba(231,185,78,.05), rgba(231,185,78,0)); }
  .promise h2{ text-align:center; margin:0 0 18px; font-size:21px; }
  .promise-grid{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; }
  @media(max-width:760px){ .promise-grid{ grid-template-columns:1fr 1fr; } }
  @media(max-width:480px){ .promise-grid{ grid-template-columns:1fr; } }
  .pr{ display:flex; gap:11px; align-items:flex-start; }
  .pr-n{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13px; font-weight:700; color:var(--gold);
         border:1px solid rgba(231,185,78,.4); border-radius:7px; padding:3px 7px; flex:0 0 auto; }
  .pr p{ margin:0; font-size:13.5px; color:var(--muted); line-height:1.5; } .pr p b{ color:var(--ink); }

  /* ====================  Mercator heatmap  ==================== */
  .worldmap-wrap{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:12px 12px 6px; margin:4px 0 16px; }
  .wm-head{ display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; padding:2px 4px 9px; }
  .wm-title{ font-weight:700; font-size:14px; color:var(--ink); }
  .wm-leg{ font-size:11.5px; color:var(--muted); display:inline-flex; align-items:center; gap:7px; }
  .lg-glow{ width:20px; height:0; border-top:2px solid var(--green); box-shadow:0 0 6px var(--green); display:inline-block; }
  .worldmap{ width:100%; height:auto; display:block; border-radius:10px; background:#0a0e14; }
  .ml-grat line{ stroke:#e7b94e; stroke-width:0.5; opacity:0.13; stroke-dasharray:1 5; }
  .ml-rhumb line{ stroke:#e7b94e; stroke-width:0.4; opacity:0.14; }
  .ml-rhumb circle{ stroke:#e7b94e; opacity:0.4; }
  .ml-lab{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11px; letter-spacing:2px; fill:#e7b94e; opacity:0.26; }
  #mapRoutes path{ stroke:#566273; stroke-width:0.7; opacity:0.5; cursor:pointer; }
  #mapRoutes path:hover{ stroke:#9aa6b6; opacity:0.9; }
  #mapGlow path{ stroke:#27d07a; stroke-width:1.5; opacity:0.95; cursor:pointer; }
  #mapGlow path:hover{ stroke:#5fffa6; }
  #mapDots circle{ fill:#f0c860; }
  .wm-hint{ font-size:11.5px; color:var(--muted); text-align:center; padding:7px 0 2px; }

  /* ====================  Trip Lab + live prices  ==================== */
  .tl-card{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px 18px; margin:0 0 18px; }
  .tl-card h2{ margin:0 0 4px; font-size:19px; }
  .tl-sub{ margin:0 0 14px; color:var(--muted); font-size:13.5px; line-height:1.55; }
  .tl-form{ display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; margin-bottom:14px; }
  .tl-form label{ display:flex; flex-direction:column; gap:5px; font-size:12px; color:var(--muted); }
  .tl-form input, .tl-form select{ background:#0e141d; color:var(--ink); border:1px solid var(--line); border-radius:9px; padding:10px 12px; font-size:14px; min-width:120px; }
  .tl-form input[maxlength="3"]{ text-transform:uppercase; letter-spacing:.08em; }
  .tl-form .tl-go{ border:0; cursor:pointer; }
  .tl-load{ text-align:center; padding:26px 10px; color:var(--muted); } .tl-load p{ margin:8px 0 0; font-size:13px; }
  .hop-leg{ border-top:1px solid var(--line); } .hop-leg:first-child{ border-top:0; }
  .hop-tag{ font-size:11.5px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--gold); padding:13px 16px 2px; }
  .live-btn{ background:none; border:1px solid var(--line); color:var(--muted); font-size:11px; padding:3px 9px; border-radius:7px; cursor:pointer; margin:0 0 10px; }
  .live-btn:hover{ border-color:var(--gold); color:var(--gold); }
  .live-ok{ font-size:11px; color:var(--green); font-weight:700; margin:0 0 10px; display:inline-block; }
  .live-up{ font-size:11px; color:var(--red); font-weight:700; margin:0 0 10px; display:inline-block; }
</style>"""

SCRIPT = r"""<script>
var ASTRO='__ASTRO__';
var ACO = __ACOJS__;
__MARKETJS__
__ONEWAYJS__
__LMJS__
__WORLDJS__
var HOME = __HOMEJS__;
var WD = JSON.parse(localStorage.getItem('fs_watch_dest') || '[]');
var WA = JSON.parse(localStorage.getItem('fs_watch_air') || '[]');
var WC = JSON.parse(localStorage.getItem('fs_home') || '[]');
var WF = JSON.parse(localStorage.getItem('fs_watch_flights') || '[]');
function save(){ localStorage.setItem('fs_watch_dest', JSON.stringify(WD));
  localStorage.setItem('fs_watch_air', JSON.stringify(WA));
  localStorage.setItem('fs_home', JSON.stringify(WC));
  localStorage.setItem('fs_watch_flights', JSON.stringify(WF)); }
function sigClass(s){ return s==='BOOK'?'s-book':(s==='WATCH'?'s-watch':'s-wait'); }
function flag(cc){ return cc ? '<img class="flag" src="https://flagcdn.com/'+String(cc).toLowerCase()+'.svg" alt="">' : '<span class="flag flag-na" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg></span>'; }
function owItem(x){ return '<a class="ti-item" href="'+x.l+'" target="_blank" rel="noopener">'
  + '<span class="ti-code">'+x.o+'&rarr;'+x.c+'</span><span class="ti-price">$'+x.p.toLocaleString()
  + '</span><span class="ow">1-way</span></a>'; }
function isAbroad(d){ return d.t && d.t.length && d.t.indexOf('USA')<0; }
function regMatch(d, sel){ if(!sel.length) return true;
  for(var i=0;i<sel.length;i++){ var r=sel[i];
    if(r==='Abroad'){ if(isAbroad(d)) return true; }
    else if(d.t && d.t.indexOf(r)>=0){ return true; } }
  return false; }
function regAvail(arr){ var s={}, abroad=false;
  (arr||[]).forEach(function(d){ (d.t||[]).forEach(function(t){ s[t]=true; if(t!=='USA') abroad=true; }); });
  if(abroad) s['Abroad']=true; return s; }
function syncChips(sel, dk, av, picked){ document.querySelectorAll(sel).forEach(function(b){ var r=b.dataset[dk];
  var show=(r==='all')||(r==='Abroad'?!!av['Abroad']:!!av[r]); b.style.display=show?'':'none';
  b.classList.toggle('on', r==='all' ? picked.length===0 : picked.indexOf(r)>=0); }); }
function buildOW(region){ var t=document.getElementById('owtrack'); if(!t) return;
  var items=OW.filter(function(x){ return region==='all' || (region==='Abroad'?isAbroad(x):x.t.indexOf(region)>=0); });
  items=items.slice(0,60);
  var h=items.length?items.map(owItem).join(''):'<span class="ti-item">No '+region+' fares right now</span>';
  t.innerHTML=h+h;
  var av=regAvail(OW);
  document.querySelectorAll('[data-region]').forEach(function(b){ var r=b.dataset.region;
    var show=(r==='all')||(r==='Abroad'?!!av['Abroad']:!!av[r]); b.style.display=show?'':'none'; }); }
function selRegion(r){ document.querySelectorAll('.regchip').forEach(function(b){ b.classList.toggle('on', b.dataset.region===r); }); buildOW(r); }
function wlRow(m){ return '<div class="mv-row"><button class="star on" onclick="toggleDest(\''+m.c+'\')">&#9733;</button>'
  + '<div class="mv-dest">'+flag(m.cc)+'<div><div class="mv-name">'+m.n+'</div>'
  + '<div class="mv-air">'+m.an+' &middot; from '+m.o+'</div></div></div>'
  + '<div class="mv-right"><span class="mv-price">$'+m.p.toLocaleString()+'</span>'
  + '<span class="down">&#9660;'+m.pct+'%</span><span class="sig '+sigClass(m.s)+'">'+m.s+'</span>'
  + '<a class="mini-book" href="'+m.l+'" target="_blank" rel="noopener">Book</a></div></div>'; }
function toggleDest(c){ var i=WD.indexOf(c); if(i<0)WD.push(c); else WD.splice(i,1); save(); render(); }
function toggleAir(a){ var i=WA.indexOf(a); if(i<0)WA.push(a); else WA.splice(i,1); save(); render(); }
function bMarketList(){ try{ return JSON.parse(localStorage.getItem('mf_bucket')||'[]'); }catch(e){ return []; } }
function bMarketEntry(code){ var m=(typeof MARKET!=='undefined')?MARKET.find(function(x){return x.c===code;}):null; if(!m) return null; return {id:m.o+m.c+(m.dep||''), o:m.o, d:m.c, date:m.dep||'', ret:m.ret||'', price:m.p, link:m.l, ow:0}; }
window.bMarketStar=function(code){ var e=bMarketEntry(code); if(!e) return; var list=bMarketList(); var i=-1; for(var k=0;k<list.length;k++){ if(list[k].id===e.id){ i=k; break; } } if(i>=0) list.splice(i,1); else list.push(e); localStorage.setItem('mf_bucket', JSON.stringify(list)); if(window.renderBucket) window.renderBucket(); render(); };
function render(){
  var _bk=bMarketList();
  document.querySelectorAll('.star[data-code]').forEach(function(b){
    var e=bMarketEntry(b.dataset.code); var on = e ? _bk.some(function(x){return x.id===e.id;}) : false;
    b.innerHTML=on?'&#9733;':'&#9734;'; b.classList.toggle('on', on);
    b.onclick=function(){ bMarketStar(b.dataset.code); }; });
  document.querySelectorAll('.airchip[data-air]').forEach(function(b){ b.classList.toggle('on', WA.indexOf(b.dataset.air)>=0); });
  var wl=document.getElementById('watchlist'), hint=document.getElementById('wl-hint');
  if(wl && hint){ var items=MARKET.filter(function(m){ return WD.indexOf(m.c)>=0 || (WA.length && WA.indexOf(m.a)>=0); });
    if(items.length===0){ hint.style.display='block'; wl.innerHTML=''; } else { hint.style.display='none'; wl.innerHTML=items.map(wlRow).join(''); } }
  var ma=document.getElementById('my-air');
  if(ma){ ma.innerHTML = WA.length ? 'Following: ' + WA.map(function(a){ var m=MARKET.find(function(x){return x.a===a;}); return m?m.an:a; }).join(', ')
    : 'No airlines followed yet — tap one above to follow it.'; }
}
function dealRow(o,d){ var on=WF.indexOf(o+'|'+d.code)>=0;
  return '<div class="mv-row"><button class="star'+(on?' on':'')+'" onclick="toggleFlight(\''+o+'\',\''+d.code+'\')">'+(on?'&#9733;':'&#9734;')+'</button>'
  + '<div class="mv-dest"><span class="emoji">&#9992;</span>'
  + '<div><div class="mv-name">'+d.name+'</div><div class="mv-air">round-trip from '+o+' &middot; '+d.depart+' &rarr; '+d['return']+'</div></div></div>'
  + '<div class="mv-right"><span class="mv-price">$'+d.price.toLocaleString()+'</span>'
  + '<a class="mini-book" href="'+d.link+'" target="_blank" rel="noopener">Book</a></div></div>'; }
function findDeal(o,c){ if(!HOME[o]) return null; var best=null;
  ['deals','lastminute'].forEach(function(k){ (HOME[o][k]||[]).forEach(function(d){ if(d.code===c && (!best||d.price<best.price)) best=d; }); });
  return best; }
function toggleFlight(o,c){ var key=o+'|'+c; var i=WF.indexOf(key); if(i<0)WF.push(key); else WF.splice(i,1); save(); renderAirportWatch(); renderCities(); }
function renderAirportWatch(){ var box=document.getElementById('airwatch'), hint=document.getElementById('aw-hint'); if(!box||!hint) return;
  if(!WF.length){ hint.style.display='block'; box.innerHTML=''; return; }
  hint.style.display='none';
  box.innerHTML=WF.map(function(key){ var p=key.split('|'), o=p[0], c=p[1]; var d=findDeal(o,c);
    if(d) return dealRow(o,d);
    return '<div class="mv-row"><button class="star on" onclick="toggleFlight(\''+o+'\',\''+c+'\')">&#9733;</button>'
      + '<div class="mv-dest"><span class="emoji">&#9992;</span><div><div class="mv-name">'+c+'</div>'
      + '<div class="mv-air">from '+o+' &middot; no current price — check back</div></div></div></div>'; }).join('');
}
function addCity(){ var s=document.getElementById('city-pick'); if(!s) return; var v=s.value;
  if(v && WC.indexOf(v)<0){ WC.push(v); save(); renderCities(); } }
function removeCity(c){ var i=WC.indexOf(c); if(i>=0){ WC.splice(i,1); save(); renderCities(); } }
function renderCities(){ var chips=document.getElementById('citychips'), deals=document.getElementById('citydeals'), hint=document.getElementById('city-hint');
  if(!chips||!deals||!hint) return;
  chips.innerHTML=WC.map(function(c){ var nm=HOME[c]?HOME[c].name:c; return '<span class="citychip">'+nm+' ('+c+') <b onclick="removeCity(\''+c+'\')">&times;</b></span>'; }).join('');
  var valid=WC.filter(function(c){ return HOME[c]; });
  if(valid.length===0){ hint.style.display='block'; deals.innerHTML=''; syncChips('[data-acr]','acr',{},ACSEL); return; }
  hint.style.display='none';
  var key = ACMODE==='lm' ? 'lastminute' : 'deals';
  var pool=[]; valid.forEach(function(c){ pool=pool.concat(HOME[c][key]||[]); });
  var av=regAvail(pool);
  ACSEL=ACSEL.filter(function(r){ return r==='Abroad'?av['Abroad']:av[r]; });
  syncChips('[data-acr]','acr',av,ACSEL);
  document.querySelectorAll('[data-act]').forEach(function(b){ b.classList.toggle('on', b.dataset.act===ACMODE); });
  var label = ACMODE==='lm' ? '— last-minute this week' : '— cheapest anytime';
  deals.innerHTML=valid.map(function(c){
    var arr=(HOME[c][key]||[]).filter(function(d){ return regMatch(d, ACSEL); });
    var h='<div class="grouphdr">'+(ACMODE==='lm'?'&#9889; ':'')+'From '+HOME[c].name+' ('+c+') '+label+'</div>';
    h += arr.length ? arr.map(function(d){ return dealRow(c,d); }).join('')
                    : '<div class="wl-hint">No '+(ACMODE==='lm'?'last-minute ':'')+'deals for this selection.</div>';
    return h; }).join('');
}
var ACSEL=[]; var ACMODE='any';
function toggleACR(r){ if(r==='all'){ ACSEL=[]; } else { var i=ACSEL.indexOf(r); if(i<0)ACSEL.push(r); else ACSEL.splice(i,1); } renderCities(); }
function setACMode(m){ ACMODE=m; renderCities(); }
function cpAppend(cls, h){ var m=document.getElementById('cpmsgs'); if(!m) return; var d=document.createElement('div'); d.className='cp-msg '+cls; d.innerHTML='<span class="bub">'+h+'</span>'; m.appendChild(d); m.scrollTop=m.scrollHeight; }
function chatToggle(){ var p=document.getElementById('chatpanel'); if(!p) return; p.classList.toggle('open');
  if(p.classList.contains('open') && !p.dataset.greeted){ cpAppend('bot', "Hi! I search the live deals on this site. Try:<br>&bull; \"cheapest one-way to Asia\"<br>&bull; \"last-minute to the Caribbean\"<br>&bull; \"where can I go under $300?\""); p.dataset.greeted='1'; } }
function chatSend(){ var i=document.getElementById('cpinput'); if(!i) return; var t=(i.value||'').trim(); if(!t) return;
  cpAppend('you', t.replace(/</g,'&lt;')); i.value='';
  var th=cpThink();
  setTimeout(function(){ if(th&&th.parentNode) th.parentNode.removeChild(th); cpAppend('bot', botReply(t)); }, 680); }
function cpThink(){ var m=document.getElementById('cpmsgs'); if(!m) return null; var d=document.createElement('div'); d.className='cp-msg bot'; d.innerHTML='<span class="bub think"><span class="astro sm">'+ASTRO+'</span></span>'; m.appendChild(d); m.scrollTop=m.scrollHeight; return d; }
function botPrice(d){ return d.p!==undefined?d.p:(d.price!==undefined?d.price:0); }
function botList(arr, n, oneway){ return arr.slice(0,n).map(function(d){ var nm=d.n||d.name, o=d.o||d.origin, l=d.l||d.link;
  return '&bull; <a href="'+l+'" target="_blank" rel="noopener">'+nm+' — $'+botPrice(d).toLocaleString()+' '+(oneway?'one-way':'round-trip')+' from '+o+'</a>'; }).join('<br>'); }
function findDest(s){ for(var i=0;i<MARKET.length;i++){ var parts=MARKET[i].n.toLowerCase().split(',');
  for(var j=0;j<parts.length;j++){ var t=parts[j].trim(); if(t.length>2 && s.indexOf(t)>=0) return MARKET[i]; } }
  return null; }
function botReply(q){ var s=q.toLowerCase();
  if(/^(hi|hey|hello|help|what can|how do)/.test(s)) return "I can search live deals here. Try:<br>&bull; \"cheapest one-way to Europe\"<br>&bull; \"last-minute to the Caribbean\"<br>&bull; \"where can I go under $200?\"<br>&bull; \"best time to visit Japan\"";
  if(/best time|when (should|to|is best)|what month|when to (go|visit|travel)/.test(s)){
    var hit=findDest(s);
    if(hit && BT[hit.c]) return "Best time to visit <b>"+hit.n+"</b>: "+BT[hit.c]+". (Based on weather/crowd averages.)";
    return "Tell me a destination — e.g. \"best time to visit Bangkok\" or \"when to go to Italy\".";
  }
  if(/how much|trip cost|cost (of|to|for)|budget for|week in|a week/.test(s)){
    var td=findDest(s);
    if(td && td.wk) return "A week in <b>"+td.n+"</b> &asymp; $"+td.wk.toLocaleString()+" — flight $"+td.p.toLocaleString()+" + ~7 nights + eSIM. (Rough estimate.)";
    return "Tell me a tracked destination — e.g. \"how much for a week in Bangkok?\"";
  }
  if(/convert|exchange|how far|worth in|dollar go|currency/.test(s)){
    var amt=100; var nm=s.match(/(\d[\d,]+|\d)/); if(nm) amt=parseInt(nm[1].replace(/,/g,''),10) || 100;
    var cur=null, place=null; var cd=findDest(s);
    if(cd && CUR[cd.c]){ cur=CUR[cd.c]; place=cd.n; }
    if(!cur){ var CN={baht:'THB',yen:'JPY',euro:'EUR',euros:'EUR',peso:'MXN',pesos:'MXN',rupee:'INR',rupees:'INR',pound:'GBP',pounds:'GBP',rand:'ZAR',real:'BRL',reais:'BRL',dong:'VND',won:'KRW',ringgit:'MYR',dirham:'AED',lira:'TRY',rupiah:'IDR'};
      for(var k in CN){ if(s.indexOf(k)>=0){ cur=CN[k]; break; } } }
    if(cur && FX[cur]){ return "$"+amt.toLocaleString()+" &asymp; <b>"+Math.round(amt*FX[cur]).toLocaleString()+" "+cur+"</b>"+(place?(" in "+place):"")+"."; }
    return "Tell me a place — e.g. \"how far does $100 go in Thailand?\"";
  }
  var lm=/last[- ]?minute|this week|soon|right now/.test(s);
  var oneway=!/round[- ]?trip/.test(s);
  var data = lm ? (oneway && typeof OWLM!=='undefined' ? OWLM : (typeof LM!=='undefined'?LM:[]))
                : (oneway && typeof OW!=='undefined' ? OW : (typeof LM!=='undefined'?LM:[]));
  if(!data || !data.length){ data = (typeof OW!=='undefined'?OW:[]); }
  var KW=[['southeast asia','SE Asia'],['se asia','SE Asia'],['east asia','E Asia'],['south asia','S Asia'],['asia','Asia'],['western europe','W Europe'],['west europe','W Europe'],['eastern europe','E Europe'],['east europe','E Europe'],['nordic','Nordic'],['scandinav','Nordic'],['europe','Europe'],['caribbean','Caribbean'],['central america','C America'],['mexico','C America'],['south america','S America'],['oceania','Oceania'],['australia','Oceania'],['middle east','Middle East'],['africa','Africa'],['canada','Canada'],['domestic','USA'],['abroad','Abroad'],['international','Abroad']];
  var region=null; for(var i=0;i<KW.length;i++){ if(s.indexOf(KW[i][0])>=0){ region=KW[i][1]; break; } }
  var cap=null; var m=s.match(/(\d{2,4})/); if(m && /under|below|less|budget|for |\$/.test(s)) cap=parseInt(m[1],10);
  var items=data.slice();
  if(region) items=items.filter(function(d){ return regMatch(d, [region]); });
  if(cap) items=items.filter(function(d){ return botPrice(d)<=cap; });
  if(!region && !cap){ var words=s.replace(/[^a-z ]/g,' ').split(/\s+/).filter(function(w){return w.length>3;});
    if(words.length){ items=data.filter(function(d){ var nm=(d.n||d.name||'').toLowerCase(); return words.some(function(w){ return nm.indexOf(w)>=0; }); }); } }
  items.sort(function(a,b){ return botPrice(a)-botPrice(b); });
  if(!items.length) return "I couldn't find "+(lm?'last-minute ':'')+(oneway?'one-way ':'')+"deals"+(region?(' to '+region):'')+(cap?(' under $'+cap):'')+" right now. Try a different region, or open the <a href='explore.html'>One-way explorer</a>.";
  var head=(lm?'Last-minute ':'')+(oneway?'one-way ':'round-trip ')+'deals'+(region?(' to '+region):'')+(cap?(' under $'+cap):'')+':';
  return head+'<br>'+botList(items,4,oneway)+'<br><a href="'+(lm?'lastminute.html':(oneway?'explore.html':'market.html'))+'">See more &rarr;</a>';
}
function fakeSubmit(e){ e.preventDefault();
  var f=e.target, a=f.getAttribute('action'), ok=document.getElementById('ok'), btn=f.querySelector('button');
  if(a.indexOf('YOUR_FORM_ID')!==-1){ ok.innerHTML='&#10003; You\'re on the list! (form endpoint not set yet)'; ok.style.display='block'; f.reset(); return false; }
  var lbl = btn ? btn.textContent : '';
  if(btn){ btn.disabled=true; btn.textContent='Joining\u2026'; }
  fetch(a,{method:'POST',body:new FormData(f),headers:{'Accept':'application/json'}})
    .then(function(r){ if(r.ok){ ok.innerHTML='&#10003; You\'re on the list! Check your inbox to confirm.'; ok.style.display='block'; f.reset(); }
      else { ok.innerHTML='Hmm, that didn\'t work \u2014 please try again.'; ok.style.display='block'; } })
    .catch(function(){ ok.innerHTML='Network error \u2014 please try again.'; ok.style.display='block'; })
    .then(function(){ if(btn){ btn.disabled=false; btn.textContent=lbl; } });
  return false; }
var HSECS=['summary','indices','movers','deals','lastminute','oneway'];
var HL=JSON.parse(localStorage.getItem('fs_home_layout')||'{}');
function secOn(s){ return HL[s]!==false; }
function applyLayout(){ HSECS.forEach(function(s){ var el=document.querySelector('[data-sec="'+s+'"]');
  if(el) el.style.display = secOn(s)?'':'none'; var cb=document.getElementById('cb-'+s); if(cb) cb.checked=secOn(s); }); }
function toggleSec(s){ HL[s]=!secOn(s); localStorage.setItem('fs_home_layout', JSON.stringify(HL)); applyLayout(); }
function toggleCustomize(){ var p=document.getElementById('customizer'); if(p) p.style.display=(p.style.display==='block')?'none':'block'; }
function lmItem(d){ return '<div class="mv-row"><div class="mv-dest"><span class="emoji">&#9889;</span>'
  + '<div><div class="mv-name">'+d.n+'</div><div class="mv-air">round-trip from '+d.o+' &middot; '+d.dep+' &rarr; '+d.ret+'</div></div></div>'
  + '<div class="mv-right"><span class="mv-price">$'+d.p.toLocaleString()+'</span>'
  + '<a class="mini-book" href="'+d.l+'" target="_blank" rel="noopener">Book</a></div></div>'; }
var LMSEL=[];
function buildLM(){ var box=document.getElementById('lmlist'); if(!box) return;
  var av=regAvail(LM);
  LMSEL=LMSEL.filter(function(r){ return r==='Abroad'?av['Abroad']:av[r]; });
  var items = LMSEL.length ? LM.filter(function(d){ return regMatch(d, LMSEL); }) : LM;
  items = items.slice(0,60);
  box.innerHTML = items.length ? items.map(lmItem).join('') : '<div class="wl-hint">No last-minute deals for that selection right now.</div>';
  syncChips('[data-lmr]','lmr',av,LMSEL);
}
function toggleLMR(r){ if(r==='all'){ LMSEL=[]; } else { var i=LMSEL.indexOf(r); if(i<0)LMSEL.push(r); else LMSEL.splice(i,1); } buildLM(); }
var OWMODE='6m'; var OWPSEL=[];
function owData(){ return OWMODE==='lm' ? OWLM : OW; }
function owMatch(d){ return OWPSEL.length===0 || (d.t && d.t.some(function(t){ return OWPSEL.indexOf(t)>=0; })); }
function owpItem(d){ return '<div class="mv-row"><div class="mv-dest"><span class="emoji">&#9992;</span>'
  + '<div><div class="mv-name">'+d.n+'</div><div class="mv-air">one-way from '+d.o+(d.dep?(' &middot; '+d.dep):'')+'</div></div></div>'
  + '<div class="mv-right"><span class="mv-price">$'+d.p.toLocaleString()+'</span>'
  + '<a class="mini-book" href="'+d.l+'" target="_blank" rel="noopener">Book</a></div></div>'; }
function buildOWPage(){ var box=document.getElementById('owpage'); if(!box) return;
  var data=owData(); var av=regAvail(data);
  OWPSEL=OWPSEL.filter(function(r){ return r==='Abroad'?av['Abroad']:av[r]; });
  var items=data.filter(function(d){ return regMatch(d, OWPSEL); }).slice(0,80);
  box.innerHTML=items.length?items.map(owpItem).join(''):'<div class="wl-hint">No one-ways for that selection right now.</div>';
  document.querySelectorAll('[data-owt]').forEach(function(b){ b.classList.toggle('on', b.dataset.owt===OWMODE); });
  syncChips('[data-owr]','owr',av,OWPSEL);
}
function setOWMode(m){ OWMODE=m; buildOWPage(); }
function toggleOWR(r){ if(r==='all'){ OWPSEL=[]; } else { var i=OWPSEL.indexOf(r); if(i<0)OWPSEL.push(r); else OWPSEL.splice(i,1); } buildOWPage(); }
function flipCard(btn){ var f=btn.closest('.flip'); if(f) f.classList.toggle('flipped'); }
function fmtRate(r){ return r>=100?Math.round(r).toLocaleString():(r>=10?r.toFixed(1):r.toFixed(2)); }
function loadFX(){ fetch('https://open.er-api.com/v6/latest/USD').then(function(r){return r.json();}).then(function(d){
  if(d&&d.rates){ FX=d.rates; document.querySelectorAll('[data-cur]').forEach(function(el){ var c=el.dataset.cur;
    if(FX[c]) el.textContent='$1 ≈ '+fmtRate(FX[c])+' '+c; }); } }).catch(function(){}); }
var WSEL=[]; var WORG='all'; var WMODE='any';
function worldItem(x){ return '<div class="mv-row"><div class="mv-dest"><span class="emoji">&#9992;</span>'
  + '<div><div class="mv-name">'+x.n+'</div><div class="mv-air">one-way: '+x.on+' ('+x.o+') &rarr; '+x.c+' &middot; '+x.dep+'</div></div></div>'
  + '<div class="mv-right"><span class="mv-price">$'+x.p.toLocaleString()+'</span>'
  + '<a class="mini-book" href="'+x.l+'" target="_blank" rel="noopener">Book</a></div></div>'; }
function mproj(lon,lat){ return [(lon+180)/360*1000, (90-lat)/180*500]; }
function mPC(c){ if(typeof ACO!=='undefined' && ACO[c]){ return mproj(ACO[c][1], ACO[c][0]); } return null; }
function marc(a,b){ var x1=a[0],y1=a[1],x2=b[0],y2=b[1]; var mx=(x1+x2)/2,my=(y1+y2)/2; var dx=x2-x1,dy=y2-y1; var d=Math.sqrt(dx*dx+dy*dy)||1; var nx=-dy/d,ny=dx/d; var k=(y1+y2>200?0.14:-0.14); var cx=mx+nx*d*k, cy=my+ny*d*k; return 'M'+x1.toFixed(1)+' '+y1.toFixed(1)+' Q'+cx.toFixed(1)+' '+cy.toFixed(1)+' '+x2.toFixed(1)+' '+y2.toFixed(1); }
function buildWorldMap(){
  var gR=document.getElementById('mapRoutes'); if(!gR||typeof ACO==='undefined') return;
  var gG=document.getElementById('mapGlow'), gD=document.getElementById('mapDots');
  var data=(WMODE==='lm'?WORLDLM:WORLD)||[];
  var scope=data.filter(function(x){ return WORG==='all'||x.o===WORG; }).filter(function(x){ return regMatch(x, WSEL); });
  scope=scope.filter(function(x){ return x.o!==x.c && ACO[x.o] && ACO[x.c]; });
  var routes;
  if(WORG==='all'){ var best={}; scope.forEach(function(x){ if(!best[x.o]||x.p<best[x.o].p) best[x.o]=x; }); routes=Object.keys(best).map(function(k){return best[k];}); }
  else { routes=scope.slice().sort(function(a,b){return a.p-b.p;}).slice(0,70); }
  routes.sort(function(a,b){return a.p-b.p;});
  var thr=routes.length? routes[Math.floor(routes.length/3)].p : 0;
  var dim='',glow='',dots={};
  routes.forEach(function(x){
    var A=mPC(x.o), B=mPC(x.c); if(!A||!B) return;
    dots[Math.round(A[0])+','+Math.round(A[1])]=A; dots[Math.round(B[0])+','+Math.round(B[1])]=B;
    var tip=x.on+' ('+x.o+') → '+x.n+'  ·  $'+x.p+(x.dep?('  ·  '+x.dep):'');
    var pth='<a href="'+x.l+'" target="_blank" rel="noopener"><path d="'+marc(A,B)+'"><title>'+tip+'</title></path></a>';
    if(x.p<=thr) glow+=pth; else dim+=pth;
  });
  gR.innerHTML=dim; gG.innerHTML=glow;
  var dh=''; Object.keys(dots).forEach(function(k){ var d=dots[k]; dh+='<circle cx="'+d[0].toFixed(1)+'" cy="'+d[1].toFixed(1)+'" r="1.6"/>'; });
  gD.innerHTML=dh;
}
function buildWorld(){ var box=document.getElementById('worldlist'); if(!box||typeof WORLD==='undefined') return;
  var data=(WMODE==='lm'?WORLDLM:WORLD)||[];
  var scope=data.filter(function(x){ return WORG==='all'||x.o===WORG; });
  var av=regAvail(scope);
  WSEL=WSEL.filter(function(r){ return r==='Abroad'?av['Abroad']:av[r]; });
  var items=scope.filter(function(x){ return regMatch(x, WSEL); }).slice(0,80);
  box.innerHTML=items.length?items.map(worldItem).join(''):'<div class="wl-hint">No flights for that selection right now.</div>';
  document.querySelectorAll('[data-wt]').forEach(function(b){ b.classList.toggle('on', b.dataset.wt===WMODE); });
  syncChips('[data-wr]','wr',av,WSEL);
  buildWorldMap();
}
function selWorldOrigin(v){ WORG=v; buildWorld(); }
function setWorldMode(m){ WMODE=m; buildWorld(); }
function toggleWR(r){ if(r==='all'){ WSEL=[]; } else { var i=WSEL.indexOf(r); if(i<0)WSEL.push(r); else WSEL.splice(i,1); } buildWorld(); }
function liveCard(btn){
  var c=btn.closest('.card'); if(!c) return;
  var o=c.getAttribute('data-o'), d=c.getAttribute('data-c'), dep=c.getAttribute('data-dep'), ret=c.getAttribute('data-ret'), ow=c.getAttribute('data-ow');
  if(!o||!d) return;
  var orig=btn.innerHTML; btn.disabled=true; btn.innerHTML='checking…';
  var u='/api/search?origin='+encodeURIComponent(o)+'&destination='+encodeURIComponent(d)+'&one_way='+(ow==='1'?'true':'false')+'&sorting=price&limit=1';
  if(dep) u+='&departure_at='+dep;
  if(ret && ow!=='1') u+='&return_at='+ret;
  fetch(u).then(function(r){return r.json();}).then(function(j){
    var f=j&&j.data&&j.data[0];
    if(!f){ btn.disabled=false; btn.innerHTML=orig; return; }
    var pe=c.querySelector('.price'); var oldp=pe?parseInt((pe.textContent||'').replace(/[^0-9]/g,''),10):0;
    var np=Math.round(f.price);
    if(pe){ var was=pe.querySelector('.was'); pe.innerHTML='$'+np.toLocaleString()+(was?' ':''); if(was) pe.appendChild(was); }
    var bk=c.querySelector('.book'); if(bk&&f.link) bk.href=f.link;
    var up=(oldp&&np>oldp); var s=document.createElement('span'); s.className=up?'live-up':'live-ok';
    s.innerHTML=up?('&#9650; live &middot; now $'+np.toLocaleString()):('&#10003; live &middot; $'+np.toLocaleString());
    btn.parentNode.replaceChild(s, btn);
  }).catch(function(){ btn.disabled=false; btn.innerHTML=orig; });
}
function liveOnView(){
  function sigInfo(price,b){ if(!b) return null; var pct=Math.round((b-price)/b*100); var cls=pct>=20?'s-book':(pct>=8?'s-watch':'s-wait'); var sg=pct>=20?'BOOK':(pct>=8?'WATCH':'WAIT'); return {pct:pct,cls:cls,s:sg}; }
  var queue=[], active=0, MAX=3;
  function pump(){ while(active<MAX && queue.length){ doFetch(queue.shift()); } }
  function apply(el,np,link,b){
    var pe=el.querySelector('.mv-price, .price');
    if(pe){ var was=pe.querySelector('.was'); pe.innerHTML='<span class="lp-dot" title="live fare"></span>$'+np.toLocaleString(); if(was){ pe.appendChild(document.createTextNode(' ')); pe.appendChild(was); } }
    var bk=el.querySelector('.mini-book, .book'); if(bk&&link) bk.href=link;
    var info=sigInfo(np,b);
    if(info){ var dn=el.querySelector('.down'); if(dn) dn.innerHTML='&#9660;'+info.pct+'%'; var sg=el.querySelector('.sig'); if(sg){ sg.textContent=info.s; sg.className='sig '+info.cls; }
      var bd=el.querySelector('.badge'); if(bd && bd.className.indexOf('flash')<0){ bd.textContent=info.pct>0?('Save '+info.pct+'%'):''; } }
  }
  function doFetch(el){ active++;
    var o=el.getAttribute('data-o'), d=el.getAttribute('data-d')||el.getAttribute('data-c'), ow=el.getAttribute('data-ow')==='1', b=parseFloat(el.getAttribute('data-b'))||0;
    if(!o||!d){ active--; pump(); return; }
    var u='/api/search?origin='+encodeURIComponent(o)+'&destination='+encodeURIComponent(d)+'&one_way='+(ow?'true':'false')+'&sorting=price&limit=1';
    fetch(u).then(function(r){return r.json();}).then(function(j){ var f=j&&j.data&&j.data[0]; if(f) apply(el, Math.round(f.price), f.link, b); }).catch(function(){}).then(function(){ active--; pump(); });
  }
  function inView(el){ var vh=window.innerHeight||document.documentElement.clientHeight; var r=el.getBoundingClientRect(); return r.height>0 && r.bottom>-250 && r.top < vh+250; }
  function scan(){ var els=document.querySelectorAll('[data-lp]'); for(var i=0;i<els.length;i++){ var el=els[i]; if(el.__lp || el.offsetParent===null) continue; if(inView(el)){ el.__lp=1; queue.push(el); } } pump(); }
  var t; function onScroll(){ clearTimeout(t); t=setTimeout(scan,120); }
  window.addEventListener('scroll', onScroll, {passive:true});
  window.addEventListener('resize', onScroll, {passive:true});
  scan(); setInterval(scan, 1500);
}
function tlSpin(el,msg){ el.innerHTML='<div class="tl-load"><span class="astro sm" style="width:34px;display:inline-block">'+ASTRO+'</span><p>'+(msg||'Charting fares…')+'</p></div>'; }
function tlRow(f, oneway){
  var price='$'+Number(f.price).toLocaleString();
  var dep=(f.departure_at||'').slice(0,10);
  var sub=f.origin_airport+' → '+f.destination_airport+' &middot; '+dep+(oneway?'':(f.return_at?(' → '+(f.return_at||'').slice(0,10)):''));
  return '<div class="mv-row"><div class="mv-dest"><span class="emoji">&#9992;</span><div><div class="mv-name">'+f.destination_airport+'</div><div class="mv-air">'+sub+'</div></div></div><div class="mv-right"><span class="mv-price">'+price+'</span><a class="mini-book" href="'+f.link+'" target="_blank" rel="noopener">Book</a></div></div>';
}
function tlTrip(){
  var o=(document.getElementById('tl-origin').value||'').trim().toUpperCase();
  var d=(document.getElementById('tl-dest').value||'').trim().toUpperCase();
  var dep=document.getElementById('tl-depart').value;
  var wk=document.getElementById('tl-weeks').value;
  var out=document.getElementById('tl-trip-out');
  if(!/^[A-Z]{3}$/.test(o)){ out.innerHTML='<div class="wl-hint">Enter a 3-letter origin airport (e.g. JFK).</div>'; return; }
  tlSpin(out);
  var u='/api/search?origin='+o+'&one_way=false&sorting=price&limit=200';
  if(/^[A-Z]{3}$/.test(d)) u+='&destination='+d;
  if(dep) u+='&departure_at='+dep;
  fetch(u).then(function(r){return r.json();}).then(function(j){
    var data=(j&&j.data)||[];
    if(wk!=='any'){ var target=parseInt(wk,10)*7;
      data=data.filter(function(f){ if(!f.departure_at||!f.return_at) return false; var n=Math.round((new Date(f.return_at)-new Date(f.departure_at))/86400000); return Math.abs(n-target)<=3; }); }
    var seen={}; data=data.filter(function(f){ var k=f.destination_airport+(f.departure_at||''); if(seen[k])return false; seen[k]=1; return true; });
    data.sort(function(a,b){return a.price-b.price;}); data=data.slice(0,24);
    out.innerHTML = data.length? data.map(function(f){return tlRow(f,false);}).join('') : '<div class="wl-hint">No round-trips matched that length/month. Try “Any length” or a different month.</div>';
  }).catch(function(){ out.innerHTML='<div class="wl-hint">Couldn’t load fares right now — please try again.</div>'; });
}
function tlHop(){
  var o=(document.getElementById('hp-origin').value||'').trim().toUpperCase();
  var d=(document.getElementById('hp-dest').value||'').trim().toUpperCase();
  var dep=document.getElementById('hp-depart').value;
  var out=document.getElementById('hp-out');
  if(!/^[A-Z]{3}$/.test(o)||!/^[A-Z]{3}$/.test(d)){ out.innerHTML='<div class="wl-hint">Enter both a 3-letter origin and destination (e.g. JFK and BKK).</div>'; return; }
  tlSpin(out,'Plotting your passage…');
  var u1='/api/search?origin='+o+'&destination='+d+'&one_way=true&sorting=price&limit=10';
  if(dep) u1+='&departure_at='+dep;
  fetch(u1).then(function(r){return r.json();}).then(function(j){
    var leg1=((j&&j.data)||[]).slice().sort(function(a,b){return a.price-b.price;})[0];
    if(!leg1){ out.innerHTML='<div class="wl-hint">No one-way found to '+d+' for that date.</div>'; return; }
    var arr=(leg1.departure_at||dep||'').slice(0,10);
    var u2='/api/search?origin='+d+'&one_way=true&sorting=price&limit=200';
    if(arr) u2+='&departure_at='+arr;
    fetch(u2).then(function(r){return r.json();}).then(function(j2){
      var onward=((j2&&j2.data)||[]).filter(function(f){ if(f.destination_airport===o) return false; if(!arr||!f.departure_at) return true; var diff=(new Date(f.departure_at)-new Date(arr))/3600000; return diff>=-6 && diff<=48; });
      onward.sort(function(a,b){return a.price-b.price;});
      var h='<div class="hop-leg"><div class="hop-tag">Leg 1 &middot; get there</div>'+tlRow(leg1,true)+'</div>';
      h+='<div class="hop-leg"><div class="hop-tag">Leg 2 &middot; cheapest onward within 48h</div>'+(onward.length? onward.slice(0,6).map(function(f){return tlRow(f,true);}).join('') : '<div class="wl-hint">No onward one-way within 48h found from '+d+' — try another date.</div>')+'</div>';
      out.innerHTML=h;
    }).catch(function(){ out.innerHTML='<div class="wl-hint">Couldn’t load the onward hop — try again.</div>'; });
  }).catch(function(){ out.innerHTML='<div class="wl-hint">Couldn’t load the hop right now — try again.</div>'; });
}
buildOW('all'); render(); renderCities(); renderAirportWatch(); applyLayout(); buildLM(); buildOWPage(); buildWorld(); loadFX(); liveOnView();
</script>"""


# Animated intro: the og-image motif drawn live — the arc draws in and a plane
# flies it start-to-finish, then the title/subtitle fade up. Shown once per
# session (see the script in top_chrome). Pure SVG+CSS, no images required.
_INTRO_GRID = "".join(
    [f'<line x1="{x}" y1="40" x2="{x}" y2="592"/>' for x in range(85, 1160, 85)] +
    [f'<line x1="40" y1="{y}" x2="1160" y2="{y}"/>' for y in range(110, 600, 70)])
INTRO_SVG = (
    '<svg class="intro-svg" viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg" '
    'role="img" aria-label="Magellan Flights">'
    '<defs><path id="arcpath" d="M 84 474 Q 600 14 1116 474"/></defs>'
    f'<g class="intro-grid">{_INTRO_GRID}</g>'
    '<use href="#arcpath" class="intro-arc"/>'
    '<circle class="intro-dot-a" cx="84" cy="474" r="12"/>'
    '<circle class="intro-dot-b" cx="1116" cy="474" r="11"/>'
    '<g class="intro-plane"><path d="M-18,-10 L20,0 L-18,10 L-9,0 Z"/>'
    '<animateMotion dur="2.2s" begin="0.25s" fill="freeze" rotate="auto" '
    'calcMode="spline" keyTimes="0;1" keySplines="0.45 0 0.25 1">'
    '<mpath href="#arcpath"/></animateMotion></g>'
    f'<text class="intro-ttl" x="82" y="180">{BRAND}</text>'
    '<text class="intro-sub" x="86" y="240">The cheapest flights from the USA</text>'
    '<text class="intro-url" x="86" y="566">magellanflights.com</text>'
    '</svg>')


def top_chrome(active, market):
    nav = []
    for href, label in NAV:
        cls = "link active" if href == active else "link"
        nav.append(f'<a class="{cls}" href="{href}">{label}</a>')
    nav_html = "".join(nav)
    return f"""<body>
<div id="astro-splash"><div class="intro-stage">{INTRO_SVG}</div></div>
<script>(function(){{var s=document.getElementById('astro-splash');if(!s)return;
if(sessionStorage.getItem('mf_intro')){{s.parentNode.removeChild(s);return;}}
var rm=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function done(){{s.classList.add('hide');sessionStorage.setItem('mf_intro','1');setTimeout(function(){{if(s.parentNode)s.parentNode.removeChild(s);}},650);}}
window.addEventListener('load',function(){{setTimeout(done, rm?700:2700);}});}})();</script>
<div class="topbar">
<div class="ticker"><span class="ti-label">Flight Tracker</span><div class="ticker-track">{ticker_rt(market)}</div></div>
<div class="regionbar">{region_buttons()}</div>
<div class="ticker ow"><span class="ti-label">&#8600; One-way</span><div class="ticker-track" id="owtrack"></div></div>
<header>
  <div class="bar">
    <a class="logo" href="index.html"><span class="mark">{LOGO_SVG}</span>{BRAND}</a>
    <nav class="nav">{nav_html}<a class="nav-cta" href="index.html#alerts">Get free alerts</a><button type="button" class="ticker-toggle" onclick="toggleTickers()" title="Hide or show the price ticker" aria-label="Toggle ticker"><span class="tt-ar">&#9650;</span> Ticker</button></nav>
  </div>
</header>
<script>
function toggleTickers(){{ var off=document.body.classList.toggle('tickers-off'); try{{ localStorage.setItem('mf_tickers', off?'off':'on'); }}catch(e){{}} var a=document.querySelector('.ticker-toggle .tt-ar'); if(a) a.innerHTML= off?'&#9660;':'&#9650;'; }}
(function(){{ var off=false; try{{ off=localStorage.getItem('mf_tickers')==='off'; }}catch(e){{}} if(off){{ document.body.classList.add('tickers-off'); var a=document.querySelector('.ticker-toggle .tt-ar'); if(a) a.innerHTML='&#9660;'; }} }})();
</script>
</div>"""


WIDGET_HTML = """<aside id="bucket-widget" class="bucket-widget"><div class="bw-head">&#9733; My Bucket List</div><div id="bw-list"></div></aside>
<button class="bw-toggle" onclick="document.body.classList.toggle('bw-open')">&#9733;<span id="bw-count"></span></button>
<script>
window.renderBucket=function(){ var list=[]; try{ list=JSON.parse(localStorage.getItem('mf_bucket')||'[]'); }catch(e){} var cnt=document.getElementById('bw-count'); if(cnt) cnt.textContent=list.length?(' '+list.length):''; var w=document.getElementById('bw-list'); if(w){ w.innerHTML = list.length ? list.map(function(f,i){ return '<div class="bw-row"><a href="'+f.link+'" target="_blank" rel="noopener"><b>'+f.o+' &rarr; '+f.d+'</b><span>$'+(f.price||0).toLocaleString()+(f.ow?' one-way':'')+'</span><small>'+(f.date||'')+(f.ret?(' &rarr; '+f.ret):'')+'</small></a><button class="bw-x" title="remove" onclick="bucketRemove('+i+')">&times;</button></div>'; }).join('') : '<div class="bw-empty">Star &#9734; any deal on Explore to save it here.</div>'; } var pg=document.getElementById('bucket-page'); if(pg){ pg.innerHTML = list.length ? ('<div class="panel">'+list.map(function(f,i){ return '<div class="mv-row"><div class="mv-dest"><span class="emoji">&#9992;</span><div><div class="mv-name">'+f.o+' &rarr; '+f.d+'</div><div class="mv-air">'+(f.date||'')+(f.ret?(' &rarr; '+f.ret):'')+(f.ow?' &middot; one-way':' &middot; round-trip')+'</div></div></div><div class="mv-right"><span class="mv-price">$'+(f.price||0).toLocaleString()+'</span><a class="mini-book" href="'+f.link+'" target="_blank" rel="noopener">Book</a><button class="star on" title="remove" onclick="bucketRemove('+i+')">&#9733;</button></div></div>'; }).join('')+'</div>') : '<div class="wl-hint">No saved flights yet. Star &#9734; any deal on the <a href="explore.html">Explore</a> page to add it to your bucket list.</div>'; } };
window.bucketRemove=function(i){ var list=[]; try{ list=JSON.parse(localStorage.getItem('mf_bucket')||'[]'); }catch(e){} list.splice(i,1); localStorage.setItem('mf_bucket',JSON.stringify(list)); window.renderBucket(); };
window.addEventListener('load', window.renderBucket);
</script>"""


def render_page(active, title, body, market, oneway, onewaylm, home, lm, world, worldlm, today):
    script = (SCRIPT.replace("__WORLDJS__",
                             ("var WORLD = " + json.dumps(world_arr(world)) + ";\nvar WORLDLM = " + json.dumps(world_arr(worldlm)) + ";")
                             if active == "world.html" else "var WORLD = []; var WORLDLM = [];")
              .replace("__MARKETJS__", market_js(market) +
                             "\nvar BT = " + json.dumps(BEST_TIME) + ";" +
                             "\nvar CUR = " + json.dumps({m["code"]: dest_currency(m["code"]) for m in market}) + ";" +
                             "\nvar FXS = " + json.dumps(FX_STATIC) + ";\nvar FX = FXS;")
              .replace("__ONEWAYJS__", "var OW = " + json.dumps(ow_arr(oneway)) +
                       ";\nvar OWLM = " + json.dumps(ow_arr(onewaylm)) + ";")
              .replace("__LMJS__", lm_js(lm))
              .replace("__HOMEJS__", json.dumps(home if active in ("airports.html", "watchlist.html") else {}))
              .replace("__ACOJS__", MAP_COORDS if active == "world.html" else "{}")
              .replace("__ASTRO__", ASTRO_SVG))
    foot = (f'<footer><p>Prices are round-trip unless marked one-way, and change fast — '
            f'book soon if you see one you love.</p><p>{BRAND} may earn a commission when you '
            f'book through our links, at no extra cost to you.<br>Fares found {today} and may change at any time.</p></footer>')
    _cc = "{}"
    if active in ("trip.html", "explore.html"):
        try:
            with open(os.path.join(HERE, "code_cc.json"), encoding="utf-8") as _ccf:
                _cc = _ccf.read().strip()
        except Exception:
            pass
    seo_title, seo_desc = _seo_for(active, title)
    seo_head = head_seo(active, seo_title, seo_desc, market)
    return (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{_esc_attr(seo_title)}</title>\n'
            f'<meta name="description" content="{_esc_attr(seo_desc)}">\n'
            f'{seo_head}\n'
            f'<link rel="icon" type="image/svg+xml" href="favicon.svg">\n'
            f'{CSS}\n</head>\n{top_chrome(active, market)}\n{body}\n{CHAT_HTML}\n{WIDGET_HTML}\n{foot}\n{script}\n</body>\n</html>').replace("__CCJS__", _cc)


# --------------------------------------------------------------------------- #
# Page bodies
# --------------------------------------------------------------------------- #
def world_map_html():
    import math as _m
    W, H = 1000, 500

    def pj(lon, lat):
        return ((lon + 180) / 360 * W, (90 - lat) / 180 * H)

    grat = []
    for lon in range(-150, 181, 30):
        x = (lon + 180) / 360 * W
        grat.append(f'<line x1="{x:.0f}" y1="18" x2="{x:.0f}" y2="430"/>')
    for lat in range(-40, 81, 20):
        y = (90 - lat) / 180 * H
        grat.append(f'<line x1="0" y1="{y:.0f}" x2="1000" y2="{y:.0f}"/>')
    rhumb = []
    for rl, rt in [(-40, 30), (150, -10)]:
        cx, cy = pj(rl, rt)
        seg = []
        for ang in range(0, 360, 45):
            x = cx + 320 * _m.cos(_m.radians(ang))
            y = cy + 320 * _m.sin(_m.radians(ang))
            seg.append(f'<line x1="{cx:.0f}" y1="{cy:.0f}" x2="{x:.0f}" y2="{y:.0f}"/>')
        seg.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="3" fill="none"/>')
        rhumb.append("".join(seg))
    labels = [('NORTH AMERICA', -100, 46), ('SOUTH AMERICA', -62, -12), ('EUROPE', 14, 55),
              ('AFRICA', 21, 2), ('ASIA', 95, 47), ('OCEANIA', 144, -26),
              ('ATLANTIC', -38, 21), ('PACIFIC', -150, 7), ('INDIAN OCEAN', 78, -30)]
    labs = []
    for t, lon, lat in labels:
        x, y = pj(lon, lat)
        labs.append(f'<text x="{x:.0f}" y="{y:.0f}" class="ml-lab" text-anchor="middle">{t}</text>')
    svg = ('<svg viewBox="0 18 1000 412" preserveAspectRatio="xMidYMid meet" class="worldmap" '
           'role="img" aria-labelledby="wmap-t wmap-d">'
           '<title id="wmap-t">World map of cheap flight routes</title>'
           '<desc id="wmap-d">Interactive map showing the cheapest tracked flight '
           'routes between cities around the world.</desc>'
           '<defs><filter id="mglow" x="-50%" y="-50%" width="200%" height="200%">'
           '<feGaussianBlur stdDeviation="3" result="b"/><feMerge>'
           '<feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
           '<rect x="0" y="0" width="1000" height="500" fill="#0a0e14"/>'
           f'<g class="ml-grat">{"".join(grat)}</g>'
           f'<g class="ml-rhumb">{"".join(rhumb)}</g>'
           f'{"".join(labs)}'
           '<g id="mapRoutes" fill="none"></g>'
           '<g id="mapGlow" fill="none" filter="url(#mglow)"></g>'
           '<g id="mapDots"></g></svg>')
    return ('<div class="worldmap-wrap">'
            '<div class="wm-head"><span class="wm-title">&#9788; The Mercator Heatmap</span>'
            '<span class="wm-leg"><i class="lg-glow"></i> biggest drops &middot; into the buy zone</span></div>'
            f'{svg}'
            '<div class="wm-hint">Passages light up from the filters below &mdash; hover any glowing route for the fare.</div></div>')


def body_trip():
    return """<div class="wrap">
  <div class="pagehead"><h1>Journey Builder</h1><p>Chain the cheapest one-way hops into a trip. Start at a US airport, see the cheapest next stop anywhere, add it, then keep hopping &mdash; filter each leg by region. <b style="color:var(--gold)">Live fares.</b></p></div>
  <div class="tl-card">
    <div class="tl-form">
      <label>Start from<input id="j-origin" value="RDU" maxlength="3" autocomplete="off"></label>
      <label>Leave on/after<input id="j-date" type="date"></label>
      <button class="btn-primary tl-go" onclick="jStart()">Start journey</button>
      <button class="btn-ghost" id="j-removebtn" style="display:none" onclick="jRemove()">&larr; Remove last hop</button>
    </div>
    <div id="j-summary" class="j-summary" style="display:none"><div id="j-itin" class="j-itin"></div><div class="j-totalwrap">Trip total <span id="j-total" class="j-total">$0</span></div></div>
    <div id="j-nightsrow" class="j-nightsrow" style="display:none"><span id="j-staylabel"></span><label>Nights here<input id="j-nights" type="number" min="0" max="90" value="3" onchange="jOptions()"></label></div>
    <div id="j-curlabel" class="j-curlabel" style="display:none"></div>
    <div id="j-regions" class="airchips" style="display:none;margin:4px 0 12px"></div>
    <div class="panel"><div id="j-options"><div class="wl-hint">Enter your starting US airport (e.g. RDU) and click &ldquo;Start journey.&rdquo;</div></div></div>
  </div>
  <p class="finehint" style="text-align:center">Live one-way fares from Aviasales, fetched as you build. Each stop opens its booking page.</p>
</div>
<style>
  .j-summary{ display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; background:#0e141d; border:1px solid var(--line); border-radius:12px; padding:12px 14px; margin:4px 0 12px; }
  .j-itin{ display:flex; flex-wrap:wrap; align-items:center; gap:8px; }
  .j-stop{ display:inline-flex; flex-direction:column; align-items:center; background:var(--gold); color:var(--ink2); font-weight:700; border-radius:8px; padding:5px 10px; text-decoration:none; font-size:14px; line-height:1.1; }
  .j-stop small{ font-weight:600; font-size:10.5px; opacity:.85; }
  .j-stop.start{ background:transparent; color:var(--ink); border:1px solid var(--line); }
  .j-arrow{ color:var(--gold); font-weight:700; }
  .j-totalwrap{ font-size:13px; color:var(--muted); white-space:nowrap; } .j-total{ color:var(--gold); font-weight:700; font-size:18px; margin-left:6px; }
  .j-nightsrow{ display:flex; gap:14px; align-items:center; flex-wrap:wrap; margin:0 0 10px; font-size:13px; color:var(--muted); }
  .j-nightsrow label{ display:flex; gap:8px; align-items:center; }
  .j-nightsrow input{ width:64px; background:#0e141d; color:var(--ink); border:1px solid var(--line); border-radius:8px; padding:7px 9px; }
  .j-curlabel{ font-weight:600; margin:6px 0 8px; }
</style>
<script>
(function(){
var CC = __CCJS__;
var GROUPS={'SE Asia':'TH VN ID SG MY PH KH LA MM BN TL','E Asia':'JP KR CN TW HK MO MN','S Asia':'IN LK NP PK BD MV BT AF','C Asia':'KZ UZ KG TJ TM','W Europe':'FR GB DE NL BE IE ES PT IT CH AT LU MC AD LI MT','Nordic':'SE NO DK FI IS','E Europe':'PL CZ HU RO BG GR HR RS SK SI UA EE LV LT AL BA MK ME MD BY RU CY','S America':'BR AR CL CO PE EC UY PY BO VE GF SR GY','C America':'MX GT BZ SV HN NI CR PA','Caribbean':'DO JM BS CU HT PR TT BB AW CW GP MQ KY BM AG LC GD VC DM KN TC VG AI MS SX BQ','Oceania':'AU NZ FJ PF NC WS TO VU PG CK GU','Middle East':'AE QA SA IL JO TR LB KW BH OM IR IQ YE SY','Africa':'ZA EG MA KE ET NG GH TZ SN CI TN DZ UG RW MU SC NA BW ZW MZ AO CM GA','Canada':'CA'};
function tagsFor(code){ var c=CC[code]; if(!c) return ['Abroad']; if(c==='US') return ['USA']; var t=[]; for(var g in GROUPS){ if((' '+GROUPS[g]+' ').indexOf(' '+c+' ')>=0){ t.push(g); if(g==='SE Asia'||g==='E Asia'||g==='S Asia'||g==='C Asia') t.push('Asia'); break; } } if(c!=='CA') t.push('Abroad'); return t; }
var REGIONS=['all','USA','Abroad','Asia','SE Asia','E Asia','S Asia','W Europe','E Europe','Nordic','S America','C America','Caribbean','Oceania','Middle East','Africa','Canada'];
var JRNY=[], JREG='all', JOPTS=[];
function go(id){ return document.getElementById(id); }
window.jStart=function(){ JRNY=[]; JREG='all'; jRender(); jOptions(); };
window.jRemove=function(){ JRNY.pop(); JREG='all'; jRender(); jOptions(); };
function jOrigin(){ return JRNY.length? JRNY[JRNY.length-1].d : (go('j-origin').value||'RDU').trim().toUpperCase(); }
function jAfter(){ if(!JRNY.length) return go('j-date').value||''; var last=JRNY[JRNY.length-1]; var n=parseInt(go('j-nights').value,10); if(isNaN(n))n=0; var dt=new Date(last.date+'T00:00:00'); dt.setDate(dt.getDate()+n); return dt.toISOString().slice(0,10); }
function jRenderChips(){ var box=go('j-regions'); box.innerHTML=REGIONS.map(function(r){ var lab=r==='all'?'All':r; return '<button class="airchip'+(JREG===r?' on':'')+'" data-r="'+r+'">'+lab+'</button>'; }).join(''); }
window.jOptions=function(){ var o=jOrigin(); var out=go('j-options'); if(!/^[A-Z]{3}$/.test(o)){ out.innerHTML='<div class="wl-hint">Enter a 3-letter starting airport (e.g. RDU).</div>'; return; } var after=jAfter(); out.innerHTML='<div class="wl-hint">Finding onward flights from '+o+(after?(' on/after '+after):'')+'&hellip;</div>'; var months=[]; if(after){ var bd=new Date(after+'T00:00:00'); if(!isNaN(bd)){ for(var k=0;k<2;k++){ var dt=new Date(bd.getFullYear(), bd.getMonth()+k, 1); months.push(dt.getFullYear()+'-'+('0'+(dt.getMonth()+1)).slice(-2)); } } } var urls = months.length ? months.map(function(m){ return '/api/search?origin='+o+'&one_way=true&sorting=price&limit=1000&departure_at='+m; }) : ['/api/search?origin='+o+'&one_way=true&sorting=price&limit=1000']; Promise.all(urls.map(function(u){ return fetch(u).then(function(r){return r.json();}).then(function(j){ return (j&&j.data)||[]; }).catch(function(){ return []; }); })).then(function(arrs){ var data=[]; arrs.forEach(function(a){ data=data.concat(a); }); var visited={}; JRNY.forEach(function(l){visited[l.d]=1;}); visited[o]=1; var best={}; data.forEach(function(f){ var d=f.destination_airport; if(!d||visited[d]) return; if(JREG!=='all' && tagsFor(d).indexOf(JREG)<0) return; var dt=(f.departure_at||'').slice(0,10); if(after && dt && dt<after) return; if(!best[d]||f.price<best[d].price) best[d]=f; }); var list=Object.keys(best).map(function(k){return best[k];}); list.sort(function(a,b){return a.price-b.price;}); JOPTS=list.slice(0,60); if(!JOPTS.length){ out.innerHTML='<div class="wl-hint">No '+(JREG==='all'?'':JREG+' ')+'flights found onward from '+o+(after?(' on/after '+after):'')+'. Try another region'+(after?' or an earlier date':'')+'.</div>'; return; } out.innerHTML=JOPTS.map(function(f,i){ var d=f.destination_airport, dt=(f.departure_at||'').slice(0,10), p=Math.round(f.price); return '<div class="mv-row"><div class="mv-dest"><span class="emoji">&#9992;</span><div><div class="mv-name">'+d+'</div><div class="mv-air">'+o+' &rarr; '+d+' &middot; '+dt+'</div></div></div><div class="mv-right"><span class="mv-price">$'+p.toLocaleString()+'</span><button class="mini-book" style="border:0;cursor:pointer" onclick="jAdd('+i+')">Add hop</button></div></div>'; }).join(''); }).catch(function(){ out.innerHTML='<div class="wl-hint">Couldn&rsquo;t load hops &mdash; try again.</div>'; }); };
window.jAdd=function(i){ var f=JOPTS[i]; if(!f) return; JRNY.push({o:jOrigin(),d:f.destination_airport,date:(f.departure_at||'').slice(0,10),price:Math.round(f.price),link:f.link}); JREG='all'; jRender(); jOptions(); };
function jRender(){ var has=JRNY.length>0; go('j-summary').style.display=has?'flex':'none'; go('j-removebtn').style.display=has?'inline-block':'none'; go('j-nightsrow').style.display=has?'flex':'none'; go('j-curlabel').style.display='block'; go('j-regions').style.display='flex'; var start=(go('j-origin').value||'RDU').trim().toUpperCase(); var html='<span class="j-stop start">'+(JRNY.length?JRNY[0].o:start)+'</span>'; var total=0; JRNY.forEach(function(l){ total+=l.price; html+='<span class="j-arrow">&rarr;</span><a class="j-stop" href="'+l.link+'" target="_blank" rel="noopener" title="'+l.date+'">'+l.d+'<small>$'+l.price.toLocaleString()+'</small></a>'; }); go('j-itin').innerHTML=html; go('j-total').textContent='$'+total.toLocaleString(); var cur=jOrigin(); if(has){ go('j-staylabel').textContent='Staying in '+JRNY[JRNY.length-1].d+' —'; go('j-curlabel').textContent='Cheapest onward hops from '+cur+':'; } else { go('j-curlabel').textContent='Cheapest first hops from '+cur+':'; } jRenderChips(); }
var rbox=go('j-regions'); if(rbox){ rbox.addEventListener('click', function(e){ var b=e.target.closest('[data-r]'); if(b){ JREG=b.getAttribute('data-r'); jRenderChips(); jOptions(); } }); }
})();
</script>"""
def context_banner(body_html):
    ic = ('<svg class="cb-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
          'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/>'
          '<path d="M12 3v18M3 12h18"/><circle cx="12" cy="12" r="2.6"/></svg>')
    return f'<div class="context-banner">{ic}<p>{body_html}</p></div>'


Q_MOVERS = ('&ldquo;The sea is dangerous and its storms terrible, but these obstacles have never been '
            'sufficient reason to remain ashore.&rdquo; &mdash; Magellan. '
            '<span class="cb-em">Below are today&rsquo;s most volatile global route drops.</span>')
Q_INDICES = ('<span class="cb-em">Charting the unknown paths.</span> Each index tracks current fares against '
             'their Standard Meridian &mdash; the historical baseline &mdash; to pinpoint your ideal departure window.')


def featured_pool(market):
    """Routes trustworthy enough to feature — corroborated by recent history.
    Falls back to the whole board if nothing qualifies (early days)."""
    pool = [m for m in market if corroborated(m["code"], m["price"])]
    return pool if pool else market


def winner_highlight(market):
    ranked = sorted(featured_pool(market), key=lambda m: signal_for(m["price"], m["benchmark"])[1], reverse=True)
    if not ranked:
        return ""
    w = ranked[0]
    sig, pct = signal_for(w["price"], w["benchmark"])
    dates = f'{html.escape(w.get("depart",""))} &rarr; {html.escape(w.get("return",""))}' if w.get("return") else html.escape(w.get("depart",""))
    rng = price_range(w["code"], w["price"])
    rng_txt = f' &middot; tracking ${rng[0]:,.0f}&ndash;${rng[1]:,.0f}' if rng else ''
    vtxt = (' &middot; <span style="color:#4ed08a">Skyscanner-checked &#10003;</span>'
            if FEATURED_VERIFIED.get(w["code"]) else '')
    return (f'<a class="winner" href="blog.html">'
            f'<span class="winner-badge">&#9733; Today&rsquo;s Biggest Winner</span>'
            f'<div class="winner-main"><div class="winner-city">{html.escape(w["name"])}</div>'
            f'<div class="winner-route">Round-trip from {html.escape(w["origin"])} &middot; {dates} &middot; <span style="color:var(--gold)">tracked fare</span> &middot; live price at booking{rng_txt}{vtxt}</div></div>'
            f'<div class="winner-right"><span class="winner-price">${w["price"]:,.0f}</span>'
            f'<span class="winner-was">${w["benchmark"]:,.0f}</span>'
            f'<span class="winner-off">{pct:.0f}% off</span></div>'
            f'<span class="winner-cta">Read the Daily Guide &rarr;</span></a>')


def body_home(market, hist, cards, lastmin, oneway, summary):
    labels = [("summary", "Market summary"), ("indices", "Fare indices"),
              ("movers", "Biggest movers"), ("deals", "Cheapest trips"),
              ("lastminute", "Last-minute getaways"), ("oneway", "One-way escapes")]
    checks = "".join(f'<label><input type="checkbox" id="cb-{k}" onchange="toggleSec(\'{k}\')"> {lab}</label>'
                     for k, lab in labels)
    top4 = sorted(featured_pool(market), key=lambda m: signal_for(m["price"], m["benchmark"])[1], reverse=True)[:4]
    flash_section = ""
    if top4:
        fcards = "\n".join(card_html(m) for m in top4)
        flash_section = (f'<section class="home-sec"><div class="sec-head">'
                         f'<h2>&#128293; Today&rsquo;s top deals</h2><span>the 4 biggest price drops right now</span></div>'
                         f'<div class="grid">{fcards}</div></section>')
    nroutes = len(market)
    noneway = len(oneway)
    try:
        _cc = json.load(open(os.path.join(HERE, "code_cc.json"), encoding="utf-8"))
        ncountries = len({_cc.get(m["code"]) for m in market if _cc.get(m["code"])})
    except Exception:
        ncountries = nroutes
    nbook = sum(1 for m in market if signal_for(m["price"], m["benchmark"])[0] == "BOOK")
    return f"""<section class="lander">
  <div class="lander-glow"></div>
  <div class="lander-inner">
    <span class="eyebrow">&#9788; The world is closer than you think</span>
    <h1>Find the world&rsquo;s cheapest flights <span class="g">from anywhere.</span></h1>
    <p class="lead">Magellan tracks the lowest fares from any city to everywhere on earth, every day &mdash; and tells you when a price is a genuine deal. We built it to prove one thing: seeing the world costs far less than you&rsquo;ve been told.</p>
    <div class="cta-row">
      <a class="btn-primary" href="#deals">Explore today&rsquo;s deals</a>
      <a class="btn-ghost" href="world.html">Anywhere &rarr; Anywhere</a>
    </div>
    <p class="trust">Free, forever &middot; fares tracked through the day &middot; live price confirmed at booking &middot; <b>{nroutes}</b> routes &amp; <b>{noneway}+</b> one-ways across <b>{ncountries}</b> countries</p>
  </div>
</section>
<div class="wrap">
  <div class="summary" data-sec="summary" style="margin-top:6px">{summary}</div>
  <div class="statbar">
    <div class="stat"><div class="n">{nroutes}</div><div class="l">routes tracked</div></div>
    <div class="stat"><div class="n">{noneway}+</div><div class="l">one-way fares</div></div>
    <div class="stat"><div class="n">{nbook}</div><div class="l">flagged BUY today</div></div>
    <div class="stat"><div class="n">{ncountries}</div><div class="l">countries</div></div>
  </div>
  <p class="updated">{market_pulse(market)} &middot; tracked fares, refreshed through the day</p>
  {winner_highlight(market)}
  <div id="deals">{flash_section}</div>
  <p class="finehint" style="text-align:center">These are recently-tracked fares &mdash; tap any deal to see today&rsquo;s live price and book on Aviasales.</p>
  <div style="text-align:center;margin:26px 0 8px">
    <a class="btn-primary" href="market.html">See the full Market &rarr;</a>
    <p style="color:var(--muted);font-size:13.5px;margin:12px auto 0;max-width:560px">Fare indices, every biggest mover, today&rsquo;s cheapest trips, last-minute getaways and one-way deals &mdash; the whole board lives on the <a href="market.html" style="color:var(--gold)">Market</a> tab.</p>
  </div>
  <div class="section-head-lg"><h2>How we flag a deal</h2><p>Every route is measured against its own price history &mdash; its Standard Meridian.</p></div>
  <div class="why">
    <div class="why-card"><span class="sig s-book">BOOK</span><h3 style="margin-top:12px">20%+ below typical</h3><p>A genuinely rare low for this route. If the trip works, book it &mdash; prices this far down don&rsquo;t last.</p></div>
    <div class="why-card"><span class="sig s-watch">WATCH</span><h3 style="margin-top:12px">8&ndash;20% below typical</h3><p>A good price, a little under the route&rsquo;s normal range. Worth watching for a deeper drop.</p></div>
    <div class="why-card"><span class="sig s-wait">WAIT</span><h3 style="margin-top:12px">Near or above typical</h3><p>Around the usual price or higher. History suggests it&rsquo;s likely to fall &mdash; hold off for now.</p></div>
  </div>
  <section class="mission">
    <div class="astro lg" style="width:66px;margin:0 auto 14px">{ASTRO_SVG}</div>
    <h2>Why &ldquo;Magellan&rdquo;?</h2>
    <p>In 1519, Ferdinand Magellan set sail to prove the world could be crossed &mdash; and his expedition became the first to circle the entire globe. It was the moment the planet became reachable. Five centuries on, the world is more connected than ever, yet the cost of seeing it is wrapped in mystery and made to feel out of reach. Magellan Flights exists to pull back that curtain: to put the real numbers in your hands, show you that a week abroad can cost less than a weekend at home, and give the freedom of travel back to ordinary people.</p>
  </section>
  <section class="promise">
    <h2>Our promise to you</h2>
    <div class="promise-grid">
      <div class="pr"><span class="pr-n">01</span><p>Prices refreshed <b>twice every day</b> — never stale.</p></div>
      <div class="pr"><span class="pr-n">02</span><p>Every fare judged against <b>its own history</b>, so a deal is really a deal.</p></div>
      <div class="pr"><span class="pr-n">03</span><p><b>Always free.</b> We earn only if you book — at no extra cost to you.</p></div>
      <div class="pr"><span class="pr-n">04</span><p><b>No spam.</b> Alerts only when a price actually drops.</p></div>
    </div>
  </section>
</div>
{SIGNUP.replace("__FORM_ACTION__", FORM_ACTION)}"""

# --------------------------------------------------------------------------- #
# Daily Guide ("biggest winner of the day") content
# --------------------------------------------------------------------------- #
# YouTube channel config — fill these in once the Magellan Flights channel exists.
# CHANNEL: your handle URL e.g. "https://www.youtube.com/@magellanflights"
# VIDEOS: map an airport code to YOUR video id, e.g. {"SJU": "dQw4w9WgXcQ"}
YT_CHANNEL = "https://www.youtube.com/@MagellanFlights"
YT_VIDEOS = {}


CITY_GUIDE = {
    "SJU": {"overview": "San Juan blends 500 years of Spanish-colonial history with Caribbean beaches and salsa-filled nights — and as part of the US, no passport is needed for Americans.",
            "todo": ["Wander the blue-cobblestone streets of Old San Juan", "Tour the clifftop forts El Morro and Castillo San Cristobal", "Relax on Condado and Isla Verde beaches", "Kayak the bioluminescent bay in nearby Fajardo", "Day-trip into El Yunque rainforest"],
            "history": "Founded in 1521, San Juan is one of the oldest European-settled cities in the Americas. Its massive fortifications were built by Spain to guard the gateway to the New World and are now a UNESCO World Heritage Site.",
            "culture": "Puerto Rican culture mixes Spanish, Taino and African roots — heard in reggaeton and salsa and tasted in mofongo and lechon. Locals are warm and family-centered, and life moves at an easy island pace."},
    "SJD": {"overview": "Los Cabos sits where the desert meets the sea at the tip of Baja California, pairing dramatic rock arches with resort beaches and world-class sportfishing.",
            "todo": ["Photograph El Arco at Land's End by boat", "Swim and snorkel at Playa del Amor", "Whale-watch (Dec-Apr)", "Stroll the San Jose del Cabo art district", "Sunset on the Cabo San Lucas marina"],
            "history": "Long home to the Pericu people, the area was settled around Spanish missions in the 1700s and grew into a sportfishing haven in the 20th century before becoming a major resort destination.",
            "culture": "Northern Mexican culture here is laid-back and maritime — fresh seafood, ranchera music and a strong fishing tradition, with tourism shaping the modern, bilingual feel of the towns."},
    "CUN": {"overview": "Cancun fronts the Caribbean with powder-white sand and turquoise water, and serves as the gateway to the Riviera Maya's cenotes and Maya ruins.",
            "todo": ["Beach days along the Hotel Zone", "Snorkel the Mesoamerican Reef", "Swim in a jungle cenote", "Explore Tulum or Chichen Itza", "Ferry to Isla Mujeres"],
            "history": "Cancun was a small fishing area until the Mexican government developed it as a planned resort in the 1970s; the surrounding Yucatan holds some of the greatest Maya cities.",
            "culture": "Yucatecan culture fuses Maya and Spanish heritage — distinctive cuisine like cochinita pibil, lively festivals, and a deep connection to ancient sites."},
    "MEX": {"overview": "Mexico City is a high-altitude megacity of world-class museums, leafy plazas and one of the planet's great food scenes, layered over an ancient Aztec capital.",
            "todo": ["Walk the Zocalo and Templo Mayor", "See Frida Kahlo's Casa Azul", "Float the canals of Xochimilco", "Visit the Teotihuacan pyramids", "Eat tacos al pastor across Roma and Condesa"],
            "history": "Built on the Aztec island-capital of Tenochtitlan (founded 1325), it became the heart of New Spain after 1521 and today is the largest city in North America.",
            "culture": "Mexican culture is vibrant and deeply traditional — Day of the Dead, mariachi, muralism, and a profound culinary heritage recognized by UNESCO."},
    "PUJ": {"overview": "Punta Cana is the Dominican Republic's beach capital — miles of palm-lined Caribbean coast, all-inclusive resorts and easy island adventures.",
            "todo": ["Lounge on Bavaro Beach", "Catamaran to natural pools", "Zipline and buggy through the countryside", "Snorkel offshore reefs", "Day-trip to Saona Island"],
            "history": "Hispaniola was the site of the first permanent European settlement in the Americas (1490s); Punta Cana itself developed from the 1970s as tourism took off.",
            "culture": "Dominican culture is merengue and bachata, baseball, and friendly hospitality, with a Spanish-Caribbean rhythm to daily life."},
    "MBJ": {"overview": "Montego Bay is Jamaica's resort hub, ringed by reefs and beaches and backed by green hills, with reggae and jerk smoke in the air.",
            "todo": ["Swim at Doctor's Cave Beach", "Float down the Martha Brae river", "Climb nearby Dunn's River Falls", "Tour a great house plantation estate", "Hit the bars on the Hip Strip"],
            "history": "Named by the Spanish, long a sugar-trading port under British rule, Montego Bay grew into a tourism center in the 20th century.",
            "culture": "Jamaican culture gave the world reggae and Rastafari; expect patois, jerk cuisine, and a famously easygoing 'no problem' attitude."},
    "AUA": {"overview": "Aruba is a sunny, arid Dutch-Caribbean island just off Venezuela, known for calm white beaches, steady trade winds and a reliably dry climate.",
            "todo": ["Relax on Eagle and Palm Beaches", "Explore Arikok National Park", "Snorkel the Antilla shipwreck", "Stroll colorful Oranjestad", "Watch sunset at the California Lighthouse"],
            "history": "Inhabited by the Caquetio, claimed by Spain then the Dutch, Aruba is now an autonomous country within the Kingdom of the Netherlands.",
            "culture": "Aruban culture is a Dutch-Caribbean-Latin blend; locals often speak Papiamento, Dutch, Spanish and English, and the island is known for its safety and hospitality."},
    "BOG": {"overview": "Bogota is Colombia's high-Andean capital — a cool, energetic city of colonial plazas, gold-filled museums and a buzzing food and coffee culture.",
            "todo": ["Ride the funicular up Monserrate", "Wander colonial La Candelaria", "See the Gold Museum and Botero Museum", "Browse Paloquemao market", "Day-trip to the Zipaquira salt cathedral"],
            "history": "Founded in 1538 on a Muisca homeland, Bogota became the capital of Gran Colombia and remains the country's political and cultural center.",
            "culture": "Colombian culture is warm and diverse — cumbia and vallenato, world-renowned coffee, and a strong cafe and arts scene in the capital."},
    "LIS": {"overview": "Lisbon tumbles over seven hills above the Tagus river — pastel facades, rattling trams, miradouro viewpoints and melancholic fado music.",
            "todo": ["Ride Tram 28 through Alfama", "Tour Belem Tower and Jeronimos Monastery", "Eat a warm pastel de nata", "Catch sunset from a miradouro", "Day-trip to fairytale Sintra"],
            "history": "One of Europe's oldest cities, Lisbon was a Moorish stronghold, then the launch point of Portugal's Age of Discovery; it was largely rebuilt after the 1755 earthquake.",
            "culture": "Portuguese culture is soulful and seafaring — fado, grilled sardines, tiled azulejos, and a gentle, welcoming pace."},
    "KEF": {"overview": "Reykjavik is the gateway to Iceland's otherworldly landscapes — geysers, glaciers, waterfalls and, in winter, the northern lights.",
            "todo": ["Soak in the Blue Lagoon", "Drive the Golden Circle (geyser, falls, rift)", "Hunt the aurora (Sep-Apr)", "Walk colorful downtown Reykjavik", "Watch whales from the old harbor"],
            "history": "Settled by Norse Vikings in the 9th century, Iceland founded one of the world's oldest parliaments in 930 AD; Reykjavik grew into the capital of a modern, independent nation.",
            "culture": "Icelandic culture prizes literature, design and a deep bond with nature; locals are reserved but friendly, and the country is among the world's safest."},
    "DUB": {"overview": "Dublin is a literary, pub-loving city on the Liffey — Georgian streets, lively music and centuries of history within easy reach of green coastline.",
            "todo": ["See the Book of Kells at Trinity College", "Tour the Guinness Storehouse", "Hear trad music in Temple Bar", "Visit Kilmainham Gaol", "Walk the coast to Howth"],
            "history": "Founded as a Viking settlement around 841, Dublin became the center of British rule in Ireland and the heart of the country's fight for independence.",
            "culture": "Irish culture is famed for storytelling, music and warmth — a city of writers (Joyce, Wilde) where conversation in the pub is an art form."},
    "BKK": {"overview": "Bangkok is a high-energy Thai capital of glittering temples, street-food stalls and buzzing markets, where ancient and ultramodern collide.",
            "todo": ["See the Grand Palace and Wat Pho's reclining Buddha", "Take a longtail boat through the canals", "Eat through a night market", "Browse Chatuchak weekend market", "Day-trip to Ayutthaya's ruins"],
            "history": "Bangkok became Siam's capital in 1782 under the Chakri dynasty and grew into one of Southeast Asia's largest and most dynamic cities.",
            "culture": "Thai culture is gracious and Buddhist at its core — the wai greeting, reverence for the monarchy and monks, and one of the world's great street-food traditions."},
    "ATH": {"overview": "Athens is the cradle of Western civilization, where ancient marble ruins overlook a lively modern city of tavernas, markets and seaside suburbs.",
            "todo": ["Climb the Acropolis and Parthenon", "Explore the Acropolis Museum", "Wander Plaka's old streets", "Watch sunset from Lycabettus Hill", "Day-trip to Cape Sounion"],
            "history": "Inhabited for over 3,000 years, Athens was the birthplace of democracy and philosophy in the 5th century BC and remains rich with classical monuments.",
            "culture": "Greek culture centers on family, food and philoxenia (hospitality) — long meals, strong coffee, and pride in an ancient heritage."},
    "IST": {"overview": "Istanbul straddles Europe and Asia across the Bosphorus — a city of imperial mosques, grand bazaars and layered Byzantine and Ottoman history.",
            "todo": ["Visit Hagia Sophia and the Blue Mosque", "Explore Topkapi Palace", "Haggle in the Grand Bazaar", "Cruise the Bosphorus", "Soak in a historic hammam"],
            "history": "Founded as Byzantium, it became Constantinople, capital of the Roman/Byzantine empire, then the Ottoman capital after 1453 — a crossroads of civilizations for 2,000 years.",
            "culture": "Turkish culture bridges East and West — tea gardens, hospitality, a renowned cuisine, and the daily rhythm of the call to prayer."},
    "DXB": {"overview": "Dubai is a futuristic desert metropolis of record-breaking towers, mega-malls and luxury beaches, with old trading roots along its creek.",
            "todo": ["Ascend the Burj Khalifa", "Desert safari with dune-bashing", "Shop the Dubai Mall and watch the fountains", "Wander the gold and spice souks", "Relax on Jumeirah Beach"],
            "history": "A small pearling and trading port on the creek, Dubai transformed within a generation after oil and then global trade and tourism made it a 21st-century hub.",
            "culture": "Emirati culture is rooted in Bedouin and Islamic tradition within an ultra-international city; dress modestly at religious sites and note strict laws on alcohol and conduct."},
    "RAK": {"overview": "Marrakech is Morocco's 'Red City' — a sensory swirl of souks, palaces and gardens behind ochre walls, with the Atlas Mountains on the horizon.",
            "todo": ["Get lost in the medina souks", "Experience Jemaa el-Fnaa square at night", "Visit the Bahia Palace and Saadian Tombs", "Relax in the Jardin Majorelle", "Day-trip to the Atlas Mountains"],
            "history": "Founded in 1070 as an imperial capital, Marrakech was a center of trade and learning on caravan routes across the Sahara.",
            "culture": "Moroccan culture is Arab-Berber and deeply hospitable — mint tea rituals, tagines, intricate craft, and lively bargaining in the souks."},
    "CAI": {"overview": "Cairo sprawls along the Nile beside the last surviving ancient wonder — a chaotic, fascinating capital of pharaonic treasures and Islamic architecture.",
            "todo": ["Stand before the Pyramids and Sphinx at Giza", "See Tutankhamun's treasures at the museum", "Wander Islamic Cairo and Khan el-Khalili", "Cruise the Nile at sunset", "Explore Coptic Cairo"],
            "history": "Near ancient Memphis and the 4,500-year-old Giza pyramids, Cairo was founded in 969 AD and became a great center of the Islamic world.",
            "culture": "Egyptian culture is warm and lively, blending ancient pride with Arab and Islamic tradition; dress modestly and expect spirited markets."},
    "BCN": {"overview": "Barcelona pairs Mediterranean beaches with Gaudi's surreal architecture, Gothic lanes and a famous food-and-football culture.",
            "todo": ["Marvel at the Sagrada Familia", "Stroll Park Guell", "Wander the Gothic Quarter and Las Ramblas", "Relax on Barceloneta beach", "Graze a tapas crawl"],
            "history": "Roman in origin and later a powerful Mediterranean trading city, Barcelona is the proud capital of Catalonia with its own language and identity.",
            "culture": "Catalan culture is distinct and creative — late dinners, vermouth hour, human-tower castells, and intense devotion to FC Barcelona."},
    "CTG": {"overview": "Cartagena de Indias is the Caribbean jewel of Colombia's coast — a walled colonial old town of candy-colored facades and flower-draped balconies, ringed by fortress walls, palm-lined plazas and easy island getaways.",
            "todo": ["Wander the walled Old Town and Plaza Santo Domingo", "Watch the sunset over the sea from the Cafe del Mar city walls", "Explore the Castillo San Felipe de Barajas fortress", "Soak up the street art, bars and nightlife of Getsemani", "Boat to the Rosario Islands and Playa Blanca for white sand", "Step into the Palace of the Inquisition in the historic center"],
            "history": "Founded in 1533, Cartagena became Spain's great fortified treasure port, where gold and silver were gathered before the long voyage to Europe. Its massive walls and forts were built to fend off pirates and privateers, and the Old City is now a UNESCO World Heritage Site.",
            "culture": "Cartagena pulses with Afro-Caribbean and Spanish-colonial rhythm — champeta and cumbia, fresh ceviche and coconut rice, and a warm, festive street life. Spanish is the language, and the tropical heat runs hot and humid year-round, with the driest, breeziest weather from December to April."},
    "MDE": {"overview": "Medellin is Colombia's reinvented \"City of Eternal Spring\" — a green Andean valley city with near-perfect weather year-round, gondolas climbing the hillsides, flower-filled plazas and one of Latin America's most remarkable urban comeback stories.",
            "todo": ["Ride the Metrocable gondolas over the hillside barrios", "Tour transformed Comuna 13 with its escalators and street art", "Stroll Plaza Botero and the Botero sculptures", "Day-trip to El Penol rock and colorful Guatape", "Wander El Poblado's cafes, restaurants and nightlife"],
            "history": "Founded in 1616 and long an industrial and coffee-trade hub, Medellin became infamous for cartel violence in the 1980s-90s, then engineered a celebrated turnaround with bold public transit, libraries and parks that made it a global model for urban renewal.",
            "culture": "Paisa culture is proud, entrepreneurial and warm — sweeping mountain views, the hearty bandeja paisa, salsa and reggaeton (the city birthed global stars), and a spring-like climate that keeps life outdoors all year."},
}


def body_blog(market):
    ranked = sorted(featured_pool(market), key=lambda m: signal_for(m["price"], m["benchmark"])[1], reverse=True)
    if not ranked:
        return '<div class="wrap"><div class="pagehead"><h1>Daily Guide</h1><p>No deals to feature yet today.</p></div></div>'
    win = ranked[0]
    code = win["code"]
    sig, pct = signal_for(win["price"], win["benchmark"])
    g = CITY_GUIDE.get(code)
    info = DEST_INFO.get(code, {"lang": "the local language", "eng": "varies", "visa": "Check entry requirements for US passports", "safe": "Check your government's latest travel advisory", "note": "Verify details before booking"})
    name = win["name"]
    link = html.escape(win["link"], quote=True)
    best = BEST_TIME.get(code, "year-round")
    dates = f'{html.escape(win.get("depart",""))} &rarr; {html.escape(win.get("return",""))}' if win.get("return") else html.escape(win.get("depart",""))
    if g:
        overview = g["overview"]; history = g["history"]; culture = g["culture"]
        todo = "".join(f"<li>{html.escape(t)}</li>" for t in g["todo"])
    else:
        overview = f"{html.escape(name)} is today's standout deal from our tracker. We don't have a full guide written for it yet, but here are the essentials to help you decide."
        history = "We're still writing the full history for this destination — check back soon."
        culture = f"Locals speak {html.escape(info['lang'])}. {html.escape(info['note'])}."
        todo = "<li>Explore the historic center and main squares</li><li>Try the regional cuisine and markets</li><li>Visit the top museums and landmarks</li><li>Take a popular day-trip nearby</li>"
    todo_block = f"<ul class='blog-list'>{todo}</ul>" if todo else ""
    series = HIST_SERIES.get(code, [])
    spark = sparkline_svg(series)
    if len(series) >= 2:
        lo = min(series)
        if win["price"] <= lo:
            verdict = f"We&rsquo;ve tracked {len(series)} days of fares to {html.escape(name.split(',')[0])} &mdash; today&rsquo;s ${win['price']:,.0f} is the <b>lowest we&rsquo;ve logged</b>. Strong time to book."
        else:
            verdict = f"Tracked {len(series)} days. Today&rsquo;s ${win['price']:,.0f} sits above the ${lo:,.0f} low we&rsquo;ve seen &mdash; it may dip again, so watch it."
    else:
        verdict = "We just started logging this route &mdash; the trend line fills in a little more every day."
    cityshort = name.split(",")[0].strip()
    _vid = YT_VIDEOS.get(code, "")
    _sub = (YT_CHANNEL + ("&" if "?" in YT_CHANNEL else "?") + "sub_confirmation=1") if YT_CHANNEL else ""
    if _vid:
        watch_html = (f'<div class="blog-embed"><iframe src="https://www.youtube.com/embed/{_vid}" '
                      f'title="{html.escape(cityshort)} guide" frameborder="0" '
                      f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" '
                      f'allowfullscreen></iframe></div>'
                      f'<a class="yt-sub" href="{_sub}" target="_blank" rel="noopener">&#9654; Subscribe on YouTube</a>')
    elif YT_CHANNEL:
        watch_html = (f'<a class="blog-video" href="{_sub}" target="_blank" rel="noopener">'
                      f'<span class="bv-play">&#9654;</span><span class="bv-text">A <b>{html.escape(cityshort)}</b> video guide is on the way &mdash; '
                      f'<b style="color:var(--gold)">subscribe</b> so you don&rsquo;t miss it.</span></a>')
    else:
        watch_html = '<div class="blog-soon">&#127909; Video guide coming soon</div>' 
    return f"""<div class="wrap blog-wrap">
  <div class="blog-eyebrow">&#9733; Today&rsquo;s Biggest Winner &middot; biggest price drop on the board</div>
  <h1 class="blog-title">{html.escape(name)}</h1>
  <div class="blog-deal">
    <div><div class="blog-deal-label">Round-trip from {html.escape(win['origin'])}</div><div class="blog-deal-dates">{dates} &middot; best time to go: {html.escape(best)}</div></div>
    <div class="blog-deal-right"><span class="blog-price">${win['price']:,.0f}</span><span class="blog-was">was ~${win['benchmark']:,.0f}</span><span class="sig s-book">{sig} &middot; {pct:.0f}% off</span><a class="book" href="{link}" target="_blank" rel="noopener">See live price &amp; book &rarr;</a></div>
  </div>
  <section class="blog-sec"><h2>The overview</h2><p>{html.escape(overview) if g else overview}</p></section>
  <section class="blog-sec"><h2>&#128200; Price trend</h2><div class="blog-spark">{spark}</div><p>{verdict}</p></section>
  <section class="blog-sec"><h2>&#128205; Top things to do</h2>{todo_block}</section>
  <section class="blog-sec"><h2>&#9654;&#65039; Watch a tour</h2>{watch_html}</section>
  <section class="blog-sec"><h2>&#128737; Is it safe?</h2><p>{html.escape(info['safe'])}. As anywhere, watch your belongings in crowds and tourist areas. Visa for US passports: {html.escape(info['visa'])}. Always check your government&rsquo;s current travel advisory before you go.</p></section>
  <section class="blog-sec"><h2>&#128220; A bit of history</h2><p>{html.escape(history) if g else history}</p></section>
  <section class="blog-sec"><h2>&#127757; Culture &amp; language</h2><p>{html.escape(culture) if g else culture}</p><p class="blog-lang"><b>Language:</b> {html.escape(info['lang'])} &middot; <b>English spoken:</b> {html.escape(info['eng'])}</p></section>
  <div class="blog-cta"><a class="btn-primary" href="{link}" target="_blank" rel="noopener">Grab the {html.escape(name.split(',')[0])} deal &rarr;</a><a class="btn-ghost" href="explore.html">Find your own deal</a></div>
  <p class="finehint" style="text-align:center;margin-top:18px">Updated daily with whichever destination has the biggest price drop. Prices are recently-tracked fares &mdash; your live price is confirmed when you book on Aviasales. Safety and visa notes are general guidance for US travelers &mdash; verify official sources before booking.</p>
</div>"""
def body_market(market, hist, cards, lastmin, oneway):
    return f"""<div class="wrap">
  <div class="pagehead"><h1>The Market</h1><p>The full board &mdash; region indices, biggest movers, today&rsquo;s cheapest trips, last-minute getaways and one-way deals.</p></div>
  <div class="summary">{market_pulse(market)}</div>
  <div class="sec-head" id="market"><h2>Fare indices</h2><span>avg vs. the Standard Meridian, by region</span></div>
  {context_banner(Q_INDICES)}
  <div class="indices">{index_cards(market, hist)}</div>
  <div class="sec-head"><h2>Today's biggest movers</h2><span>signal: book / watch / wait</span></div>
  {context_banner(Q_MOVERS)}
  <div id="mv-chips" class="airchips" style="margin:2px 0 10px">
    <button class="airchip on" data-mv="all" onclick="mvFilter('all')">All</button>
    <button class="airchip" data-mv="Asia" onclick="mvFilter('Asia')">Asia</button>
    <button class="airchip" data-mv="Europe" onclick="mvFilter('Europe')">Europe</button>
    <button class="airchip" data-mv="Americas" onclick="mvFilter('Americas')">Americas</button>
    <button class="airchip" data-mv="Middle East" onclick="mvFilter('Middle East')">Middle East</button>
    <button class="airchip" data-mv="Oceania" onclick="mvFilter('Oceania')">Oceania</button>
    <button class="airchip" data-mv="Africa" onclick="mvFilter('Africa')">Africa</button>
  </div>
  <div id="mv-head" class="mv-head"><span style="font-size:12px;color:var(--muted);margin-right:auto">Sort &rarr;</span><button class="mv-sortbtn" data-k="price" onclick="mvSort('price')">Price <span class="mv-ar">&#8597;</span></button><button class="mv-sortbtn on" data-k="pct" onclick="mvSort('pct')">% off <span class="mv-ar">&#9660;</span></button></div>
  <div class="panel"><div id="movers-list">{movers_html(market)}</div></div>
  <button id="mv-more" class="mv-more" onclick="mvToggleMore()" style="display:none"></button>
  <script>
  var MV_REGION='all', MV_SORT='pct', MV_EXPANDED=false, MV_DIR={{price:'asc', pct:'desc'}};
  function mvFilter(reg){{ MV_REGION=reg; var lim=MV_EXPANDED?9999:5; var rows=document.querySelectorAll('#movers-list .mv-row'); var shown=0, matched=0; for(var i=0;i<rows.length;i++){{ var rr=rows[i].getAttribute('data-region'); var m=(reg==='all')||(rr===reg); if(m){{ matched++; if(shown<lim){{ rows[i].style.display=''; shown++; }} else {{ rows[i].style.display='none'; }} }} else {{ rows[i].style.display='none'; }} }} var chips=document.querySelectorAll('#mv-chips .airchip'); for(var k=0;k<chips.length;k++){{ chips[k].classList.toggle('on', chips[k].getAttribute('data-mv')===reg); }} var more=document.getElementById('mv-more'); if(more){{ if(matched>5){{ more.style.display='block'; more.innerHTML=MV_EXPANDED?('Show less &#9652;'):('Show all '+matched+' &#9662;'); }} else {{ more.style.display='none'; }} }} }}
  function mvNum(el,sel){{ var n=el.querySelector(sel); if(!n) return 0; var v=parseInt((n.textContent||'').replace(/[^0-9]/g,''),10); return isNaN(v)?0:v; }}
  function mvArrows(){{ var btns=document.querySelectorAll('#mv-head .mv-sortbtn'); for(var i=0;i<btns.length;i++){{ var k=btns[i].getAttribute('data-k'); var ar=btns[i].querySelector('.mv-ar'); if(k===MV_SORT){{ btns[i].classList.add('on'); ar.innerHTML=(MV_DIR[k]==='asc')?'&#9650;':'&#9660;'; }} else {{ btns[i].classList.remove('on'); ar.innerHTML='&#8597;'; }} }} }}
  function mvSort(key){{ if(MV_SORT===key){{ MV_DIR[key]=(MV_DIR[key]==='asc')?'desc':'asc'; }} MV_SORT=key; var dir=MV_DIR[key]; var sel=(key==='price')?'.mv-price':'.down'; var box=document.getElementById('movers-list'); var rows=[].slice.call(box.querySelectorAll('.mv-row')); rows.sort(function(a,b){{ var av=mvNum(a,sel), bv=mvNum(b,sel); return dir==='asc'?(av-bv):(bv-av); }}); for(var r=0;r<rows.length;r++){{ box.appendChild(rows[r]); }} mvArrows(); mvFilter(MV_REGION); }}
  function mvToggleMore(){{ MV_EXPANDED=!MV_EXPANDED; mvFilter(MV_REGION); }}
  mvArrows(); mvFilter('all'); setTimeout(function(){{ mvFilter(MV_REGION); }}, 60); window.addEventListener('load', function(){{ mvFilter(MV_REGION); }});
  </script>
  <div class="sec-head" id="deals"><h2>Today's cheapest trips</h2><span>tap to book</span></div>
  <div class="grid">{cards}</div>
  <div class="sec-head"><h2>&#9889; Last-minute getaways</h2><span><a href="lastminute.html">see all &rarr;</a></span></div>
  <div class="panel">{lastminute_html(lastmin, 8)}</div>
  <div class="sec-head"><h2>One-way deals</h2><span><a href="explore.html">one-way explorer &rarr;</a></span></div>
  <div class="panel">{oneway_html(oneway, 8)}</div>
</div>"""


def body_explore():
    return """<div class="wrap">
  <div class="pagehead"><h1>Explore</h1><p>Two ways to search: leave <b>To</b> empty to see the cheapest deals to <b>anywhere</b> from your home airport(s) &mdash; or type a destination (e.g. BKK, HNL) to track a <b>specific route</b> and see every fare we have for it. Add several home airports and we&rsquo;ll find the cheapest across all of them. Star any deal to save it.</p></div>
  <div class="tl-card">
    <div class="tl-form" style="align-items:flex-end">
      <div style="display:flex;flex-direction:column;gap:5px">
        <span style="font-size:12px;color:var(--muted)">From (add one or more airports)</span>
        <div style="display:flex;gap:6px"><input id="ex-add" maxlength="3" placeholder="e.g. CLT" autocomplete="off" style="width:96px;background:#0e141d;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:9px 10px" onkeydown="if(event.key==='Enter'){exAddOrig();return false;}"><button class="airchip" onclick="exAddOrig()">+ Add airport</button></div>
        <div id="ex-origs" class="airchips"></div>
      </div>
      <label style="display:flex;flex-direction:column;gap:5px;font-size:12px;color:var(--muted)">To (optional)<input id="ex-to" maxlength="3" placeholder="anywhere" autocomplete="off" style="width:110px;background:#0e141d;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:9px 10px;text-transform:uppercase" onkeydown="if(event.key==='Enter'){exSearch();return false;}"></label>
      <div style="display:flex;flex-direction:column;gap:5px"><span style="font-size:12px;color:var(--muted)">Trip</span><div class="airchips"><button class="airchip on" id="ex-rt-rt" onclick="exSetTrip('round')">Round-trip</button><button class="airchip" id="ex-rt-ow" onclick="exSetTrip('oneway')">One-way</button></div></div>
      <button class="btn-primary tl-go" onclick="exSearch()">Find deals</button>
    </div>
    <div id="ex-when" style="margin:8px 0 2px"><span style="font-size:12px;color:var(--muted);margin-right:6px">When (anywhere mode):</span><span class="airchips" style="display:inline-flex"><button class="airchip on" id="ex-wh-any" onclick="exSetWhen('any')">Anytime</button><button class="airchip" id="ex-wh-soon" onclick="exSetWhen('soon')">&#9889; Soon</button></span></div>
    <div id="ex-regions" class="airchips" style="margin:6px 0 12px"></div>
    <div class="panel"><div id="ex-out"><div class="wl-hint">Add your home airport(s) and hit &ldquo;Find deals.&rdquo;</div></div></div>
  </div>
  <p class="finehint" style="text-align:center">Live fares from Aviasales. Star &#9734; a deal to add it to your Bucket List. Want to chain multiple stops into one trip? Use the <a href="trip.html" style="color:var(--gold)">Journey</a> tab.</p>
</div>
<script>
(function(){
var CC = __CCJS__;
var GROUPS={'SE Asia':'TH VN ID SG MY PH KH LA MM BN TL','E Asia':'JP KR CN TW HK MO MN','S Asia':'IN LK NP PK BD MV BT AF','C Asia':'KZ UZ KG TJ TM','W Europe':'FR GB DE NL BE IE ES PT IT CH AT LU MC AD LI MT','Nordic':'SE NO DK FI IS','E Europe':'PL CZ HU RO BG GR HR RS SK SI UA EE LV LT AL BA MK ME MD BY RU CY','S America':'BR AR CL CO PE EC UY PY BO VE GF SR GY','C America':'MX GT BZ SV HN NI CR PA','Caribbean':'DO JM BS CU HT PR TT BB AW CW GP MQ KY BM AG LC GD VC DM KN TC VG AI MS SX BQ','Oceania':'AU NZ FJ PF NC WS TO VU PG CK GU','Middle East':'AE QA SA IL JO TR LB KW BH OM IR IQ YE SY','Africa':'ZA EG MA KE ET NG GH TZ SN CI TN DZ UG RW MU SC NA BW ZW MZ AO CM GA','Canada':'CA'};
function tagsFor(code){ var c=CC[code]; if(!c) return ['Abroad']; if(c==='US') return ['USA']; var t=[]; for(var g in GROUPS){ if((' '+GROUPS[g]+' ').indexOf(' '+c+' ')>=0){ t.push(g); if(g==='SE Asia'||g==='E Asia'||g==='S Asia'||g==='C Asia') t.push('Asia'); break; } } if(c!=='CA') t.push('Abroad'); return t; }
var REGIONS=['all','USA','Abroad','Asia','SE Asia','E Asia','S Asia','W Europe','E Europe','Nordic','S America','C America','Caribbean','Oceania','Middle East','Africa','Canada'];
function go(id){ return document.getElementById(id); }
var EX_TRIP='round', EX_WHEN='any', EX_REG='all', EX_DATA=[], EX_SHOWN=[], EX_ORIG=['RDU'], EX_P2P=false;
function bucket(){ try{ return JSON.parse(localStorage.getItem('mf_bucket')||'[]'); }catch(e){ return []; } }
function saved(id){ return bucket().some(function(x){ return x.id===id; }); }
function renderOrigs(){ var box=go('ex-origs'); if(!box) return; box.innerHTML=EX_ORIG.map(function(c){ return '<button class="airchip on" data-o="'+c+'" title="remove">'+c+' &times;</button>'; }).join(''); }
window.exAddOrig=function(){ var v=(go('ex-add').value||'').trim().toUpperCase(); if(!/^[A-Z]{3}$/.test(v)){ go('ex-add').focus(); return; } if(EX_ORIG.indexOf(v)<0) EX_ORIG.push(v); go('ex-add').value=''; renderOrigs(); exSearch(); };
window.exSetTrip=function(t){ EX_TRIP=t; go('ex-rt-rt').classList.toggle('on',t==='round'); go('ex-rt-ow').classList.toggle('on',t==='oneway'); exSearch(); };
window.exSetWhen=function(w){ EX_WHEN=w; go('ex-wh-any').classList.toggle('on',w==='any'); go('ex-wh-soon').classList.toggle('on',w==='soon'); if(!EX_P2P) exFilter(); };
function renderChips(){ go('ex-regions').innerHTML=REGIONS.map(function(r){ var lab=r==='all'?'All':r; return '<button class="airchip'+(EX_REG===r?' on':'')+'" data-r="'+r+'">'+lab+'</button>'; }).join(''); }
window.exSearch=function(){ if(!EX_ORIG.length){ EX_ORIG=['RDU']; renderOrigs(); } var ow=(EX_TRIP==='oneway'?'true':'false'); var to=(go('ex-to').value||'').trim().toUpperCase(); var when=''; EX_P2P=/^[A-Z]{3}$/.test(to); go('ex-regions').style.display=EX_P2P?'none':'flex'; go('ex-when').style.display=EX_P2P?'none':'block';
  if(EX_P2P){
    go('ex-out').innerHTML='<div class="wl-hint">Finding '+(EX_TRIP==='oneway'?'one-way':'round-trip')+' fares to '+to+' from '+EX_ORIG.join(', ')+(when?(' around '+when):'')+'&hellip;</div>';
    var calls=EX_ORIG.map(function(o){ return fetch('/api/search?origin='+o+'&destination='+to+'&one_way='+ow+'&sorting=route&limit=100').then(function(r){return r.json();}).then(function(j){ return (j&&j.data)||[]; }).catch(function(){ return []; }); });
    Promise.all(calls).then(function(arrs){ var all=[]; arrs.forEach(function(d){ all=all.concat(d); }); all=all.filter(function(f){ return f.destination_airport===to && f.departure_at; }); var seen={}; all.forEach(function(f){ var key=f.origin_airport+'|'+(f.departure_at||'').slice(0,10); if(!seen[key]||f.price<seen[key].price) seen[key]=f; }); var list=Object.keys(seen).map(function(k){return seen[k];}); if(when){ var only=list.filter(function(f){ return (f.departure_at||'').slice(0,10)>=when; }); if(only.length) list=only; } list.sort(function(a,b){ var da=(a.departure_at||'').slice(0,10), db=(b.departure_at||'').slice(0,10); if(da!==db) return da<db?-1:1; return a.price-b.price; }); EX_DATA=list; EX_SHOWN=list.slice(0,40); exRender(); if(!list.length){ go('ex-out').innerHTML='<div class="wl-hint">We don&rsquo;t have cached fares for '+EX_ORIG.join('/')+' &rarr; '+to+' right now. Try a major hub (JFK, LAX, ORD) as a From airport, or remove the date.</div>'; } }).catch(function(){ go('ex-out').innerHTML='<div class="wl-hint">Couldn&rsquo;t load that route &mdash; try again.</div>'; });
    return;
  }
  go('ex-out').innerHTML='<div class="wl-hint">Finding the cheapest '+(EX_TRIP==='oneway'?'one-way':'round-trip')+' fares from '+EX_ORIG.join(', ')+'&hellip;</div>'; var origset={}; EX_ORIG.forEach(function(o){origset[o]=1;}); var calls2=EX_ORIG.map(function(o){ return fetch('/api/search?origin='+o+'&one_way='+ow+'&sorting=price&limit=600').then(function(r){return r.json();}).then(function(j){ return (j&&j.data)||[]; }).catch(function(){ return []; }); }); Promise.all(calls2).then(function(arrs){ var best={}; arrs.forEach(function(data){ data.forEach(function(f){ var d=f.destination_airport; if(!d||origset[d]) return; if(!best[d]||f.price<best[d].price) best[d]=f; }); }); EX_DATA=Object.keys(best).map(function(k){return best[k];}).sort(function(a,b){return a.price-b.price;}); exFilter(); }).catch(function(){ go('ex-out').innerHTML='<div class="wl-hint">Couldn&rsquo;t load deals &mdash; try again.</div>'; }); };
function exFilter(){ var now=new Date(); var soon=new Date(); soon.setDate(soon.getDate()+16); var rows=EX_DATA.filter(function(f){ if(EX_REG!=='all' && tagsFor(f.destination_airport).indexOf(EX_REG)<0) return false; if(EX_WHEN==='soon'){ var dp=new Date((f.departure_at||'').slice(0,10)+'T00:00:00'); if(isNaN(dp)||dp<now||dp>soon) return false; } return true; }); EX_SHOWN=rows.slice(0,40); exRender(); }
function exRender(){ var out=go('ex-out'); if(!EX_SHOWN.length){ out.innerHTML='<div class="wl-hint">'+(EX_P2P?'No fares found for that route/date. Try clearing the date or switching trip type.':'No fares match those filters. Try another region or Anytime.')+'</div>'; return; } var multi=EX_ORIG.length>1; out.innerHTML=EX_SHOWN.map(function(f,i){ var d=f.destination_airport, dp=(f.departure_at||'').slice(0,10), rt=(f.return_at||'').slice(0,10), p=Math.round(f.price); var oo=f.origin_airport; var id=oo+d+dp; var on=saved(id)?' on':''; var star=saved(id)?'&#9733;':'&#9734;'; var sub=oo+' &rarr; '+d+' &middot; '+dp+(EX_TRIP==='round'&&rt?(' &rarr; '+rt):''); var title=EX_P2P?dp:(d+(multi?('<span style="display:inline-block;background:#0e141d;border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-size:11px;color:var(--gold);margin-left:8px">from '+oo+'</span>'):'')); return '<div class="mv-row"><button class="star'+on+'" onclick="exSave(this,'+i+')">'+star+'</button><div class="mv-dest"><span class="emoji">&#9992;</span><div><div class="mv-name">'+title+'</div><div class="mv-air">'+sub+'</div></div></div><div class="mv-right"><span class="mv-price">$'+p.toLocaleString()+'</span><a class="mini-book" href="'+f.link+'" target="_blank" rel="noopener">Book</a></div></div>'; }).join(''); }
window.exSave=function(btn,i){ var f=EX_SHOWN[i]; if(!f) return; var list=bucket(); var id=f.origin_airport+f.destination_airport+(f.departure_at||'').slice(0,10); var idx=-1; for(var k=0;k<list.length;k++){ if(list[k].id===id){ idx=k; break; } } if(idx>=0){ list.splice(idx,1); btn.classList.remove('on'); btn.innerHTML='&#9734;'; } else { list.push({id:id,o:f.origin_airport,d:f.destination_airport,date:(f.departure_at||'').slice(0,10),ret:(f.return_at||'').slice(0,10),price:Math.round(f.price),link:f.link,ow:EX_TRIP==='oneway'?1:0}); btn.classList.add('on'); btn.innerHTML='&#9733;'; } localStorage.setItem('mf_bucket',JSON.stringify(list)); if(window.renderBucket) window.renderBucket(); };
var rb=go('ex-regions'); if(rb){ rb.addEventListener('click', function(e){ var b=e.target.closest('[data-r]'); if(b){ EX_REG=b.getAttribute('data-r'); renderChips(); exFilter(); } }); }
var ob=go('ex-origs'); if(ob){ ob.addEventListener('click', function(e){ var b=e.target.closest('[data-o]'); if(!b) return; var c=b.getAttribute('data-o'); EX_ORIG=EX_ORIG.filter(function(x){return x!==c;}); if(!EX_ORIG.length) EX_ORIG=['RDU']; renderOrigs(); exSearch(); }); }
renderOrigs(); renderChips(); exSearch();
})();
</script>"""


def body_lastminute(lm):
    return f"""<div class="wrap">
  <div class="pagehead"><h1>&#9889; Last-minute getaways</h1><p>Cheapest round-trips leaving soon, from anywhere in the USA. Filter by region &mdash; tap one or several (USA for domestic).</p></div>
  <div class="airchips" style="margin:6px 0 16px;">{region_chip_bar("data-lmr", "toggleLMR")}</div>
  <div class="panel"><div id="lmlist"></div></div>
</div>"""


def body_airports(home):
    return f"""<div class="wrap">
  <div class="pagehead" id="airports"><h1>The Captain&rsquo;s Log</h1><p>Your home airports and tracked fares &mdash; a captain&rsquo;s log of raw data: coordinates, prices and deviations. Set your home airport to see the cheapest trips leaving from your city. Saved in this browser.</p></div>
  <div class="citybar">
    <select id="city-pick">{city_options(home)}</select>
    <button onclick="addCity()">Add my airport</button>
  </div>
  <div class="citychips" id="citychips"></div>
  <div class="sec-head"><h2>&#11088; My watched flights</h2><span>star any deal below to track it</span></div>
  <div class="panel"><div id="airwatch"></div>
    <div class="wl-hint" id="aw-hint">Star (&#9734;) any deal below to add it to your watched flights — saved in this browser.</div></div>
  <div class="sec-head"><h2>Deals from your airport</h2><span>tap &#9734; to watch</span></div>
  <div class="airchips" style="margin:6px 0 8px;">
    <button class="airchip on" data-act="any" onclick="setACMode('any')">Cheapest anytime</button>
    <button class="airchip" data-act="lm" onclick="setACMode('lm')">&#9889; Last-minute this week</button>
  </div>
  <div class="airchips" style="margin:0 0 14px;">{region_chip_bar("data-acr", "toggleACR")}</div>
  <div class="panel"><div id="citydeals"></div>
    <div class="wl-hint" id="city-hint">Add your home airport (e.g. Raleigh &mdash; RDU) to see the cheapest trips leaving from your city.</div></div>
</div>"""


def body_world(world):
    origins = sorted(set((w["o"], w["on"]) for w in world), key=lambda x: x[1])
    opts = ('<option value="all">All origins — cheapest worldwide</option>'
            + "".join(f'<option value="{o}">{html.escape(n)} ({o})</option>' for o, n in origins))
    return f"""<div class="wrap">
  <div class="pagehead"><h1>World &mdash; anywhere to anywhere</h1><p>Cheapest one-way flights from major hubs worldwide, including international origins. Pick any origin city and filter by region.</p></div>
  {world_map_html()}
  <div class="citybar"><select id="world-origin" onchange="selWorldOrigin(this.value)">{opts}</select></div>
  <div class="airchips" style="margin:4px 0 8px;">
    <button class="airchip on" data-wt="any" onclick="setWorldMode('any')">Cheapest fares</button>
    <button class="airchip" data-wt="lm" onclick="setWorldMode('lm')">&#9889; Last-minute</button>
  </div>
  <div class="airchips" style="margin:0 0 14px;">{region_chip_bar("data-wr", "toggleWR")}</div>
  <div class="panel"><div id="worldlist"></div></div>
</div>"""


def body_essentials():
    return f"""<div class="wrap">
  <div class="pagehead"><h1>Travel essentials</h1><p>Everything else you need for the trip — hotels, data, insurance and more. Every booking supports {BRAND} at no extra cost to you.</p></div>
  <div class="grid">{essentials_cards()}</div>
  <div class="summary" style="margin-top:24px">&#128161; Tip: the cheapest flight is just step one — booking your hotel, eSIM and activities here in one place keeps the whole trip organized.</div>
</div>"""


def body_watchlist(market):
    return """<div class="wrap">
  <div class="pagehead"><h1>My Bucket List Flights</h1><p>Every deal you&rsquo;ve starred, saved right here in your browser. Hop over to <a href="explore.html" style="color:var(--gold)">Explore</a> and tap &#9734; on any fare to add it.</p></div>
  <div id="bucket-page"></div>
</div>"""


# --------------------------------------------------------------------------- #
# Evergreen blog (SEO). Each article targets a keyword cluster (see seo/).
# To publish a post, append a dict to ARTICLES — the page, Article + FAQ schema,
# sitemap entry, and index card are all generated automatically. Booking links
# stay Aviasales/Travelpayouts. {LIVE_*} tokens are filled from today's data.
# --------------------------------------------------------------------------- #
ARTICLES = [
    {
        "slug": "cheapest-day-to-book-flights",
        "title": "The Cheapest Day to Book Flights (What the Data Shows) | Magellan Flights",
        "h1": "The cheapest day to book flights",
        "description": "The cheapest day to book flights is usually Tuesday or "
                       "Wednesday - but your booking window matters more. Here's "
                       "what thousands of live fares actually show.",
        "primary": "cheapest day to book flights",
        "secondary": ["cheapest day to fly", "what day of the week are flights cheapest",
                      "best day to buy plane tickets", "is tuesday the cheapest day to fly"],
        "kicker": "Booking timing",
        "published": "2026-06-22", "updated": "2026-06-22", "read_min": 6,
        "money_href": "market.html", "money_label": "today's cheapest flight deals",
        "lede": "Everyone &ldquo;knows&rdquo; you should book flights on a Tuesday. "
                "It&rsquo;s half true &mdash; and it&rsquo;s quietly costing you money, "
                "because the day of the week is the <i>smallest</i> lever you can pull. "
                "Here&rsquo;s what actually decides the price, backed by the thousands of "
                "live fares we track every day.",
        "sections": [
            ("The short answer",
             "<p>The <b>cheapest day to book a flight is usually Tuesday or Wednesday</b>, "
             "when airlines and their rivals refresh fares after the weekend. The "
             "<b>cheapest days to fly</b> are typically Tuesday, Wednesday and Saturday. "
             "But here&rsquo;s the part most articles skip: the day of the week is a small "
             "lever &mdash; worth a few percent. <b>How far ahead you book, and whether a "
             "fare has actually dropped below its normal range, matters far more.</b></p>"),
            ("Does the day of the week really matter?",
             "<p>There&rsquo;s a kernel of truth to the Tuesday myth. Airlines file fare "
             "changes through the week and competitors match them, so mid-week you&rsquo;ll "
             "sometimes catch a fresh, slightly lower price. Large fare studies keep landing "
             "in the same place: booking Tuesday or Wednesday saves a little versus a "
             "weekend &mdash; on the order of a few percent on average.</p>"
             "<p>The trap is treating that as your <i>main</i> strategy. A 2&ndash;3% "
             "midweek dip is real, but it&rsquo;s noise next to the 20&ndash;40% swings that "
             "come from booking in the right window or catching a sale. Don&rsquo;t "
             "reorganize your life around a Tuesday.</p>"),
            ("The lever that actually moves the price: your booking window",
             "<p>This is where the real money is. Fares are cheapest inside a sweet spot "
             "&mdash; far enough ahead that cheap seats remain, close enough that the airline "
             "isn&rsquo;t charging a premium for certainty.</p>"
             "<ul class='blog-list'>"
             "<li><b>Domestic US flights:</b> roughly <b>1 to 3 months</b> ahead.</li>"
             "<li><b>International flights:</b> roughly <b>2 to 8 months</b> ahead &mdash; "
             "longer for peak summer and the holidays.</li>"
             "<li><b>The danger zone:</b> inside two weeks, prices usually climb fast as the "
             "cheap fare buckets sell out.</li></ul>"
             "<p>Booking on a perfect Tuesday inside the wrong window still loses to booking "
             "on a Sunday inside the right one.</p>"),
            ("What our live fare data shows",
             "<p>We don&rsquo;t guess at this &mdash; we track it. Magellan Flights watches "
             "<b>{LIVE_ROUTES} routes</b> from the USA and logs the price every day, like a "
             "stock ticker for airfare. That reveals the thing a single search can&rsquo;t: "
             "each route&rsquo;s <i>normal</i> price, and the moment a fare drops below it.</p>"
             "<p>Right now the standout on the board is <b>{LIVE_TOPCITY}</b>, sitting about "
             "<b>{LIVE_TOPPCT}% below</b> its usual fare. That&rsquo;s the real "
             "&ldquo;cheapest day to book&rdquo; &mdash; not a weekday on the calendar, but "
             "the day a specific route dips under its normal range. You can watch those live "
             "on <a href='market.html'>today&rsquo;s deal board</a>.</p>"),
            ("Cheapest days to fly (which is a different question)",
             "<p>Booking day and travel day aren&rsquo;t the same thing. To <i>fly</i> "
             "cheaply, midweek wins more clearly than it does for booking:</p>"
             "<ul class='blog-list'>"
             "<li><b>Cheapest to fly:</b> Tuesday, Wednesday and Saturday.</li>"
             "<li><b>Most expensive:</b> Friday and Sunday, when weekend and business "
             "travelers crowd in.</li>"
             "<li>Shifting a trip by a day &mdash; flying out Wednesday instead of Friday "
             "&mdash; often beats any booking-day trick.</li></ul>"),
            ("A 5-minute routine to book at the low",
             "<p>Here&rsquo;s the routine we&rsquo;d actually use:</p>"
             "<ul class='blog-list'>"
             "<li><b>Start early</b> &mdash; begin watching 1&ndash;3 months out (domestic) "
             "or 2&ndash;8 months (international).</li>"
             "<li><b>Track, don&rsquo;t refresh</b> &mdash; let a tracker show you the normal "
             "price so you recognize a real drop.</li>"
             "<li><b>Stay flexible by a day or two</b> &mdash; midweek departures are cheaper.</li>"
             "<li><b>Book when it dips below normal</b>, not on a magic weekday.</li></ul>"
             "<p>Flying overseas? The windows shift a little &mdash; browse our "
             "<a href='world.html'>international deal board</a> to see them move in real time.</p>"),
        ],
        "faqs": [
            ("What day of the week are flights cheapest to book?",
             "On average, Tuesday and Wednesday are slightly cheaper to book than weekends, "
             "because airlines refresh fares mid-week. The gap is usually only a few percent, "
             "so it matters far less than booking in the right window."),
            ("Is Tuesday really the cheapest day to fly?",
             "Tuesday is one of the cheapest days to fly, along with Wednesday and Saturday. "
             "Friday and Sunday are typically the most expensive, because that's when leisure "
             "and business demand peak."),
            ("What is the best day to buy plane tickets?",
             "There isn't a magic day. The best time to buy is when a fare drops below its "
             "normal range, which can happen any day. Booking 1 to 3 months ahead for "
             "domestic trips and 2 to 8 months for international gives you the best odds."),
            ("Does booking at a specific time of day get cheaper flights?",
             "Not reliably. Fares can change at any hour as inventory updates, but there is no "
             "consistent cheapest time of day to book. Watching the price trend beats timing "
             "the clock."),
        ],
    },
]
ARTICLE_BY_FILE = {a["slug"] + ".html": a for a in ARTICLES}


def _live_stats(market):
    routes = len(market)
    best = None
    for m in market:
        try:
            _sig, pct = signal_for(m["price"], m["benchmark"])
        except Exception:
            continue
        if best is None or pct > best[1]:
            best = (m["name"].split(",")[0], pct)
    return {
        "routes": f"{routes:,}",
        "topcity": html.escape(best[0]) if best else "a top city",
        "toppct": f"{best[1]:.0f}" if best else "30",
    }


def body_article(a, market):
    secs = "\n".join(
        f'<section class="blog-sec"><h2>{html.escape(h2)}</h2>{para}</section>'
        for h2, para in a["sections"])
    faq_html = ""
    if a.get("faqs"):
        items = "".join(
            f'<details class="art-q"><summary>{html.escape(q)}</summary>'
            f'<p>{html.escape(ans)}</p></details>'
            for q, ans in a["faqs"])
        faq_html = f'<section class="blog-sec"><h2>Frequently asked questions</h2>{items}</section>'
    related = [x for x in ARTICLES if x["slug"] != a["slug"]][:3]
    rel_html = ""
    if related:
        links = "".join(
            f'<li><a href="{x["slug"]}.html">{html.escape(x["h1"])}</a></li>'
            for x in related)
        rel_html = f'<section class="blog-sec"><h2>Keep reading</h2><ul class="blog-list">{links}</ul></section>'
    cta = (f'<div class="art-cta"><div class="art-cta-txt"><b>See it live:</b> '
           f'{html.escape(a["money_label"])} are on the board right now, refreshed '
           f'through the day.</div>'
           f'<a class="book" href="{a["money_href"]}">Open the tracker &rarr;</a></div>')
    out = f"""<div class="wrap blog-wrap">
  <nav class="crumbs"><a href="guides.html">Guides</a> &rsaquo; {html.escape(a["h1"])}</nav>
  <div class="blog-eyebrow">{html.escape(a["kicker"])}</div>
  <h1 class="blog-title">{html.escape(a["h1"])}</h1>
  <div class="art-meta">Updated {a["updated"]} &middot; {a["read_min"]} min read &middot; {BRAND}</div>
  <p class="art-lede">{a["lede"]}</p>
  {cta}
  {secs}
  {faq_html}
  {cta}
  {rel_html}
</div>"""
    st = _live_stats(market)
    return (out.replace("{LIVE_ROUTES}", st["routes"])
               .replace("{LIVE_TOPCITY}", st["topcity"])
               .replace("{LIVE_TOPPCT}", st["toppct"]))


def body_guides(market):
    cards = "".join(
        f'<a class="guide-card" href="{a["slug"]}.html">'
        f'<div class="gc-kick">{html.escape(a["kicker"])}</div>'
        f'<div class="gc-title">{html.escape(a["h1"])}</div>'
        f'<div class="gc-desc">{html.escape(a["description"])}</div>'
        f'<div class="gc-more">Read guide &rarr;</div></a>'
        for a in ARTICLES)
    return f"""<div class="wrap">
  <div class="pagehead"><h1>Flight deal guides</h1><p>Straight answers on when to book, where to go, and how to catch a cheap fare &mdash; backed by the fares we track every day.</p></div>
  <div class="guide-grid">{cards}</div>
</div>"""


def main():
    market = read_snapshot()
    if not market:
        print("No data/market_latest.csv yet. Run 'py market.py' first.")
        return
    oneway = read_oneway(kind="6m")
    onewaylm = read_oneway(kind="lm")
    lm_all = read_lastminute(limit=400, kind="all")
    lm_intl = read_lastminute(limit=400, kind="intl")
    merged = {}
    for d in lm_all + lm_intl:
        if d["code"] not in merged or d["price"] < merged[d["code"]]["price"]:
            merged[d["code"]] = d
    lastmin = sorted(merged.values(), key=lambda x: x["price"])
    world = read_world(kind="any")
    worldlm = read_world(kind="lm")
    home = read_homebase()
    for c in home.values():
        for key in ("deals", "lastminute"):
            for d in c.get(key, []):
                d["t"] = lm_tags(d.get("cc", ""))
    hist = index_history()
    global HIST_SERIES, FEATURED_VERIFIED
    HIST_SERIES = read_history_series()
    try:
        FEATURED_VERIFIED = json.load(open(os.path.join(DATA_DIR, "featured_verified.json"), encoding="utf-8"))
    except Exception:
        FEATURED_VERIFIED = {}
    today = datetime.now().strftime("%B %d, %Y")
    summary = market_summary(market)
    cards_src = sorted(market, key=lambda m: signal_for(m["price"], m["benchmark"])[1], reverse=True)[:8]
    cards = "\n".join(card_html(m) for m in cards_src)

    pages = {
        "index.html": ("Home", body_home(market, hist, cards, lastmin, oneway, summary)),
        "market.html": ("Market", body_market(market, hist, cards, lastmin, oneway)),
        "world.html": ("World", body_world(world)),
        "trip.html": ("Journey", body_trip()),
        "explore.html": ("Explore", body_explore()),
        "blog.html": ("Daily Guide", body_blog(market)),
        "lastminute.html": ("Last-minute", body_lastminute(lastmin)),
        "airports.html": ("Captain's Log", body_airports(home)),
        "watchlist.html": ("Watchlist", body_watchlist(market)),
        "essentials.html": ("Travel essentials", body_essentials()),
        "guides.html": ("Guides", body_guides(market)),
    }

    os.makedirs(SITE_DIR, exist_ok=True)
    for fname, (title, body) in pages.items():
        doc = render_page(fname, title, body, market, oneway, onewaylm, home, lastmin, world, worldlm, today)
        with open(os.path.join(SITE_DIR, fname), "w", encoding="utf-8") as f:
            f.write(doc)

    # Evergreen blog articles (one page per cluster).
    for a in ARTICLES:
        fname = a["slug"] + ".html"
        doc = render_page(fname, a["h1"], body_article(a, market), market,
                          oneway, onewaylm, home, lastmin, world, worldlm, today)
        with open(os.path.join(SITE_DIR, fname), "w", encoding="utf-8") as f:
            f.write(doc)

    all_files = list(pages) + [a["slug"] + ".html" for a in ARTICLES]
    write_seo_files(all_files)
    print(f"Built {len(pages)} pages + {len(ARTICLES)} articles + sitemap/robots -> {SITE_DIR}  "
          f"({len(market)} routes, {len(oneway)} one-ways, {len(home)} home airports)")


def write_seo_files(pages):
    """Emit sitemap.xml + robots.txt so search engines can crawl efficiently.

    `pages` is an iterable of page filenames to include in the sitemap.
    """
    lastmod = datetime.now().strftime("%Y-%m-%d")
    # Rough priority: home highest, then the deal boards, then helper pages.
    prio = {"index.html": "1.0", "market.html": "0.9", "world.html": "0.8",
            "explore.html": "0.8", "lastminute.html": "0.8", "guides.html": "0.7",
            "blog.html": "0.7", "airports.html": "0.6"}
    article_files = set(globals().get("ARTICLE_BY_FILE", {}))
    urls = []
    for fname in pages:
        loc = BASE_URL + "/" + ("" if fname == "index.html" else fname)
        urls.append(
            f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{'monthly' if fname in article_files else 'daily'}</changefreq>\n"
            f"    <priority>{prio.get(fname, '0.6' if fname in article_files else '0.5')}</priority>\n  </url>")
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "\n".join(urls) + "\n</urlset>\n")
    with open(os.path.join(SITE_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap)
    robots = (f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n")
    with open(os.path.join(SITE_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots)


if __name__ == "__main__":
    main()
