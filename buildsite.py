#!/usr/bin/env python3
"""
BuildSite - generates a multi-page, CNBC-style flight website into site/.

Pages (shared header, tickers, nav and footer on every one):
  index.html       Home - tickers, market summary, top deals, email signup
  market.html      Region indices + movers board + all deal cards
  explore.html     Region-selectable ticker + one-way escapes abroad
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
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import quote, quote_plus

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
try:
    AIRPORT_NAMES = json.load(open(os.path.join(HERE, "airport_names.json"), encoding="utf-8"))
except Exception:
    AIRPORT_NAMES = {}

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

# Continents used for the fare indices (Middle East kept separate from Asia).
INDEX_REGIONS = ["Asia", "Europe", "Middle East", "Americas", "Oceania", "Africa"]

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

# Primary nav — kept to five clear destinations. Secondary pages live in the
# grouped footer (FOOTER_NAV) so nothing is lost and everything stays crawlable.
NAV = [("index.html", "Home"), ("market.html", "Market"), ("explore.html", "Explore"),
       ("around-the-world.html", "Around the World"), ("guides.html", "Guides"), ("cheap-flights.html", "By airport"),
       ("ask.html", "Ask Magellan")]

FOOTER_NAV = [
    ("Browse fares", [("market.html", "The Market"), ("explore.html", "Explore &amp; search"),
                      ("around-the-world.html", "Around the World"),
                      ("cheap-europe-trip.html", "Continent trips"),
                      ("cheap-flights.html", "Flight deals by airport")]),
    ("Learn", [("city-guides.html", "City guides"), ("guides.html", "Guides &amp; tips"),
               ("blog.html", "Today&rsquo;s Daily Guide"), ("cheap-flight-index.html", "Cheap Flight Index"),
               ("travel-cards.html", "Travel cards"), ("essentials.html", "Travel kit"),
               ("our-story.html", "Our story")]),
    ("Your trips", [("watchlist.html", "My bucket list"), ("newsletter.html", "Free newsletter"),
               ("consultant.html", "Hire a consultant")]),
]


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
BEEHIIV_URL = "https://daltons-newsletter-44b474.beehiiv.com/"
# Reusable "join the newsletter" CTA for the bottom of content pages (articles + city guides).
NL_CTA = ('<div class="art-cta nl-cta"><div class="art-cta-txt">'
          '<b>Get these deals in your inbox.</b> The week&rsquo;s biggest flight-price '
          'drops from the USA &mdash; free, every week.</div>'
          '<a class="book" href="newsletter.html">Join the free newsletter &rarr;</a></div>')
BRAND = "Magellan Flights"
TAGLINE = "The cheapest flights from the USA, tracked like a market - every day."

# --------------------------------------------------------------------------- #
# SEO: per-page titles + descriptions, social cards, schema, sitemap.
# All booking links stay Aviasales/Travelpayouts (marker 741311) — SEO only
# touches the <head> and a couple of static text files; it never changes links.
# --------------------------------------------------------------------------- #
BASE_URL = "https://www.magellanflights.com"      # canonical home (served domain; apex 308s here)
OG_IMAGE = BASE_URL + "/og-image.png"             # 1200x630 social share image
# Paste the token from Google Search Console's "HTML tag" verification method here
# (just the content="..." value), then deploy — the meta tag goes on every page.
GOOGLE_SITE_VERIFICATION = ""
# Google Analytics 4 Measurement ID (public; embedded on every page). Empty = no tag.
GA_MEASUREMENT_ID = "G-EX9M7KPYCK"

# Unique, keyword-targeted <title> + meta description per page. Keep titles
# ~55-60 chars and descriptions ~150-160 so Google shows them in full.
SEO = {
    "index.html": (
        "Cheap Flights from the USA and Abroad | Magellan Flights",
        "The market for flights. Real fares from the USA and abroad, "
        "refreshed several times a day and tracked like a stock market, so you "
        "book at the low. Round-trip and one-way deals."),
    "market.html": (
        "Cheap Flight Deals Today — Live Fare Tracker | Magellan Flights",
        "A live board of the cheapest one-way flights from the USA, with "
        "price history and how far below normal each fare is. Updated daily."),
    "heatmap.html": (
        "Flight Fare Heatmap — Every Deal at a Glance | Magellan Flights",
        "A live heatmap of every flight fare we track from the USA: green when a fare is "
        "below its normal price, red when above. The deeper the color, the bigger the move."),
    "world.html": (
        "Cheapest One-Way Flights Worldwide | Magellan Flights",
        "Explore the cheapest flights between 50 global hubs — anywhere to "
        "anywhere. Compare live fares and find the best-value route today."),
    "explore.html": (
        "Cheap One-Way Flights from the USA (Next 6 Months) | Magellan Flights",
        "The cheapest one-way flights from the USA over the next six months. "
        "Filter by region and home airport to find your next trip for less."),
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
    "cheap-flights.html": (
        "Cheap Flights by Departure City — Live Deals | Magellan Flights",
        "Find the cheapest flights from your home airport. Live, bookable fares "
        "from 25 major US cities to everywhere they fly, updated daily."),
    "around-the-world.html": (
        "Cheapest Around-the-World Flights — Build Your Loop | Magellan Flights",
        "Build the cheapest around-the-world trip from live one-way fares: set your start, "
        "stops, regions and direction (east or west). Real, bookable fares, refreshed daily."),
    "cheap-flight-index.html": (
        "The Cheap Flight Index — Cheapest Places to Fly from the USA | Magellan Flights",
        "A live data study of the cheapest real fares from US airports right now: cheapest "
        "international destinations, cheapest US airports to fly abroad from, and how far below "
        "normal today's deals are. Updated daily, free to cite."),
    "newsletter.html": (
        "Weekly Flight-Market Briefing — Free Newsletter | Magellan Flights",
        "The free weekly flight-market briefing: how each country's fares moved, what's below "
        "normal now, and one trip to book this week — from fares tracked daily. Unsubscribe anytime."),
    "our-story.html": (
        "Our Story — Why Magellan Flights | Magellan Flights",
        "How Magellan Flights came to be, and how we track the cheapest flights from the USA "
        "like a market — judging every fare against its own price history so you book at the low."),
    "travel-cards.html": (
        "Best Travel Cards for Cheap-Flight Hunters (Honest Guide) | Magellan Flights",
        "An honest guide to travel credit cards worth it for cheap-flight hunters: what to look "
        "for, who each suits, and the catch. We only earn if you're approved, at no cost to you. "
        "General information, not financial advice."),
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
    money = globals().get("MONEY_BY_FILE", {})
    if active in money:
        return (money[active]["title"], money[active]["description"])
    cg = globals().get("CITYGUIDE_BY_FILE", {})
    if active in cg:
        return (cg[active]["title"], cg[active]["description"])
    rt = globals().get("ROUTE_BY_FILE", {})
    if active in rt:
        return (rt[active]["title"], rt[active]["description"])
    rtour = globals().get("REGION_TOUR_BY_FILE", {})
    if active in rtour:
        m = rtour[active]
        return (f"Cheap {m['name']} Trip \u2014 Multi-City Flights | {BRAND}", f"Build the cheapest multi-city {m['name']} trip from live one-way fares \u2014 a real, bookable loop refreshed daily. See the route, prices and best time to go.")
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
    tags = []
    if GOOGLE_SITE_VERIFICATION:
        tags.append(f'<meta name="google-site-verification" content="{GOOGLE_SITE_VERIFICATION}">')
    tags += [
        f'<link rel="canonical" href="{url}">',
        '<meta name="robots" content="index, follow, max-image-preview:large">',
        '<meta name="theme-color" content="#f3ecd8">',
        f'<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{BRAND}">',
        f'<meta property="og:title" content="{t}">',
        f'<meta property="og:description" content="{d}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{OG_IMAGE}">',
        f'<meta property="og:image:alt" content="{_esc_attr(BRAND)} — the cheapest flights from the USA">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:site" content="@MagellanFlights">',
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
        if a.get("howto"):
            ht = a["howto"]
            graph.append({
                "@type": "HowTo", "name": ht.get("name", a["h1"]),
                "step": [{"@type": "HowToStep", "position": i,
                          "name": s.get("name", ""), "text": s.get("text", "")}
                         for i, s in enumerate(ht.get("steps", []), 1)]})
    # Money page: ItemList of the cheapest fares + breadcrumb + FAQ.
    money = globals().get("MONEY_BY_FILE", {})
    if active in money:
        p = money[active]
        items = [{"@type": "ListItem", "position": i,
                  "name": f"{p['city']} to {d['name'].split(',')[0]}", "url": url}
                 for i, d in enumerate(p["deals"][:20], 1)]
        graph.append({"@type": "ItemList", "name": f"Cheapest flights from {p['city']}",
                      "numberOfItems": len(items), "itemListElement": items})
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Cheap flights",
             "item": BASE_URL + "/cheap-flights.html"},
            {"@type": "ListItem", "position": 2, "name": p["h1"], "item": url}]})
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a2}}
            for q, a2 in money_faqs(p)]})
    # City guide: TouristDestination + breadcrumb + FAQ + (VideoObject if present).
    cg_by = globals().get("CITYGUIDE_BY_FILE", {})
    if active in cg_by:
        g = cg_by[active]
        info = DEST_INFO.get(g["code"], {})
        best = BEST_TIME.get(g["code"], "year-round")
        deal = find_city_deal(g["code"], market) if market else None
        graph.append({"@type": "TouristDestination", "name": g["city"],
                      "description": g["description"], "url": url})
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "City guides",
             "item": BASE_URL + "/city-guides.html"},
            {"@type": "ListItem", "position": 2, "name": g["city"], "item": url}]})
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a3}}
            for q, a3 in city_faqs(g, deal, best, info)]})
        vid = YT_VIDEOS.get(g["code"], "")
        if vid:
            graph.append({"@type": "VideoObject", "name": f"{g['city']} travel guide",
                          "description": g["description"],
                          "thumbnailUrl": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                          "embedUrl": f"https://www.youtube.com/embed/{vid}",
                          "uploadDate": datetime.now().strftime("%Y-%m-%d")})
    if active == "cheap-flight-index.html":
        graph.append({"@type": "Dataset", "name": f"{BRAND} Cheap Flight Index",
                      "description": "Live data on the cheapest real, bookable fares from US airports to destinations worldwide, updated daily.",
                      "url": url, "creator": {"@id": BASE_URL + "/#org"},
                      "isAccessibleForFree": True, "dateModified": datetime.now().strftime("%Y-%m-%d")})
        graph.append({"@type": "Article", "headline": "The Magellan Cheap Flight Index",
                      "description": "The cheapest places to fly from the USA right now, from live fare data.",
                      "dateModified": datetime.now().strftime("%Y-%m-%d"),
                      "author": {"@id": BASE_URL + "/#org"}, "publisher": {"@id": BASE_URL + "/#org"},
                      "mainEntityOfPage": {"@id": url + "#webpage"}})
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Guides", "item": BASE_URL + "/guides.html"},
            {"@type": "ListItem", "position": 2, "name": "Cheap Flight Index", "item": url}]})
    rtour_by = globals().get("REGION_TOUR_BY_FILE", {})
    if active in rtour_by:
        m = rtour_by[active]
        graph.append({"@type": "Article", "headline": f"Cheap {m['name']} Trip",
                      "description": f"The cheapest multi-city {m['name']} trip from live one-way fares.",
                      "dateModified": datetime.now().strftime("%Y-%m-%d"),
                      "author": {"@id": BASE_URL + "/#org"}, "publisher": {"@id": BASE_URL + "/#org"},
                      "mainEntityOfPage": {"@id": url + "#webpage"}})
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Around the World", "item": BASE_URL + "/around-the-world.html"},
            {"@type": "ListItem", "position": 2, "name": f"{m['name']} trip", "item": url}]})
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a5}}
            for q, a5 in region_tour_faqs(m, None)]})
    rt_by = globals().get("ROUTE_BY_FILE", {})
    if active in rt_by:
        p = rt_by[active]
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Cheap flights",
             "item": BASE_URL + "/cheap-flights.html"},
            {"@type": "ListItem", "position": 2, "name": p["h1"], "item": url}]})
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a4}}
            for q, a4 in route_faqs(p)]})
    # Hub pages: ItemList so search engines & AI read them as curated link lists.
    if active == "cheap-flights.html":
        items = [{"@type": "ListItem", "position": i,
                  "name": f"Cheap flights from {mp['city']} ({mp['code']})",
                  "url": BASE_URL + "/" + mp["fname"]}
                 for i, mp in enumerate(globals().get("MONEY_PAGES", []), 1)]
        if items:
            graph.append({"@type": "ItemList", "name": "Cheap flights by departure city",
                          "numberOfItems": len(items), "itemListElement": items})
    if active == "city-guides.html":
        items = [{"@type": "ListItem", "position": i,
                  "name": f"{cg['city']} travel guide",
                  "url": BASE_URL + "/" + cg["fname"]}
                 for i, cg in enumerate(CITY_GUIDES, 1)]
        if items:
            graph.append({"@type": "ItemList", "name": "City guides",
                          "numberOfItems": len(items), "itemListElement": items})
    if active == "guides.html":
        items = [{"@type": "ListItem", "position": i,
                  "name": ar.get("h1", ar.get("slug", "")),
                  "url": BASE_URL + "/" + ar["slug"] + ".html"}
                 for i, ar in enumerate(ARTICLES, 1)]
        if items:
            graph.append({"@type": "ItemList", "name": "Flight deal guides",
                          "numberOfItems": len(items), "itemListElement": items})
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
VERIFIED_ISO = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")  # build time = verify time
HIST_SERIES = {}  # {code: [price per day, oldest..newest]} — filled in main()
ONEWAY_PRICE_HISTORY = {}  # {code: [recent cheapest one-way prices]} — each route's own one-way baseline, filled in main()
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
        return '<p class="trip">Uses the US dollar</p>'
    rate = FX_STATIC.get(cur)
    if not rate:
        return ""
    return (f'<p class="trip"><span data-cur="{cur}">'
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


def price_bar(code, price, benchmark=0):
    """The price-position signal: where today's fare sits between this route's
    low and high, anchored on its baseline (the Standard Meridian / benchmark) so
    a colored signal shows immediately and sharpens as price history accumulates.
    Returns HTML for a track with end-caps, a faint 'typical' tick and a
    green/yellow/red dot, plus a one-line verdict. Replaces BOOK/WATCH/WAIT."""
    try:
        price = float(price)
    except Exception:
        return ""
    try:
        benchmark = float(benchmark)
    except Exception:
        benchmark = 0.0
    hist = [p for p in HIST_SERIES.get(code, []) if p and p > 0]
    pool = sorted([p for p in (hist + [price, benchmark]) if p and p > 0])
    if len(pool) < 2:
        return ""
    lo, hi = pool[0], pool[-1]
    if hi <= lo:
        return ""
    typ = benchmark if benchmark > 0 else pool[len(pool) // 2]
    frac = max(2.0, min(98.0, (price - lo) / (hi - lo) * 100))
    tfrac = max(0.0, min(100.0, (typ - lo) / (hi - lo) * 100))
    if price <= typ * 0.90:
        c, v = "g", "Low — great deal"
    elif price <= typ * 1.10:
        c, v = "y", "Typical price"
    else:
        c, v = "r", "High right now"
    return (f'<div class="prange"><span class="pr-cap"></span>'
            f'<span class="pr-line"><span class="pr-typ" style="left:{tfrac:.0f}%"></span>'
            f'<span class="pr-dot {c}" style="left:{frac:.0f}%"></span></span>'
            f'<span class="pr-cap"></span></div>'
            f'<div class="pr-lab"><span>${lo:,.0f} low</span>'
            f'<span class="pr-verdict {c}">{v}</span><span>${hi:,.0f} high</span></div>')


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
    color = "#2e8b57" if falling else "#c0392b"
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
    # Explicit width/height prevent layout shift (CLS) — sizes match the CSS.
    w, h = (18, 13) if "ti-flag" in cls else (30, 21)
    if cc:
        return (f'<img class="{cls}" src="https://flagcdn.com/{cc}.svg" alt="" '
                f'width="{w}" height="{h}" loading="lazy">')
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


def read_oneway(limit=1500, kind="6m"):
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


def essentials_cards():
    out = []
    for label, ic, url, blurb in AFFILIATE:
        live = url and url != "#"
        if live:
            btn = f'<a class="book" href="{url}" target="_blank" rel="noopener">Search {label.lower()}</a>'
        else:
            btn = '<a class="book" style="background:#9a8f72;cursor:default;pointer-events:none;">Coming soon</a>'
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


def index_sparkline(series):
    """Tiny pure-SVG line chart of a region's average-price history (time x, price y)."""
    if not series or len(series) < 2:
        return '<div class="idx-chart-empty">History chart builds as more days are logged.</div>'
    vals = [v for _, v in series]
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    W, H, PL, PR, PT, PB = 280.0, 78.0, 4.0, 4.0, 12.0, 4.0
    n = len(series)
    xs = [PL + i * (W - PL - PR) / (n - 1) for i in range(n)]
    ys = [(H - PB) - (v - lo) / rng * (H - PT - PB) for v in vals]
    line = "M" + " L".join(f"{xs[i]:.1f},{ys[i]:.1f}" for i in range(n))
    area = (f"M{xs[0]:.1f},{H - PB:.1f} " + " ".join(f"L{xs[i]:.1f},{ys[i]:.1f}" for i in range(n))
            + f" L{xs[-1]:.1f},{H - PB:.1f} Z")
    def _fmt(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").strftime("%b %d")
        except Exception:
            return d
    return (
        f'<svg class="idx-chart" viewBox="0 0 280 78" preserveAspectRatio="none" role="img" aria-label="price history">'
        f'<path d="{area}" fill="rgba(47,107,70,.12)"/>'
        f'<path d="{line}" fill="none" stroke="#2f6b46" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>'
        f'<text x="6" y="11" fill="#7a715a" font-size="9">${hi:,.0f}</text>'
        f'<text x="6" y="{H - 2:.0f}" fill="#7a715a" font-size="9">${lo:,.0f}</text>'
        f'</svg>'
        f'<div class="idx-chart-x"><span>{_fmt(series[0][0])}</span><span>{_fmt(series[-1][0])}</span></div>'
    )


OW_INDEX_LOG = os.path.join(HERE, "oneway_index.json")
OW_PRICE_LOG = os.path.join(HERE, "oneway_pricelog.json")  # per-route one-way price history (rolling)


def country_from_name(name):
    """"Athens, Greece" -> "Greece";  "Singapore" -> "Singapore"."""
    if name and "," in name:
        return name.rsplit(",", 1)[1].strip()
    return (name or "").strip()


def update_oneway_index_log(oneway, days=60):
    """Append today's per-region average ONE-WAY fare to oneway_index.json (one point/day)."""
    today = datetime.now().strftime("%Y-%m-%d")
    by_reg = defaultdict(dict)
    for o in oneway:
        if (o.get("cc") or "").upper() == "US":
            continue
        reg = continent_of(o["code"])
        if reg not in INDEX_REGIONS:
            continue
        c = o["code"]
        try:
            p = float(o["price"])
        except (TypeError, ValueError):
            continue
        if c not in by_reg[reg] or p < by_reg[reg][c]:
            by_reg[reg][c] = p
    todays = {reg: round(sum(d.values()) / len(d), 2) for reg, d in by_reg.items() if d}
    try:
        log = json.load(open(OW_INDEX_LOG, encoding="utf-8"))
    except Exception:
        log = {}
    if todays:
        log[today] = todays
    for d in sorted(log)[:-days]:
        log.pop(d, None)
    try:
        json.dump(log, open(OW_INDEX_LOG, "w", encoding="utf-8"))
    except Exception:
        pass


def oneway_index_history():
    try:
        log = json.load(open(OW_INDEX_LOG, encoding="utf-8"))
    except Exception:
        return {}
    series = defaultdict(list)
    for d in sorted(log):
        for reg, val in log[d].items():
            series[reg].append((d, val))
    return series


def update_oneway_price_log(oneway, cap=40):
    """Append today's cheapest one-way per destination to a rolling per-route log, so
    each route accrues its OWN one-way price baseline over time. This is what lets the
    Rare Fare detector tell a genuine drop from a route that is simply always cheap
    (e.g. Kutaisi, whose one-way is structurally ~$240) — a benchmark can't, because
    the global one-way/round-trip ratio over-states 'normal' for such routes."""
    cheapest = {}
    for o in oneway:
        if (o.get("cc") or "").upper() == "US":
            continue
        c = o.get("code")
        if not c:
            continue
        try:
            p = float(o["price"])
        except (TypeError, ValueError):
            continue
        if p <= 0:
            continue
        if c not in cheapest or p < cheapest[c]:
            cheapest[c] = p
    try:
        log = json.load(open(OW_PRICE_LOG, encoding="utf-8"))
        if not isinstance(log, dict):
            log = {}
    except Exception:
        log = {}
    for c, p in cheapest.items():
        arr = log.get(c) or []
        arr.append(round(p, 2))
        log[c] = arr[-cap:]                       # keep only the most recent `cap` observations
    try:
        json.dump(log, open(OW_PRICE_LOG, "w", encoding="utf-8"))
    except Exception:
        pass


def read_oneway_price_series():
    """{code: [recent cheapest one-way prices, oldest..newest]} — each route's own baseline."""
    try:
        log = json.load(open(OW_PRICE_LOG, encoding="utf-8"))
        return log if isinstance(log, dict) else {}
    except Exception:
        return {}


def index_cards(oneway, hist):
    by_reg = defaultdict(dict)  # reg -> {code: cheapest one-way row}
    for o in oneway:
        if (o.get("cc") or "").upper() == "US":
            continue
        reg = continent_of(o["code"])
        if reg not in INDEX_REGIONS:
            continue
        c = o["code"]
        try:
            p = float(o["price"])
        except (TypeError, ValueError):
            continue
        cur = by_reg[reg].get(c)
        if cur is None or p < float(cur["price"]):
            by_reg[reg][c] = o
    cards = []
    for reg in INDEX_REGIONS:
        items = list(by_reg.get(reg, {}).values())
        if not items:
            continue
        avg = sum(float(o["price"]) for o in items) / len(items)
        move = '<span class="idx-move new">today</span>'
        series = hist.get(reg, [])
        if len(series) >= 2:
            diff = series[-1][1] - series[-2][1]
            if abs(diff) >= 1:
                ar, cl = ("&#9660;", "down") if diff < 0 else ("&#9650;", "up")
                move = f'<span class="idx-move {cl}">{ar}${abs(diff):,.0f} vs yest</span>'
            else:
                move = '<span class="idx-move flat">flat</span>'
        const_rows = "".join(
            f'<li><span>{html.escape(o.get("name", o["code"]))} '
            f'<span class="idx-c-from">from {html.escape(o["origin"])}</span></span>'
            f'<span>${float(o["price"]):,.0f}</span></li>'
            for o in sorted(items, key=lambda x: float(x["price"])))
        cards.append(
            f'<details class="idx">'
            f'<summary class="idx-sum"><span class="idx-sum-name">{reg}</span>'
            f'<span class="idx-sum-right"><span class="idx-val">${avg:,.0f}</span>{move}</span></summary>'
            f'<div class="idx-body">'
            f'<p class="idx-sub">avg one-way of {len(items)} tracked routes</p>'
            f'{index_sparkline(series)}'
            f'<ul class="idx-list">{const_rows}</ul>'
            f'</div></details>')
    return "".join(cards)


_MOVER_REGIONS = {
    "Asia": ["TYO","BKK","DPS","HKT","SGN","HAN","NRT","KIX","ICN","SIN","KUL","MNL","DEL","BOM","HKG","TPE","KTM","PEK","PVG","CAN","CTU","CGK","REP","PNH","CMB","MLE","BLR","MAA","FUK","CEB","KHH", "CTS", "OKA", "CNX", "DAD", "USM", "GOI", "COK", "PEN", "SUB"],
    "Middle East": ["DXB","DOH","IST","TLV","AUH","RUH","JED","AMM","BEY","MCT", "KWI", "BAH", "GYD", "TBS", "EVN"],
    "Europe": ["LON","PAR","LHR","CDG","FCO","BCN","MAD","LIS","AMS","FRA","ATH","DUB","KEF","PRG","CPH","MUC","ZRH","VIE","BRU","MXP","VCE","NCE","EDI","MAN","GVA","OSL","ARN","HEL","WAW","BUD","KRK","OPO", "HAM", "DUS", "BER", "STR", "CGN", "SOF", "OTP", "BEG", "ZAG", "SPU", "DBV", "TLL", "RIX", "VNO", "BLQ", "FLR", "NAP", "CTA", "AGP", "SVQ", "VLC", "FAO", "LYS", "MRS", "GLA", "BHX"],
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


# The board splits the Americas into North vs South America for cleaner browsing
# (the fare INDICES keep the single "Americas" region).
SA_CC = {"CO", "PE", "BR", "AR", "CL", "EC", "BO", "UY", "PY", "VE", "GY", "SR", "GF"}
SA_CODES = {"BOG", "MDE", "CTG", "CLO", "CUC", "ADZ", "SMR", "LIM", "CUZ", "AQP", "IQT",
            "GRU", "GIG", "BSB", "CWB", "POA", "FOR", "REC", "SSA", "FLN", "CNF", "VCP", "MAO",
            "EZE", "COR", "MDZ", "SCL", "UIO", "GYE", "MVD", "ASU", "CCS", "MAR", "VVI", "LPB",
            "GEO", "PBM", "CAY"}


def board_region_of(code):
    reg = continent_of(code)
    if reg == "Americas":
        cc = (CODE_CC_MAP.get(code) or "").upper()
        return "South America" if (cc in SA_CC or code in SA_CODES) else "North America"
    return reg


def city_options(home, any_opt=False):
    opts = ['<option value="">Choose your home airport…</option>']
    if any_opt:
        opts.append('<option value="__ANY__">Best deals from any airport</option>')
    for code in sorted(home, key=lambda c: home[c]["name"]):
        opts.append(f'<option value="{code}">{html.escape(home[code]["name"])} ({code})</option>')
    return "".join(opts)


def verified_tag():
    """Freshness stamp; JS turns it into 'verified Xh ago' client-side so it stays
    accurate on the static page."""
    return (f'<div class="pr-fresh" data-verified="{VERIFIED_ISO}">'
            f'<i class="dotc"></i><span>tracked just now</span></div>')


def share_icon():
    return ('<svg class="shico" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>'
            '<path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>')


def card_html(m):
    code = m["code"]
    _, pct = signal_for(m["price"], m["benchmark"])
    flash = is_flash(code, m["price"], m["benchmark"])
    hlabel, hcls = hist_signal(code, m["price"], m["benchmark"])
    badge = ('<span class="badge flash">FLASH</span>' if flash
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
      <article class="card flip-front" data-lp data-b="{m['benchmark']}" data-o="{html.escape(m['origin'], quote=True)}" data-c="{code}" data-n="{html.escape(m['name'], quote=True)}" data-p="{m['price']:.0f}" data-dep="{html.escape(m.get('depart', ''), quote=True)}" data-ret="{html.escape(m.get('return', ''), quote=True)}" data-ow="0">
        <div class="card-top">{flag_img(code)}
          <div class="card-top-right">{badge}
            <button class="star" data-code="{code}" aria-label="watch">&#9734;</button></div></div>
        <h3 class="dest">{html.escape(m["name"])}</h3>
        <p class="route">{html.escape(airline_name(m['airline']))} &middot; round-trip from {html.escape(m["origin"])}</p>
        <p class="dates">{dates}</p>
        <p class="dates">Best time: {html.escape(BEST_TIME.get(code, "year-round"))}</p>
        <p class="price">${m['price']:,.0f} <span class="was" title="The Standard Meridian — this route's historical baseline fare">${m['benchmark']:,.0f}</span></p>
        <p style="font-size:11px;color:var(--muted);margin:-11px 0 8px;letter-spacing:.03em">&#9678; vs. the <b style="color:var(--gold);font-weight:600">Standard Meridian</b> &middot; historical baseline</p>
        {price_bar(code, m['price'], m['benchmark'])}
        {verified_tag()}
        <div class="cardmeta">{spark}</div>
        <p class="trip">A week here &asymp; <b>${wk:,}</b> <span>(flight ${m['price']:,.0f} &middot; hotel ~${hn}/nt &times;7 &middot; eSIM ${ESIM_COST})</span></p>
        {fx}
        <a class="book" href="{link}" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a>
        <div class="cardacts">
          <button class="sharebtn" onclick="shareDeal(this)" aria-label="Share this deal">{share_icon()} Share</button>
          <button class="flipbtn" onclick="flipCard(this)">&#9432; Things to know &rarr;</button>
        </div>
      </article>
      <article class="card flip-back">
        <h3 class="dest">{html.escape(m["name"])}</h3>
        <p class="binfo-h">Things to know before you go</p>
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
    <h2>The weekly flight-market briefing</h2>
    <p>One email a week: how each country&rsquo;s fares moved, what&rsquo;s below normal right now, and the one trip worth booking this week, from the fares we track every day. Free.</p>
    <form class="signup-form" onsubmit="return mfInlineSub(event)" style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center;max-width:460px;margin:12px auto 0">
      <input type="email" required placeholder="you@email.com" autocomplete="email" aria-label="Email address" style="flex:1;min-width:220px;background:#fffdf6;color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:15px">
      <button class="book" type="submit" style="font-size:15px;padding:12px 26px">Get the briefing &rarr;</button>
    </form>
    <p style="font-size:12px;color:var(--muted);margin-top:9px">Free &middot; one email a week &middot; unsubscribe anytime.</p>
  </div>
</section>"""

BRIEFING_CTA = """<div class="signup" style="margin-top:24px"><div class="signup-inner">
  <h2>Get this in your inbox</h2>
  <p>The weekly flight-market briefing: how each country&rsquo;s fares moved, what&rsquo;s below normal right now, and the one trip worth booking this week. Free.</p>
  <form class="signup-form" onsubmit="return mfInlineSub(event)" style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center;max-width:460px;margin:12px auto 0">
    <input type="email" required placeholder="you@email.com" autocomplete="email" aria-label="Email address" style="flex:1;min-width:220px;background:#fffdf6;color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:15px">
    <button class="book" type="submit" style="font-size:15px;padding:11px 24px">Get the briefing &rarr;</button>
  </form>
  <p style="font-size:12px;color:var(--muted);margin-top:9px">Free &middot; one email a week &middot; unsubscribe anytime.</p>
</div></div>"""

CHAT_HTML = f"""
<button id="chatbtn" onclick="chatToggle()" aria-label="Ask {BRAND}">{icon('chat', 'chat-ic')}</button>
<div id="chatpanel">
  <div class="cp-head">Ask {BRAND}<span onclick="chatToggle()" style="cursor:pointer;float:right">&times;</span></div>
  <div class="cp-msgs" id="cpmsgs"></div>
  <div class="cp-in"><input id="cpinput" placeholder="e.g. cheapest one-way to Asia" onkeydown="if(event.key==='Enter')chatSend()"><button onclick="chatSend()">Send</button></div>
</div>"""

# Digital astrolabe — thin-line gold loader (rotating rete over a graduated ring).
ASTRO_SVG = (
    '<svg viewBox="0 0 100 100" fill="none" stroke="#2f6b46" stroke-width="1.4" '
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
    '<circle cx="74" cy="30" r="1.8" fill="#2f6b46" stroke="none"/>'
    '<circle cx="26" cy="70" r="1.8" fill="#2f6b46" stroke="none"/>'
    '<circle cx="30" cy="34" r="1.6" fill="#2f6b46" stroke="none"/>'
    '</g>'
    '<line x1="50" y1="3" x2="50" y2="97" stroke-width="1" stroke-opacity=".4"/>'
    '<line x1="3" y1="50" x2="97" y2="50" stroke-width="1" stroke-opacity=".4"/>'
    '<circle cx="50" cy="50" r="3.4" fill="#efe5cd"/>'
    '<circle cx="50" cy="50" r="2.2" fill="#2f6b46" stroke="none"/>'
    '</svg>'
)

LOGO_SVG = (
    '<svg viewBox="0 0 100 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<circle cx="50" cy="50" r="47" fill="none" stroke="#2f6b46" stroke-width="2"/>'
    '<circle cx="50" cy="50" r="39" fill="none" stroke="#2f6b46" stroke-width="1" opacity="0.4"/>'
    '<g stroke="#2f6b46" stroke-width="1.4" opacity="0.7">'
    '<line x1="50" y1="50" x2="71" y2="29"/><line x1="50" y1="50" x2="71" y2="71"/>'
    '<line x1="50" y1="50" x2="29" y2="71"/><line x1="50" y1="50" x2="29" y2="29"/></g>'
    '<path d="M50 7 L42 42 L50 50 Z" fill="#5a9b78"/><path d="M50 7 L58 42 L50 50 Z" fill="#245537"/>'
    '<path d="M93 50 L58 42 L50 50 Z" fill="#5a9b78"/><path d="M93 50 L58 58 L50 50 Z" fill="#245537"/>'
    '<path d="M50 93 L58 58 L50 50 Z" fill="#5a9b78"/><path d="M50 93 L42 58 L50 50 Z" fill="#245537"/>'
    '<path d="M7 50 L42 58 L50 50 Z" fill="#5a9b78"/><path d="M7 50 L42 42 L50 50 Z" fill="#245537"/>'
    '<circle cx="50" cy="50" r="5.5" fill="#efe5cd"/><circle cx="50" cy="50" r="3" fill="#5a9b78"/>'
    '</svg>'
)

CSS = r"""<style>
  @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');
  :root{ --bg:#f3ecd8; --card:#fbf6e9; --ink:#2c2a1e; --muted:#675e48; --line:#d9c9a0;
         --blue:#2f6b46; --blue-d:#245537; --green:#2e8b57; --green-bg:rgba(46,139,87,.14);
         --red:#c0392b; --amber:#b8801f; --amber-bg:rgba(184,128,31,.14); --ink2:#2f6b46; --gold:#2f6b46;
         --lux:#2f6b46; --lux-d:#245537; }
  *{ box-sizing:border-box; }
  .hicon{ width:1em; height:1em; display:inline-block; vertical-align:-0.13em; margin-right:.38em; flex:0 0 auto; }
  body{ margin:0; background:var(--bg); color:var(--ink);
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; line-height:1.6; }
  a{ color:inherit; }
  h1, h2{ font-family:"Fraunces",Georgia,"Times New Roman",serif; font-weight:700; letter-spacing:0; }
  .chartbg{ position:fixed; inset:0; z-index:-1; pointer-events:none;
            background:url("world-bg.svg") center center / cover no-repeat; }
  .cfi-grid{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:18px 0 8px; }
  .cfi-stat{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 18px; box-shadow:0 6px 18px rgba(0,0,0,.10); }
  .cfi-num{ font-size:30px; font-weight:700; color:var(--ink); line-height:1.1; }
  .cfi-lab{ font-size:13px; color:var(--muted); margin-top:6px; }
  .cfi-reggrid{ display:grid; grid-template-columns:repeat(2,1fr); gap:14px 26px; }
  .cfi-reg h3{ font-size:15px; margin:8px 0 4px; color:var(--ink); }
  @media(max-width:680px){ .cfi-grid{ grid-template-columns:repeat(2,1fr); } .cfi-reggrid{ grid-template-columns:1fr; } }
  .rtw-controls{ display:flex; gap:18px; flex-wrap:wrap; align-items:flex-end; }
  .rtw-ctl{ display:flex; flex-direction:column; gap:5px; font-size:12px; color:var(--muted); }
  .rtw-ctl select, .rtw-ctl input[type=range]{ min-width:200px; background:#efe5cd; color:var(--ink); border:1px solid var(--line); border-radius:8px; padding:8px 10px; }
  .rtw-ctl b{ color:var(--gold); }
  .rtw-detail{ font-size:12.5px; color:var(--muted); padding:2px 0 12px 40px; line-height:1.5; }
  .rtw-detail .rtw-blurb{ color:var(--ink); }
  .rtw-note{ background:rgba(47,107,70,.08); border:1px solid rgba(47,107,70,.3); border-radius:10px; padding:10px 14px; font-size:13.5px; margin:10px 0; }
  .rtw-share{ display:flex; gap:8px; flex-wrap:wrap; justify-content:center; margin-top:16px; }
  .rtw-share .airchip{ text-decoration:none; cursor:pointer; }
  @media(max-width:620px){ .rtw-detail{ padding-left:8px; } }
  .ticker{ overflow:hidden; background:var(--ink2); border-bottom:1px solid #d9c9a0; }
  .ticker.ow{ background:#efe5cd; }
  .ticker-track{ display:inline-flex; white-space:nowrap; animation:scrollL 70s linear infinite; }
  .ticker.ow .ticker-track{ animation:scrollR 90s linear infinite; }
  .ticker:hover .ticker-track{ animation-play-state:paused; }
  .ti-item{ display:inline-flex; align-items:center; gap:7px; padding:8px 18px; text-decoration:none;
            font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13.5px; color:#8a7d64; border-right:1px solid #d9c9a0; }
  .ti-item:hover{ background:#efe5cd; }
  .ti-flag{ width:18px; height:13px; object-fit:cover; border-radius:2px; }
  .ti-code{ color:var(--ink); font-weight:700; }  .ti-price{ color:var(--ink); font-weight:700; }
  .down{ color:#2e8b57; } .up{ color:#c0392b; } .ow{ color:#5a9b78; }
  @keyframes scrollL{ from{ transform:translateX(0);} to{ transform:translateX(-50%);} }
  @keyframes scrollR{ from{ transform:translateX(-50%);} to{ transform:translateX(0);} }
  .regionbar{ background:#efe5cd; border-bottom:1px solid #d9c9a0; padding:8px 14px; overflow-x:auto; white-space:nowrap; }
  .regchip{ background:transparent; border:1px solid #d9c9a0; color:#8a7d64; font-size:12.5px;
            padding:5px 13px; border-radius:20px; cursor:pointer; margin-right:7px; }
  .regchip.on{ background:#2f6b46; color:#fff; border-color:#2f6b46; font-weight:600; }
  .topbar{ position:sticky; top:0; z-index:60; }
  .blog-wrap{ max-width:760px; }
  .blog-eyebrow{ color:var(--lux); font-size:12.5px; letter-spacing:.05em; text-transform:uppercase; margin-bottom:6px; }
  .blog-title{ font-size:40px; margin:0 0 16px; }
  .blog-deal{ display:flex; flex-wrap:wrap; gap:14px; justify-content:space-between; align-items:center; background:#efe5cd; border:1px solid var(--line); border-radius:14px; padding:16px 18px; margin-bottom:22px; }
  .blog-deal-label{ font-weight:700; } .blog-deal-dates{ color:var(--muted); font-size:13px; }
  .blog-deal-right{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  .blog-price{ font-size:26px; font-weight:800; color:var(--ink); } .blog-was{ color:var(--muted); font-size:13px; }
  .blog-sec{ margin:0 0 22px; } .blog-sec h2{ font-size:21px; margin:0 0 8px; } .blog-sec p{ color:var(--ink); line-height:1.7; }
  .blog-list{ margin:0; padding-left:20px; line-height:1.9; } .blog-list li{ color:var(--ink); }
  .blog-sec a, .art-lede a{ color:var(--gold); }
  .crumbs{ font-size:12.5px; color:var(--muted); margin-bottom:10px; } .crumbs a{ color:var(--gold); text-decoration:none; }
  .art-meta{ font-size:12.5px; color:var(--muted); margin:-8px 0 18px; }
  .art-lede{ font-size:18px; line-height:1.75; color:var(--ink); margin:0 0 22px; }
  .art-answer, .art-takeaways{ background:rgba(47,107,70,.08); border:1px solid rgba(47,107,70,.3);
            border-radius:12px; padding:14px 18px; margin:0 0 22px; }
  .aa-label{ font-size:11.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--gold); font-weight:700; margin-bottom:5px; }
  .art-answer p{ margin:0; color:var(--ink); line-height:1.65; font-size:16px; }
  .art-takeaways ul{ margin:0; padding-left:20px; line-height:1.8; } .art-takeaways li{ color:var(--ink); }
  .art-cta{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:14px;
            background:#efe5cd; border:1px solid var(--line); border-left:3px solid var(--gold);
            border-radius:12px; padding:16px 18px; margin:0 0 24px; }
  .art-cta-txt{ color:var(--ink); font-size:14.5px; max-width:62ch; }
  .art-q{ border-bottom:1px solid var(--line); padding:12px 0; }
  .art-q summary{ cursor:pointer; font-weight:600; color:var(--ink); list-style:none; }
  .art-q summary::-webkit-details-marker{ display:none; }
  .art-q summary::before{ content:"+"; color:var(--gold); margin-right:9px; font-weight:700; }
  .art-q[open] summary::before{ content:"\2013"; }
  .art-q p{ color:var(--ink); line-height:1.7; margin:10px 0 2px; }
  .deal-table{ width:100%; border-collapse:collapse; margin:0 0 24px; }
  .deal-table th{ text-align:left; color:var(--muted); font-weight:600; font-size:11.5px; letter-spacing:.04em; text-transform:uppercase; padding:8px 10px; border-bottom:1px solid var(--line); }
  .deal-table td{ padding:11px 10px; border-bottom:1px solid var(--line); vertical-align:middle; }
  .deal-table tr:hover td{ background:#efe5cd; }
  .dt-dest{ font-weight:600; color:var(--ink); } .dt-code{ color:var(--muted); font-size:12px; font-weight:400; margin-left:4px; }
  .dt-dest .flag{ vertical-align:-4px; margin-right:8px; }
  .dt-dates{ color:var(--muted); font-size:13px; white-space:nowrap; }
  .dt-price{ color:var(--ink); font-weight:800; font-size:17px; white-space:nowrap; }
  .deal-table .book{ padding:6px 13px; font-size:13px; white-space:nowrap; }
  @media(max-width:560px){ .deal-table .dt-dates{ display:none; } }
  .guide-grid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; }
  .guide-card{ display:flex; flex-direction:column; gap:8px; background:var(--card); border:1px solid var(--line); box-shadow:0 6px 18px rgba(0,0,0,.10);
               border-radius:14px; padding:18px 18px 16px; text-decoration:none; transition:border-color .15s,transform .15s; }
  .guide-card:hover{ border-color:var(--gold); transform:translateY(-2px); }
  .gc-kick{ font-size:14.5px; font-weight:800; letter-spacing:.04em; text-transform:uppercase; color:var(--gold); }
  .gc-title{ font-size:18px; font-weight:700; color:var(--ink); line-height:1.3; }
  .gc-desc{ font-size:13.5px; color:var(--muted); line-height:1.55; flex:1; }
  .gc-more{ font-size:13px; color:var(--gold); font-weight:600; }
  .blog-lang{ font-size:13.5px; color:var(--muted); margin-top:8px; }
  .blog-video{ display:flex; align-items:center; gap:14px; background:linear-gradient(135deg,#efe5cd,#efe5cd); border:1px solid var(--line); border-radius:12px; padding:18px 20px; text-decoration:none; color:var(--ink); transition:border-color .15s; }
  .blog-video:hover{ border-color:var(--gold); }
  .bv-play{ display:inline-flex; align-items:center; justify-content:center; width:46px; height:46px; border-radius:50%; background:var(--gold); color:#efe5cd; font-size:18px; flex:0 0 auto; }
  .bv-text{ font-size:15px; }
  .blog-soon{ display:flex; align-items:center; gap:10px; background:#efe5cd; border:1px dashed var(--line); border-radius:12px; padding:18px 20px; color:var(--muted); font-size:14px; }
  .blog-embed{ position:relative; padding-bottom:56.25%; height:0; border-radius:12px; overflow:hidden; border:1px solid var(--line); }
  .blog-embed iframe{ position:absolute; top:0; left:0; width:100%; height:100%; }
  .yt-sub{ display:inline-flex; align-items:center; gap:7px; margin-top:12px; background:#ff0000; color:#fff; border-radius:9px; padding:9px 16px; text-decoration:none; font-weight:600; font-size:14px; }
  .yt-sub:hover{ filter:brightness(1.08); }
  .blog-spark{ background:#efe5cd; border:1px solid var(--line); border-radius:12px; padding:14px 16px; margin-bottom:10px; }
  .blog-spark svg{ width:100%; height:auto; }
    .blog-cta{ display:flex; gap:12px; flex-wrap:wrap; justify-content:center; margin-top:8px; }
  .mv-more{ display:block; margin:10px auto 2px; background:#efe5cd; color:var(--gold); border:1px solid var(--line); border-radius:9px; padding:9px 18px; font-size:13px; cursor:pointer; }
  .mv-more:hover{ border-color:var(--gold); }
  .mv-head{ display:flex; align-items:center; gap:16px; margin:2px 8px 8px; }
  .mv-sortbtn{ background:none; border:0; color:var(--muted); cursor:pointer; font-size:12.5px; display:inline-flex; align-items:center; gap:5px; padding:2px 0; }
  .mv-sortbtn:hover{ color:var(--ink); }
  .mv-sortbtn.on{ color:var(--gold); font-weight:600; }
  .mv-ar{ font-size:10px; }
  .lp-dot{ display:inline-block; width:7px; height:7px; border-radius:50%; background:#2e8b57; margin-right:6px; vertical-align:middle; animation:lppulse 1.8s infinite; }
  @keyframes lppulse{ 0%{box-shadow:0 0 0 0 rgba(46,139,87,.45)} 70%{box-shadow:0 0 0 6px rgba(46,139,87,0)} 100%{box-shadow:0 0 0 0 rgba(46,139,87,0)} }
  .ticker-toggle{ background:#efe5cd; color:var(--gold); border:1px solid var(--line); border-radius:8px; padding:6px 9px; font-size:12px; cursor:pointer; display:inline-flex; align-items:center; gap:5px; line-height:1; }
  .ticker-toggle:hover{ border-color:var(--gold); }
  body.tickers-off .topbar .ticker, body.tickers-off .topbar .regionbar{ display:none !important; }
  header{ background:rgba(255,255,255,.96); backdrop-filter:blur(8px);
          border-bottom:1px solid var(--line); }
  .bar{ max-width:1080px; margin:0 auto; padding:13px 20px; display:flex; align-items:center; justify-content:space-between; gap:12px; }
  .logo{ display:flex; align-items:center; gap:9px; font-weight:700; font-size:19px; text-decoration:none; }
  .logo .mark{ width:34px; height:34px; display:flex; align-items:center; justify-content:center; }
  .logo .mark svg{ width:34px; height:34px; display:block; }
  .nav{ display:flex; align-items:center; gap:15px; flex-wrap:wrap; }
  .nav a.link{ font-size:14px; color:var(--ink); text-decoration:none; }
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
  .indices{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; max-width:1040px; margin:0 auto; }
  @media(max-width:880px){ .indices{ grid-template-columns:repeat(2,1fr); } }
  @media(max-width:560px){ .indices{ grid-template-columns:1fr; } }
  .idx-top{ display:flex; justify-content:space-between; align-items:baseline; gap:8px; }
  .idx-chart{ display:block; width:100%; height:auto; margin-top:8px; }
  .idx-chart-x{ display:flex; justify-content:space-between; font-size:10px; color:#7a715a; margin-top:1px; }
  .idx-chart-empty{ font-size:11px; color:#7a715a; margin-top:8px; }
  .idx-sum{ list-style:none; cursor:pointer; display:flex; align-items:center; justify-content:space-between; gap:10px; padding:14px 16px; }
  .idx-sum::-webkit-details-marker{ display:none; }
  .idx-sum-name{ font-size:15px; font-weight:700; }
  .idx-sum-right{ display:flex; align-items:center; gap:10px; }
  .idx-sum .idx-val{ font-size:19px; margin:0; }
  .idx-sum::after{ content:"\25be"; color:var(--muted); transition:transform .15s; }
  details.idx[open] .idx-sum::after{ transform:rotate(180deg); }
  details.idx[open] .idx-sum{ border-bottom:1px solid var(--line); }
  .idx-body{ padding:12px 16px 14px; font-size:12px; }
  .idx-list{ list-style:none; margin:10px 0 0; padding:0; max-height:230px; overflow:auto; }
  .idx-list li{ display:flex; justify-content:space-between; gap:10px; padding:7px 8px; border-radius:7px; border-top:1px solid rgba(0,0,0,.07); }
  .idx-list li:first-child{ border-top:none; }
  .idx-list li:hover{ background:rgba(47,107,70,.12); }
  .idx-list li span:last-child{ font-variant-numeric:tabular-nums; color:var(--ink); white-space:nowrap; font-weight:600; }
  .owm-bar{ display:flex; gap:8px; margin:2px 0 12px; }
  .owm-bar input{ flex:1; background:#efe5cd; border:1px solid #d9c9a0; border-radius:8px; color:var(--ink); padding:9px 12px; font:inherit; }
  .owreg{ border:1px solid var(--line); border-radius:12px; margin-bottom:10px; background:var(--card); overflow:hidden; box-shadow:0 6px 18px rgba(0,0,0,.10); }
  .owreg-sum{ list-style:none; cursor:pointer; display:flex; align-items:center; justify-content:space-between; gap:10px; padding:15px 18px; }
  .owreg-sum::-webkit-details-marker{ display:none; }
  .owreg-name{ font-size:18px; font-weight:800; color:var(--blue); letter-spacing:.01em; }
  .owreg-meta{ font-size:12.5px; color:var(--muted); font-weight:500; white-space:nowrap; }
  .owreg-meta b{ color:var(--ink); }
  .owreg-sum::after{ content:"\25be"; color:var(--muted); margin-left:6px; transition:transform .15s; }
  details.owreg[open] .owreg-sum::after{ transform:rotate(180deg); }
  details.owreg[open] .owreg-sum{ border-bottom:1px solid var(--line); }
  .owreg-body{ padding:10px 12px 12px; }
  .hm-grid{ display:grid; grid-template-columns:repeat(auto-fill,minmax(74px,1fr)); gap:6px; margin:14px 0; }
  .hm-tile{ position:relative; aspect-ratio:1/1; border-radius:8px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-decoration:none; padding:4px; border:1px solid rgba(0,0,0,.08); transition:transform .1s ease, box-shadow .1s ease; }
  .hm-tile .hm-star{ position:absolute; top:1px; right:3px; background:none; border:0; cursor:pointer; font-size:13px; line-height:1; padding:2px 3px; color:rgba(255,255,255,.6); opacity:.5; text-shadow:0 1px 2px rgba(0,0,0,.45); z-index:2; }
  .hm-tile:hover .hm-star{ opacity:1; }
  .hm-tile .hm-star.on{ opacity:1; color:#fff; }
  .hm-tile:hover{ transform:scale(1.1); box-shadow:0 5px 16px rgba(0,0,0,.22); position:relative; z-index:3; }
  .hm-code{ font-weight:800; font-size:14px; letter-spacing:.02em; line-height:1.1; }
  .hm-city{ font-weight:800; font-size:10.5px; line-height:1.05; max-width:100%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:center; }
  .hm-cc{ font-size:8.5px; font-weight:600; opacity:.82; line-height:1.15; margin-top:1px; max-width:100%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:center; }
  .hm-price{ font-size:11px; font-weight:700; margin-top:2px; font-family:ui-monospace,Menlo,Consolas,monospace; }
  .hm-legend{ display:flex; align-items:center; gap:14px; flex-wrap:wrap; font-size:12.5px; color:var(--muted); margin:4px 0 2px; }
  .hm-leg-item{ display:inline-flex; align-items:center; gap:6px; }
  .hm-key{ width:15px; height:15px; border-radius:4px; display:inline-block; border:1px solid rgba(0,0,0,.08); }
  @media(max-width:560px){ .hm-grid{ grid-template-columns:repeat(auto-fill,minmax(64px,1fr)); gap:5px; } .hm-code{ font-size:12px; } .hm-city{ font-size:9.5px; } .hm-cc{ font-size:7.5px; } .hm-price{ font-size:10px; } }
  .owc-reg{ font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-weight:700; margin:16px 0 6px; padding-top:4px; border-top:1px solid rgba(0,0,0,.08); }
  .owc-reg:first-child{ border-top:none; margin-top:2px; }
  details.owc{ border:1px solid #d9c9a0; border-radius:10px; margin-bottom:8px; background:#efe5cd; overflow:hidden; }
  details.owc[open]{ border-color:#d9c9a0; }
  .owc-sum{ list-style:none; cursor:pointer; display:flex; align-items:center; justify-content:space-between; gap:10px; padding:12px 14px; }
  .owc-sum::-webkit-details-marker{ display:none; }
  .owc-sum::after{ content:"\25be"; color:var(--muted); margin-left:6px; transition:transform .15s; }
  details.owc[open] .owc-sum::after{ transform:rotate(180deg); }
  .owc-country{ display:flex; align-items:center; gap:9px; font-weight:600; font-size:15px; }
  .owc-meta{ font-size:13px; color:var(--muted); white-space:nowrap; }
  .owc-meta b{ color:var(--ink); }
  .owc-body{ padding:2px 10px 10px; border-top:1px solid rgba(0,0,0,.06); }
  .owc-body .owr{ border-bottom:1px solid rgba(0,0,0,.06); }
  .owc-body .owr:last-child{ border-bottom:none; }
  .idx-c-from{ color:#7a715a; font-size:11px; }
  .idx{ background:var(--card); border-radius:12px; color:var(--ink); overflow:hidden; }
  .idx-name{ margin:0; font-size:13px; color:var(--muted); } .idx-val{ margin:4px 0 0; font-size:24px; font-weight:700; }
  .idx-sub{ margin:2px 0 0; font-size:12px; color:#7a715a; }
  .idx-move.down{ color:#2e8b57; } .idx-move.up{ color:#c0392b; } .idx-move.new,.idx-move.flat{ color:#7a715a; }
  .panel{ background:var(--card); border:1px solid var(--line); border-radius:14px; overflow:hidden; }
  .mv-row{ display:flex; align-items:center; gap:10px; padding:11px 16px; border-top:1px solid var(--line); }
  .mv-row:first-child{ border-top:0; }
  .mv-dest{ display:flex; align-items:center; gap:11px; min-width:0; flex:1; }
  .mv-name{ font-size:15px; } .mv-air{ font-size:12px; color:var(--muted); }
  .mv-right{ display:flex; align-items:center; gap:13px; }
  .mv-price{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:15px; color:var(--ink); font-weight:700; }
  .flag{ width:30px; height:21px; object-fit:cover; border-radius:3px; border:1px solid var(--line); }
  .flag-na{ display:inline-flex; align-items:center; justify-content:center; color:var(--muted); background:#efe5cd; }
  .flag-na svg{ width:62%; height:62%; }
  .emoji{ font-size:24px; }
  .sig{ font-size:12px; font-weight:700; padding:3px 10px; border-radius:7px; }
  .s-book{ background:var(--green-bg); color:var(--green); } .s-watch{ background:var(--amber-bg); color:var(--amber); }
  .s-wait{ background:#efe5cd; color:var(--muted); }
  .prange{ display:flex; align-items:center; gap:6px; margin:10px 0 0; }
  .pr-cap{ width:2px; height:11px; background:var(--line); border-radius:2px; flex:none; }
  .pr-line{ position:relative; flex:1; height:4px; background:#e7dcc0; border-radius:3px; }
  .pr-typ{ position:absolute; top:-3px; width:2px; height:10px; background:var(--muted); opacity:.5; transform:translateX(-50%); }
  .pr-dot{ position:absolute; top:50%; width:12px; height:12px; border-radius:50%; border:2px solid var(--card); transform:translate(-50%,-50%); }
  .pr-dot.g{ background:var(--green); } .pr-dot.y{ background:var(--gold); } .pr-dot.r{ background:var(--red); }
  .pr-lab{ display:flex; justify-content:space-between; font-size:11px; color:var(--muted); margin:5px 0 8px; }
  .pr-verdict{ font-weight:700; } .pr-verdict.g{ color:var(--green); } .pr-verdict.y{ color:var(--gold); } .pr-verdict.r{ color:var(--red); }
  .pr-fresh{ font-size:11px; color:var(--muted); margin:0 0 10px; }
  .pr-fresh .dotc{ display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--green); margin-right:6px; vertical-align:middle; }
  .owm-bar{ display:flex; gap:10px; align-items:center; margin:0 0 12px; flex-wrap:wrap; }
  .owm-bar input{ flex:1; min-width:170px; background:#efe5cd; color:var(--ink); border:1px solid var(--line); border-radius:9px; padding:9px 12px; font-size:14px; }
  .owm-bar input::placeholder{ color:var(--muted); }
  .owm-sort{ background:var(--card); border:1px solid var(--line); color:var(--ink); font-size:13px; font-weight:600; padding:9px 14px; border-radius:9px; cursor:pointer; white-space:nowrap; }
  .owm-sort:hover{ border-color:var(--gold); color:var(--gold); }
  .owm-sort.active{ border-color:var(--gold); color:var(--gold); }
  .rtw-hero{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:26px; text-align:center; margin:18px 0 22px; }
  .rtw-hero-label{ color:var(--muted); font-size:13.5px; letter-spacing:.04em; }
  .rtw-hero-price{ font-size:48px; font-weight:800; color:var(--ink); line-height:1.1; margin:6px 0; }
  .rtw-hero-sub{ color:var(--muted); font-size:13.5px; }
  .rtw-route{ display:flex; flex-direction:column; gap:10px; }
  .rtw-leg{ display:flex; align-items:center; gap:14px; background:var(--card); border:1px solid var(--line); border-radius:13px; padding:13px 16px; flex-wrap:wrap; }
  .rtw-num{ width:26px; height:26px; flex:none; border-radius:50%; background:#e7dcc0; color:var(--gold); font-weight:700; font-size:13px; display:flex; align-items:center; justify-content:center; }
  .rtw-cities{ display:flex; align-items:center; gap:9px; flex:1; min-width:0; flex-wrap:wrap; }
  .rtw-city{ font-weight:600; font-size:15px; }
  .rtw-arrow{ color:var(--gold); font-size:16px; }
  .rtw-legright{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .rtw-legprice{ font-size:18px; font-weight:800; color:var(--ink); }
  .rtw-legunit{ color:var(--muted); font-size:12px; font-weight:600; }
  @media(max-width:620px){ .rtw-legright{ width:100%; justify-content:flex-start; padding-left:40px; } }
  .ac-wrap{ position:relative; }
  .ac-drop{ display:none; position:absolute; top:100%; left:0; z-index:40; background:var(--card); border:1px solid var(--line); border-radius:10px; margin-top:5px; min-width:260px; max-height:300px; overflow:auto; box-shadow:0 10px 30px rgba(0,0,0,.12); }
  .ac-item{ padding:9px 13px; cursor:pointer; font-size:14px; color:var(--ink); display:flex; justify-content:space-between; gap:12px; align-items:center; }
  .ac-item:hover{ background:#efe5cd; }
  .ac-code{ color:var(--gold); font-size:12px; font-weight:600; }
  @media(max-width:760px){
    .bar{ flex-wrap:wrap; padding:10px 14px; gap:8px 12px; }
    .logo{ font-size:17px; }
    .nav{ width:100%; gap:10px 14px; row-gap:8px; }
    .nav a.link{ font-size:13px; }
    .nav-cta{ padding:7px 12px; font-size:13px; }
    .ticker-toggle{ font-size:11px; padding:5px 8px; }
  }
  @media(max-width:620px){
    .mv-row{ flex-wrap:wrap; align-items:flex-start; row-gap:8px; padding:12px 14px; }
    .mv-dest{ flex:1 1 100%; }
    .mv-right{ flex:1 1 100%; justify-content:flex-start; align-items:center; flex-wrap:wrap; gap:8px 12px; padding-left:0; margin-top:2px; }
    .mv-right .minibar{ order:1; }
    .mv-right .owr-price{ order:2; }
    .mv-right .addret-sm{ order:3; }
    .mv-right .mini-book{ order:4; flex:1 1 100%; text-align:center; font-size:13px; padding:9px 12px; margin-top:2px; }
    .mb-track{ width:60px; }
    .owr .owret{ padding-left:16px; }
    body{ padding-bottom:76px; }
    #chatbtn{ width:48px; height:48px; bottom:14px; right:14px; }
    #chatbtn .chat-ic{ width:20px; height:20px; }
    .bw-toggle{ bottom:14px; left:14px; transform:scale(.9); }
  }
  .minibar{ display:flex; align-items:center; gap:8px; }
  .mb-track{ position:relative; width:74px; height:4px; background:#e7dcc0; border-radius:3px; flex:none; }
  .mb-dot{ position:absolute; top:50%; width:11px; height:11px; border-radius:50%; border:2px solid var(--card); transform:translate(-50%,-50%); }
  .mb-dot.g{ background:var(--green); } .mb-dot.y{ background:var(--gold); } .mb-dot.r{ background:var(--red); }
  .mb-lab{ font-size:11.5px; font-weight:700; min-width:46px; } .mb-lab.g{ color:var(--green); } .mb-lab.y{ color:var(--gold); } .mb-lab.r{ color:var(--red); }
  .mv-destcol{ min-width:0; }
  .owr .mv-row .pr-fresh{ margin:3px 0 0; }
  .owr-price{ display:flex; align-items:baseline; gap:5px; white-space:nowrap; }
  .owr-price .mv-price{ font-size:16px; }
  .ow-unit{ color:var(--muted); font-size:11.5px; font-weight:600; }
  .owr-pct{ font-size:11.5px; font-weight:700; white-space:nowrap; }
  .owr-pct.good{ color:var(--green); } .owr-pct.bad{ color:var(--red); } .owr-pct.meh{ color:var(--muted); font-weight:600; }
  .addret-sm{ background:transparent; border:1px solid var(--line); color:var(--ink); font-size:12px; font-weight:600; padding:6px 11px; border-radius:7px; cursor:pointer; white-space:nowrap; }
  .addret-sm:hover{ border-color:var(--gold); color:var(--gold); }
  .owr .owret{ display:none; padding:0 16px 12px 49px; }
  .owr .owret.show{ display:block; }
  .owret-lab{ color:var(--muted); font-size:12.5px; } .owret-rp{ font-weight:700; font-size:15px; color:var(--ink); } .owret-link{ color:var(--gold); font-size:12.5px; margin-left:8px; }
  @media(max-width:760px){ .mv-right{ flex-wrap:wrap; justify-content:flex-end; gap:8px; } .owr .owret{ padding-left:16px; } }
  .ow-card .ow-top{ display:flex; align-items:center; gap:8px; margin-bottom:4px; }
  .ow-card .ow-from{ color:var(--muted); font-size:12.5px; }
  .ow-card .ow-date{ color:var(--muted); font-size:13px; margin:2px 0 0; }
  .ow-unit{ color:var(--muted); font-size:12.5px; font-weight:600; }
  .addret{ margin:6px 0 0; background:transparent; border:1px solid var(--line); color:var(--ink); font-size:13px; font-weight:600; padding:9px; border-radius:9px; cursor:pointer; width:100%; }
  .addret:hover{ border-color:var(--gold); color:var(--gold); }
  .owret{ display:none; margin-top:10px; border-top:1px dashed var(--line); padding-top:10px; }
  .owret.show{ display:block; }
  .owret-lab{ color:var(--muted); font-size:12px; }
  .owret-rp{ font-size:17px; font-weight:700; color:var(--ink); margin:2px 0 8px; } .owret-rp span{ color:var(--muted); font-size:12px; font-weight:600; }
  .star{ background:none; border:0; cursor:pointer; font-size:19px; color:#b3a584; line-height:1; padding:0; }
  .star.on{ color:var(--lux); }
  .mini-book{ background:var(--blue); color:#fff; text-decoration:none; font-size:13px; font-weight:600; padding:6px 13px; border-radius:7px; }
  .mini-book:hover{ background:var(--blue-d); }
  .citybar{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
  .citybar select{ padding:10px 12px; border:1px solid var(--line); border-radius:9px; font-size:14px; min-width:240px; }
  .citybar button{ background:var(--blue); color:#fff; border:0; padding:10px 16px; border-radius:9px; font-weight:600; cursor:pointer; }
  .citychips{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
  .citychip{ background:var(--ink2); color:#fff; font-size:13px; padding:6px 12px; border-radius:20px; display:inline-flex; gap:8px; align-items:center; }
  .citychip b{ cursor:pointer; color:#8a7d64; }
  .airchips{ display:flex; flex-wrap:wrap; gap:8px; }
  .airchip{ background:var(--card); border:1.5px solid var(--blue); color:var(--blue); font-size:13px; font-weight:600; padding:6px 14px; border-radius:20px; cursor:pointer; }
  .airchip.on{ background:var(--ink2); color:#fff; border-color:#15130c; }
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
  .cardacts{ display:flex; align-items:center; gap:10px; margin-top:12px; }
  .cardacts .flipbtn{ margin-top:0; width:auto; flex:1; }
  .sharebtn{ display:inline-flex; align-items:center; gap:6px; background:none; border:1px solid var(--line); color:var(--ink); font:inherit; font-size:12.5px; font-weight:600; padding:7px 12px; border-radius:8px; cursor:pointer; white-space:nowrap; }
  .sharebtn:hover{ border-color:var(--blue); color:var(--blue); background:rgba(47,107,70,.06); }
  .sharebtn .shico{ width:15px; height:15px; }
  .share-backdrop{ position:fixed; inset:0; z-index:9998; background:rgba(0,0,0,.28); }
  .sharepop{ position:fixed; z-index:9999; background:var(--card); border:1px solid var(--line); border-radius:14px; box-shadow:0 14px 44px rgba(0,0,0,.24); padding:16px 16px 15px; width:min(330px,92vw); }
  .sharepop h4{ margin:0 0 5px; font-size:15px; }
  .sharepop .sp-msg{ font-size:12.5px; color:var(--muted); margin:0 0 13px; line-height:1.5; }
  .sharepop .sp-links{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  .sharepop .sp-links a, .sharepop .sp-copy{ display:flex; align-items:center; justify-content:center; gap:6px; padding:9px 10px; border-radius:9px; border:1px solid var(--line); background:var(--bg); color:var(--ink); text-decoration:none; font-size:13px; font-weight:600; cursor:pointer; }
  .sharepop .sp-links a:hover, .sharepop .sp-copy:hover{ border-color:var(--blue); color:var(--blue); }
  .sharepop .sp-copy{ grid-column:1 / -1; }
  .mf-toast{ position:fixed; left:50%; bottom:26px; transform:translateX(-50%); z-index:10000; background:#1f2d24; color:#fff; padding:11px 18px; border-radius:10px; font-size:13.5px; font-weight:600; box-shadow:0 8px 26px rgba(0,0,0,.3); }
  .owr-acts{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
  .owr-share{ display:inline-flex; align-items:center; gap:5px; background:none; border:1px solid var(--line); color:var(--muted); font:inherit; font-size:12px; font-weight:600; padding:6px 10px; border-radius:8px; cursor:pointer; white-space:nowrap; }
  .owr-share:hover{ border-color:var(--blue); color:var(--blue); background:rgba(47,107,70,.06); }
  .owr-share .shico{ width:13px; height:13px; }
  .deal-flash{ animation:dealflash 3s ease-out 1; border-radius:12px; }
  @keyframes dealflash{ 0%,55%{ background:rgba(46,139,87,.20); box-shadow:0 0 0 3px rgba(46,139,87,.38); } 100%{ background:transparent; box-shadow:none; } }
  .binfo-h{ font-weight:600; font-size:14px; margin:8px 0 10px; }
  .binfo{ font-size:13px; margin:5px 0; line-height:1.5; } .binfo b{ font-weight:600; }
  .finehint{ font-size:11px; color:var(--muted); margin:12px 0 0; }
  .card{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px; display:flex; flex-direction:column; box-shadow:0 6px 18px rgba(0,0,0,.10); }
  .card-top{ display:flex; align-items:center; justify-content:space-between; min-height:34px; }
  .card-top-right{ display:flex; align-items:center; gap:8px; }
  .badge{ background:var(--green-bg); color:var(--green); font-weight:600; font-size:12px; padding:4px 10px; border-radius:20px; }
  .badge.flash{ background:#fdecec; color:#c0392b; }
  .cardmeta{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin:0 0 10px; }
  .spark{ vertical-align:middle; }
  .trip{ font-size:12.5px; color:var(--muted); margin:0 0 12px; } .trip b{ color:var(--ink); font-weight:600; }
  .dest{ font-size:19px; margin:12px 0 2px; } .route{ color:var(--muted); font-size:13.5px; margin:0; }
  .dates{ color:var(--muted); font-size:13px; margin:2px 0 0; }
  .price{ font-size:27px; font-weight:700; margin:14px 0 16px; color:var(--ink); }
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
  #chatbtn{ position:fixed; bottom:20px; right:20px; width:56px; height:56px; border-radius:50%; background:var(--blue); color:#fff; border:0; font-size:24px; cursor:pointer; box-shadow:0 4px 14px rgba(0,0,0,.10); z-index:50; }
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
  header{ background:rgba(247,241,224,.94); backdrop-filter:blur(8px); border-bottom:1px solid var(--line); }
  .logo .mark{ background:none; }
  .nav a.link.active{ color:var(--gold); font-weight:700; text-decoration:underline; text-underline-offset:6px; text-decoration-thickness:2px; }
  /* dark text on gold buttons */
  .nav-cta, .book, .mini-book, .form button, .citybar button, .cp-in button{ color:#fff; font-weight:700; }
  .nav-cta:hover{ filter:brightness(1.07); }
  #chatbtn{ color:#fff; box-shadow:0 6px 20px rgba(0,0,0,.55); }
  .cp-msg.you .bub, .cp-msg.you .bub a{ color:#15130c; }
  .ticker, .ticker.ow, .regionbar{ background:#1c3d29; border-bottom:1px solid #16301f; }
  .ti-item{ color:#e7f0e8; font-weight:600; border-right:1px solid rgba(255,255,255,.10); }
  .ti-item:hover{ background:rgba(255,255,255,.10); }
  .ti-code{ color:#ffffff; } .ti-price{ color:#ffffff; }
  .down{ color:#74dca0; } .up{ color:#ff8a7a; } .ow{ color:#9fd8b6; }
  .regchip{ background:rgba(255,255,255,.06); border-color:rgba(255,255,255,.32); color:#eaf3ec; }
  .regchip:hover{ background:rgba(255,255,255,.14); border-color:rgba(255,255,255,.5); }
  .regchip.on{ background:#f3ecd8; color:#1c3d29; border-color:#f3ecd8; font-weight:700; }
  .idx{ background:#efe5cd; border:1px solid var(--line); }
  .badge.flash{ background:rgba(192,57,43,.13); color:#c0392b; }
  .s-wait{ background:rgba(122,113,90,.13); color:var(--muted); }
  .airchip.on{ background:var(--gold); color:#fff; border-color:var(--gold); font-weight:700; }
  .citychip{ background:var(--gold); color:#fff; } .citychip b{ color:#fff; }
  .summary{ background:var(--card); border-color:var(--line); border-left:4px solid var(--gold); }
  input, select, textarea{ background:#efe5cd; color:var(--ink); border-color:var(--line); }
  .citybar select, .form input, .cp-in input{ background:#efe5cd; color:var(--ink); }
  ::placeholder{ color:#7a715a; }
  .star{ color:#7a715a; }
  .cust-btn{ color:var(--muted); }
  .cp-msg .bub{ background:#efe5cd; }

  /* ====================  Fleet Tracker label  ==================== */
  .ticker{ display:flex; align-items:stretch; }
  .ticker{ position:relative; }
  .ticker .ticker-track{ flex:1 1 auto; min-width:0; position:relative; z-index:1; }
  .ti-label{ flex:0 0 auto; position:relative; z-index:3; display:inline-flex; align-items:center; gap:6px; padding:8px 14px;
             background:#f3ecd8; color:#1c3d29; font-family:ui-monospace,Menlo,Consolas,monospace;
             font-size:11.5px; font-weight:700; letter-spacing:.10em; text-transform:uppercase; white-space:nowrap; }
  .ticker.ow .ti-label{ background:#f3ecd8; color:#1c3d29; border-right:1px solid rgba(255,255,255,.14); }

  /* ====================  Historical context banners  ==================== */
  .context-banner{ display:flex; gap:10px; align-items:flex-start; margin:0 0 14px;
                   background:linear-gradient(90deg, rgba(231,185,78,.09), rgba(47,107,70,0));
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
  .intro-grid line{ stroke:#efe5cd; stroke-width:1; }
  .intro-arc{ fill:none; stroke:var(--gold); stroke-width:4; stroke-linecap:round;
              stroke-dasharray:1300; stroke-dashoffset:1300;
              animation:mfArc 1.0s cubic-bezier(.45,0,.25,1) .1s forwards; }
  .intro-dot-a{ fill:var(--ink); opacity:0; animation:mfFade .3s ease .05s forwards; }
  .intro-dot-b{ fill:none; stroke:var(--gold); stroke-width:4; opacity:0;
                animation:mfFade .3s ease 1.0s forwards; }
  .intro-plane{ opacity:0; animation:mfFade .25s ease .1s forwards; }
  .intro-plane path{ fill:var(--gold); }
  .intro-ttl{ font:800 96px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
              fill:var(--ink); opacity:0; animation:mfFade .45s ease .45s forwards; }
  .intro-sub{ font:600 40px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
              fill:var(--gold); opacity:0; animation:mfFade .45s ease .7s forwards; }
  .intro-url{ font:500 30px ui-monospace,Menlo,Consolas,monospace;
              fill:var(--muted); opacity:0; animation:mfFade .4s ease 1.0s forwards; }
  @keyframes mfArc{ to{ stroke-dashoffset:0; } }
  @keyframes mfFade{ from{ opacity:0; } to{ opacity:1; } }
  @media(prefers-reduced-motion:reduce){
    .intro-arc{ animation:none; stroke-dashoffset:0; }
    .intro-plane,.intro-ttl,.intro-sub,.intro-url,.intro-dot-a,.intro-dot-b{
      animation:none; opacity:1; }
  }

  /* ====================  Landing hero  ==================== */
  .lander{ position:relative; overflow:hidden; text-align:center; padding:48px 20px 22px; }
  .lander-slim{ padding:34px 20px 12px; }
  .lander-slim h1{ font-size:33px; }
  .lander-glow{ position:absolute; top:-170px; left:50%; transform:translateX(-50%); width:820px; height:440px;
                background:radial-gradient(ellipse at center, rgba(47,107,70,.14), rgba(47,107,70,0) 70%);
                pointer-events:none; z-index:0; }
  .lander-inner{ position:relative; z-index:1; max-width:660px; margin:0 auto; }
  .eyebrow{ display:inline-block; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:10px;
            letter-spacing:.22em; text-transform:uppercase; color:var(--lux);
            border:1px solid rgba(47,107,70,.4); border-radius:30px; padding:6px 13px; margin-bottom:16px; }
  .lander h1{ font-size:38px; line-height:1.08; margin:0 0 13px; letter-spacing:-.015em; }
  .lander h1 .g{ color:var(--gold); }
  .lander .lead{ font-size:15px; color:var(--muted); max-width:560px; margin:0 auto 20px; line-height:1.6; }
  .lander .lead .buy{ color:var(--green); font-weight:700; }
  /* ---- Hybrid bright hero (light sky band; dark data resumes below) ---- */
  .lander-bright{ background:linear-gradient(180deg,#dcebff 0%,#e8f3ff 8%,#eaf4ff 60%,#dfeefc 100%); }
  .lander-bright{ background:linear-gradient(180deg,#d6e9ff 0%,#e9f4ff 55%,#f4faff 100%); border-bottom:1px solid #efe5cd; }
  .lander-bright h1{ color:#0d1a30; }
  .lander-bright h1 .g{ color:#2f6b46; }
  .lander-bright .lead{ color:#3c4a62; }
  .lander-bright .eyebrow{ color:#2f6b46; border-color:rgba(23,105,196,.35); background:rgba(255,255,255,.7); }
  .lander-bright .trust{ color:#5b6b86; }
  .lander-bright .trust b{ color:#0d1a30; }
  .fsearch{ background:var(--card); border:1px solid var(--line); border-radius:16px; box-shadow:0 14px 38px rgba(0,0,0,.12);
            padding:15px; max-width:560px; margin:6px auto 12px; text-align:left; }
  .fsearch .fs-row{ display:flex; gap:10px; flex-wrap:wrap; align-items:flex-end; margin-bottom:10px; }
  .fs-trip{ align-items:center; gap:16px; margin-bottom:12px; }
  .fs-radio,.fs-check{ display:inline-flex; align-items:center; gap:7px; font-size:13px; color:var(--ink); font-weight:600; cursor:pointer; }
  .fs-radio input,.fs-check input{ accent-color:var(--blue); width:16px; height:16px; }
  .fs-field{ display:flex; flex-direction:column; gap:5px; flex:1; min-width:115px; }
  .fs-field label{ font-size:10.5px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
  .fs-field input,.fs-field select{ background:#fffdf7; color:var(--ink); border:1px solid #cdbb8e; border-radius:9px;
            padding:9px 10px; font-size:13.5px; font-family:inherit; transition:border-color .15s, box-shadow .15s; }
  .fsearch input:focus,.fsearch select:focus{ outline:none; border-color:var(--green); box-shadow:0 0 0 3px rgba(46,139,87,.18); }
  .fs-od .fs-field{ flex:1; min-width:150px; }
  .fs-swap{ flex:0 0 auto; align-self:flex-end; margin-bottom:4px; background:#efe5cd; border:1px solid var(--line);
            color:var(--blue); width:34px; height:34px; border-radius:9px; cursor:pointer; font-size:16px; }
  .fs-swap:hover{ background:#e7dcc0; }
  .fs-alert{ background:#efe5cd; border:1px solid var(--line); border-radius:11px; padding:10px 12px; margin:2px 0 12px; }
  .fs-alert-lab{ display:block; font-size:12.5px; font-weight:700; color:var(--ink); margin-bottom:7px; }
  .fs-alert-lab span{ color:var(--muted); font-weight:500; }
  .fs-alert input{ width:100%; background:#fffdf7; color:var(--ink); border:1px solid #cdbb8e; border-radius:9px; padding:9px 10px; font-size:13.5px; transition:border-color .15s, box-shadow .15s; }
  .fs-go{ display:block; width:100%; background:var(--blue); color:#fff; font-weight:800; font-size:14px; border:0;
          border-radius:11px; padding:11px; cursor:pointer; letter-spacing:.02em; transition:transform .15s, filter .15s, box-shadow .15s; }
  .fs-go:hover{ filter:brightness(1.06); transform:translateY(-1px); box-shadow:0 8px 20px rgba(46,139,87,.28); }
  .fsearch input::placeholder{ color:#8294b5; }
  @media(max-width:560px){ .fs-od{ flex-wrap:wrap; } .fs-swap{ display:none; } }
  .cta-row{ display:flex; gap:12px; justify-content:center; flex-wrap:wrap; }
  .btn-primary{ background:var(--gold); color:#fff; font-weight:700; text-decoration:none;
                padding:13px 26px; border-radius:10px; font-size:15px; }
  .btn-primary:hover{ filter:brightness(1.07); }
  .btn-ghost{ background:#efe5cd; color:var(--ink); border:1px solid #d9c9a0; text-decoration:none;
              padding:13px 24px; border-radius:10px; font-size:15px; font-weight:600; }
  .btn-ghost:hover{ border-color:var(--gold); color:var(--gold); background:#e7dcc0; }
  .trust{ margin:24px 0 0; font-size:12.5px; color:var(--muted); letter-spacing:.02em; }
  .trust b{ color:var(--ink); }
  .statbar{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:24px 0 4px; }
  .stat{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; text-align:center; box-shadow:0 6px 18px rgba(0,0,0,.10); }
  .stat .n{ font-size:26px; font-weight:700; color:var(--gold); font-family:ui-monospace,Menlo,Consolas,monospace; }
  .stat .l{ font-size:12px; color:var(--muted); margin-top:3px; }
  .winner{ display:flex; flex-wrap:wrap; align-items:center; gap:14px 22px; margin:20px 0 4px; padding:20px 24px 18px; border-radius:18px; text-decoration:none; color:var(--ink);
    background:#f0ead0; border:1px solid var(--blue); position:relative; overflow:hidden; transition:border-color .15s, transform .15s; }
  .winner:hover{ border-color:var(--gold); transform:translateY(-2px); }
  .winner-badge{ position:absolute; top:0; left:0; background:var(--lux); color:#fff; font-size:11px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; padding:5px 12px; border-bottom-right-radius:12px; }
  .winner-main{ flex:1 1 240px; min-width:190px; padding-top:12px; }
  .winner-city{ font-size:27px; font-weight:800; line-height:1.15; }
  .winner-route{ color:var(--muted); font-size:13.5px; margin-top:4px; }
  .winner-right{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; padding-top:12px; }
  .winner-price{ font-size:30px; font-weight:800; color:var(--ink); }
  .winner-was{ color:var(--muted); font-size:13px; text-decoration:line-through; }
  .winner-off{ background:rgba(46,139,87,.15); color:#2e8b57; font-weight:700; font-size:12.5px; padding:4px 10px; border-radius:999px; }
  .winner-cta{ flex:0 0 auto; color:var(--gold); font-weight:700; font-size:14px; padding-top:12px; }
  @media(max-width:560px){ .winner-city{ font-size:22px; } .winner-price{ font-size:25px; } }
  .why{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin:32px 0 6px; }
  .why-card{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:22px; }
  .why-card .wi{ width:30px; height:30px; color:var(--gold); margin-bottom:12px; }
  .why-card h3{ margin:0 0 7px; font-size:17px; }
  .why-card p{ margin:0; font-size:13.5px; color:var(--muted); line-height:1.6; }
  @media(max-width:760px){ .why{ grid-template-columns:1fr; } }
  @media(max-width:680px){ .statbar{ grid-template-columns:repeat(2,1fr); } .lander h1{ font-size:27px; } .lander{ padding-top:34px; } }

  /* ====================  Promise strip  ==================== */
  .promise{ margin:46px 0 6px; border:1px solid var(--line); border-radius:16px; padding:26px 24px;
            background:linear-gradient(180deg, rgba(231,185,78,.05), rgba(47,107,70,0)); }
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
  .worldmap{ width:100%; height:auto; display:block; border-radius:10px; background:#efe5cd; }
  .ml-grat line{ stroke:#2f6b46; stroke-width:0.5; opacity:0.13; stroke-dasharray:1 5; }
  .ml-rhumb line{ stroke:#2f6b46; stroke-width:0.4; opacity:0.14; }
  .ml-rhumb circle{ stroke:#2f6b46; opacity:0.4; }
  .ml-lab{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11px; letter-spacing:2px; fill:#2f6b46; opacity:0.26; }
  #mapRoutes path{ stroke:#566273; stroke-width:0.7; opacity:0.5; cursor:pointer; }
  #mapRoutes path:hover{ stroke:#9aa6b6; opacity:0.9; }
  #mapGlow path{ stroke:#2e8b57; stroke-width:1.5; opacity:0.95; cursor:pointer; }
  #mapGlow path:hover{ stroke:#5fffa6; }
  #mapDots circle{ fill:#5a9b78; }
  .wm-hint{ font-size:11.5px; color:var(--muted); text-align:center; padding:7px 0 2px; }

  /* ====================  Trip Lab + live prices  ==================== */
  .tl-card{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px 18px; margin:0 0 18px; }
  .tl-card h2{ margin:0 0 4px; font-size:19px; }
  .tl-sub{ margin:0 0 14px; color:var(--muted); font-size:13.5px; line-height:1.55; }
  .tl-form{ display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; margin-bottom:14px; }
  .tl-form label{ display:flex; flex-direction:column; gap:5px; font-size:12px; color:var(--muted); }
  .tl-form input, .tl-form select{ background:#efe5cd; color:var(--ink); border:1px solid var(--line); border-radius:9px; padding:10px 12px; font-size:14px; min-width:120px; }
  .tl-form input[maxlength="3"]{ text-transform:uppercase; letter-spacing:.08em; }
  .tl-form .tl-go{ border:0; cursor:pointer; }
  .mm-card{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; margin-bottom:10px; box-shadow:0 6px 18px rgba(0,0,0,.10); }
  .mm-card[data-best]{ border-color:var(--blue); }
  .mm-head{ display:flex; align-items:center; gap:12px; margin-bottom:11px; }
  .mm-city{ font-size:17px; font-weight:700; }
  .mm-badge{ font-size:10.5px; font-weight:700; background:var(--blue); color:#fff; padding:2px 9px; border-radius:999px; margin-left:6px; vertical-align:middle; }
  .mm-tot{ font-size:15px; font-weight:700; color:var(--ink); margin-top:2px; } .mm-tot span{ font-size:12px; font-weight:500; color:var(--muted); }
  .mm-legs{ display:flex; gap:10px; flex-wrap:wrap; }
  .mm-leg{ flex:1; min-width:180px; display:flex; align-items:center; gap:10px; background:#efe5cd; border:1px solid var(--line); border-radius:9px; padding:9px 12px; text-decoration:none; color:var(--ink); }
  .mm-leg:hover{ border-color:var(--blue); }
  .mm-who{ font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.05em; color:var(--blue); }
  .mm-from{ font-size:12.5px; color:var(--muted); flex:1; }
  .mm-price{ font-weight:800; }
  .tl-load{ text-align:center; padding:26px 10px; color:var(--muted); } .tl-load p{ margin:8px 0 0; font-size:13px; }
  .hop-leg{ border-top:1px solid var(--line); } .hop-leg:first-child{ border-top:0; }
  .hop-tag{ font-size:11.5px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--gold); padding:13px 16px 2px; }
  .live-btn{ background:none; border:1px solid var(--line); color:var(--muted); font-size:11px; padding:3px 9px; border-radius:7px; cursor:pointer; margin:0 0 10px; }
  .live-btn:hover{ border-color:var(--gold); color:var(--gold); }
  .live-ok{ font-size:11px; color:var(--green); font-weight:700; margin:0 0 10px; display:inline-block; }
  .live-up{ font-size:11px; color:var(--red); font-weight:700; margin:0 0 10px; display:inline-block; }

  /* ====================  Design refresh: nav, rhythm, footer  ==================== */
  .nav{ gap:18px; }
  .nav-star{ font-size:18px; color:var(--muted); text-decoration:none; line-height:1; padding:2px 4px; }
  .nav-star:hover{ color:var(--lux); }
  /* one calm vertical rhythm for stacked homepage / content sections */
  .home-sec{ margin:48px 0 0; }
  .sec-head{ margin:0 0 14px; }
  .section-head-lg{ text-align:center; max-width:620px; margin:60px auto 24px; }
  .section-head-lg h2{ font-size:24px; margin:0 0 8px; letter-spacing:-.01em; }
  .section-head-lg p{ margin:0; color:var(--muted); font-size:14.5px; line-height:1.6; }
  .why-sig{ display:inline-flex; align-items:center; gap:8px; font-weight:700; font-size:13px; }
  .why-dot{ width:12px; height:12px; border-radius:50%; display:inline-block; }
  .why-dot.g{ background:var(--green); } .why-dot.y{ background:var(--gold); } .why-dot.r{ background:var(--red); }
  .readnote{ text-align:center; color:var(--muted); font-size:13.5px; line-height:1.6; max-width:620px; margin:18px auto 0; }
  .mission{ max-width:760px; margin:60px auto 0; text-align:center; }
  .mission .astro{ margin:0 auto 6px; }
  .mission h2{ font-size:24px; margin:6px 0 12px; letter-spacing:-.01em; }
  .mission p{ color:var(--muted); font-size:15px; line-height:1.75; margin:0 auto; max-width:680px; }
  /* slightly larger, calmer cards */
  .why-card{ border-radius:16px; }
  .stat{ border-radius:14px; }
  .statbar{ margin:22px 0 6px; }
  .stat-note{ text-align:center; font-size:13px; color:var(--muted); margin:8px auto 0; }
  /* footer */
  .site-footer{ max-width:1080px; margin:72px auto 0; padding:0 20px; color:var(--muted);
                border-top:1px solid var(--line); text-align:left; }
  .ft-top{ display:grid; grid-template-columns:1.3fr 2fr; gap:40px; padding:40px 0 32px; }
  .ft-brand .logo{ font-size:19px; color:var(--ink); margin-bottom:12px; }
  .ft-tag{ font-size:13.5px; line-height:1.65; color:var(--muted); margin:0 0 16px; max-width:340px; }
  .ft-cta{ display:inline-block; }
  .ft-links{ display:grid; grid-template-columns:repeat(3,1fr); gap:24px; }
  .ft-col h4{ font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink); margin:0 0 12px; }
  .ft-col a{ display:block; color:var(--muted); text-decoration:none; font-size:13.5px; padding:4px 0; }
  .ft-col a:hover{ color:var(--gold); }
  .ft-bottom{ border-top:1px solid var(--line); padding:18px 0 50px; line-height:1.6; }
  .ft-bottom p{ margin:0 0 6px; font-size:12px; color:var(--muted); }
  @media(max-width:760px){ .ft-top{ grid-template-columns:1fr; gap:26px; } }
  @media(max-width:480px){ .ft-links{ grid-template-columns:1fr 1fr; gap:16px; } }

  /* bucket-list quick widget — floating bottom-left, hidden until opened */
  .bw-toggle{ position:fixed; bottom:20px; left:20px; z-index:50; display:inline-flex; align-items:center; gap:6px;
              background:var(--card); color:var(--gold); border:1px solid var(--line); border-radius:24px;
              padding:10px 15px; font-size:15px; cursor:pointer; box-shadow:0 4px 14px rgba(0,0,0,.45); line-height:1; }
  .bw-toggle:hover{ border-color:var(--gold); }
  .bw-toggle #bw-count{ font-size:13px; font-weight:700; color:var(--ink); }
  .bucket-widget{ position:fixed; bottom:74px; left:20px; z-index:50; width:300px; max-width:92vw; max-height:60vh;
                  overflow-y:auto; background:var(--card); border:1px solid var(--line); border-radius:14px;
                  box-shadow:0 8px 30px rgba(0,0,0,.5); padding:14px 16px; display:none; }
  body.bw-open .bucket-widget{ display:block; }
  .bw-head{ font-weight:700; font-size:14px; color:var(--ink); margin-bottom:10px; }
  .bw-empty{ font-size:13px; color:var(--muted); line-height:1.5; }
  .bw-row{ display:flex; align-items:center; gap:8px; border-top:1px solid var(--line); padding:9px 0; }
  .bw-row:first-of-type{ border-top:0; }
  .bw-row a{ flex:1; min-width:0; text-decoration:none; color:var(--ink); display:flex; flex-direction:column; gap:1px; }
  .bw-row a b{ font-size:13.5px; } .bw-row a span{ font-size:13px; color:var(--gold); } .bw-row a small{ font-size:11.5px; color:var(--muted); }
  .bw-x{ background:none; border:0; color:var(--muted); font-size:16px; cursor:pointer; line-height:1; }
  .bw-x:hover{ color:var(--red); }
  /* share row on city guides */
  .share-row{ display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin:6px 0 22px; }
  .share-lbl{ font-size:13px; color:var(--muted); margin-right:2px; }
  .share-btn{ display:inline-flex; align-items:center; gap:6px; background:#efe5cd; border:1px solid var(--line);
              color:var(--ink); text-decoration:none; font-size:13px; font-weight:600; padding:7px 14px; border-radius:8px; }
  .share-btn:hover{ border-color:var(--gold); color:var(--gold); }
</style>"""

POPUP_JS = r"""<script>
/* Open Aviasales (affiliate) links as a pop-out window so Magellan stays in the background. */
(function(){
  function popout(url){
    var w=Math.min(1180,(screen.availWidth||1180)), h=Math.min(840,(screen.availHeight||840));
    var lx=Math.round(((screen.availWidth||w)-w)/2+(screen.availLeft||0));
    var ty=Math.round(((screen.availHeight||h)-h)/2+(screen.availTop||0));
    var feat='popup=yes,scrollbars=yes,resizable=yes,width='+w+',height='+h+',left='+lx+',top='+ty;
    var win;
    try{ win=window.open(url,'mfBook',feat); }catch(e){ win=null; }
    if(win){ try{ win.focus(); }catch(e){} return true; }
    return false;
  }
  document.addEventListener('click', function(ev){
    if(ev.defaultPrevented) return;
    if(ev.button!==0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    var a=ev.target.closest ? ev.target.closest('a[href]') : null;
    if(!a) return;
    var href=a.getAttribute('href')||'';
    if(href.indexOf('aviasales.com')===-1) return;
    if(popout(a.href)) ev.preventDefault();
  }, true);
})();
</script>"""

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
function flag(cc){ return cc ? '<img class="flag" src="https://flagcdn.com/'+String(cc).toLowerCase()+'.svg" alt="" width="30" height="21" loading="lazy">' : '<span class="flag flag-na" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg></span>'; }
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
function wlRow(m){ return '<div class="mv-row" data-lp data-o="'+m.o+'" data-d="'+m.c+'" data-ow="0"><button class="star on" onclick="toggleDest(\''+m.c+'\')">&#9733;</button>'
  + '<div class="mv-dest">'+flag(m.cc)+'<div><div class="mv-name">'+m.n+'</div>'
  + '<div class="mv-air">'+m.an+' &middot; from '+m.o+'</div></div></div>'
  + '<div class="mv-right"><span class="mv-price">$'+m.p.toLocaleString()+'</span>'
  + '<span class="down">&#9660;'+m.pct+'%</span><span class="sig '+sigClass(m.s)+'">'+m.s+'</span>'
  + '<a class="mini-book" href="'+m.l+'" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div></div>'; }
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
    b.onclick=function(ev){ if(ev){ev.preventDefault();ev.stopPropagation();} bMarketStar(b.dataset.code); }; });
  document.querySelectorAll('.airchip[data-air]').forEach(function(b){ b.classList.toggle('on', WA.indexOf(b.dataset.air)>=0); });
  var wl=document.getElementById('watchlist'), hint=document.getElementById('wl-hint');
  if(wl && hint){ var items=MARKET.filter(function(m){ return WD.indexOf(m.c)>=0 || (WA.length && WA.indexOf(m.a)>=0); });
    if(items.length===0){ hint.style.display='block'; wl.innerHTML=''; } else { hint.style.display='none'; wl.innerHTML=items.map(wlRow).join(''); } }
  var ma=document.getElementById('my-air');
  if(ma){ ma.innerHTML = WA.length ? 'Following: ' + WA.map(function(a){ var m=MARKET.find(function(x){return x.a===a;}); return m?m.an:a; }).join(', ')
    : 'No airlines followed yet — tap one above to follow it.'; }
}
function dealRow(o,d){ var on=WF.indexOf(o+'|'+d.code)>=0; var ow=!d['return'];
  var sub = ow ? ('one-way from '+o+(d.depart?(' &middot; '+d.depart):'')) : ('round-trip from '+o+' &middot; '+d.depart+' &rarr; '+d['return']);
  return '<div class="mv-row" data-lp data-o="'+o+'" data-d="'+d.code+'" data-ow="'+(ow?1:0)+'"><button class="star'+(on?' on':'')+'" onclick="toggleFlight(\''+o+'\',\''+d.code+'\')">'+(on?'&#9733;':'&#9734;')+'</button>'
  + '<div class="mv-dest"><span class="flag flag-na" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg></span>'
  + '<div><div class="mv-name">'+d.name+'</div><div class="mv-air">'+sub+'</div></div></div>'
  + '<div class="mv-right"><span class="mv-price">$'+d.price.toLocaleString()+'</span> <span class="ow-unit">'+(ow?'one-way':'round-trip')+'</span>'
  + '<a class="mini-book" href="'+d.link+'" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div></div>'; }
function findDeal(o,c){ if(!HOME[o]) return null; var best=null;
  var keys = (ACTRIP==='ow') ? ['oneway'] : ['deals'];
  keys.forEach(function(k){ (HOME[o][k]||[]).forEach(function(d){ if(d.code===c && (!best||d.price<best.price)) best=d; }); });
  return best; }
function toggleFlight(o,c){ var key=o+'|'+c; var i=WF.indexOf(key); if(i<0)WF.push(key); else WF.splice(i,1); save(); renderAirportWatch(); renderCities(); }
function renderAirportWatch(){ var box=document.getElementById('airwatch'), hint=document.getElementById('aw-hint'); if(!box||!hint) return;
  if(!WF.length){ hint.style.display='block'; box.innerHTML=''; return; }
  hint.style.display='none';
  box.innerHTML=WF.map(function(key){ var p=key.split('|'), o=p[0], c=p[1]; var d=findDeal(o,c);
    if(d) return dealRow(o,d);
    return '<div class="mv-row"><button class="star on" onclick="toggleFlight(\''+o+'\',\''+c+'\')">&#9733;</button>'
      + '<div class="mv-dest"><span class="flag flag-na" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg></span><div><div class="mv-name">'+c+'</div>'
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
  var ow=(ACTRIP==='ow');
  document.querySelectorAll('[data-actrip]').forEach(function(b){ b.classList.toggle('on', (b.dataset.actrip==='ow')===ow); });
  var key = ow ? 'oneway' : 'deals';
  var pool=[]; valid.forEach(function(c){ pool=pool.concat(HOME[c][key]||[]); });
  var av=regAvail(pool);
  ACSEL=ACSEL.filter(function(r){ return r==='Abroad'?av['Abroad']:av[r]; });
  syncChips('[data-acr]','acr',av,ACSEL);
  var label = ow ? '&middot; cheapest one-way' : '&middot; cheapest anytime';
  deals.innerHTML=valid.map(function(c){
    var arr=(HOME[c][key]||[]).filter(function(d){ return regMatch(d, ACSEL); });
    var h='<div class="grouphdr">'+''+'From '+HOME[c].name+' ('+c+') '+label+'</div>';
    h += arr.length ? arr.map(function(d){ return dealRow(c,d); }).join('')
                    : '<div class="wl-hint">No '+(ow?'one-way ':'')+'deals for this selection.</div>';
    return h; }).join('');
}
var ACSEL=[]; var ACMODE='any'; var ACTRIP='rt';
function toggleACR(r){ if(r==='all'){ ACSEL=[]; } else { var i=ACSEL.indexOf(r); if(i<0)ACSEL.push(r); else ACSEL.splice(i,1); } renderCities(); }
function setACMode(m){ ACMODE=m; renderCities(); }
function setACTrip(t){ ACTRIP=t; if(t==='ow') ACMODE='any'; renderCities(); }
function cpAppend(cls, h){ var m=document.getElementById('cpmsgs'); if(!m) return; var d=document.createElement('div'); d.className='cp-msg '+cls; d.innerHTML='<span class="bub">'+h+'</span>'; m.appendChild(d); m.scrollTop=m.scrollHeight; }
function chatToggle(){ var p=document.getElementById('chatpanel'); if(!p) return; p.classList.toggle('open');
  if(p.classList.contains('open') && !p.dataset.greeted){ cpAppend('bot', "Hi! I search the live deals on this site. Try:<br>&bull; \"cheapest one-way to Asia\"<br>&bull; \"where can I go under $300?\"<br>&bull; \"best time to visit Japan\""); p.dataset.greeted='1'; } }
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
  if(/^(hi|hey|hello|help|what can|how do)/.test(s)) return "I can search live deals here. Try:<br>&bull; \"cheapest one-way to Europe\"<br>&bull; \"where can I go under $200?\"<br>&bull; \"best time to visit Japan\"";
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
  var oneway=!/round[- ]?trip/.test(s);
  var data = (typeof OW!=='undefined' ? OW : []);
  var KW=[['southeast asia','SE Asia'],['se asia','SE Asia'],['east asia','E Asia'],['south asia','S Asia'],['asia','Asia'],['western europe','W Europe'],['west europe','W Europe'],['eastern europe','E Europe'],['east europe','E Europe'],['nordic','Nordic'],['scandinav','Nordic'],['europe','Europe'],['caribbean','Caribbean'],['central america','C America'],['mexico','C America'],['south america','S America'],['oceania','Oceania'],['australia','Oceania'],['middle east','Middle East'],['africa','Africa'],['canada','Canada'],['domestic','USA'],['abroad','Abroad'],['international','Abroad']];
  var region=null; for(var i=0;i<KW.length;i++){ if(s.indexOf(KW[i][0])>=0){ region=KW[i][1]; break; } }
  var cap=null; var m=s.match(/(\d{2,4})/); if(m && /under|below|less|budget|for |\$/.test(s)) cap=parseInt(m[1],10);
  var items=data.slice();
  if(region) items=items.filter(function(d){ return regMatch(d, [region]); });
  if(cap) items=items.filter(function(d){ return botPrice(d)<=cap; });
  if(!region && !cap){ var words=s.replace(/[^a-z ]/g,' ').split(/\s+/).filter(function(w){return w.length>3;});
    if(words.length){ items=data.filter(function(d){ var nm=(d.n||d.name||'').toLowerCase(); return words.some(function(w){ return nm.indexOf(w)>=0; }); }); } }
  items.sort(function(a,b){ return botPrice(a)-botPrice(b); });
  if(!items.length) return "I couldn't find "+(oneway?'one-way ':'')+"deals"+(region?(' to '+region):'')+(cap?(' under $'+cap):'')+" right now. Try a different region, or open the <a href='explore.html'>One-way explorer</a>.";
  var head=(oneway?'one-way ':'round-trip ')+'deals'+(region?(' to '+region):'')+(cap?(' under $'+cap):'')+':';
  return head+'<br>'+botList(items,4,oneway)+'<br><a href="'+(oneway?'explore.html':'market.html')+'">See more &rarr;</a>';
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
var HSECS=['summary','indices','movers','deals','oneway'];
var HL=JSON.parse(localStorage.getItem('fs_home_layout')||'{}');
function secOn(s){ return HL[s]!==false; }
function applyLayout(){ HSECS.forEach(function(s){ var el=document.querySelector('[data-sec="'+s+'"]');
  if(el) el.style.display = secOn(s)?'':'none'; var cb=document.getElementById('cb-'+s); if(cb) cb.checked=secOn(s); }); }
function toggleSec(s){ HL[s]=!secOn(s); localStorage.setItem('fs_home_layout', JSON.stringify(HL)); applyLayout(); }
function toggleCustomize(){ var p=document.getElementById('customizer'); if(p) p.style.display=(p.style.display==='block')?'none':'block'; }
function lmItem(d){ return '<div class="mv-row" data-lp data-o="'+d.o+'" data-d="'+d.c+'" data-ow="0"><div class="mv-dest"><span class="flag flag-na" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg></span>'
  + '<div><div class="mv-name">'+d.n+'</div><div class="mv-air">round-trip from '+d.o+' &middot; '+d.dep+' &rarr; '+d.ret+'</div></div></div>'
  + '<div class="mv-right"><span class="mv-price">$'+d.p.toLocaleString()+'</span>'
  + '<a class="mini-book" href="'+d.l+'" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div></div>'; }
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
function owpItem(d){ return '<div class="mv-row" data-lp data-o="'+d.o+'" data-d="'+d.c+'" data-ow="1"><div class="mv-dest"><span class="flag flag-na" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg></span>'
  + '<div><div class="mv-name">'+d.n+'</div><div class="mv-air">one-way from '+d.o+(d.dep?(' &middot; '+d.dep):'')+'</div></div></div>'
  + '<div class="mv-right"><span class="mv-price">$'+d.p.toLocaleString()+'</span>'
  + '<a class="mini-book" href="'+d.l+'" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div></div>'; }
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
function toggleOwRet(code){ var el=document.getElementById('owret-'+code); if(el) el.classList.toggle('show'); }
document.addEventListener('click', function(e){ var b=e.target.closest && e.target.closest('[data-owret]'); if(b){ toggleOwRet(b.getAttribute('data-owret')); } });
function mfRel(iso){var t=new Date(iso).getTime();if(isNaN(t))return'';var s=Math.max(0,(Date.now()-t)/1000);if(s<5400)return'tracked '+Math.max(1,Math.round(s/60))+'m ago';if(s<86400)return'tracked '+Math.round(s/3600)+'h ago';return'tracked '+Math.round(s/86400)+'d ago';}
function mfFresh(){var ns=document.querySelectorAll('.pr-fresh[data-verified]');for(var i=0;i<ns.length;i++){var sp=ns[i].querySelector('span');if(sp)sp.textContent=mfRel(ns[i].getAttribute('data-verified'));}}
mfFresh();
function flipCard(btn){ var f=btn.closest('.flip'); if(f) f.classList.toggle('flipped'); }
function mfToast(msg){ var t=document.createElement('div'); t.className='mf-toast'; t.textContent=msg; document.body.appendChild(t); setTimeout(function(){ t.style.transition='opacity .4s'; t.style.opacity='0'; setTimeout(function(){ if(t.parentNode) t.parentNode.removeChild(t); },400); },1900); }
function shareClose(){ var b=document.getElementById('share-backdrop'); if(b) b.remove(); var p=document.getElementById('sharepop'); if(p) p.remove(); }
function shareDeal(btn){ var c=btn.closest('[data-c]'); if(!c) return; var enc=encodeURIComponent;
  var o=c.getAttribute('data-o')||'', code=c.getAttribute('data-c')||'', nm=c.getAttribute('data-n')||code, p=c.getAttribute('data-p')||'', dep=c.getAttribute('data-dep')||'', ret=c.getAttribute('data-ret')||'', ow=(c.getAttribute('data-ow')==='1');
  var unit=ow?'one-way':'round-trip';
  var url=location.origin+'/market.html?deal='+enc(o)+'-'+enc(code);
  var pn=Number(p); var ps=isNaN(pn)?p:pn.toLocaleString();
  var text=o+' to '+nm+' for $'+ps+' '+unit+', tracked on Magellan Flights.';
  if(navigator.share){ navigator.share({title:'Magellan Flights deal', text:text, url:url}).catch(function(){}); return; }
  shareSheet(text, url); }
function shareSheet(text, url){ shareClose(); var full=text+' '+url; var enc=encodeURIComponent;
  var bd=document.createElement('div'); bd.className='share-backdrop'; bd.id='share-backdrop'; bd.onclick=shareClose; document.body.appendChild(bd);
  var X='https://twitter.com/intent/tweet?text='+enc(text)+'&url='+enc(url);
  var wa='https://wa.me/?text='+enc(full);
  var fb='https://www.facebook.com/sharer/sharer.php?u='+enc(url);
  var em='mailto:?subject='+enc('A flight deal I found')+'&body='+enc(full);
  var pop=document.createElement('div'); pop.className='sharepop'; pop.id='sharepop'; pop.style.left='50%'; pop.style.top='50%'; pop.style.transform='translate(-50%,-50%)';
  pop.innerHTML='<h4>Share this deal</h4><p class="sp-msg">'+text.replace(/&/g,'&amp;').replace(/</g,'&lt;')+'</p><div class="sp-links">'
    +'<a href="'+X+'" target="_blank" rel="noopener">X</a>'
    +'<a href="'+wa+'" target="_blank" rel="noopener">WhatsApp</a>'
    +'<a href="'+fb+'" target="_blank" rel="noopener">Facebook</a>'
    +'<a href="'+em+'">Email</a>'
    +'<button class="sp-copy" type="button">Copy link and message</button></div>';
  document.body.appendChild(pop);
  pop.querySelector('.sp-copy').onclick=function(){ function done(){ shareClose(); mfToast('Copied. Paste it anywhere to share.'); }
    if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(full).then(done).catch(function(){ fallbackCopy(full); done(); }); }
    else { fallbackCopy(full); done(); } };
}
function fallbackCopy(s){ var ta=document.createElement('textarea'); ta.value=s; ta.style.position='fixed'; ta.style.opacity='0'; document.body.appendChild(ta); ta.select(); try{ document.execCommand('copy'); }catch(e){} ta.remove(); }
window.shareDeal=shareDeal;
function fmtRate(r){ return r>=100?Math.round(r).toLocaleString():(r>=10?r.toFixed(1):r.toFixed(2)); }
function loadFX(){ fetch('https://open.er-api.com/v6/latest/USD').then(function(r){return r.json();}).then(function(d){
  if(d&&d.rates){ FX=d.rates; document.querySelectorAll('[data-cur]').forEach(function(el){ var c=el.dataset.cur;
    if(FX[c]) el.textContent='$1 ≈ '+fmtRate(FX[c])+' '+c; }); } }).catch(function(){}); }
var WSEL=[]; var WORG='all'; var WMODE='any';
function worldItem(x){ return '<div class="mv-row" data-lp data-o="'+x.o+'" data-d="'+x.c+'" data-ow="1"><div class="mv-dest"><span class="flag flag-na" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg></span>'
  + '<div><div class="mv-name">'+x.n+'</div><div class="mv-air">one-way: '+x.on+' ('+x.o+') &rarr; '+x.c+' &middot; '+x.dep+'</div></div></div>'
  + '<div class="mv-right"><span class="mv-price">$'+x.p.toLocaleString()+'</span>'
  + '<a class="mini-book" href="'+x.l+'" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div></div>'; }
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
  var c=btn.closest('[data-lp]'); if(!c) return;
  var o=c.getAttribute('data-o'), d=c.getAttribute('data-c'), dep=c.getAttribute('data-dep'), ret=c.getAttribute('data-ret'), ow=c.getAttribute('data-ow');
  if(!o||!d) return;
  var orig=btn.innerHTML; btn.disabled=true; btn.innerHTML='checking…';
  var u='/api/search?origin='+encodeURIComponent(o)+'&destination='+encodeURIComponent(d)+'&one_way='+(ow==='1'?'true':'false')+'&sorting=price&limit=1';
  if(dep) u+='&departure_at='+dep;
  if(ret && ow!=='1') u+='&return_at='+ret;
  fetch(u).then(function(r){return r.json();}).then(function(j){
    var f=j&&j.data&&j.data[0];
    if(!f){ btn.disabled=false; btn.innerHTML=orig; return; }
    var pe=c.querySelector('.price')||c.querySelector('.mv-price'); var oldp=pe?parseInt((pe.textContent||'').replace(/[^0-9]/g,''),10):0;
    var np=Math.round(f.price);
    if(pe){ if(pe.classList.contains('mv-price')){ pe.textContent='$'+np.toLocaleString(); } else { var was=pe.querySelector('.was'); var unit=pe.querySelector('.ow-unit'); pe.innerHTML='$'+np.toLocaleString(); if(was){ pe.appendChild(document.createTextNode(' ')); pe.appendChild(was); } if(unit){ pe.appendChild(document.createTextNode(' ')); pe.appendChild(unit); } } }
    var bk=c.querySelector('.book')||c.querySelector('.mini-book'); if(bk&&f.link) bk.href=f.link;
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
    var pe=el.querySelector('.mv-price, .price, .dt-price, .winner-price, .blog-price');
    if(pe){ var was=pe.querySelector('.was'); pe.innerHTML='<span class="lp-dot" title="Freshest tracked fare — your live, bookable price is confirmed on Aviasales"></span>$'+np.toLocaleString(); if(was){ pe.appendChild(document.createTextNode(' ')); pe.appendChild(was); } }
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
  return '<div class="mv-row"><div class="mv-dest"><span class="flag flag-na" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg></span><div><div class="mv-name">'+f.destination_airport+'</div><div class="mv-air">'+sub+'</div></div></div><div class="mv-right">'+owMini(p,typ)+'<span class="mv-price"><span class="lp-dot" title="Freshest tracked fare — your live, bookable price is confirmed on Aviasales"></span>'+price+'</span><a class="mini-book" href="'+f.link+'" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div></div>';
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
    '<text class="intro-sub" x="86" y="240">Find the flight deal.</text>'
    '<text class="intro-url" x="86" y="566">magellanflights.com</text>'
    '</svg>')


def top_chrome(active, market):
    nav = []
    for href, label in NAV:
        cls = "link active" if href == active else "link"
        nav.append(f'<a class="{cls}" href="{href}">{label}</a>')
    nav_html = "".join(nav)
    return f"""<body class="tickers-off">
<div id="astro-splash"><div class="intro-stage">{INTRO_SVG}</div></div>
<script>(function(){{var s=document.getElementById('astro-splash');if(!s)return;
var seen;try{{seen=localStorage.getItem('mf_intro');}}catch(e){{}}
if(seen){{s.parentNode.removeChild(s);return;}}
var rm=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function done(){{s.classList.add('hide');try{{localStorage.setItem('mf_intro','1');}}catch(e){{}}setTimeout(function(){{if(s.parentNode)s.parentNode.removeChild(s);}},600);}}
window.addEventListener('load',function(){{setTimeout(done, rm?400:1400);}});}})();</script>
<div class="topbar">
<div class="ticker"><span class="ti-label">Flight Tracker</span><div class="ticker-track">{ticker_rt(market)}</div></div>
<div class="regionbar">{region_buttons()}</div>
<div class="ticker ow"><span class="ti-label">&#8600; One-way</span><div class="ticker-track" id="owtrack"></div></div>
<header>
  <div class="bar">
    <a class="logo" href="index.html"><span class="mark">{LOGO_SVG}</span>{BRAND}</a>
    <nav class="nav">{nav_html}<a class="nav-star" href="watchlist.html" title="My bucket list" aria-label="My bucket list">&#9733;</a><a class="nav-cta" href="newsletter.html">Newsletter</a><button type="button" class="ticker-toggle" onclick="toggleTickers()" title="Hide or show the price ticker" aria-label="Toggle ticker"><span class="tt-ar">&#9660;</span> Ticker</button></nav>
  </div>
</header>
<script>
function toggleTickers(){{ var off=document.body.classList.toggle('tickers-off'); try{{ localStorage.setItem('mf_tickers', off?'off':'on'); }}catch(e){{}} var a=document.querySelector('.ticker-toggle .tt-ar'); if(a) a.innerHTML= off?'&#9660;':'&#9650;'; }}
(function(){{ var on=false; try{{ on=localStorage.getItem('mf_tickers')==='on'; }}catch(e){{}} if(on){{ document.body.classList.remove('tickers-off'); }} var a=document.querySelector('.ticker-toggle .tt-ar'); if(a) a.innerHTML= on?'&#9650;':'&#9660;'; }})();
</script>
</div>"""


WIDGET_HTML = """<aside id="bucket-widget" class="bucket-widget"><div class="bw-head">&#9733; My Bucket List</div><div id="bw-list"></div></aside>
<button class="bw-toggle" onclick="document.body.classList.toggle('bw-open')">&#9733;<span id="bw-count"></span></button>
<script>
window.renderBucket=function(){ var list=[]; try{ list=JSON.parse(localStorage.getItem('mf_bucket')||'[]'); }catch(e){} var cnt=document.getElementById('bw-count'); if(cnt) cnt.textContent=list.length?(' '+list.length):''; var w=document.getElementById('bw-list'); if(w){ w.innerHTML = list.length ? list.map(function(f,i){ return '<div class="bw-row"><a href="'+f.link+'" target="_blank" rel="noopener"><b>'+f.o+' &rarr; '+f.d+'</b><span>$'+(f.price||0).toLocaleString()+(f.ow?' one-way':'')+'</span><small>'+(f.date||'')+(f.ret?(' &rarr; '+f.ret):'')+'</small></a><button class="bw-x" title="remove" onclick="bucketRemove('+i+')">&times;</button></div>'; }).join('') : '<div class="bw-empty">Star &#9734; any deal on Explore to save it here.</div>'; } var pg=document.getElementById('bucket-page'); if(pg){ pg.innerHTML = list.length ? ('<div class="panel">'+list.map(function(f,i){ return '<div class="mv-row" data-lp data-o="'+f.o+'" data-d="'+f.d+'" data-ow="'+(f.ow?'1':'0')+'"><div class="mv-dest"><span class="flag flag-na" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg></span><div><div class="mv-name">'+f.o+' &rarr; '+f.d+'</div><div class="mv-air">'+(f.date||'')+(f.ret?(' &rarr; '+f.ret):'')+(f.ow?' &middot; one-way':' &middot; round-trip')+'</div></div></div><div class="mv-right"><span class="mv-price">$'+(f.price||0).toLocaleString()+'</span><a class="mini-book" href="'+f.link+'" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a><button class="star on" title="remove" onclick="bucketRemove('+i+')">&#9733;</button></div></div>'; }).join('')+'</div>') : '<div class="wl-hint">No saved flights yet. Star &#9734; any deal on the <a href="explore.html">Explore</a> page to add it to your bucket list.</div>'; } };
window.bucketRemove=function(i){ var list=[]; try{ list=JSON.parse(localStorage.getItem('mf_bucket')||'[]'); }catch(e){} list.splice(i,1); localStorage.setItem('mf_bucket',JSON.stringify(list)); window.renderBucket(); };
window.addEventListener('load', window.renderBucket);
</script>"""


# Non-intrusive email capture: a dismissible slide-in that appears only AFTER the
# visitor has engaged (scrolled a bit or ~22s in). Never blocks the page, remembers
# a dismissal for 30 days, and hides for good once someone subscribes. Turns one-time
# SEO/social visitors into repeat visitors via the weekly briefing.
EMAIL_CAPTURE = ("""
<div id="mf-capture" class="mf-capture" role="complementary" aria-label="Newsletter signup">
  <button class="mfc-x" onclick="mfCaptureClose()" aria-label="Dismiss">&times;</button>
  <div class="mfc-body">
    <div class="mfc-title">Catch the deals before they vanish</div>
    <div class="mfc-sub">One email a week: the best fares we tracked and the one trip worth booking. Free, unsubscribe anytime.</div>
    <form class="mfc-form" onsubmit="return mfCaptureSub(event)">
      <input id="mfc-email" type="email" required placeholder="you@email.com" autocomplete="email" aria-label="Email address">
      <button type="submit">Get deals</button>
    </form>
  </div>
</div>
<style>
.mf-capture{ position:fixed; left:50%; bottom:18px; transform:translateX(-50%) translateY(180%); width:min(452px,94vw); background:var(--card,#fbf6e9); border:1px solid var(--line,#d9c9a0); border-radius:14px; box-shadow:0 16px 46px rgba(0,0,0,.24); padding:16px 18px 15px; z-index:9000; transition:transform .5s cubic-bezier(.2,.85,.25,1); }
.mf-capture.show{ transform:translateX(-50%) translateY(0); }
.mfc-x{ position:absolute; top:7px; right:11px; background:none; border:0; font-size:23px; line-height:1; color:var(--muted,#7a715a); cursor:pointer; padding:2px 4px; }
.mfc-x:hover{ color:var(--ink,#2c2a1e); }
.mfc-title{ font-family:"Fraunces",Georgia,serif; font-weight:700; font-size:17.5px; color:var(--ink,#2c2a1e); margin:0 22px 3px 0; }
.mfc-sub{ font-size:12.5px; color:var(--muted,#7a715a); line-height:1.45; margin:0 0 11px; }
.mfc-form{ display:flex; gap:8px; }
.mfc-form input{ flex:1; min-width:0; background:#fffdf6; color:var(--ink,#2c2a1e); border:1px solid var(--line,#d9c9a0); border-radius:9px; padding:10px 12px; font-size:14px; }
.mfc-form input:focus{ outline:none; border-color:var(--blue,#2f6b46); }
.mfc-form button{ background:var(--blue,#2f6b46); color:#fff; border:0; border-radius:9px; padding:10px 17px; font-weight:600; font-size:14px; cursor:pointer; white-space:nowrap; }
.mfc-form button:hover{ background:var(--blue-d,#245537); }
.mfc-ok{ font-size:14.5px; color:var(--green,#2e8b57); font-weight:600; padding:4px 0; }
@media (max-width:520px){ .mf-capture{ bottom:0; border-radius:14px 14px 0 0; width:100vw; } }
</style>
<script>
(function(){
  function subd(){ try{ if(localStorage.getItem('mf_sub')==='1') return true; var d=localStorage.getItem('mf_nl_dismiss'); if(d){ if((Date.now()-parseInt(d,10))/86400000 < 30) return true; } }catch(e){} return false; }
  window.mfCaptureClose=function(){ var el=document.getElementById('mf-capture'); if(el){ el.classList.remove('show'); el.style.transform=''; } try{ localStorage.setItem('mf_nl_dismiss', String(Date.now())); }catch(e){} };
  window.mfCaptureSub=function(e){ e.preventDefault(); var em=((document.getElementById('mfc-email')||{}).value||'').trim(); if(!em) return false; var ap=''; try{ var h=JSON.parse(localStorage.getItem('fs_home')||'[]'); if(h&&h.length) ap=h[0]; }catch(_){}
    var done=function(){ try{ localStorage.setItem('mf_sub','1'); }catch(_){} var b=document.querySelector('#mf-capture .mfc-body'); if(b) b.innerHTML='<div class="mfc-ok">&#10003; You’re in. Check your inbox to confirm.</div>'; setTimeout(window.mfCaptureClose,2800); };
    var fb=function(){ var u="__BEEHIIV__"; var q=u+(u.indexOf('?')<0?'?':'&')+'email='+encodeURIComponent(em)+(ap?('&home_airport='+encodeURIComponent(ap)):''); try{ localStorage.setItem('mf_sub','1'); }catch(_){} try{ window.open(q,'_blank','noopener'); }catch(_){} done(); };
    fetch('/api/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:em,home_airport:ap})}).then(function(r){ if(!r.ok) throw 0; done(); }).catch(fb); return false; };
  // Inline signup blocks placed in-page (mid-content) reuse the same subscribe flow.
  window.mfInlineSub=function(e){ e.preventDefault(); var f=e.target; var inp=f.querySelector('input[type=email]'); var em=inp?((inp.value||'').trim()):''; if(!em) return false; var ap=''; try{ var h=JSON.parse(localStorage.getItem('fs_home')||'[]'); if(h&&h.length) ap=h[0]; }catch(_){}
    var done=function(){ try{ localStorage.setItem('mf_sub','1'); }catch(_){} f.innerHTML='<p style="font-size:1.05rem;color:var(--green);font-weight:600;margin:8px 0">&#10003; You’re in. Check your inbox to confirm.</p>'; };
    var fb=function(){ var u="__BEEHIIV__"; var q=u+(u.indexOf('?')<0?'?':'&')+'email='+encodeURIComponent(em)+(ap?('&home_airport='+encodeURIComponent(ap)):''); try{ localStorage.setItem('mf_sub','1'); }catch(_){} try{ window.open(q,'_blank','noopener'); }catch(_){} done(); };
    fetch('/api/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:em,home_airport:ap})}).then(function(r){ if(!r.ok) throw 0; done(); }).catch(fb); return false; };
  if(subd()) return;
  var shown=false; function reveal(){ if(shown||subd()) return; shown=true; var el=document.getElementById('mf-capture'); if(el){ el.classList.add('show'); el.style.transform='translateX(-50%) translateY(0)'; } }
  setTimeout(reveal, 22000);
  window.addEventListener('scroll', function(){ if(window.scrollY>680) reveal(); }, {passive:true});
})();
</script>""").replace("__BEEHIIV__", BEEHIIV_URL)


def site_footer(today):
    cols = []
    for heading, links in FOOTER_NAV:
        items = "".join(f'<a href="{href}">{label}</a>' for href, label in links)
        cols.append(f'<div class="ft-col"><h4>{heading}</h4>{items}</div>')
    cols_html = "".join(cols)
    return f"""<footer class="site-footer">
  <div class="ft-top">
    <div class="ft-brand">
      <a class="logo" href="index.html"><span class="mark">{LOGO_SVG}</span>{BRAND}</a>
      <p class="ft-tag">Flight deals from the USA and abroad, tracked every day and judged against each route&rsquo;s own price history.</p>
      <a class="nav-cta ft-cta" href="newsletter.html">Join the free newsletter</a>
    </div>
    <nav class="ft-links">{cols_html}</nav>
  </div>
  <div class="ft-bottom">
    <p>Prices are one-way unless marked otherwise and change fast, so book soon if you see one you love. {BRAND} may earn a commission when you book through our links, at no extra cost to you.</p>
    <p>&copy; {BRAND} &middot; Fares found {today} and may change at any time.</p>
  </div>
</footer>"""


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
              .replace("__HOMEJS__", json.dumps(home if active in ("airports.html", "watchlist.html", "explore.html") else {}))
              .replace("__ACOJS__", MAP_COORDS if active == "world.html" else "{}")
              .replace("__ASTRO__", ASTRO_SVG))
    foot = site_footer(today)
    _cc = "{}"; _bm = "{}"; _names = "{}"; _major = "[]"; _heron = "{}"
    if active in ("index.html", "our-story.html"):
        try:
            _hc = set(WORLD_HUBS.keys()) | set(home.keys())
            for _o in oneway:
                _hc.add(_o.get("code")); _hc.add(_o.get("origin"))
            for _m in market:
                _hc.add(_m.get("code")); _hc.add(_m.get("origin"))
            _heron = json.dumps({c: AIRPORT_NAMES[c] for c in sorted(_hc) if c and c in AIRPORT_NAMES})
        except Exception:
            pass
    if active == "explore.html":
        try:
            with open(os.path.join(HERE, "airport_names.json"), encoding="utf-8") as _nf:
                _names = _nf.read().strip()
        except Exception:
            pass
        try:
            _mc = set(WORLD_HUBS.keys()) | set(home.keys())
            for _o in oneway:
                _mc.add(_o.get("code")); _mc.add(_o.get("origin"))
            for _m in market:
                _mc.add(_m.get("code")); _mc.add(_m.get("origin"))
            _major = json.dumps(sorted(c for c in _mc if c))
        except Exception:
            pass
    if active in ("trip.html", "explore.html"):
        try:
            with open(os.path.join(HERE, "code_cc.json"), encoding="utf-8") as _ccf:
                _cc = _ccf.read().strip()
        except Exception:
            pass
        try:
            _bm = json.dumps({m["code"]: round(float(m["benchmark"])) for m in market if m.get("benchmark")})
        except Exception:
            pass
    seo_title, seo_desc = _seo_for(active, title)
    seo_head = head_seo(active, seo_title, seo_desc, market)
    ga = ""
    if GA_MEASUREMENT_ID:
        ga = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>\n'
              f'<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}'
              f'gtag(\'js\',new Date());gtag(\'config\',\'{GA_MEASUREMENT_ID}\');</script>\n')
    # Vercel Web Analytics - framework-agnostic script; Vercel serves /_vercel/insights/script.js
    # for any project once "Web Analytics" is turned on in the project dashboard (Analytics tab).
    # No-ops harmlessly if that toggle is off, so it's always safe to ship.
    vercel_analytics = '<script defer src="/_vercel/insights/script.js"></script>\n'
    return (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'{ga}'
            f'{vercel_analytics}'
            f'<title>{_esc_attr(seo_title)}</title>\n'
            f'<meta name="description" content="{_esc_attr(seo_desc)}">\n'
            f'{seo_head}\n'
            f'<link rel="preconnect" href="https://flagcdn.com" crossorigin>\n'
            f'<link rel="dns-prefetch" href="https://flagcdn.com">\n'
            f'<link rel="icon" type="image/svg+xml" href="favicon.svg">\n'
            f'<link rel="icon" type="image/png" sizes="96x96" href="favicon-96.png">\n'
            f'<link rel="icon" type="image/png" sizes="48x48" href="favicon-48.png">\n'
            f'<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">\n'
            f'<link rel="apple-touch-icon" href="apple-touch-icon.png">\n'
            f'{CSS}\n</head>\n{top_chrome(active, market)}\n{CHART_BG}\n{body}\n{CHAT_HTML}\n{WIDGET_HTML}\n'
            f'{EMAIL_CAPTURE if active not in ("newsletter.html", "newsletter-issue.html", "deal-tweets.html") else ""}\n'
            f'{foot}\n{script}\n{POPUP_JS}\n</body>\n</html>').replace("__CCJS__", _cc).replace("__BMJS__", _bm).replace("__NAMESJS__", _names).replace("__MAJORJS__", _major).replace("__HERONAMESJS__", _heron)


# --------------------------------------------------------------------------- #
# Page bodies
# --------------------------------------------------------------------------- #
def chart_bg_html():
    """A faint fixed 'navigator's chart' behind every page (Atlas vibe):
    graticule grid + compass roses + dashed great-circle arcs, in faint green."""
    import math as _m
    W, H = 1600, 900
    el = []
    for x in range(0, W + 1, 100):
        el.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}"/>')
    for y in range(0, H + 1, 90):
        el.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}"/>')
    grat = f'<g stroke="#2f6b46" stroke-width="1" opacity="0.06">{"".join(el)}</g>'
    roses = []
    for cx, cy, r in [(300, 250, 270), (1290, 660, 320)]:
        seg = []
        for ang in range(0, 360, 30):
            x = cx + r * _m.cos(_m.radians(ang)); y = cy + r * _m.sin(_m.radians(ang))
            seg.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.0f}" y2="{y:.0f}"/>')
        seg.append(f'<circle cx="{cx}" cy="{cy}" r="{r*0.55:.0f}" fill="none"/>')
        seg.append(f'<circle cx="{cx}" cy="{cy}" r="{r*0.3:.0f}" fill="none"/>')
        roses.append(f'<g stroke="#2f6b46" stroke-width="1" opacity="0.08">{"".join(seg)}</g>')
    arcs = []
    for x1, y1, cxx, cyy, x2, y2 in [(110, 720, 720, 180, 1520, 520), (60, 300, 820, 760, 1540, 170)]:
        arcs.append(f'<path d="M{x1} {y1} Q{cxx} {cyy} {x2} {y2}"/>')
    arcg = (f'<g stroke="#2f6b46" stroke-width="1.5" stroke-dasharray="2 9" fill="none" '
            f'opacity="0.13" stroke-linecap="round">{"".join(arcs)}</g>')
    svg = (f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice" '
           f'xmlns="http://www.w3.org/2000/svg">{grat}{roses[0]}{roses[1]}{arcg}</svg>')
    return f'<div class="chartbg-chart" aria-hidden="true">{svg}</div>'


CHART_BG = '<div class="chartbg" aria-hidden="true"></div>'


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
           '<rect x="0" y="0" width="1000" height="500" fill="#efe5cd"/>'
           f'<g class="ml-grat">{"".join(grat)}</g>'
           f'<g class="ml-rhumb">{"".join(rhumb)}</g>'
           f'{"".join(labs)}'
           '<g id="mapRoutes" fill="none"></g>'
           '<g id="mapGlow" fill="none" filter="url(#mglow)"></g>'
           '<g id="mapDots"></g></svg>')
    return ('<div class="worldmap-wrap">'
            '<div class="wm-head"><span class="wm-title">The Mercator Heatmap</span>'
            '<span class="wm-leg"><i class="lg-glow"></i> biggest drops &middot; into the buy zone</span></div>'
            f'{svg}'
            '<div class="wm-hint">Passages light up from the filters below &mdash; hover any glowing route for the fare.</div></div>')


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
    pool = [m for m in market
            if corroborated(m["code"], m["price"]) or FEATURED_VERIFIED.get(m["code"])]
    return pool if pool else market


def oneway_winner(oneway, market):
    """Today's Biggest Winner as a ONE-WAY deal (round-trip only via add-return)."""
    by_code = {}
    for m in market:
        c = m["code"]
        if c not in by_code or m["price"] < by_code[c]["price"]:
            by_code[c] = m
    # Collect the best one-way *values* (furthest below typical), one per destination,
    # then rotate through the top few by day-of-year so the same city isn't featured
    # every single day.
    cands = []  # (ratio, one-way, rt)
    cheapest = None
    seen = set()
    for o in oneway:
        if (o.get("cc") or "").upper() == "US":
            continue
        code = o["code"]
        if cheapest is None:
            cheapest = (o, by_code.get(code))
        if code in seen:
            continue
        rt_o = by_code.get(code)
        try:
            typ_o = float(rt_o["price"]) * 0.62 if rt_o and rt_o.get("price") else 0
            if typ_o > 0:
                cands.append((float(o["price"]) / typ_o, o, rt_o))
                seen.add(code)
        except Exception:
            continue
    if cands:
        cands.sort(key=lambda x: x[0])
        pool = cands[:7]
        idx = datetime.now().timetuple().tm_yday % len(pool)
        w, rt = pool[idx][1], pool[idx][2]
    elif cheapest:
        w, rt = cheapest
    else:
        return ""
    price = float(w["price"]); code = w["code"]
    typ = (float(rt["price"]) * 0.62) if (rt and rt.get("price")) else 0
    c, v = "g", "Low"
    if typ:
        if price > typ * 1.10:
            c, v = "r", "High"
        elif price > typ * 0.90:
            c, v = "y", "Typical"
    palette = {"g": ("rgba(46,139,87,.15)", "var(--green)"),
               "y": ("rgba(47,107,70,.14)", "var(--gold)"),
               "r": ("rgba(192,57,43,.13)", "var(--red)")}
    bg, col = palette[c]
    rtnote = ''
    return (f'<a class="winner" data-o="{html.escape(w["origin"], quote=True)}" data-d="{code}" data-ow="1" href="{html.escape(w["link"], quote=True)}" target="_blank" rel="noopener">'
            f'<span class="winner-badge">Today&rsquo;s Biggest Winner</span>'
            f'<div class="winner-main"><div class="winner-city">{html.escape(w["name"])}</div>'
            f'<div class="winner-route">One-way from {html.escape(w["origin"])} &middot; {html.escape(w["depart"])} &middot; <span style="color:var(--gold)">live price at booking</span>{rtnote}</div></div>'
            f'<div class="winner-right"><span class="winner-price">${price:,.0f}</span>'
            f'<span style="color:var(--muted);font-size:13px">one-way</span>'
            f'<span class="winner-off" style="background:{bg};color:{col}">{v}</span></div>'
            f'<span class="winner-cta">See live price on Aviasales &rarr;</span></a>')


def roundtrip_winner(market):
    """Today's best ROUND-TRIP deal (biggest below-normal), as a winner banner
    that visually matches oneway_winner so the homepage opens with a matched pair."""
    pool = [m for m in featured_pool(market) if m.get("benchmark")]
    if not pool:
        return ""
    # Prefer an ATTRACTIVE deal for the hero: meaningfully below normal AND
    # affordable in absolute terms, so we don't headline a $2k fare just because
    # it's the biggest % drop. Rotate the top few by day so it isn't stale.
    cands = [m for m in pool if signal_for(m["price"], m["benchmark"])[1] >= 15 and float(m["price"]) <= 900]
    if not cands:
        cands = [m for m in pool if signal_for(m["price"], m["benchmark"])[1] >= 8]
    if not cands:
        cands = pool
    cands.sort(key=lambda m: signal_for(m["price"], m["benchmark"])[1], reverse=True)
    pool7 = cands[:7]
    best = pool7[datetime.now().timetuple().tm_yday % len(pool7)]
    _, pct = signal_for(best["price"], best["benchmark"])
    price = float(best["price"])
    if pct >= 8:
        c, v = "g", "Low"
    elif pct >= -6:
        c, v = "y", "Typical"
    else:
        c, v = "r", "High"
    palette = {"g": ("rgba(46,139,87,.15)", "var(--green)"),
               "y": ("rgba(47,107,70,.14)", "var(--gold)"),
               "r": ("rgba(192,57,43,.13)", "var(--red)")}
    bg, col = palette[c]
    dates = (f'{html.escape(best.get("depart",""))} &rarr; {html.escape(best.get("return",""))}'
             if best.get("return") else html.escape(best.get("depart","")))
    return (f'<a class="winner" data-o="{html.escape(best["origin"], quote=True)}" data-d="{best["code"]}" data-ow="0" href="{html.escape(best["link"], quote=True)}" target="_blank" rel="noopener">'
            f'<span class="winner-badge">Today&rsquo;s Best Round-Trip</span>'
            f'<div class="winner-main"><div class="winner-city">{html.escape(best["name"])}</div>'
            f'<div class="winner-route">Round-trip from {html.escape(best["origin"])} &middot; {dates} &middot; <span style="color:var(--gold)">live price at booking</span></div></div>'
            f'<div class="winner-right"><span class="winner-price">${price:,.0f}</span>'
            f'<span style="color:var(--muted);font-size:13px">round-trip</span>'
            f'<span class="winner-off" style="background:{bg};color:{col}">{v}</span></div>'
            f'<span class="winner-cta">See live price on Aviasales &rarr;</span></a>')


def oneway_bar(price, typ):
    """Price-position bar for a one-way fare, using a baseline `typ` derived from
    the destination's round-trip benchmark."""
    try:
        price = float(price); typ = float(typ)
    except Exception:
        return ""
    if typ <= 0:
        return ""
    lo, hi = typ * 0.60, typ * 1.40
    if hi <= lo:
        return ""
    frac = max(2.0, min(98.0, (price - lo) / (hi - lo) * 100))
    tfrac = max(0.0, min(100.0, (typ - lo) / (hi - lo) * 100))
    if price <= typ * 0.90:
        c, v = "g", "Low — great deal"
    elif price <= typ * 1.10:
        c, v = "y", "Typical price"
    else:
        c, v = "r", "High right now"
    return (f'<div class="prange"><span class="pr-cap"></span>'
            f'<span class="pr-line"><span class="pr-typ" style="left:{tfrac:.0f}%"></span>'
            f'<span class="pr-dot {c}" style="left:{frac:.0f}%"></span></span>'
            f'<span class="pr-cap"></span></div>'
            f'<div class="pr-lab"><span>${lo:,.0f} low</span>'
            f'<span class="pr-verdict {c}">{v}</span><span>${hi:,.0f} high</span></div>')


def oneway_card(o, rt):
    code = o["code"]; price = float(o["price"])
    typ = (float(rt["price"]) * 0.62) if (rt and rt.get("price")) else 0
    bar = oneway_bar(price, typ)
    link = html.escape(o["link"], quote=True)
    ret_html = ""; addret = ""
    return (f'<article class="card ow-card" data-region="{continent_of(code)}" data-lp data-o="{html.escape(o["origin"], quote=True)}" data-c="{code}" data-dep="{html.escape(o["depart"], quote=True)}" data-ow="1">'
            f'<div class="ow-top">{flag_img(code)}<span class="ow-from">one-way from {html.escape(o["origin"])}</span></div>'
            f'<h3 class="dest">{html.escape(o["name"])}</h3>'
            f'<p class="ow-date">{html.escape(o["depart"])} &middot; one-way</p>'
            f'<p class="price">${price:,.0f} <span class="ow-unit">one-way</span></p>'
            f'{bar}{verified_tag()}{addret}{ret_html}'
            f'<a class="book" href="{link}" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a>'
            f'</article>')


def oneway_board(oneway, market, limit=8):
    by_code = {}
    for m in market:
        c = m["code"]
        if c not in by_code or m["price"] < by_code[c]["price"]:
            by_code[c] = m
    seen = set(); cards = []
    for o in oneway:
        if (o.get("cc") or "").upper() == "US":
            continue
        if o["code"] in seen:
            continue
        seen.add(o["code"])
        cards.append(oneway_card(o, by_code.get(o["code"])))
        if len(cards) >= limit:
            break
    if not cards:
        return ""
    return (f'<section class="home-sec"><div class="sec-head">'
            f'<h2><svg class="hicon" viewBox="0 0 24 24" fill="none" stroke="#2f6b46" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2.5c.8 0 1.3 1.1 1.3 2.6v3.7l7.2 4.1v1.9l-7.2-2.1v3.6l1.9 1.4v1.5L12 18.5l-3.2 1.2v-1.5l1.9-1.4v-3.6L3.5 14.8v-1.9l7.2-4.1V5.1C10.7 3.6 11.2 2.5 12 2.5z"/></svg> One-way Voyages</h2>'
            f'<span>one-way deals to anywhere</span></div>'
            f'<div class="grid">{"".join(cards)}</div></section>')


HOME_SEARCH_JS = """<script>
var HNAMES=__HERONAMESJS__;
function fsTrip(t){ var r=document.getElementById('hs-return-wrap'); if(r) r.style.display=(t==='oneway')?'none':''; }
function fsSwap(){ var a=document.getElementById('hs-from'), b=document.getElementById('hs-to'), ac=document.getElementById('hs-from-code'), bc=document.getElementById('hs-to-code');
  if(a&&b){ var v=a.value; a.value=b.value; b.value=v; } if(ac&&bc){ var c=ac.value; ac.value=bc.value; bc.value=c; } }
function hsAC(which){
  var inp=document.getElementById('hs-'+which), drop=document.getElementById('hs-'+which+'-ac'), hid=document.getElementById('hs-'+which+'-code');
  if(hid) hid.value='';
  var q=(inp.value||'').trim().toLowerCase(); if(q.length<2){ drop.style.display='none'; drop.innerHTML=''; return; }
  var starts=[],cont=[]; for(var c in HNAMES){ var nm=HNAMES[c]; if(!nm) continue; var i=nm.toLowerCase().indexOf(q); if(i<0) continue; (i===0?starts:cont).push([c,nm]); }
  var list=starts.concat(cont).slice(0,7); if(!list.length){ drop.style.display='none'; drop.innerHTML=''; return; }
  drop.innerHTML=list.map(function(x){ return '<div class="ac-item" data-code="'+x[0]+'" data-name="'+x[1].replace(/"/g,'&quot;')+'"><span>'+x[1]+'</span><span class="ac-code">'+x[0]+'</span></div>'; }).join('');
  drop.style.display='block';
  if(!drop._b){ drop._b=1; drop.addEventListener('click', function(e){ var it=e.target.closest('.ac-item'); if(!it) return; inp.value=it.getAttribute('data-name'); if(hid) hid.value=it.getAttribute('data-code'); drop.style.display='none'; }); }
}
document.addEventListener('click', function(e){ if(!e.target.closest('.ac-wrap')){ var ds=document.querySelectorAll('.ac-drop'); for(var i=0;i<ds.length;i++) ds[i].style.display='none'; } });
function hsResolve(txt){ if(!txt) return ''; var up=txt.trim().toUpperCase(); if(/^[A-Z]{3}$/.test(up)) return up; var q=txt.trim().toLowerCase();
  for(var c in HNAMES){ if((HNAMES[c]||'').toLowerCase().indexOf(q)===0) return c; } for(var c2 in HNAMES){ if((HNAMES[c2]||'').toLowerCase().indexOf(q)>=0) return c2; } return ''; }
function fsDDMM(v){ if(!v) return ''; var p=v.split('-'); return (p.length<3)?'':(p[2]+p[1]); }
function fsSoon(days){ var d=new Date(); d.setDate(d.getDate()+days); return ('0'+d.getDate()).slice(-2)+('0'+(d.getMonth()+1)).slice(-2); }
function homeSearch(e){ e.preventDefault();
  var fEl=document.getElementById('hs-from'), tEl=document.getElementById('hs-to');
  var f=(fEl.value||'').trim(), t=(tEl.value||'').trim();
  if(!f){ fEl.focus(); return false; } if(!t){ tEl.focus(); return false; }
  var fc=((document.getElementById('hs-from-code')||{}).value)||hsResolve(f);
  var tc=((document.getElementById('hs-to-code')||{}).value)||hsResolve(t);
  var dep=document.getElementById('hs-depart').value, ret=document.getElementById('hs-return').value;
  var owEl=document.querySelector('input[name="fs-trip"]:checked'); var oneway=(owEl&&owEl.value==='oneway');
  var travEl=document.getElementById('hs-trav'); var adults=1; if(travEl){ var mt=(travEl.value||'').match(/[0-9]+/); if(mt) adults=Math.max(1,parseInt(mt[0],10)); }
  var emEl=document.getElementById('hs-email'); var em=emEl?emEl.value.trim():'';
  /* A2b. Subscribe through /api/subscribe, not the hosted Beehiiv URL.

     This used to window.open the hosted page with ?email=, which A3 proved on
     2026-07-01 does NOT work: Beehiiv's hosted subscribe page ignores URL query
     params, so the email did not even prefill. Somebody who typed their address
     here got a popup asking for it again, and no home_airport was ever captured.

     The departure airport is BETTER data than the newsletter form gets, because
     the newsletter form has to ask and this one already knows: they just told us
     where they are flying from.

     keepalive is load bearing. The Aviasales redirect fires immediately below,
     and a normal fetch is cancelled on navigation, so the subscribe would be lost
     exactly when the search succeeded. */
  var sub=e.target.getAttribute('data-subscribe');
  if(em){
    if(fc){ try{ localStorage.setItem('fs_home',JSON.stringify([fc])); }catch(_){} }
    try{
      fetch('/api/subscribe',{method:'POST',keepalive:true,
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({email:em,home_airport:fc||''})})
        .catch(function(){ if(sub){ try{ window.open(sub,'_blank','noopener'); }catch(_){} } });
    }catch(_){ if(sub){ try{ window.open(sub,'_blank','noopener'); }catch(_){} } }
  }
  if(fc && tc && fc!==tc){
    var dd=fsDDMM(dep)||fsSoon(21); var path=fc+dd+tc;
    if(!oneway){ path+=(fsDDMM(ret)||fsSoon(28)); }
    path+=adults;
    window.location.href='https://www.aviasales.com/search/'+path+'?marker=741311'; return false;
  }
  var q='explore.html?from='+encodeURIComponent(f)+'&to='+encodeURIComponent(t)+'&trip='+(oneway?'oneway':'round');
  if(dep) q+='&depart='+dep; if(ret && !oneway) q+='&return='+ret;
  window.location.href=q; return false;
}
</script>"""


def body_home(market, hist, cards, lastmin, oneway, summary, world, home=None):
    labels = [("summary", "Market summary"), ("indices", "Fare indices"),
              ("movers", "Biggest movers"), ("deals", "Best deals"),
              ("oneway", "One-way escapes")]
    checks = "".join(f'<label><input type="checkbox" id="cb-{k}" onchange="toggleSec(\'{k}\')"> {lab}</label>'
                     for k, lab in labels)
    top4 = sorted(featured_pool(market), key=lambda m: signal_for(m["price"], m["benchmark"])[1], reverse=True)[:4]
    flash_section = ""
    if top4:
        fcards = "\n".join(card_html(m) for m in top4)
        flash_section = (f'<section class="home-sec"><div class="sec-head">'
                         f'<h2>Round-trip deals</h2><span>there &amp; back</span></div>'
                         f'<div class="grid">{fcards}</div></section>')
    nroutes = len(market)
    noneway = len(oneway)
    try:
        _cc = json.load(open(os.path.join(HERE, "code_cc.json"), encoding="utf-8"))
        ncountries = len({_cc.get(m["code"]) for m in market if _cc.get(m["code"])})
    except Exception:
        ncountries = nroutes
    nbook = sum(1 for m in market if signal_for(m["price"], m["benchmark"])[0] == "BOOK")
    home_trips = {}
    for _og in (home or {}):
        _ow = oneway_winner_for(oneway, market, _og)
        _atw = atw_highlight_for(world, _og)
        if _ow or _atw:
            home_trips[_og] = {"ow": _ow, "atw": _atw}
    home_trips_js = json.dumps(home_trips)
    return f"""<section class="lander lander-slim">
  <div class="lander-inner">
    <span class="eyebrow">Flights, tracked like a stock market</span>
    <h1>Find the flight <span class="g">deal</span>.</h1>
    <p class="lead">Fares from the USA and abroad, judged against each route&rsquo;s own history. Here are today&rsquo;s two standouts &mdash; a full trip and a one-way &mdash; both trading below normal right now.</p>
    <div style="display:flex;gap:22px;justify-content:center;flex-wrap:wrap;margin:14px 0 2px;color:var(--muted);font-size:13.5px">
      <span><b style="color:var(--ink)">{nroutes:,}</b> routes tracked</span>
      <span><b style="color:var(--ink)">{ncountries}</b> countries</span>
      <span><b style="color:var(--green)">{nbook}</b> below normal <i>right now</i></span>
    </div>
    <p class="trust">Free, forever &middot; fares tracked through the day &middot; live price confirmed when you book on Aviasales</p>
  </div>
</section>
<div class="wrap">
  <section class="home-sec" id="deals" style="margin-top:6px">
    <div class="sec-head"><h2>Today&rsquo;s best deals</h2><span>the biggest drops below normal right now</span></div>
    <div id="home-rt">{roundtrip_winner(market)}</div>
    <div id="home-ow" style="margin-top:14px">{oneway_winner(oneway, market)}</div>
    <div style="text-align:center;margin-top:20px">
      <a href="market.html" style="background:var(--blue);color:#fff;font-weight:800;font-size:15px;padding:15px 28px;border-radius:12px;text-decoration:none;display:inline-flex;align-items:center;box-shadow:0 8px 20px rgba(46,139,87,.22)">Find more deals like these in the Market &rarr;</a>
    </div>
    <p class="finehint" style="text-align:center;margin-top:12px">Tap any deal to see today&rsquo;s live price and book on Aviasales.</p>
  </section>

  <section class="home-sec" id="from-your-airport" style="margin-top:10px">
    <div class="sec-head"><h2>Deals from your home airport</h2><span>the deals that actually matter to you</span></div>
    <p style="color:var(--muted);margin:0 0 12px;max-width:640px">The one thing every flight-deal list gets wrong: showing you fares from airports you&rsquo;ll never use. Pick yours and see only the one-way deals that actually leave from near you.</p>
    <div id="fya-welcome" style="display:none;background:rgba(47,107,70,.10);border:1px solid var(--line);border-radius:10px;padding:11px 15px;margin:0 0 12px;font-size:14.5px"></div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
      <select id="fya-select" aria-label="Choose your home airport" onchange="mhSet(this.value)" style="flex:1;min-width:240px;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:15px">{city_options(home or {}, any_opt=True)}</select>
      <a class="btn-ghost" href="airports.html">Browse all airports &rarr;</a>
    </div>
    <script>
    var HOME_TRIPS={home_trips_js};
    function mhSet(c){{if(!c)return;if(c==='__ANY__'){{mhClear();return;}}try{{localStorage.setItem('mh_home',c);}}catch(e){{}}var u=new URL(location.href);u.searchParams.set('home',c);location.href=u.toString();}}
    function mhClear(){{try{{localStorage.removeItem('mh_home');}}catch(e){{}}var u=new URL(location.href);u.searchParams.delete('home');location.href=u.toString();}}
    (function(){{function apply(){{try{{var p=new URLSearchParams(location.search);var code=(p.get('home')||localStorage.getItem('mh_home')||'').toUpperCase();if(!code){{var s0=document.getElementById('fya-select');if(s0)s0.value='__ANY__';return;}}var sel=document.getElementById('fya-select');if(sel)sel.value=code;var nm=(sel&&sel.selectedIndex>=0&&sel.options[sel.selectedIndex])?sel.options[sel.selectedIndex].text:code;var t=HOME_TRIPS[code];var w=document.getElementById('fya-welcome');var tail=' <a href="airports.html" style="color:var(--gold);font-weight:600">See all deals from here &rarr;</a> &middot; <a href="#" onclick="mhClear();return false" style="color:var(--muted)">change</a>';if(t){{if(t.ow){{var ow=document.getElementById('home-ow');if(ow)ow.innerHTML=t.ow;}}if(t.atw){{var aw=document.getElementById('home-atw');if(aw)aw.innerHTML=t.atw;}}if(w){{w.innerHTML='&#9992;&#65039; Showing your best trips from <b>'+nm+'</b>.'+tail;w.style.display='block';}}}}else{{if(w){{w.innerHTML='We don&rsquo;t track enough one-ways from <b>'+nm+'</b> yet &mdash; here are today&rsquo;s top picks.'+tail;w.style.display='block';}}}}}}catch(e){{}}}}if(document.readyState!=='loading'){{apply();}}else{{document.addEventListener('DOMContentLoaded',apply);}}}})();
    </script>
  </section>

  <section class="home-sec"><div id="home-atw">{atw_highlight(world)}</div>
    <div style="text-align:center;margin-top:14px"><a class="btn-ghost" href="around-the-world.html">Search more Around the World trips &rarr;</a></div>
  </section>
  <div class="summary" data-sec="summary">{summary}</div>
  <p class="finehint" style="text-align:center;margin-top:22px"><a href="our-story.html" style="color:var(--blue)">Why &ldquo;Magellan,&rdquo; how we read a price, and everything we track &rarr;</a></p>
</div>
{HOME_SEARCH_JS}
{SIGNUP.replace("__FORM_ACTION__", FORM_ACTION)}"""


def body_story(market, oneway, world):
    """Our Story / About page — the Magellan narrative + how the site works,
    fronted by the same bright BookingBuddy-style search as the homepage."""
    nroutes = len(market)
    noneway = len(oneway)
    try:
        _cc = json.load(open(os.path.join(HERE, "code_cc.json"), encoding="utf-8"))
        ncountries = len({_cc.get(m["code"]) for m in market if _cc.get(m["code"])})
    except Exception:
        ncountries = nroutes
    nbook = sum(1 for m in market if signal_for(m["price"], m["benchmark"])[0] == "BOOK")
    return f"""<section class="lander">
  <div class="lander-inner">
    <span class="eyebrow">Our story</span>
    <h1>Airfare, <span class="g">handed back</span> to ordinary travelers.</h1>
    <p class="lead">Magellan Flights tracks flight deals from the USA and abroad, every day &mdash; and tells you the moment a fare drops below its normal price. Start with a search, or read how we got here.</p>
    <form class="fsearch" data-alert="{FORM_ACTION}" data-subscribe="{BEEHIIV_URL}" onsubmit="return homeSearch(event)" aria-label="Flight search">
      <div class="fs-row fs-trip">
        <label class="fs-radio"><input type="radio" name="fs-trip" value="round" checked onchange="fsTrip('round')"> Round-trip</label>
        <label class="fs-radio"><input type="radio" name="fs-trip" value="oneway" onchange="fsTrip('oneway')"> One-way</label>
        <label class="fs-check"><input type="checkbox" id="hs-nonstop"> Non-stop only</label>
      </div>
      <div class="fs-row fs-od">
        <div class="fs-field"><label>From</label><span class="ac-wrap" style="display:block"><input id="hs-from" placeholder="City or airport" autocomplete="off" oninput="hsAC('from')" style="width:100%"><div id="hs-from-ac" class="ac-drop"></div></span><input type="hidden" id="hs-from-code"></div>
        <button type="button" class="fs-swap" onclick="fsSwap()" aria-label="Swap from and to" title="Swap">&#8644;</button>
        <div class="fs-field"><label>To</label><span class="ac-wrap" style="display:block"><input id="hs-to" placeholder="Where to?" autocomplete="off" oninput="hsAC('to')" style="width:100%"><div id="hs-to-ac" class="ac-drop"></div></span><input type="hidden" id="hs-to-code"></div>
      </div>
      <div class="fs-row">
        <div class="fs-field"><label>Depart</label><input id="hs-depart" type="date"></div>
        <div class="fs-field" id="hs-return-wrap"><label>Return</label><input id="hs-return" type="date"></div>
        <div class="fs-field"><label>Travelers</label><select id="hs-trav"><option>1 traveler</option><option>2 travelers</option><option>3 travelers</option><option>4 travelers</option><option>5+ travelers</option></select></div>
        <div class="fs-field"><label>Class</label><select id="hs-class"><option>Economy</option><option>Premium</option><option>Business</option><option>First</option></select></div>
      </div>
      <div class="fs-alert">
        <span class="fs-alert-lab">Send me alerts when prices drop <span>(optional)</span></span>
        <input id="hs-email" type="email" placeholder="Enter your email" autocomplete="email">
      </div>
      <button type="submit" class="fs-go">Find deals &rarr;</button>
    </form>
    <p class="trust">Free, forever &middot; fares tracked through the day &middot; live price confirmed when you book on Aviasales</p>
  </div>
</section>
<div class="wrap">
  <div class="statbar" style="margin-top:26px">
    <div class="stat"><div class="n">{nroutes}</div><div class="l">routes tracked</div></div>
    <div class="stat"><div class="n">{noneway}+</div><div class="l">one-way fares</div></div>
    <div class="stat"><div class="n">{nbook}</div><div class="l">flagged BUY today</div></div>
    <div class="stat"><div class="n">{ncountries}</div><div class="l">countries</div></div>
  </div>
  <p class="stat-note">Live counts &mdash; the routes, fares and countries we are tracking right now, refreshed through the day.</p>

  <section class="mission" style="margin-top:34px">
    <div class="astro lg" style="width:58px">{ASTRO_SVG}</div>
    <h2>Why &ldquo;Magellan&rdquo;?</h2>
    <p>In 1519, Ferdinand Magellan&rsquo;s expedition set out to do something no one had ever done &mdash; sail all the way around the world. Three years later the survivors came home, and for the first time the whole planet was proven reachable. The map stopped being a rumor and became a place you could actually go.</p>
    <p>Five centuries on, the map is open but the prices are not. Airfare is deliberately confusing &mdash; the same seat swings hundreds of dollars with no explanation. Magellan Flights pulls back that curtain. We put the real numbers in your hands, judge every fare against its own history, and hand the freedom of travel back to ordinary people.</p>
  </section>

  <div class="section-head-lg"><h2>What we actually do</h2><p>Three jobs, every single day &mdash; so you don&rsquo;t have to refresh a dozen booking sites hoping to get lucky.</p></div>
  <div class="why">
    <div class="why-card"><h3>1 &middot; We track</h3><p>We watch one-way and round-trip fares from {nroutes} US routes to {ncountries} countries, refreshed several times a day &mdash; a living market of real, bookable prices.</p></div>
    <div class="why-card"><h3>2 &middot; We judge</h3><p>Every fare is measured against that route&rsquo;s own price history &mdash; its Standard Meridian. That&rsquo;s how we know a $300 ticket to Europe is a genuine steal and a $300 ticket next door is not.</p></div>
    <div class="why-card"><h3>3 &middot; We flag &amp; alert</h3><p>When a price drops well below normal we flag it BUY ({nbook} today) and, if you ask, email you the moment it happens &mdash; so you book at the low instead of the average.</p></div>
  </div>

  <div class="section-head-lg"><h2>How to read a price</h2><p>Every deal carries a colored bar showing where today&rsquo;s fare sits against this route&rsquo;s normal range.</p></div>
  <div class="why">
    <div class="why-card"><span class="why-sig"><span class="why-dot g"></span>Low</span><h3 style="margin-top:12px">A great deal</h3><p>Well below this route&rsquo;s typical price &mdash; a genuinely good moment to book.</p></div>
    <div class="why-card"><span class="why-sig"><span class="why-dot y"></span>Typical</span><h3 style="margin-top:12px">A fair price</h3><p>Around the route&rsquo;s usual range. Fine to book, though a dip may still come.</p></div>
    <div class="why-card"><span class="why-sig"><span class="why-dot r"></span>High</span><h3 style="margin-top:12px">Above normal</h3><p>Higher than this route usually runs. History suggests it&rsquo;s likely to fall &mdash; worth waiting.</p></div>
  </div>
  <p class="readnote">Prices refresh several times a day, and each fare&rsquo;s live price is confirmed when you book on Aviasales &mdash; the figures here are a guide from recent history, so the deal you see is the deal you get.</p>

  <section class="promise">
    <h2>Our promise to you</h2>
    <div class="promise-grid">
      <div class="pr"><span class="pr-n">01</span><p>Prices refreshed <b>through the day</b> — never stale.</p></div>
      <div class="pr"><span class="pr-n">02</span><p>Every fare judged against <b>its own history</b>, so a deal is really a deal.</p></div>
      <div class="pr"><span class="pr-n">03</span><p><b>Always free.</b> We earn only if you book — at no extra cost to you.</p></div>
      <div class="pr"><span class="pr-n">04</span><p><b>No spam.</b> Alerts only when a price actually drops.</p></div>
    </div>
  </section>

  <section class="mission">
    <h2>Where we&rsquo;re headed</h2>
    <p>Magellan started as one traveler&rsquo;s spreadsheet and became a daily market for the rest of us. We&rsquo;re building the place you check first &mdash; where a fair price is obvious, a real deal is unmistakable, and the next trip is always one search away. Thanks for traveling with us.</p>
    <div class="cta-row" style="margin-top:18px"><a class="btn-ghost" href="market.html">Browse today&rsquo;s deals &rarr;</a><a class="btn-ghost" href="newsletter.html">Get the free newsletter &rarr;</a></div>
  </section>
</div>
{HOME_SEARCH_JS}
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
    "LON": {"overview": "London layers two thousand years of history along the Thames: royal palaces, world-class free museums, and villages-turned-neighborhoods, each with its own pulse.",
            "todo": ["Walk the Thames from Westminster to Tower Bridge", "Hit the British Museum and the National Gallery (both free)", "Catch a West End show", "Market-hop Borough and Camden", "Day-trip to Windsor or Oxford by train"],
            "history": "Founded by the Romans as Londinium nearly 2,000 years ago, London grew into the seat of an empire and remains one of the world's great financial and cultural capitals.",
            "culture": "Deeply multicultural and famously understated; pub culture, football, afternoon tea, and a theater and music scene that has shaped the world for decades. More than 300 languages are spoken."},
    "ANC": {"overview": "Anchorage is the gateway to Alaska — a city ringed by mountains and water, minutes from glaciers, fjords and some of the best wildlife viewing on the continent.",
            "todo": ["See glaciers on a Kenai Fjords cruise", "Ride the Alaska Railroad toward Denali", "Spot moose, bears and bald eagles", "Drive the scenic Seward Highway", "Chase the northern lights (Sep–Mar)"],
            "history": "Founded as a railroad construction camp in 1915, Anchorage grew with the military and the 1968 oil boom into Alaska’s largest city and the hub for exploring the 49th state.",
            "culture": "Alaska blends frontier spirit with deep Alaska Native heritage; the outdoors is the culture here, with hiking, fishing and aurora-watching woven into daily life."},
    "GOH": {"overview": "Nuuk is the world’s smallest capital — a colorful town on Greenland’s southwest coast, surrounded by ice-flecked fjords, whales and the raw Arctic.",
            "todo": ["Cruise the Nuuk Fjord past icebergs", "Watch for humpback whales", "Visit the Greenland National Museum", "Hike Lille Malene for big views", "Experience Inuit food and culture"],
            "history": "Founded in 1728 by missionary Hans Egede, Nuuk grew from a small colony into the capital of Greenland, an autonomous territory within the Kingdom of Denmark.",
            "culture": "Greenlandic (Kalaallisut) and Danish are spoken, and Inuit traditions — kayaking, hunting and drum dancing — remain central to a modern Arctic society."},
    "SJO": {"overview": "San Jose is the laid-back capital of Costa Rica and the launch pad for the country’s volcanoes, cloud forests, beaches and famous ‘pura vida’ way of life.",
            "todo": ["Day-trip to Poás or Irazú volcano", "Zipline a cloud forest", "Raft the Pacuare River", "Tour Central Valley coffee farms", "Spot sloths, toucans and monkeys"],
            "history": "San Jose became Costa Rica’s capital in 1823; coffee wealth built its theaters and boulevards, in a country that famously abolished its army in 1948.",
            "culture": "Costa Ricans (‘Ticos’) are known for warmth and the ‘pura vida’ philosophy; the country is a global eco-tourism leader, protecting a quarter of its land as parks and reserves."},
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


def body_blog(market, oneway):
    by_code = {}
    for m in market:
        c = m["code"]
        if c not in by_code or m["price"] < by_code[c]["price"]:
            by_code[c] = m
    best = None; cheapest = None
    for o in oneway:
        if (o.get("cc") or "").upper() == "US":
            continue
        if cheapest is None:
            cheapest = (o, by_code.get(o["code"]))
        rt_o = by_code.get(o["code"])
        try:
            typ_o = float(rt_o["price"]) * 0.62 if (rt_o and rt_o.get("price")) else 0
            if typ_o > 0:
                ratio = float(o["price"]) / typ_o
                if best is None or ratio < best[0]:
                    best = (ratio, o, rt_o)
        except Exception:
            continue
    if best:
        win, rt = best[1], best[2]
    elif cheapest:
        win, rt = cheapest
    else:
        return '<div class="wrap"><div class="pagehead"><h1>Daily Guide</h1><p>No deals to feature yet today.</p></div></div>'
    code = win["code"]; name = win["name"]; price = float(win["price"]); link = html.escape(win["link"], quote=True)
    typ = (float(rt["price"]) * 0.62) if (rt and rt.get("price")) else 0
    rtprice = float(rt["price"]) if (rt and rt.get("price")) else 0
    cc2, vv = "g", "Low — great deal"
    if typ:
        if price > typ * 1.10:
            cc2, vv = "r", "High right now"
        elif price > typ * 0.90:
            cc2, vv = "y", "Typical price"
    pal = {"g": ("rgba(46,139,87,.15)", "var(--green)"), "y": ("rgba(47,107,70,.14)", "var(--gold)"), "r": ("rgba(192,57,43,.13)", "var(--red)")}
    pbg, pcol = pal[cc2]
    g = CITY_GUIDE.get(code)
    info = DEST_INFO.get(code, {"lang": "the local language", "eng": "varies", "visa": "Check entry requirements for US passports", "safe": "Check your government's latest travel advisory", "note": "Verify details before booking"})
    best_time = BEST_TIME.get(code, "year-round")
    if g:
        overview = g["overview"]; history = g["history"]; culture = g["culture"]
        todo = "".join(f"<li>{html.escape(t)}</li>" for t in g["todo"])
    else:
        overview = f"{html.escape(name)} is today's standout one-way deal from our tracker. We don't have a full guide written for it yet, but here are the essentials to help you decide."
        history = "We're still writing the full history for this destination — check back soon."
        culture = f"Locals speak {html.escape(info['lang'])}. {html.escape(info['note'])}."
        todo = "<li>Explore the historic center and main squares</li><li>Try the regional cuisine and markets</li><li>Visit the top museums and landmarks</li><li>Take a popular day-trip nearby</li>"
    todo_block = f"<ul class='blog-list'>{todo}</ul>" if todo else ""
    series = HIST_SERIES.get(code, [])
    spark = sparkline_svg(series)
    if typ and price <= typ * 0.90:
        verdict = f"At <b>${price:,.0f} one-way</b>, this is running well below the usual fare for this route &mdash; a strong time to grab it."
    elif typ:
        verdict = f"Today&rsquo;s <b>${price:,.0f} one-way</b> is around the usual range for this route."
    else:
        verdict = f"Today&rsquo;s standout one-way fare is <b>${price:,.0f}</b>. We track this route&rsquo;s prices daily, so the trend fills in a little more over time."
    cityshort = name.split(",")[0].strip()
    cg_fname = next((gg["fname"] for gg in CITY_GUIDES if gg["code"] == code), None)
    guide_link = (f'<p style="text-align:center;margin-top:8px"><a href="{cg_fname}" '
                  f'style="color:var(--gold);font-weight:600">&rarr; Open the full {html.escape(cityshort)} '
                  f'travel guide</a></p>') if cg_fname else ""
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
        watch_html = '<div class="blog-soon">Video guide coming soon</div>'
    rtnote = f' &middot; round-trip ${rtprice:,.0f} with a return' if (rt and rtprice) else ''
    return f"""<div class="wrap blog-wrap">
  <div class="blog-eyebrow">&#9733; Today&rsquo;s Biggest Winner &middot; best one-way deal on the board</div>
  <h1 class="blog-title">{html.escape(name)}</h1>
  <div class="blog-deal" data-lp data-o="{html.escape(win['origin'], quote=True)}" data-d="{code}" data-ow="1">
    <div><div class="blog-deal-label">One-way from {html.escape(win['origin'])}</div><div class="blog-deal-dates">{html.escape(win.get('depart',''))} &middot; one-way &middot; best time to go: {html.escape(best_time)}{rtnote}</div></div>
    <div class="blog-deal-right"><span class="blog-price">${price:,.0f}</span><span class="blog-was">one-way</span><span class="winner-off" style="background:{pbg};color:{pcol}">{vv}</span><a class="book" href="{link}" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div>
  </div>
  <section class="blog-sec"><h2>The overview</h2><p>{html.escape(overview) if g else overview}</p></section>
  <section class="blog-sec"><h2>Price trend</h2><div class="blog-spark">{spark}</div><p>{verdict}</p></section>
  <section class="blog-sec"><h2>Top things to do</h2>{todo_block}</section>
  <section class="blog-sec"><h2>&#9654;&#65039; Watch a tour</h2>{watch_html}</section>
  <section class="blog-sec"><h2>Is it safe?</h2><p>{html.escape(info['safe'])}. As anywhere, watch your belongings in crowds and tourist areas. Visa for US passports: {html.escape(info['visa'])}. Always check your government&rsquo;s current travel advisory before you go.</p></section>
  <section class="blog-sec"><h2>A bit of history</h2><p>{html.escape(history) if g else history}</p></section>
  <section class="blog-sec"><h2>Culture &amp; language</h2><p>{html.escape(culture) if g else culture}</p><p class="blog-lang"><b>Language:</b> {html.escape(info['lang'])} &middot; <b>English spoken:</b> {html.escape(info['eng'])}</p></section>
  <div class="blog-cta"><a class="btn-primary" href="{link}" target="_blank" rel="noopener">Grab the {html.escape(cityshort)} deal &rarr;</a><a class="btn-ghost" href="explore.html">Find your own deal</a></div>
  {guide_link}
  <p class="finehint" style="text-align:center;margin-top:18px">Updated daily with the standout one-way fare from our tracker. Prices are recently-tracked fares &mdash; your live price is confirmed when you book on Aviasales. Safety and visa notes are general guidance for US travelers &mdash; verify official sources before booking.</p>
</div>"""

def oneway_minibar(price, typ):
    try:
        price = float(price); typ = float(typ)
    except Exception:
        return ""
    if typ <= 0:
        return ""
    lo, hi = typ * 0.6, typ * 1.4
    if hi <= lo:
        return ""
    frac = max(2.0, min(98.0, (price - lo) / (hi - lo) * 100))
    if price <= typ * 0.90:
        c, v = "g", "Low"
    elif price <= typ * 1.10:
        c, v = "y", "Typical"
    else:
        c, v = "r", "High"
    return (f'<div class="minibar"><div class="mb-track"><span class="mb-dot {c}" style="left:{frac:.0f}%"></span></div>'
            f'<span class="mb-lab {c}">{v}</span></div>')


def oneway_row(o, rt, pfx="m"):
    code = o["code"]; price = float(o["price"])
    typ = (float(rt["price"]) * 0.62) if (rt and rt.get("price")) else 0
    bar = oneway_minibar(price, typ)
    pctbadge = ""; dpct = None
    if typ and typ > 0:
        d = (typ - price) / typ * 100
        dpct = d
        if d >= 8:
            pctbadge = f'<span class="owr-pct good">&#9660; {d:.0f}% below typical</span>'
        elif d <= -8:
            pctbadge = f'<span class="owr-pct bad">&#9650; {abs(d):.0f}% above typical</span>'
        else:
            pctbadge = '<span class="owr-pct meh">about typical</span>'
    link = html.escape(o["link"], quote=True)
    addret = ""; ret_html = ""
    pct_attr = f' data-pct="{dpct:.1f}"' if dpct is not None else ""
    return (f'<div class="owr" data-region="{continent_of(code)}" data-price="{price:.0f}" data-month="{(o.get("depart") or "")[:7]}"{pct_attr}>'
            f'<div class="mv-row" data-lp data-o="{html.escape(o["origin"], quote=True)}" data-c="{code}" data-n="{html.escape(o["name"], quote=True)}" data-p="{price:.0f}" data-dep="{html.escape(o["depart"], quote=True)}" data-ow="1">'
            f'<button class="star" data-code="{code}" aria-label="watch">&#9734;</button>'
            f'<div class="mv-dest">{flag_img(code)}<div class="mv-destcol"><div class="mv-name">{html.escape(o["name"])}</div>'
            f'<div class="mv-air">one-way from {html.escape(o["origin"])}</div>{verified_tag()}</div></div>'
            f'<div class="mv-right">{bar}'
            f'<div class="owr-price"><span class="mv-price">${price:,.0f}</span> <span class="ow-unit">one-way</span></div>'
            f'{pctbadge}'
            f'{addret}'
            f'<div class="owr-acts"><button class="owr-share" onclick="shareDeal(this)" aria-label="Share this deal">{share_icon()}<span>Share</span></button>'
            f'<a class="mini-book" href="{link}" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div></div>'
            f'</div>{ret_html}</div>')


def oneway_rows_block(rows_data, market, limit, pfx="m", per_region=0):
    by_code = {}
    for m in market:
        c = m["code"]
        if c not in by_code or m["price"] < by_code[c]["price"]:
            by_code[c] = m
    seen = set(); cand = []
    for o in rows_data:
        if (o.get("cc") or "").upper() == "US":
            continue
        code = o["code"]
        if code in seen:
            continue
        reg = board_region_of(code)
        if reg == "Other":
            continue
        seen.add(code); cand.append((reg, o))
    if per_region:
        groups = {}
        order = []
        for reg, o in cand:
            if reg not in groups:
                groups[reg] = []; order.append(reg)
            groups[reg].append(o)
        picked = []
        for reg in order:
            for o in groups[reg][:per_region]:
                picked.append((reg, o))
        picked.sort(key=lambda x: float(x[1]["price"]))
        cand = picked
    out = []; regions = set()
    for reg, o in cand:
        regions.add(reg)
        out.append(oneway_row(o, by_code.get(o["code"]), pfx))
        if limit and len(out) >= limit:
            break
    return out, regions


def oneway_market(oneway, market, limit=30):
    by_code = {}
    for m in market:
        c = m["code"]
        if c not in by_code or m["price"] < by_code[c]["price"]:
            by_code[c] = m
    seen = {}
    for o in oneway:
        if (o.get("cc") or "").upper() == "US":
            continue
        code = o["code"]
        reg = board_region_of(code)
        if reg == "Other":
            continue
        if code not in seen or float(o["price"]) < float(seen[code]["price"]):
            seen[code] = o
    if not seen:
        return ""
    groups = {}
    for code, o in seen.items():
        reg = board_region_of(code)
        cname = country_from_name(o["name"])
        groups.setdefault((reg, cname), []).append(o)
    region_order = ["North America", "South America", "Europe", "Asia", "Middle East", "Africa", "Oceania"]
    items = []
    for (reg, cname), rows in groups.items():
        rows.sort(key=lambda x: float(x["price"]))
        items.append((reg, float(rows[0]["price"]), cname, rows))
    items.sort(key=lambda t: (region_order.index(t[0]) if t[0] in region_order else 99, t[1]))
    regions_present = [r for r in region_order if any(it[0] == r for it in items)]
    chips = ['<button class="airchip on" data-owreg="all" onclick="owSetReg(&#39;all&#39;)">All</button>']
    for r in regions_present:
        chips.append(f'<button class="airchip" data-owreg="{r}" onclick="owSetReg(&#39;{r}&#39;)">{r}</button>')
    ncountries = len(items)
    ncities = sum(len(it[3]) for it in items)
    by_region = {}
    for reg, cheapest, cname, rows in items:
        by_region.setdefault(reg, []).append((cheapest, cname, rows))
    body = []
    for reg in regions_present:
        countries = by_region[reg]
        reg_cheapest = min(c[0] for c in countries)
        inner = []
        for cheapest, cname, rows in countries:
            city_rows = "".join(oneway_row(o, by_code.get(o["code"]), "m") for o in rows)
            nc = len(rows)
            flag = flag_img(rows[0]["code"])
            cities_attr = html.escape(" ".join((o.get("name") or "").lower() for o in rows), quote=True)
            summary = (f'<summary class="owc-sum"><span class="owc-country">{flag}<span>{html.escape(cname)}</span></span>'
                       f'<span class="owc-meta">from <b>${cheapest:,.0f}</b> one-way &middot; {nc} cit{"y" if nc == 1 else "ies"}</span></summary>')
            inner.append(f'<details class="owc" data-region="{reg}" data-country="{html.escape(cname.lower(), quote=True)}" data-cities="{cities_attr}">{summary}<div class="owc-body">{city_rows}</div></details>')
        reg_sum = (f'<summary class="owreg-sum"><span class="owreg-name">{reg}</span>'
                   f'<span class="owreg-meta">{len(countries)} countries &middot; from <b>${reg_cheapest:,.0f}</b></span></summary>')
        body.append(f'<details class="owreg" data-region="{reg}">{reg_sum}<div class="owreg-body">{"".join(inner)}</div></details>')
    head = ('<div class="sec-head" id="deals"><h2><svg class="hicon" viewBox="0 0 24 24" fill="none" stroke="#2f6b46" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2.5c.8 0 1.3 1.1 1.3 2.6v3.7l7.2 4.1v1.9l-7.2-2.1v3.6l1.9 1.4v1.5L12 18.5l-3.2 1.2v-1.5l1.9-1.4v-3.6L3.5 14.8v-1.9l7.2-4.1V5.1C10.7 3.6 11.2 2.5 12 2.5z"/></svg> One-way Voyages</h2>'
            f'<span>{len(regions_present)} regions &middot; {ncountries} countries &middot; {ncities} one-way fares &middot; tap a region, then a country</span></div>')
    chips_html = f'<div class="airchips" style="margin:2px 0 10px">{"".join(chips)}</div>'
    searchbar = ('<div class="owm-bar"><input type="text" id="ow-q" placeholder="Search a country or city\u2026" oninput="owApply()" autocomplete="off">'
                 '<select id="ow-month" onchange="owApply()" style="background:#efe5cd;color:var(--ink);border:1px solid var(--line);border-radius:9px;padding:9px 12px;font:inherit"><option value="">Any month</option></select></div>')
    panel = f'<div class="panel owm-panel">{"".join(body)}</div>'
    return head + chips_html + searchbar + panel + """<script>var OW_REG="all";function owMonthFill(){var sel=document.getElementById('ow-month');if(!sel)return;var now=new Date();var mn=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];var h='<option value="">Any month</option>';for(var k=0;k<10;k++){var dt=new Date(now.getFullYear(),now.getMonth()+k,1);var v=dt.getFullYear()+'-'+('0'+(dt.getMonth()+1)).slice(-2);h+='<option value="'+v+'">'+mn[dt.getMonth()]+' '+dt.getFullYear()+'</option>';}sel.innerHTML=h;}function owSetReg(r){OW_REG=r;var ch=document.querySelectorAll('[data-owreg]');for(var k=0;k<ch.length;k++){ch[k].classList.toggle('on',ch[k].getAttribute('data-owreg')===r);}owApply();}function owApply(){var q=((document.getElementById('ow-q')||{}).value||'').toLowerCase();var mo=(document.getElementById('ow-month')||{}).value||'';var regs=document.querySelectorAll('.owm-panel .owreg');for(var i=0;i<regs.length;i++){var rg=regs[i];var reg=rg.getAttribute('data-region');if(!(OW_REG==='all'||reg===OW_REG)){rg.style.display='none';continue;}var cs=rg.querySelectorAll('.owc');var any=0;for(var j=0;j<cs.length;j++){var c=cs[j];var ctry=c.getAttribute('data-country')||'';var cities=c.getAttribute('data-cities')||'';var hit=(q===''||ctry.indexOf(q)>=0||cities.indexOf(q)>=0);if(!hit){c.style.display='none';continue;}var rows=c.querySelectorAll('.owr');var vis=0;for(var k2=0;k2<rows.length;k2++){var m=rows[k2].getAttribute('data-month')||'';var rok=(!mo||m===mo);rows[k2].style.display=rok?'':'none';if(rok)vis++;}if(vis){c.style.display='';c.open=(!!mo||!!q);any++;}else{c.style.display='none';}}if(any){rg.style.display='';rg.open=(!!q||!!mo||OW_REG!=='all');}else{rg.style.display='none';}}}owMonthFill();(function(){try{var p=new URLSearchParams(location.search);var d=p.get('deal');if(!d)return;var ix=d.indexOf('-');if(ix<0)return;var o=d.slice(0,ix),c=d.slice(ix+1);setTimeout(function(){try{var row=document.querySelector('.owm-panel .owr .mv-row[data-o="'+o+'"][data-c="'+c+'"]');if(!row)return;var owr=row.closest('.owr'),owc=row.closest('.owc'),owreg=row.closest('.owreg');if(owreg){owreg.style.display='block';owreg.open=true;}if(owc){owc.style.display='block';owc.open=true;}if(owr)owr.style.display='block';try{row.scrollIntoView({block:'center'});}catch(e){}(owr||row).classList.add('deal-flash');}catch(e){}},160);}catch(e){}})();</script>"""


def oneway_lastminute(oneway, market, limit=8):
    soon = sorted([o for o in oneway if (o.get("cc") or "").upper() != "US"], key=lambda o: o.get("depart", ""))
    rows, _ = oneway_rows_block(soon, market, limit, "lm")
    if not rows:
        return ""
    return f'<div class="panel">{"".join(rows)}</div>'


DAILY_WINNER = None


def compute_daily_winner(market, series):
    """Route with the biggest % discount vs its OWN historical average."""
    best = None
    for m in market:
        code = m.get("code")
        try:
            price = float(m["price"])
        except (TypeError, ValueError, KeyError):
            continue
        hist = series.get(code, [])
        if len(hist) < 3:
            continue
        avg = sum(hist) / len(hist)
        if avg <= 0:
            continue
        disc = (avg - price) / avg * 100
        if disc < 5:
            continue
        if best is None or disc > best["disc"]:
            best = {"code": code, "name": m.get("name", code), "origin": m.get("origin", ""),
                    "price": price, "avg": avg, "disc": disc, "link": m.get("link", "")}
    return best


def update_winners_log(winner, days=14):
    """Append today's winner to a rolling JSON log (one entry per date), newest first."""
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(HERE, "winners.json")
    log = []
    try:
        log = json.load(open(path, encoding="utf-8"))
        if not isinstance(log, list):
            log = []
    except Exception:
        log = []
    log = [w for w in log if w.get("date") != today]
    if winner:
        log.insert(0, {"date": today, "code": winner["code"], "name": winner["name"],
                       "origin": winner["origin"], "price": round(winner["price"]),
                       "avg": round(winner["avg"]), "disc": round(winner["disc"]),
                       "link": winner.get("link", "")})
    log = log[:days]
    try:
        json.dump(log, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass
    return log


def winner_highlight_html():
    w = DAILY_WINNER
    if not w:
        return ""
    fl = flag_img(w["code"])
    link = html.escape(w.get("link", ""), quote=True)
    book = (f'<a class="book" href="{link}" target="_blank" rel="noopener" style="font-size:13px;padding:7px 14px">See live price &rarr;</a>'
            if link else f'<a class="book" href="explore.html" style="font-size:13px;padding:7px 14px">Find it &rarr;</a>')
    return (
        '<div style="background:var(--card);border:1px solid var(--gold);border-radius:12px;padding:14px 16px;margin:0 0 16px;display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px">'
        '<div style="display:flex;flex-direction:column;gap:2px;flex:1;min-width:210px">'
        '<span style="font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--gold)">Today&rsquo;s biggest winner</span>'
        f'<span style="font-size:16px;font-weight:700">{fl} {html.escape(w["name"])} <span style="color:var(--muted);font-weight:500;font-size:13px">one-way from {html.escape(w["origin"])}</span></span>'
        f'<span style="font-size:13px;color:var(--muted)"><b style="color:var(--green)">{w["disc"]:.0f}% below</b> its average of ${w["avg"]:,.0f}</span>'
        '</div>'
        '<div style="display:flex;flex-direction:column;align-items:flex-end;gap:5px">'
        f'<span style="font-size:22px;font-weight:800">${w["price"]:,.0f}</span>{book}'
        '</div></div>'
    )


def hm_color(pct):
    """pct = % below the route's normal price (positive = cheaper = greener)."""
    if pct >= 25: return ("#15643a", "#ffffff")
    if pct >= 12: return ("#2e8b57", "#ffffff")
    if pct >= 4:  return ("#9bccab", "#16361f")
    if pct > -4:  return ("#e7dcc0", "#6b6147")
    if pct > -12: return ("#e3a89e", "#591e16")
    if pct > -25: return ("#c0392b", "#ffffff")
    return ("#8d1f17", "#ffffff")


def heatmap_legend():
    keys = [("#15643a", "Big drop"), ("#2e8b57", "Below normal"), ("#e7dcc0", "About even"),
            ("#c0392b", "Above normal"), ("#8d1f17", "Way above")]
    sw = "".join(f'<span class="hm-leg-item"><span class="hm-key" style="background:{c}"></span>{l}</span>'
                 for c, l in keys)
    return f'<div class="hm-legend">{sw}</div>'


HM_REGION_ORDER = ["North America", "South America", "Europe", "Asia", "Middle East", "Africa", "Oceania"]


def _hm_items(oneway, market):
    """Sorted (pct, oneway-row, price) for each destination, best deal first.
    pct = how far the cheapest one-way sits below its NORMAL one-way price, where
    'normal' is estimated from the route's round-trip BENCHMARK (its typical price),
    not the volatile current cheapest round-trip. Using the current cheapest RT made
    discounts look fake (70-90%) because that price is itself often inflated; the
    benchmark is the route's real baseline and improves as price history accrues.
    Guards against stale/phantom cache lows, and caps the claim at a believable
    ceiling so we never over-state a discount."""
    by_code = {}
    for m in market:
        c = m.get("code")
        if not c:
            continue
        try:
            if c not in by_code or float(m["price"]) < float(by_code[c]["price"]):
                by_code[c] = m
        except (TypeError, ValueError, KeyError):
            continue
    best = {}
    for o in oneway:
        if (o.get("cc") or "").upper() == "US":
            continue
        code = o.get("code")
        if not code:
            continue
        rt = by_code.get(code)
        try:
            p = float(o["price"])
            bench = float(rt["benchmark"]) if (rt and rt.get("benchmark")) else 0.0
        except (TypeError, ValueError, KeyError):
            continue
        # Estimated NORMAL one-way = benchmark RT x 0.46. 0.46 is the empirical
        # median ratio of (cheapest one-way / round-trip benchmark) across tracked
        # routes, so a *typical* cheap one-way sits at ~0% below normal and only
        # genuinely-cheap fares show a real discount (was 0.62, which over-flagged
        # nearly everything as a deal).
        typ = bench * 0.46
        if p <= 0 or typ <= 0:
            continue
        if p < bench * 0.12:                    # absurdly low vs the route's normal => stale/phantom
            continue
        pct = (typ - p) / typ * 100.0
        if pct > 55.0:                          # cap: never over-claim a discount we can't stand behind
            pct = 55.0
        if code not in best or pct > best[code][0]:
            best[code] = (pct, o, p)
    return sorted(best.values(), key=lambda x: -x[0])


def _hm_tile(pct, o, p):
    code = o["code"]
    reg = board_region_of(code)
    bg, tc = hm_color(pct)
    below = "below" if pct >= 0 else "above"
    tip = html.escape(f'{o.get("name", code)} from {o.get("origin", "")} — ${p:,.0f}, '
                      f'{abs(pct):.0f}% {below} normal (one-way) — tap for {o.get("name", code)}', quote=True)
    # link to the city's own page: a rich city guide if we have one, else Explore
    # pre-filtered to that destination (cheapest ways to get there).
    cp = globals().get("CODE_TO_CITYPAGE", {}).get(code)
    href = cp if cp else f"explore.html?to={code}"
    nm = o.get("name", code)
    if ", " in nm:
        city, ctry = nm.rsplit(", ", 1)
    else:
        city, ctry = nm, ""
    cc_line = (html.escape(ctry) + " &middot; " + html.escape(code)) if ctry else html.escape(code)
    return (f'<a class="hm-tile" data-region="{html.escape(reg, quote=True)}" href="{href}" '
            f'style="background:{bg};color:{tc}" title="{tip}">'
            f'<button class="star hm-star" data-code="{html.escape(code, quote=True)}" aria-label="Save {html.escape(city, quote=True)} to your watchlist" title="Save to watchlist">&#9734;</button>'
            f'<span class="hm-city">{html.escape(city)}</span>'
            f'<span class="hm-cc">{cc_line}</span>'
            f'<span class="hm-price">${p:,.0f}</span></a>')


def heatmap_build(oneway, market):
    items = _hm_items(oneway, market)
    present = []
    tiles = []
    for it in items:
        reg = board_region_of(it[1]["code"])
        if reg in HM_REGION_ORDER and reg not in present:
            present.append(reg)
        tiles.append(_hm_tile(*it))
    chips = ['<button class="airchip on" data-hmr="all" onclick="hmReg(&#39;all&#39;)">All</button>']
    for r in [x for x in HM_REGION_ORDER if x in present]:
        chips.append(f'<button class="airchip" data-hmr="{r}" onclick="hmReg(&#39;{r}&#39;)">{r}</button>')
    grid = f'<div class="hm-grid" id="hm-grid">{"".join(tiles)}</div>'
    return grid, "".join(chips)


def heatmap_preview(oneway, market, n=42):
    tiles = "".join(_hm_tile(*it) for it in _hm_items(oneway, market)[:n])
    return f'<div class="hm-grid">{tiles}</div>'


HM_JS = ("""<script>(function(){var R='all';function ap(){var ts=document.querySelectorAll('#hm-grid .hm-tile');"""
         """for(var i=0;i<ts.length;i++){var t=ts[i];t.style.display=(R==='all'||t.getAttribute('data-region')===R)?'':'none';}"""
         """var cs=document.querySelectorAll('#hm-chips [data-hmr]');for(var k=0;k<cs.length;k++){cs[k].classList.toggle('on',cs[k].getAttribute('data-hmr')===R);}}"""
         """window.hmReg=function(r){R=r;ap();};})();</script>""")


def body_heatmap(oneway, market):
    grid, chips = heatmap_build(oneway, market)
    return f"""<div class="wrap">
  <div class="pagehead"><h1>Flight Fare Heatmap</h1><p>Every <b>one-way</b> fare we track, at a glance &mdash; <b style="color:#2e8b57">green when it&rsquo;s below its normal price</b> (a deal) and <b style="color:#c0392b">red when it&rsquo;s above</b>. The deeper the color, the bigger the move; about-even fares stay parchment. Filter by region, and tap any tile to see its live price and book.</p></div>
  {heatmap_legend()}
  <div class="airchips" id="hm-chips" style="margin:8px 0 6px">{chips}</div>
  {grid}
  <p class="finehint" style="text-align:center;margin-top:14px">Sorted best deal first. One-way fares judged against each route&rsquo;s usual one-way price &mdash; your live, bookable price is confirmed on Aviasales.</p>
  {BRIEFING_CTA}
{HM_JS}
</div>"""


def body_market(market, hist, cards, lastmin, oneway):
    return f"""<div class="wrap">
  <div class="pagehead"><h1>The Market &mdash; One-Way Flight Deals from the USA</h1><p>The full board &mdash; one-way deals to anywhere, judged against each route&rsquo;s own price history, plus region fare indices.</p></div>
  <div class="summary">{market_pulse(market)}</div>
  <div class="sec-head"><h2>Fare heatmap</h2><span>one-way deals vs. their normal price</span></div>
  {heatmap_legend()}
  {heatmap_preview(oneway, market, 12)}
  <div style="text-align:center;margin:8px 0 18px"><a class="btn-ghost" href="heatmap.html">View the full heatmap &rarr;</a></div>
  <div class="sec-head" id="market"><h2>Fare indices</h2><span>avg vs. the Standard Meridian, by region</span></div>
  {context_banner(Q_INDICES)}
  <div class="indices">{index_cards(oneway, hist)}</div>
  <p class="finehint" style="text-align:center;margin:2px 0 14px">See the bigger picture &mdash; <a href="cheap-flight-index.html" style="color:var(--gold);font-weight:600">the Magellan Cheap Flight Index</a>: the cheapest places to fly from the USA right now, by region and by airport.</p>
  {oneway_market(oneway, market)}
  {BRIEFING_CTA}
</div>"""


WORLD_HUBS = {
    "JFK":"New York","LAX":"Los Angeles","MIA":"Miami","ORD":"Chicago","SFO":"San Francisco",
    "BOS":"Boston","ATL":"Atlanta","SEA":"Seattle","YTO":"Toronto","YVR":"Vancouver",
    "DTW":"Detroit","IAH":"Houston","DEN":"Denver","DFW":"Dallas","TPA":"Tampa","HNL":"Honolulu","PHX":"Phoenix","LAS":"Las Vegas",
    "RDU":"Raleigh","CLT":"Charlotte","MCO":"Orlando","BNA":"Nashville","CMH":"Columbus",
    "ANC":"Anchorage","GOH":"Nuuk","KEF":"Reykjavik","SJO":"San Jose",
    "LON":"London","PAR":"Paris","FRA":"Frankfurt","AMS":"Amsterdam","MAD":"Madrid","BCN":"Barcelona",
    "FCO":"Rome","IST":"Istanbul","LIS":"Lisbon","DUB":"Dublin","ZRH":"Zurich","VIE":"Vienna",
    "CPH":"Copenhagen","MUC":"Munich","ATH":"Athens",
    "DXB":"Dubai","DOH":"Doha","AUH":"Abu Dhabi","TLV":"Tel Aviv",
    "SIN":"Singapore","BKK":"Bangkok","HKG":"Hong Kong","TYO":"Tokyo","ICN":"Seoul","DEL":"Delhi",
    "BOM":"Mumbai","KUL":"Kuala Lumpur","TPE":"Taipei","MNL":"Manila","CGK":"Jakarta","SGN":"Ho Chi Minh",
    "SYD":"Sydney","MEL":"Melbourne","AKL":"Auckland",
    "MEX":"Mexico City","GRU":"Sao Paulo","BOG":"Bogota","EZE":"Buenos Aires","LIM":"Lima",
    "JNB":"Johannesburg","CAI":"Cairo","NBO":"Nairobi","CMN":"Casablanca",
    "DLM":"Dalaman","AYT":"Antalya","BJV":"Bodrum","SPU":"Split","DBV":"Dubrovnik","NAP":"Naples",
    "VCE":"Venice","CTA":"Catania","NCE":"Nice","AGP":"Malaga","PMI":"Palma de Mallorca","IBZ":"Ibiza",
    "OPO":"Porto","FAO":"Faro","SKG":"Thessaloniki","HER":"Heraklion","JTR":"Santorini","JMK":"Mykonos",
    "RHO":"Rhodes","HRG":"Hurghada","SSH":"Sharm el-Sheikh","RAK":"Marrakech","CPT":"Cape Town","ZNZ":"Zanzibar",
    "MRU":"Mauritius","SEZ":"Seychelles","MLE":"Maldives","CMB":"Colombo","KTM":"Kathmandu","GOI":"Goa",
    "HKT":"Phuket","KBV":"Krabi","CNX":"Chiang Mai","DAD":"Da Nang","DPS":"Bali","CEB":"Cebu",
    "ZQN":"Queenstown","PPT":"Tahiti","CUN":"Cancun","PUJ":"Punta Cana","AUA":"Aruba","SJU":"San Juan",
    "GDL":"Guadalajara","MTY":"Monterrey","SJD":"Los Cabos","PVR":"Puerto Vallarta","TIJ":"Tijuana","MID":"Merida",
    "BJX":"Leon","QRO":"Queretaro","OAX":"Oaxaca","MZT":"Mazatlan","ZIH":"Ixtapa","ACA":"Acapulco","SLP":"San Luis Potosi",
    "AGU":"Aguascalientes","VER":"Veracruz","CZM":"Cozumel","CUU":"Chihuahua","HMO":"Hermosillo",
    "CTG":"Cartagena","CUZ":"Cusco","UIO":"Quito",
}
RTW_US_STARTS = ["JFK","LAX","MIA","ORD","SFO","BOS","ATL","SEA","DTW","IAH","DEN","DFW","TPA","HNL","PHX","LAS","RDU","CLT","MCO","BNA","CMH"]


def round_the_world(world, min_stops=3, max_stops=5, gap_min=35, gap_max=175, only_start=None):
    try:
        coords = json.load(open(os.path.join(HERE, "airport_coords.json"), encoding="utf-8"))
    except Exception:
        return None
    leg = {}
    for r in world:
        a, b = r.get("o"), r.get("c")
        if a in WORLD_HUBS and b in WORLD_HUBS and a != b:
            if (a, b) not in leg or r["price"] < leg[(a, b)]["price"]:
                leg[(a, b)] = r
    lon = {h: coords[h][1] for h in WORLD_HUBS if h in coords and isinstance(coords[h], list)}
    hubs = [h for h in WORLD_HUBS if h in lon]
    best = None
    for start in ([only_start] if only_start else RTW_US_STARTS):
        if start not in lon:
            continue
        rel = {h: ((lon[h] - lon[start]) % 360) for h in hubs}
        cand = sorted([h for h in hubs if h != start and 0 < rel[h] < 360], key=lambda h: rel[h])
        dp = {}
        for h in cand:
            if gap_min <= rel[h] <= gap_max and (start, h) in leg:
                dp[(h, 1)] = (leg[(start, h)]["price"], None)
        for k in range(2, max_stops + 1):
            for h in cand:
                bestp = None
                for p in cand:
                    if rel[p] >= rel[h]:
                        continue
                    gap = rel[h] - rel[p]
                    if not (gap_min <= gap <= gap_max):
                        continue
                    if (p, k - 1) not in dp or (p, h) not in leg:
                        continue
                    cost = dp[(p, k - 1)][0] + leg[(p, h)]["price"]
                    if bestp is None or cost < bestp[0]:
                        bestp = (cost, p)
                if bestp:
                    dp[(h, k)] = bestp
        for k in range(min_stops, max_stops + 1):
            for h in cand:
                if (h, k) not in dp:
                    continue
                final_gap = 360 - rel[h]
                if not (gap_min <= final_gap <= gap_max) or (h, start) not in leg:
                    continue
                total = dp[(h, k)][0] + leg[(h, start)]["price"]
                if best is None or total < best[0]:
                    path = [h]; cur_h, cur_k = h, k
                    while dp[(cur_h, cur_k)][1] is not None:
                        p = dp[(cur_h, cur_k)][1]; path.append(p); cur_h, cur_k = p, cur_k - 1
                    path.reverse()
                    best = (total, [start] + path + [start])
    if not best:
        return None
    total, route = best
    legs = []
    for i in range(len(route) - 1):
        a, b = route[i], route[i + 1]
        L = leg[(a, b)]
        legs.append({"from": a, "from_name": WORLD_HUBS[a], "to": b, "to_name": WORLD_HUBS[b],
                     "price": L["price"], "link": L.get("link", ""), "depart": L.get("depart", "")})
    return {"start": route[0], "start_name": WORLD_HUBS[route[0]], "total": total,
            "stops": len(route) - 2, "flights": len(legs), "legs": legs}


def atw_highlight(world):
    """Today's best Around-the-World value — the cheapest full loop, as a highlight card
    matching the one-way 'Biggest Winner' treatment, linking into the ATW builder."""
    trip = round_the_world(world)
    if not trip:
        return ""
    legs = trip["legs"]
    route = " &rarr; ".join(html.escape(c) for c in ([trip["start"]] + [L["to"] for L in legs]))
    return (f'<a class="winner" href="around-the-world.html?start={html.escape(trip["start"], quote=True)}">'
            f'<span class="winner-badge">Today&rsquo;s best Around the World trip</span>'
            f'<div class="winner-main"><div class="winner-city">{html.escape(trip["start_name"])} &rarr; around the world &rarr; home</div>'
            f'<div class="winner-route">{trip["stops"]} stops &middot; {trip["flights"]} one-way flights &middot; {route} &middot; '
            f'<span style="color:var(--gold)">live fares</span></div></div>'
            f'<div class="winner-right"><span class="winner-price">${trip["total"]:,.0f}</span>'
            f'<span style="color:var(--muted);font-size:13px">whole loop</span></div>'
            f'<span class="winner-cta">Build this trip on Around the World &rarr;</span></a>')


def oneway_winner_for(oneway, market, origin):
    """The best one-way 'winner' deal from a specific origin airport (personalized)."""
    by_code = {}
    for m in market:
        c = m["code"]
        if c not in by_code or m["price"] < by_code[c]["price"]:
            by_code[c] = m
    cands = []
    for o in oneway:
        if (o.get("cc") or "").upper() == "US":
            continue
        if o.get("origin") != origin:
            continue
        rt_o = by_code.get(o["code"])
        try:
            typ_o = float(rt_o["price"]) * 0.62 if rt_o and rt_o.get("price") else 0
            if typ_o > 0:
                cands.append((float(o["price"]) / typ_o, o, rt_o))
        except Exception:
            continue
    if not cands:
        return ""
    cands.sort(key=lambda x: x[0])
    w, rt = cands[0][1], cands[0][2]
    price = float(w["price"]); code = w["code"]
    typ = (float(rt["price"]) * 0.62) if (rt and rt.get("price")) else 0
    c, v = "g", "Low"
    if typ:
        if price > typ * 1.10:
            c, v = "r", "High"
        elif price > typ * 0.90:
            c, v = "y", "Typical"
    palette = {"g": ("rgba(46,139,87,.15)", "var(--green)"),
               "y": ("rgba(47,107,70,.14)", "var(--gold)"),
               "r": ("rgba(192,57,43,.13)", "var(--red)")}
    bg, col = palette[c]
    return (f'<a class="winner" href="{html.escape(w["link"], quote=True)}" target="_blank" rel="noopener">'
            f'<span class="winner-badge">Your best one-way from {html.escape(origin)}</span>'
            f'<div class="winner-main"><div class="winner-city">{html.escape(w["name"])}</div>'
            f'<div class="winner-route">One-way from {html.escape(origin)} &middot; {html.escape(w.get("depart", ""))} &middot; '
            f'<span style="color:var(--gold)">live price at booking</span></div></div>'
            f'<div class="winner-right"><span class="winner-price">${price:,.0f}</span>'
            f'<span style="color:var(--muted);font-size:13px">one-way</span>'
            f'<span class="winner-off" style="background:{bg};color:{col}">{v}</span></div>'
            f'<span class="winner-cta">See live price on Aviasales &rarr;</span></a>')


def atw_highlight_for(world, start):
    """The cheapest around-the-world loop starting from a specific airport (personalized)."""
    trip = round_the_world(world, only_start=start)
    if not trip:
        return ""
    legs = trip["legs"]
    route = " &rarr; ".join(html.escape(c) for c in ([trip["start"]] + [L["to"] for L in legs]))
    return (f'<a class="winner" href="around-the-world.html?start={html.escape(trip["start"], quote=True)}">'
            f'<span class="winner-badge">Your Around the World from {html.escape(trip["start"])}</span>'
            f'<div class="winner-main"><div class="winner-city">{html.escape(trip["start_name"])} &rarr; around the world &rarr; home</div>'
            f'<div class="winner-route">{trip["stops"]} stops &middot; {trip["flights"]} one-way flights &middot; {route} &middot; '
            f'<span style="color:var(--gold)">live fares</span></div></div>'
            f'<div class="winner-right"><span class="winner-price">${trip["total"]:,.0f}</span>'
            f'<span style="color:var(--muted);font-size:13px">whole loop</span></div>'
            f'<span class="winner-cta">Build this trip on Around the World &rarr;</span></a>')


def body_rtw(world):
    # --- cheapest hub-to-hub one-way legs (a,b both world hubs) ---
    leg = {}
    for r in world:
        a, b = r.get("o"), r.get("c")
        if a in WORLD_HUBS and b in WORLD_HUBS and a != b:
            if (a, b) not in leg or r["price"] < leg[(a, b)]["price"]:
                leg[(a, b)] = r
    try:
        coords = json.load(open(os.path.join(HERE, "airport_coords.json"), encoding="utf-8"))
    except Exception:
        coords = {}
    HUBS = {}
    for h, nm in WORLD_HUBS.items():
        if h in coords and isinstance(coords[h], list):
            HUBS[h] = {"n": nm, "lon": coords[h][1], "cont": continent_of(h), "fl": flag_img(h)}
    LEGS = {f"{a}>{b}": {"p": round(L["price"]), "l": L.get("link", ""), "d": L.get("depart", "")}
            for (a, b), L in leg.items() if a in HUBS and b in HUBS}
    conts = sorted({HUBS[h]["cont"] for h in HUBS if h not in RTW_US_STARTS})
    start_opts = ('<option value="AUTO">Auto &mdash; cheapest start</option>'
                  + "".join(f'<option value="{h}">{html.escape(WORLD_HUBS[h])} ({h})</option>'
                            for h in RTW_US_STARTS if h in HUBS))
    cont_chips = "".join(f'<button type="button" class="airchip on" data-rcont="{html.escape(c, quote=True)}" '
                         f'onclick="rtwToggleCont(this)">{html.escape(c)}</button>' for c in conts)

    # supplemental best-time/visa for major hubs not in dealsgen
    RTW_HUB_INFO = {
        "LON": ("Apr-Jun & Sep", "Visa-free, up to 6 months"),
        "PAR": ("Apr-Jun & Sep-Oct", "Visa-free, 90 days (Schengen)"),
        "TYO": ("Mar-May & Oct-Nov", "Visa-free, 90 days"),
        "ZRH": ("May-Sep", "Visa-free, 90 days (Schengen)"),
        "VIE": ("Apr-Oct", "Visa-free, 90 days (Schengen)"),
        "MUC": ("May-Sep", "Visa-free, 90 days (Schengen)"),
        "AUH": ("Nov-Mar", "Visa on arrival, 30 days"),
        "CGK": ("May-Sep (dry season)", "Visa on arrival, 30 days"),
        "YTO": ("May-Oct", "eTA required"),
        "YVR": ("Jun-Sep", "eTA required"),
    }
    RDEST = {}
    for h in HUBS:
        best = BEST_TIME.get(h, "") or RTW_HUB_INFO.get(h, ("", ""))[0]
        visa = DEST_INFO.get(h, {}).get("visa", "") or RTW_HUB_INFO.get(h, ("", ""))[1]
        blurb = CITY_GUIDE.get(h, {}).get("overview", "")
        gfile = next((g["fname"] for g in CITY_GUIDES if g["code"] == h), "")
        if best or visa or blurb or gfile:
            RDEST[h] = {"b": best, "v": visa, "g": gfile, "d": (blurb[:170] + ("..." if len(blurb) > 170 else "")) if blurb else ""}
    must_opts = "".join(f'<option value="{html.escape(WORLD_HUBS[h], quote=True)}"></option>'
                        for h in sorted(HUBS, key=lambda x: WORLD_HUBS[x]) if h not in RTW_US_STARTS)

    # --- server-rendered default loop (SEO + no-JS fallback) ---
    trip = round_the_world(world)
    if trip:
        rows = []
        for i, l in enumerate(trip["legs"], 1):
            lk = html.escape(l["link"], quote=True)
            rows.append(
                f'<div class="rtw-leg"><span class="rtw-num">{i}</span>'
                f'<div class="rtw-cities">{flag_img(l["from"])}<span class="rtw-city">{html.escape(l["from_name"])}</span>'
                f'<span class="rtw-arrow">&rarr;</span>{flag_img(l["to"])}<span class="rtw-city">{html.escape(l["to_name"])}</span></div>'
                f'<div class="rtw-legright"><span class="rtw-legprice">${l["price"]:,.0f}</span>'
                f'<span class="rtw-legunit">one-way</span>'
                f'<a class="mini-book" href="{lk}" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div></div>')
        first_link = html.escape(trip["legs"][0]["link"], quote=True)
        default_html = (
            f'<div class="rtw-hero"><div class="rtw-hero-label">Around the world from</div>'
            f'<div class="rtw-hero-price">${trip["total"]:,.0f}</div>'
            f'<div class="rtw-hero-sub">{trip["flights"]} one-way flights &middot; {trip["stops"]} stops &middot; '
            f'loops back to {html.escape(trip["start_name"])}</div></div>'
            f'<div class="rtw-route">{"".join(rows)}</div>'
            f'<div class="blog-cta"><a class="btn-primary" href="{first_link}" target="_blank" rel="noopener">'
            f'Start the loop &mdash; book leg 1 &rarr;</a></div>')
    else:
        default_html = ('<div class="wl-hint">We couldn&rsquo;t assemble a full loop from today&rsquo;s fares. '
                        'Try different settings, or browse one-way deals on the '
                        '<a href="market.html" style="color:var(--gold)">Market</a>.</div>')

    COMPASS = ('<svg class="hicon" viewBox="0 0 24 24" fill="none" stroke="#2f6b46" stroke-width="1.7" '
               'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/>'
               '<path d="m15.6 8.4-2.1 5.1-5.1 2.1 2.1-5.1 5.1-2.1z"/></svg>')

    shell = """<style>.mf-ledger{margin-top:14px;background:#efe5cd;border:1px solid #d9c9a0;border-radius:12px;padding:14px}.mf-totals{display:flex;gap:12px;flex-wrap:wrap}.mf-tot{flex:1;min-width:150px;background:#efe5cd;border:1px solid #d9c9a0;border-radius:10px;padding:10px 12px}.mf-tot .mf-lbl{display:block;font-size:12px;color:var(--muted)}.mf-tot .mf-val{font-size:22px;font-weight:700}.mf-tot .mf-sub{display:block;font-size:11px;color:var(--muted);margin-top:2px}.mf-conf{border-color:rgba(46,139,87,.45)}.mf-conf .mf-val{color:#2e8b57}.mf-save{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;align-items:center}.mf-save input{flex:1;min-width:180px;background:#efe5cd;border:1px solid #d9c9a0;border-radius:8px;color:var(--ink);padding:8px 10px;font:inherit}.rtw-confwrap{display:flex;align-items:center;gap:6px;margin-top:6px}.rtw-bk{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--muted);cursor:pointer}.rtw-bp{width:84px;background:#efe5cd;border:1px solid #d9c9a0;border-radius:6px;color:var(--ink);padding:3px 6px;font:inherit}.rtw-bp:disabled{opacity:.4}.mf-trips-h{font-size:12px;color:var(--muted);margin:14px 0 4px}.mf-trip{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:8px 0;border-top:1px solid #d9c9a0}.mf-trip-nm{font-weight:600}.mf-trip-meta{font-size:12px;color:var(--muted)}.mf-mini{padding:3px 10px;font-size:12px}.rtw-mustchips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.rtw-chip{display:inline-flex;align-items:center;gap:5px;background:#2f6b46;border:1px solid #d9c9a0;border-radius:999px;padding:3px 4px 3px 10px;font-size:12px;color:#fff}.rtw-chip button{background:none;border:none;color:var(--muted);cursor:pointer;font-size:15px;line-height:1;padding:0 3px}.rtw-chip button:hover{color:#fff}.rtw-mustbtns{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:8px;font-size:12px;color:var(--muted)}.rtw-mustbtns select{background:#efe5cd;border:1px solid #d9c9a0;border-radius:6px;color:var(--ink);padding:3px 6px;font:inherit}.rtw-mustnote{font-size:11px;color:var(--muted);margin-top:6px}</style>
<div class="wrap">
  <div class="pagehead"><h1>__COMPASS__ Cheapest Around-the-World Flights</h1>
  <p>Five centuries after Magellan circled the globe, build your own way to do it today &mdash; one one-way deal at a time. Set your start, stops, regions and budget, and we&rsquo;ll find the lowest-cost real loop our tracker can assemble right now.</p></div>
  <div class="tl-card">
    <div class="rtw-controls">
      <label class="rtw-ctl"><span>Scope</span>
        <select id="rtw-scope" onchange="rtwScope();rtwBuild()"><option value="WORLD">Whole world (full loop)</option><option value="EUROPE">Europe trip</option><option value="ASIA">Asia trip</option><option value="LATAM">Latin America trip</option><option value="AFRME">Africa &amp; Middle East trip</option><option value="NORTHAM">North America trip</option></select></label>
      <label class="rtw-ctl" id="rtw-start-wrap"><span>Start from</span>
        <select id="rtw-start" onchange="rtwBuild()">__START_OPTS__</select></label>
      <label class="rtw-ctl" id="rtw-dir-wrap"><span>Direction</span>
        <select id="rtw-dir" onchange="rtwBuild()"><option value="BOTH">Either &mdash; cheapest</option><option value="W">Westward (Magellan&rsquo;s way)</option><option value="E">Eastward</option></select></label>
      <label class="rtw-ctl" id="rtw-end-wrap"><span>End</span>
        <select id="rtw-end" onchange="rtwEndToggle();rtwBuild()"><option value="START">Back to your start</option><option value="ANY">Cheapest US arrival</option></select></label>
      <label class="rtw-ctl" id="rtw-endarea-wrap" style="display:none"><span>Arrive</span>
        <select id="rtw-endarea" onchange="rtwBuild()"><option value="MAIN">Mainland US (no Hawaii)</option><option value="ANY">Anywhere in the US</option><option value="EAST">East Coast</option><option value="CENTRAL">Central US</option><option value="WEST">West Coast</option></select></label>
      <label class="rtw-ctl"><span><span id="rtw-stops-cap">Stops</span> <b id="rtw-stops-lab">3</b></span>
        <input type="range" id="rtw-stops" min="2" max="5" value="3" oninput="rtwStopsLab();rtwBuild()"></label>
    </div>
    <div class="rtw-controls" style="margin-top:10px">
      <label class="rtw-ctl"><span>Max budget (optional)</span>
        <input type="number" id="rtw-budget" min="0" step="50" placeholder="e.g. 1500" oninput="rtwBuild()"></label>
      <label class="rtw-ctl" id="rtw-must-wrap"><span>Must-visit cities <small style="color:var(--muted)">(up to 6)</small></span>
        <input id="rtw-must" list="rtw-must-dl" placeholder="Type a city &amp; press Enter" autocomplete="off"><datalist id="rtw-must-dl">__MUST_OPTS__</datalist>
        <div id="rtw-must-chips" class="rtw-mustchips"></div>
        <div class="rtw-mustbtns"><button type="button" class="airchip mf-mini" onclick="rtwFromBucket()">&#9733; Build from my bucket list</button>
          <span id="rtw-modewrap" style="display:none">Plan: <select id="rtw-mode" onchange="rtwBuild()"><option value="fill">fill to a full loop</option><option value="exact">visit only these cities</option></select></span></div>
        <div id="rtw-must-note" class="rtw-mustnote"></div></label>
      <label class="rtw-ctl"><span>Trip length (weeks, optional)</span>
        <input type="number" id="rtw-weeks" min="1" max="20" placeholder="e.g. 4" oninput="rtwBuild()"></label>
    </div>
    <div class="rtw-ctl" id="rtw-regions-wrap" style="margin-top:10px"><span style="font-size:12px;color:var(--muted)">Pass through (tap to include/skip regions)</span>
      <div class="airchips" id="rtw-conts" style="margin-top:6px">__CONT_CHIPS__</div></div>
  </div>
  <div id="rtw-out">__DEFAULT__</div>
  <p class="finehint" style="text-align:center;margin-top:18px">Set <b>End</b> to &ldquo;Cheapest US arrival&rdquo; if you don&rsquo;t need to land back where you started &mdash; we&rsquo;ll start and end anywhere in the US for the lowest total, so you can position to a cheap start city and take the cheapest way back into the country. Use <b>Arrive</b> to keep it on the mainland (no Hawaii) or bias to your coast so the last hop home is short. Loops are built from recently-tracked one-way fares &mdash; geography won&rsquo;t always be textbook-perfect, and each leg&rsquo;s live price is confirmed when you book on Aviasales. No full loop for some combinations &mdash; widen the regions, raise the budget, or change the stop count. Want a hand? <a href="consultant.html" style="color:var(--gold)">Hire a consultant</a>.</p>
</div>
<script>
/* Interactive cheapest-circumnavigation builder. Eastward/westward DP over tracked
   hub-to-hub one-way fares, entirely in the browser (free, no backend).
   FUTURE/AI: POST the user's text + RHUBS/RLEGS to an LLM to return
   {start, stops, regions, budget, must}, then call rtwBuild(). */
(function(){
var RHUBS = __HUBS__;
var RLEGS = __LEGS__;
var RUS = __US__;
var RDEST = __RDEST__;
var GMIN=35, GMAX=175;
function go(id){ return document.getElementById(id); }
function legP(a,b){ var k=RLEGS[a+">"+b]; return k?k.p:null; }
function relLon(start, dir){ var l0=RHUBS[start].lon, r={}; for(var h in RHUBS){ var d=RHUBS[h].lon-l0; if(dir==="W") d=-d; r[h]=((d)%360+360)%360; } return r; }
var MFMUST=[];
function mustName(c){ return RHUBS[c]?RHUBS[c].n:c; }
function nameToCode(v){ v=(v||"").trim(); if(!v) return ""; if(RHUBS[v]) return v; v=v.toLowerCase(); for(var h in RHUBS){ if((RHUBS[h].n||"").toLowerCase()===v) return h; } return ""; }
function renderMustChips(){ var w=go("rtw-must-chips"); if(w){ w.innerHTML=MFMUST.map(function(c){ return '<span class="rtw-chip">'+(RHUBS[c]?RHUBS[c].fl:"")+'<span>'+mustName(c)+'</span><button type="button" title="remove" onclick="rtwMustDel(\\''+c+'\\')">&times;</button></span>'; }).join(""); } var mw=go("rtw-modewrap"); if(mw) mw.style.display=MFMUST.length?"":"none"; var inp=go("rtw-must"); if(inp){ if(MFMUST.length>=6){ inp.disabled=true; inp.placeholder="Up to 6 cities"; } else { inp.disabled=false; inp.placeholder="Type a city & press Enter"; } } }
window.rtwMustAdd=function(){ var inp=go("rtw-must"); if(!inp) return; var c=nameToCode(inp.value); inp.value=""; if(c && MFMUST.indexOf(c)<0 && MFMUST.length<6){ MFMUST.push(c); renderMustChips(); rtwBuild(); } else { renderMustChips(); } };
window.rtwMustDel=function(c){ var i=MFMUST.indexOf(c); if(i>=0){ MFMUST.splice(i,1); var nt=go("rtw-must-note"); if(nt) nt.textContent=""; renderMustChips(); rtwBuild(); } };
window.rtwFromBucket=function(){ var list=[]; try{ list=JSON.parse(localStorage.getItem('mf_bucket')||'[]'); }catch(e){} var note=go("rtw-must-note"); if(!list.length){ if(note) note.innerHTML="Your bucket list is empty &mdash; star &#9734; deals on <a href=\\"explore.html\\" style=\\"color:var(--gold)\\">Explore</a> to save cities here."; return; } var added=0, skipped=0, full=false, seen={}; for(var i=0;i<list.length;i++){ var c=list[i].d; if(c && seen[c]) continue; if(c) seen[c]=1; if(c && RHUBS[c]){ if(MFMUST.indexOf(c)<0){ if(MFMUST.length<6){ MFMUST.push(c); added++; } else { full=true; } } } else { skipped++; } } renderMustChips(); var msg=added?('Added '+added+' cit'+(added>1?'ies':'y')+' from your bucket list.'):'No new routable cities to add.'; if(full) msg+=' (6-city max reached.)'; if(skipped) msg+=' '+skipped+' saved place'+(skipped>1?'s aren\\'t':' isn\\'t')+' a routable hub yet, so skipped.'; if(note) note.textContent=msg; rtwBuild(); };
function cheapestCycle(start, cities){ var n=cities.length; if(!n||!RHUBS[start]) return null; var full=(1<<n)-1; var dp=[], par=[]; for(var m=0;m<=full;m++){ dp[m]=[]; par[m]=[]; for(var j=0;j<n;j++){ dp[m][j]=Infinity; par[m][j]=-1; } } for(var j0=0;j0<n;j0++){ var p0=legP(start,cities[j0]); if(p0!=null) dp[1<<j0][j0]=p0; } for(var m=1;m<=full;m++){ for(var j=0;j<n;j++){ if(!(m&(1<<j))) continue; var cj=dp[m][j]; if(cj===Infinity) continue; for(var k=0;k<n;k++){ if(m&(1<<k)) continue; var pk=legP(cities[j],cities[k]); if(pk==null) continue; var nm=m|(1<<k), nc=cj+pk; if(nc<dp[nm][k]){ dp[nm][k]=nc; par[nm][k]=j; } } } } var best=Infinity, bj=-1; for(var j2=0;j2<n;j2++){ if(dp[full][j2]===Infinity) continue; var pe=legP(cities[j2],start); if(pe==null) continue; var t=dp[full][j2]+pe; if(t<best){ best=t; bj=j2; } } if(bj<0) return null; var order=[], mm=full, jj=bj; while(jj>=0){ order.push(cities[jj]); var pj=par[mm][jj]; mm=mm&~(1<<jj); jj=pj; } order.reverse(); return {total:best, order:order}; }
function pickExtras(musts, pool, target){ var set=musts.slice(), inset={}; set.forEach(function(c){ inset[c]=1; }); while(set.length<target){ var bc=null, bp=Infinity; for(var i=0;i<pool.length;i++){ var c=pool[i]; if(inset[c]||!RHUBS[c]) continue; var mp=Infinity; for(var j=0;j<set.length;j++){ var a=legP(set[j],c), b=legP(c,set[j]); if(a!=null&&a<mp) mp=a; if(b!=null&&b<mp) mp=b; } if(mp<bp){ bp=mp; bc=c; } } if(bc==null) break; set.push(bc); inset[bc]=1; } return set; }
function inArea(e, area){
  var lo=RHUBS[e]?RHUBS[e].lon:null; if(lo==null) return false;
  switch(area){
    case "MAIN": return lo>=-130;                 // continental US (drops Hawaii ~-157)
    case "EAST": return lo>=-90;
    case "CENTRAL": return lo>=-105 && lo<-90;
    case "WEST": return lo>=-130 && lo<-105;
    default: return true;                          // ANY
  }
}
function buildLoop(start, nStops, allowed, dir, mustH, endMode, endArea){
  if(!RHUBS[start]) return null;
  var rel=relLon(start, dir);
  var cand=[]; for(var h in RHUBS){ if(h===start||rel[h]<=0) continue; if(allowed && !allowed[RHUBS[h].cont]) continue; cand.push(h); }
  cand.sort(function(a,b){ return rel[a]-rel[b]; });
  var scont=RHUBS[start].cont;
  var dp={};
  // First leg must leave the start's continent, so a world loop never opens with
  // a token hop to a neighbour (e.g. Chicago -> Vancouver) that reads as "staying put".
  cand.forEach(function(h){ if(rel[h]>=GMIN&&rel[h]<=GMAX&&RHUBS[h].cont!==scont){ var p=legP(start,h); if(p!=null) dp[h+"|1"]={c:p,prev:null}; } });
  for(var k=2;k<=nStops;k++){
    cand.forEach(function(h){
      var best=null;
      cand.forEach(function(p){
        if(rel[p]>=rel[h]) return;
        if(RHUBS[p].cont===RHUBS[h].cont) return; // hop continent-to-continent around the globe
        var gap=rel[h]-rel[p]; if(gap<GMIN||gap>GMAX) return;
        var d=dp[p+"|"+(k-1)]; if(!d) return; var lp=legP(p,h); if(lp==null) return;
        var c=d.c+lp; if(best==null||c<best.c) best={c:c,prev:p};
      });
      if(best) dp[h+"|"+k]=best;
    });
  }
  // Where the last leg lands: back to the start (closed loop) or, in open-jaw
  // mode, whichever US airport is cheapest to arrive at (start anywhere in the
  // US, end anywhere in the US). rel[e]===0 for e===start reproduces the old
  // closed-loop math exactly.
  var ends;
  if(endMode==="ANY"){ ends=RUS.filter(function(e){ return inArea(e, endArea); }); if(!ends.length) ends=RUS; }
  else { ends=[start]; }
  var best=null;
  cand.forEach(function(h){
    var d=dp[h+"|"+nStops]; if(!d) return;
    var path=[h], ch=h, ck=nStops;
    while(dp[ch+"|"+ck].prev!=null){ var pp=dp[ch+"|"+ck].prev; path.push(pp); ch=pp; ck--; }
    path.reverse();
    if(mustH && mustH!==start && path.indexOf(mustH)<0) return;
    ends.forEach(function(e){
      if(!RHUBS[e]) return;
      if(e!==start && path.indexOf(e)>=0) return;      // don't revisit a hub
      var fg=((rel[e]-rel[h])%360+360)%360;            // forward gap from last hub to the US arrival
      if(fg<GMIN||fg>GMAX) return;
      var lp=legP(h,e); if(lp==null) return;
      var total=d.c+lp;
      if(best==null||total<best.total){ best={total:total, route:[start].concat(path).concat([e]), end:e}; }
    });
  });
  return best;
}
var REGIONS={
  "EUROPE":{name:"Europe", h:["LON","PAR","FRA","AMS","MAD","BCN","FCO","IST","LIS","DUB","ZRH","VIE","CPH","MUC","ATH"]},
  "ASIA":{name:"Asia", h:["SIN","BKK","HKG","TYO","ICN","DEL","BOM","KUL","TPE","MNL","CGK","SGN"]},
  "LATAM":{name:"Latin America", h:["MEX","GRU","BOG","EZE","LIM"]},
  "AFRME":{name:"Africa & the Middle East", h:["JNB","CAI","NBO","CMN","DXB","DOH","AUH","TLV"]},
  "NORTHAM":{name:"North America", h:["ANC","YVR","YTO","SEA","SFO","DEN","ORD","MIA","MEX","SJO","KEF","GOH"]}
};
function buildTour(hubList, nCities, mustH, usStart){
  var pool=[]; for(var i=0;i<hubList.length;i++){ if(RHUBS[hubList[i]]) pool.push(hubList[i]); }
  if(pool.length<1) return null;
  if(nCities>pool.length) nCities=pool.length;
  var starts = (usStart && usStart!=="AUTO" && RHUBS[usStart]) ? [usStart] : RUS;
  var best=null;
  starts.forEach(function(s){
    if(!RHUBS[s]) return;
    pool.forEach(function(entry){
      var inP=legP(s,entry); if(inP==null) return;
      var route=[entry], used={}; used[entry]=1; var cur=entry, total=inP, ok=true;
      for(var step=1; step<nCities; step++){
        var nb=null, nbp=null;
        pool.forEach(function(c){ if(used[c]) return; var p=legP(cur,c); if(p==null) return; if(nbp==null||p<nbp){ nbp=p; nb=c; } });
        if(nb==null){ ok=false; break; }
        route.push(nb); used[nb]=1; total+=nbp; cur=nb;
      }
      if(!ok) return;
      var outP=legP(cur,s); if(outP==null) return; total+=outP;
      if(mustH && route.indexOf(mustH)<0) return;
      if(best==null||total<best.total){ best={total:total, route:[s].concat(route).concat([s]), tour:true}; }
    });
  });
  return best;
}
function legDetail(code){
  var x=RDEST[code]; if(!x) return "";
  var meta=[]; if(x.b) meta.push("Best time: "+x.b); if(x.v) meta.push(x.v);
  var g=x.g?(' <a href="'+x.g+'" style="color:var(--gold)">city guide &rarr;</a>'):"";
  if(!x.d && !meta.length && !g) return "";
  return '<div class="rtw-detail">'+(x.d?('<span class="rtw-blurb">'+x.d+'</span> '):"")
    +(meta.length?('<span class="rtw-meta">'+meta.join(" &middot; ")+'</span>'):"")+g+'</div>';
}
function legRow(a,b,i){
  var k=RLEGS[a+">"+b]; var price=k?k.p:0; var link=k?k.l:"#";
  return '<div class="rtw-leg"><span class="rtw-num">'+i+'</span><div class="rtw-cities">'
    +RHUBS[a].fl+'<span class="rtw-city">'+RHUBS[a].n+'</span><span class="rtw-arrow">&rarr;</span>'
    +RHUBS[b].fl+'<span class="rtw-city">'+RHUBS[b].n+'</span></div>'
    +'<div class="rtw-legright"><span class="rtw-legprice">$'+price.toLocaleString()+'</span>'
    +'<span class="rtw-legunit">one-way</span>'
    +'<a class="mini-book" href="'+link+'" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a>'
    +'<span class="rtw-confwrap"><label class="rtw-bk"><input type="checkbox" data-key="'+a+'>'+b+'" data-est="'+price+'" onchange="mfToggle(this)"'+(MFCONF[a+">"+b]!=null?' checked':'')+'> Booked</label>'
    +'<input type="number" class="rtw-bp" data-key="'+a+'>'+b+'" value="'+(MFCONF[a+">"+b]!=null?MFCONF[a+">"+b]:price)+'"'+(MFCONF[a+">"+b]!=null?'':' disabled')+' onchange="mfPrice(this)" oninput="mfPrice(this)"></span></div></div>'
    +legDetail(b);
}
function shareBar(total, startName){
  var url=location.href;
  var txt="I just built a way around the world from "+startName+" for $"+total.toLocaleString()+" with Magellan Flights:";
  return '<div class="rtw-share"><button class="airchip" onclick="rtwCopy(this)">Copy link</button>'
    +'<a class="airchip" target="_blank" rel="noopener" href="https://twitter.com/intent/tweet?text='+encodeURIComponent(txt)+'&url='+encodeURIComponent(url)+'">Share on X</a>'
    +'<a class="airchip" target="_blank" rel="noopener" href="https://api.whatsapp.com/send?text='+encodeURIComponent(txt+" "+url)+'">WhatsApp</a>'
    +'<a class="airchip" target="_blank" rel="noopener" href="https://www.facebook.com/sharer/sharer.php?u='+encodeURIComponent(url)+'">Facebook</a></div>';
}
function render(best, opts){
  var out=go("rtw-out");
  if(!best){ out.innerHTML=(opts&&opts.custom)?'<div class="wl-hint">We couldn&rsquo;t connect all those cities into a trip from today&rsquo;s tracked fares. Try removing a city, switching the plan to &ldquo;fill to a full loop,&rdquo; or picking a nearby hub.</div>':'<div class="wl-hint">No full loop with these settings &mdash; try more regions, a higher budget, fewer stops, or remove a must-visit city.</div>'; return; }
  var r=best.route, legs="", first=RLEGS[r[0]+">"+r[1]];
  MFLEGS=[]; mfEstTotal=best.total;
  for(var i=0;i<r.length-1;i++){ var _k=r[i]+">"+r[i+1]; MFLEGS.push({key:_k, est:(RLEGS[_k]||{}).p||0}); legs+=legRow(r[i],r[i+1],i+1); }
  var stops=r.length-2, flights=r.length-1, startName=RHUBS[r[0]].n;
  var _places=best.tour?(r.length-2):stops; var pace = (opts && opts.weeks && _places>0) ? (' &middot; ~'+Math.max(1,Math.round(opts.weeks*7/_places))+' nights per stop') : "";
  var note = (opts && opts.budget && best.total>opts.budget)
    ? '<div class="rtw-note">This is the cheapest loop with these settings &mdash; <b>$'+best.total.toLocaleString()+'</b>, a little above your $'+opts.budget.toLocaleString()+' cap. Try more stops, more regions, or raise the cap.</div>'
    : "";
  var isTour=best.tour, rn=(opts&&opts.regionName)||"the region";
  var heroLabel=best.custom?'Your custom trip from':(isTour?('Trip around '+rn+' from'):'Around the world from');
  var sub=best.custom
    ? ((r.length-1)+' flights &middot; '+(r.length-2)+' cities'+pace+' &middot; round-trip from '+startName)
    : (isTour
      ? ((r.length-1)+' flights &middot; '+(r.length-2)+' cities in '+rn+pace+' &middot; round-trip from '+startName)
      : (flights+' one-way flights &middot; '+stops+' stops &middot; heading '+(best.dir==="W"?'west':'east')+pace+' &middot; '+((best.end && best.end!==r[0])?('starts '+startName+', ends '+RHUBS[best.end].n):('loops back to '+startName))));
  out.innerHTML='<div class="rtw-hero"><div class="rtw-hero-label">'+heroLabel+'</div>'
    +'<div class="rtw-hero-price">$'+best.total.toLocaleString()+'</div>'
    +'<div class="rtw-hero-sub">'+sub+'</div></div>'
    +note
    +'<div class="rtw-route">'+legs+'</div>'
    +mfLedger(best.total, r.length-1)
    +'<div class="blog-cta"><a class="btn-primary" href="'+(first?first.l:"#")+'" target="_blank" rel="noopener">Start the loop &mdash; book leg 1 &rarr;</a></div>'
    +shareBar(best.total, startName);
  mfRecalc(); mfRenderTrips();
}
window.rtwStopsLab=function(){ go("rtw-stops-lab").textContent=go("rtw-stops").value; };
function fillMust(scope){ var dl=go("rtw-must-dl"); if(!dl) return; var inp=go("rtw-must"); var cur=inp?inp.value:""; var codes=[]; if(scope!=="WORLD" && REGIONS[scope]){ codes=REGIONS[scope].h.slice(); } else { for(var h in RHUBS){ if(RUS.indexOf(h)<0) codes.push(h); } } codes=codes.filter(function(h){ return RHUBS[h]; }); codes.sort(function(a,b){ var an=RHUBS[a].n, bn=RHUBS[b].n; return an<bn?-1:(an>bn?1:0); }); var html=""; var ok={}; for(var i=0;i<codes.length;i++){ var nm=RHUBS[codes[i]].n||""; ok[nm.toLowerCase()]=1; html+='<option value="'+nm.replace(/"/g,"&quot;")+'"></option>'; } dl.innerHTML=html; if(inp && cur && !ok[cur.toLowerCase()]) inp.value=""; }
function mustCode(){ var inp=go("rtw-must"); if(!inp) return ""; var v=(inp.value||"").trim().toLowerCase(); if(!v) return ""; for(var h in RHUBS){ if((RHUBS[h].n||"").toLowerCase()===v) return h; } return ""; }
window.rtwEndToggle=function(){ var scope=go("rtw-scope")?go("rtw-scope").value:"WORLD"; var open=(go("rtw-end")&&go("rtw-end").value==="ANY"&&scope==="WORLD"); var w=go("rtw-endarea-wrap"); if(w) w.style.display=open?"":"none"; };
window.rtwScope=function(){ var scope=go("rtw-scope")?go("rtw-scope").value:"WORLD", world=(scope==="WORLD"); var dw=go("rtw-dir-wrap"), sw=go("rtw-start-wrap"), rw=go("rtw-regions-wrap"), ew=go("rtw-end-wrap"); if(dw) dw.style.display=world?"":"none"; if(ew) ew.style.display=world?"":"none"; if(sw) sw.style.display=""; if(rw) rw.style.display=world?"":"none"; var cap=go("rtw-stops-cap"); if(cap) cap.textContent=world?"Stops":"Cities"; rtwEndToggle(); fillMust(scope); };
window.rtwToggleCont=function(btn){ btn.classList.toggle("on"); rtwBuild(); };
window.rtwCopy=function(btn){ try{ navigator.clipboard.writeText(location.href); }catch(e){} var t=btn.textContent; btn.textContent="Copied!"; setTimeout(function(){ btn.textContent=t; },1500); };
var MFCONF={}, MFLEGS=[], mfEstTotal=0;
function mfConfTotal(){ var t=0,n=0; for(var i=0;i<MFLEGS.length;i++){ var k=MFLEGS[i].key; if(MFCONF[k]!=null){ t+=(+MFCONF[k]||0); n++; } } return {t:t,n:n}; }
function mfLedger(total, nlegs){
  return '<div class="mf-ledger"><div class="mf-totals">'
    +'<div class="mf-tot"><span class="mf-lbl">Estimated</span><span class="mf-val">$'+total.toLocaleString()+'</span><span class="mf-sub">tracked fares &middot; confirm on Aviasales</span></div>'
    +'<div class="mf-tot mf-conf"><span class="mf-lbl">Confirmed so far</span><span class="mf-val" id="mf-confval">$0</span><span class="mf-sub" id="mf-confsub">0 of '+nlegs+' legs booked</span></div></div>'
    +'<div class="mf-save"><input type="text" id="mf-name" placeholder="Name this trip (e.g. My RTW 2026)" maxlength="60">'
    +'<button class="airchip" onclick="mfSave()">Save trip</button>'
    +'<button class="airchip" onclick="rtwCopy(this)">Copy trip link</button></div>'
    +'<div id="mf-trips"></div></div>';
}
function mfRecalc(){ var c=mfConfTotal(); var v=go("mf-confval"), sb=go("mf-confsub"); if(v) v.textContent="$"+c.t.toLocaleString(); if(sb) sb.textContent=c.n+" of "+MFLEGS.length+" legs booked"; }
function mfQbp(key){ try{ return go("rtw-out").querySelector('.rtw-bp[data-key="'+key+'"]'); }catch(e){ return null; } }
window.mfToggle=function(cb){ var key=cb.getAttribute("data-key"); var inp=mfQbp(key); if(cb.checked){ var v=inp?(+inp.value|| +cb.getAttribute("data-est")||0):(+cb.getAttribute("data-est")||0); MFCONF[key]=v; if(inp) inp.disabled=false; } else { delete MFCONF[key]; if(inp) inp.disabled=true; } mfPersist(); mfRecalc(); };
window.mfPrice=function(inp){ var key=inp.getAttribute("data-key"); if(MFCONF[key]!=null){ MFCONF[key]=(+inp.value||0); mfPersist(); mfRecalc(); } };
function mfPersist(){ try{ localStorage.setItem("mfCurConf", JSON.stringify(MFCONF)); }catch(e){} }
function mfLoadConf(){ try{ var x=localStorage.getItem("mfCurConf"); MFCONF=x?JSON.parse(x):{}; }catch(e){ MFCONF={}; } }
function mfGetTrips(){ try{ var x=localStorage.getItem("mfTrips"); return x?JSON.parse(x):[]; }catch(e){ return []; } }
function mfEsc(x){ return (x||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
window.mfSave=function(){ var el=go("mf-name"); var nm=(el&&el.value||"").trim(); if(!nm) nm="My trip"; var trips=mfGetTrips(); trips.unshift({id:Date.now(), name:nm, url:location.href, est:mfEstTotal, conf:JSON.parse(JSON.stringify(MFCONF)), legs:MFLEGS.map(function(l){return l.key;}), ts:Date.now()}); trips=trips.slice(0,20); try{ localStorage.setItem("mfTrips", JSON.stringify(trips)); }catch(e){} if(el) el.value=""; mfRenderTrips(); };
window.mfDelete=function(id){ var trips=mfGetTrips().filter(function(t){ return t.id!=id; }); try{ localStorage.setItem("mfTrips", JSON.stringify(trips)); }catch(e){} mfRenderTrips(); };
window.mfLoad=function(id){ var t=mfGetTrips().filter(function(x){ return x.id==id; })[0]; if(!t) return; try{ localStorage.setItem("mfCurConf", JSON.stringify(t.conf||{})); }catch(e){} location.href=t.url; };
function mfRenderTrips(){ var el=go("mf-trips"); if(!el) return; var trips=mfGetTrips(); if(!trips.length){ el.innerHTML=""; return; } var h='<div class="mf-trips-h">My saved trips</div>'; for(var i=0;i<trips.length;i++){ var t=trips[i]; h+='<div class="mf-trip"><span class="mf-trip-nm">'+mfEsc(t.name)+'</span><span class="mf-trip-meta">$'+((t.est||0)).toLocaleString()+' &middot; '+((t.legs&&t.legs.length)||0)+' legs</span><button class="airchip mf-mini" onclick="mfLoad('+t.id+')">Load</button><button class="airchip mf-mini" onclick="mfDelete('+t.id+')">Delete</button></div>'; } el.innerHTML=h; }
function regionsOn(){ var out=[]; var chips=go("rtw-conts").querySelectorAll("[data-rcont]"); for(var i=0;i<chips.length;i++){ if(chips[i].classList.contains("on")) out.push(chips[i].getAttribute("data-rcont")); } return out; }
function updateURL(){
  var p={scope:go("rtw-scope")?go("rtw-scope").value:"WORLD", start:go("rtw-start").value, dir:go("rtw-dir").value, end:(go("rtw-end")?go("rtw-end").value:"START"), endarea:(go("rtw-endarea")?go("rtw-endarea").value:"MAIN"), stops:go("rtw-stops").value,
         budget:go("rtw-budget").value, must:MFMUST.join(","), mode:(MFMUST.length&&go("rtw-mode")?go("rtw-mode").value:""), weeks:go("rtw-weeks").value, regions:regionsOn().join("~")};
  var q=[]; for(var k in p){ if(p[k]!=="" && p[k]!=null) q.push(k+"="+encodeURIComponent(p[k])); }
  try{ history.replaceState(null,"", location.pathname+"?"+q.join("&")); }catch(e){}
}
window.rtwBuild=function(){
  var nStops=parseInt(go("rtw-stops").value,10);
  var budget=parseInt(go("rtw-budget").value,10); if(isNaN(budget)||budget<=0) budget=0;
  var weeks=parseInt(go("rtw-weeks").value,10); if(isNaN(weeks)||weeks<=0) weeks=0;
  var scope=go("rtw-scope")?go("rtw-scope").value:"WORLD";
  var best=null, regionName="", custom=false;
  if(MFMUST.length){
    custom=true;
    var mode=go("rtw-mode")?go("rtw-mode").value:"fill";
    var startSel=go("rtw-start")?go("rtw-start").value:"AUTO";
    var cstarts=(startSel && startSel!=="AUTO" && RHUBS[startSel])?[startSel]:RUS;
    var pool=[], target;
    if(scope!=="WORLD" && REGIONS[scope]){
      regionName=REGIONS[scope].name;
      pool=REGIONS[scope].h.filter(function(h){ return RHUBS[h]; });
      target = mode==="exact" ? MFMUST.length : Math.max(nStops, MFMUST.length);
    } else {
      regionName="the world";
      var onw=regionsOn();
      for(var h in RHUBS){ if(RUS.indexOf(h)>=0) continue; if(onw.length && onw.indexOf(RHUBS[h].cont)<0) continue; pool.push(h); }
      target = mode==="exact" ? MFMUST.length : Math.max(nStops, MFMUST.length);
    }
    var cities = mode==="exact" ? MFMUST.slice() : pickExtras(MFMUST.slice(), pool, target);
    cstarts.forEach(function(s){ if(!RHUBS[s]) return; var x=cheapestCycle(s, cities); if(x && (best==null||x.total<best.total)){ best={total:x.total, route:[s].concat(x.order).concat([s]), tour:true, custom:true, dir:null}; } });
  } else if(scope!=="WORLD" && REGIONS[scope]){
    regionName=REGIONS[scope].name;
    var rs=go("rtw-start")?go("rtw-start").value:"AUTO";
    best=buildTour(REGIONS[scope].h, nStops, "", rs);
    if(best) best.dir=null;
  } else {
    var on=regionsOn(); var allowed=null;
    if(on.length){ allowed={}; on.forEach(function(c){ allowed[c]=true; }); }
    var start=go("rtw-start").value, dir=go("rtw-dir").value;
    var endMode=go("rtw-end")?go("rtw-end").value:"START";
    var endArea=go("rtw-endarea")?go("rtw-endarea").value:"MAIN";
    var dirs = dir==="BOTH" ? ["E","W"] : [dir];
    var starts = start==="AUTO" ? RUS : [start];
    starts.forEach(function(s){ dirs.forEach(function(dd){ var x=buildLoop(s,nStops,allowed,dd,"",endMode,endArea); if(x&&(best==null||x.total<best.total)){ x.dir=dd; best=x; } }); });
  }
  updateURL();
  render(best, {budget:budget, weeks:weeks, regionName:regionName, custom:custom, mode:(go("rtw-mode")?go("rtw-mode").value:"")});
};
function rtwInit(){
  mfLoadConf();
  var qs; try{ qs=new URLSearchParams(location.search); }catch(e){ qs=null; }
  if(qs){
    if(qs.get("scope") && go("rtw-scope")) go("rtw-scope").value=qs.get("scope");
    if(qs.get("start")) go("rtw-start").value=qs.get("start");
    if(qs.get("dir")) go("rtw-dir").value=qs.get("dir");
    if(qs.get("end") && go("rtw-end")) go("rtw-end").value=qs.get("end");
    if(qs.get("endarea") && go("rtw-endarea")) go("rtw-endarea").value=qs.get("endarea");
    if(qs.get("stops")){ go("rtw-stops").value=qs.get("stops"); rtwStopsLab(); }
    if(qs.get("budget")) go("rtw-budget").value=qs.get("budget");
    if(qs.get("must")){ var mm=qs.get("must").split(","); for(var mi=0;mi<mm.length;mi++){ var raw=mm[mi].trim(); if(!raw) continue; var cc=RHUBS[raw]?raw:nameToCode(raw); if(cc && MFMUST.indexOf(cc)<0 && MFMUST.length<6) MFMUST.push(cc); } }
    if(qs.get("mode") && go("rtw-mode")) go("rtw-mode").value=qs.get("mode");
    if(qs.get("weeks")) go("rtw-weeks").value=qs.get("weeks");
    if(qs.get("regions")!=null && qs.get("regions")!==""){ var sel=qs.get("regions").split("~"); var chips=go("rtw-conts").querySelectorAll("[data-rcont]"); for(var i=0;i<chips.length;i++){ chips[i].classList.toggle("on", sel.indexOf(chips[i].getAttribute("data-rcont"))>=0); } }
  }
  rtwScope();
  var mip=go("rtw-must");
  if(mip){ mip.addEventListener("change", function(){ rtwMustAdd(); }); mip.addEventListener("keydown", function(e){ if(e.key==="Enter"){ e.preventDefault(); rtwMustAdd(); } }); }
  renderMustChips();
  rtwBuild();
}
rtwInit();
})();
</script>"""
    return (shell
            .replace("__COMPASS__", COMPASS)
            .replace("__START_OPTS__", start_opts)
            .replace("__MUST_OPTS__", must_opts)
            .replace("__CONT_CHIPS__", cont_chips)
            .replace("__DEFAULT__", default_html)
            .replace("__HUBS__", json.dumps(HUBS))
            .replace("__LEGS__", json.dumps(LEGS))
            .replace("__RDEST__", json.dumps(RDEST))
            .replace("__US__", json.dumps([h for h in RTW_US_STARTS if h in HUBS])))


def body_consultant():
    return f"""<div class="wrap" style="max-width:720px">
  <div class="pagehead"><h1>Hire a Trip Consultant</h1>
  <p>Tell us where you want to go &mdash; or just your budget and rough dates &mdash; and we&rsquo;ll design the cheapest possible trip and <b>guarantee the best deals</b>: smart one-way routing, round-the-world loops, and fares most people never find. Save hours of searching and often hundreds on flights.</p></div>
  <div class="rtw-hero" style="padding:20px"><div class="rtw-hero-label">Our fee</div><div class="rtw-hero-price" style="font-size:34px">10% of your trip</div><div class="rtw-hero-sub">and we guarantee the best deals we can find &mdash; so the savings more than cover it.</div></div>
  <div class="panel" style="padding:24px">
    <form class="form" style="flex-direction:column;max-width:none;align-items:stretch;gap:12px" action="{FORM_ACTION}" method="POST" onsubmit="return fakeSubmit(event)">
      <input type="hidden" name="_subject" value="New trip-consultation request">
      <input type="hidden" name="type" value="consultation">
      <input type="text" name="name" placeholder="Your name" required>
      <input type="email" name="email" placeholder="you@email.com" required>
      <textarea name="message" rows="5" required placeholder="Where do you want to go, roughly when, and your budget? Round-the-world? One country? A few cities? We&rsquo;ll take it from there." style="background:#efe5cd;color:var(--ink);border:1px solid var(--line);border-radius:9px;padding:12px 14px;font-size:15px;font-family:inherit;resize:vertical"></textarea>
      <button type="submit">Send my trip request</button>
    </form>
    <div class="ok" id="ok">&#10003; Got it &mdash; we&rsquo;ll get back to you by email with a plan and a quote.</div>
  </div>
  <div class="blog-sec" style="margin-top:24px"><h2>What you get</h2><ul class="blog-list"><li>A custom itinerary with the cheapest routing, specific flights and dates</li><li>A best-deal guarantee &mdash; we surface one-way and round-the-world fares most sites never show</li><li>Direct booking links so you book the exact fares yourself</li></ul></div>
  <p class="finehint" style="text-align:center;margin-top:18px">No obligation to ask. Fee is 10% of your trip cost, charged only once you&rsquo;re happy with the plan.</p>
</div>"""


def body_explore(home):
    _air_card = ('''<div class="tl-card" id="ex-tab-air" style="display:none">
  <p style="font-size:13.5px;color:var(--muted);margin:0 0 12px">The simplest way to plan: pick your home airport and see the cheapest one-ways leaving from your city, judged against their normal price. Star &#9734; any deal to watch it. Everything saves in this browser.</p>
  <div class="citybar"><select id="city-pick">__CITYOPTS__</select><button onclick="addCity()">Add my airport</button></div>
  <div class="citychips" id="citychips"></div>
  <div class="sec-head"><h2>&#11088; My watched flights</h2><span>star any deal below to track it</span></div>
  <div class="panel"><div id="airwatch"></div><div class="wl-hint" id="aw-hint">Star (&#9734;) any deal below to add it to your watched flights. Saved in this browser.</div></div>
  <div class="sec-head"><h2>Deals from your airport</h2><span>tap &#9734; to watch</span></div>
  <div class="airchips" style="margin:6px 0 8px;"><button class="airchip on" data-actrip="rt" onclick="setACTrip('rt')">Round-trip</button><button class="airchip" data-actrip="ow" onclick="setACTrip('ow')">One-way</button></div>
  <div class="airchips" style="margin:0 0 14px;">__ACREGIONS__</div>
  <div class="panel"><div id="citydeals"></div><div class="wl-hint" id="city-hint">Add your home airport (e.g. Raleigh, RDU) to see the cheapest trips leaving from your city.</div></div>
</div>'''.replace("__CITYOPTS__", city_options(home)).replace("__ACREGIONS__", region_chip_bar("data-acr", "toggleACR")))
    _html = """<div class="wrap">
  <div class="pagehead"><h1>Find One-Way Flight Deals from the USA</h1><p>Add your home airport(s) and we&rsquo;ll find the best one-way deals to <b>anywhere</b>, or type a destination to see every fare we have for it. Add several airports and we compare across all of them. Just want to browse today&rsquo;s deals? That&rsquo;s the <a href="market.html" style="color:var(--gold)">Market</a>.</p></div>
  <div class="airchips" id="ex-tabs" style="margin:0 0 14px;gap:8px">
    <button type="button" class="airchip on" id="ex-tab-explore-btn" onclick="exTab('explore')">Explore anywhere</button>
    <button type="button" class="airchip" id="ex-tab-air-btn" onclick="exTab('air')">From my airport</button>
    <button type="button" class="airchip" id="ex-tab-fav-btn" onclick="exTab('fav')">&#9733; Your favorites</button>
    <button type="button" class="airchip" id="ex-tab-meet-btn" onclick="exTab('meet')">Meet in the middle</button>
  </div>
  <div class="tl-card" id="ex-tab-explore">
    <div style="display:flex;gap:8px;align-items:center;margin:0 0 12px;flex-wrap:wrap">
      <button type="button" class="airchip on" id="ex-rt-ow" onclick="exSetTrip('oneway')">One-way</button>
      <button type="button" class="airchip" id="ex-rt-rt" onclick="exSetTrip('round')">Round-trip</button>
      <button type="button" class="airchip" onclick="exAllUS()" title="Add every major US airport as an origin">&#43; All US hubs</button>
    </div>
    <div class="tl-form" style="align-items:flex-end">
      <div style="display:flex;flex-direction:column;gap:5px">
        <span style="font-size:12px;color:var(--muted)">From &mdash; any airport, US or abroad</span>
        <div style="display:flex;gap:6px;align-items:flex-start"><span class="ac-wrap"><input id="ex-add" placeholder="Search a city or airport (Charlotte, CLT)" autocomplete="off" style="width:240px;max-width:72vw;background:#efe5cd;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:9px 10px" oninput="exAddAC()" onkeydown="if(event.key==='Enter'){exAddOrig();return false;}"><div id="ex-add-ac" class="ac-drop"></div></span><button class="airchip" onclick="exAddOrig()">+ Add</button></div>
        <div id="ex-origs" class="airchips"></div>
      </div>
      <label style="display:flex;flex-direction:column;gap:5px;font-size:12px;color:var(--muted)">To (optional)<div class="ac-wrap"><input id="ex-to" placeholder="Search a city or leave blank for anywhere" autocomplete="off" oninput="exToAC()" style="width:230px;background:#efe5cd;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:9px 10px" onkeydown="if(event.key==='Enter'){document.getElementById('ex-to-ac').style.display='none';exSearch();return false;}"><div id="ex-to-ac" class="ac-drop"></div></div></label>
      
      <button class="btn-primary tl-go" onclick="exSearch()">Find deals</button>
    </div>
    <div id="ex-when" style="margin:8px 0 2px"><span style="font-size:12px;color:var(--muted);margin-right:6px">When:</span><span class="airchips" style="display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap"><button class="airchip on" id="ex-wh-any" onclick="exSetWhen('any')">Anytime</button><select id="ex-wh-month" onchange="exSetMonth(this.value)" style="background:#efe5cd;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:7px 9px;font:inherit"><option value="">Flexible month…</option></select><input type="date" id="ex-wh-date" onchange="exSetDate(this.value)" style="background:#efe5cd;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:7px 9px;font:inherit"></span></div>
    <div id="ex-regions" class="airchips" style="margin:6px 0 12px"></div>
    <div class="panel"><div id="ex-out"><div class="wl-hint">Add your home airport(s) and hit &ldquo;Find deals.&rdquo;</div></div></div>
  </div>
  <div class="tl-card" id="ex-tab-fav" style="display:none">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px">
      <div style="font-size:13px;color:var(--muted)">Your starred deals &mdash; we re-check today&rsquo;s cheapest price for each.</div>
      <button class="airchip" onclick="exFavRender()">Refresh prices</button>
    </div>
    <div class="panel"><div id="ex-fav-out"><div class="wl-hint">Loading your favorites&hellip;</div></div></div>
  </div>
  <div class="tl-card" id="ex-tab-meet" style="display:none">
    <p style="font-size:13.5px;color:var(--muted);margin:0 0 12px">Two people, two home cities &mdash; we rank the destinations where your <b>combined</b> airfare is cheapest. Perfect for meeting a friend or partner halfway.</p>
    <div class="tl-form" style="align-items:flex-end;flex-wrap:wrap;gap:12px">
      <label>You fly from<span class="ac-wrap"><input id="mm-a" placeholder="City or airport (New York, JFK)" autocomplete="off" style="min-width:190px" oninput="mmAAC()" onkeydown="if(event.key==='Enter'){var _d=document.getElementById('mm-a-ac');if(_d)_d.style.display='none';mmSearch();}"><div id="mm-a-ac" class="ac-drop"></div></span></label>
      <label>They fly from<span class="ac-wrap"><input id="mm-b" placeholder="City or airport (Bangkok, BKK)" autocomplete="off" style="min-width:190px" oninput="mmBAC()" onkeydown="if(event.key==='Enter'){var _d=document.getElementById('mm-b-ac');if(_d)_d.style.display='none';mmSearch();}"><div id="mm-b-ac" class="ac-drop"></div></span></label>
      <div style="display:flex;gap:8px"><button type="button" class="airchip on" id="mm-rt" onclick="mmTrip('round')">Round-trip</button><button type="button" class="airchip" id="mm-ow" onclick="mmTrip('oneway')">One-way</button></div>
      <button class="btn-primary tl-go" onclick="mmSearch()">Find our meeting spot</button>
    </div>
    <div class="airchips" id="mm-regions" style="margin:8px 0 2px;display:none"><span style="font-size:12px;color:var(--muted);margin-right:4px;align-self:center">Meet in:</span><button type="button" class="airchip on" data-mmr="all" onclick="mmReg('all')">Anywhere</button><button type="button" class="airchip" data-mmr="Americas" onclick="mmReg('Americas')">Americas</button><button type="button" class="airchip" data-mmr="Europe" onclick="mmReg('Europe')">Europe</button><button type="button" class="airchip" data-mmr="Asia" onclick="mmReg('Asia')">Asia</button><button type="button" class="airchip" data-mmr="Middle East" onclick="mmReg('Middle East')">Middle East</button><button type="button" class="airchip" data-mmr="Africa" onclick="mmReg('Africa')">Africa</button><button type="button" class="airchip" data-mmr="Oceania" onclick="mmReg('Oceania')">Oceania</button></div>
    <div class="panel" style="margin-top:10px"><div id="mm-out"><div class="wl-hint">Enter both home airports and hit search &mdash; we&rsquo;ll rank the cheapest places to meet.</div></div></div>
  </div>
  __AIRPORT_TAB_CARD__
  <p class="finehint" style="text-align:center">Live fares from Aviasales. Star &#9734; a deal to add it to your favorites. Want to chain multiple stops into one trip? Try <a href="around-the-world.html" style="color:var(--blue)">Around the World</a>.</p>
</div>
<script>
(function(){
var CC = __CCJS__;
var GROUPS={'SE Asia':'TH VN ID SG MY PH KH LA MM BN TL','E Asia':'JP KR CN TW HK MO MN','S Asia':'IN LK NP PK BD MV BT AF','C Asia':'KZ UZ KG TJ TM','W Europe':'FR GB DE NL BE IE ES PT IT CH AT LU MC AD LI MT','Nordic':'SE NO DK FI IS','E Europe':'PL CZ HU RO BG GR HR RS SK SI UA EE LV LT AL BA MK ME MD BY RU CY','S America':'BR AR CL CO PE EC UY PY BO VE GF SR GY','C America':'MX GT BZ SV HN NI CR PA','Caribbean':'DO JM BS CU HT PR TT BB AW CW GP MQ KY BM AG LC GD VC DM KN TC VG AI MS SX BQ','Oceania':'AU NZ FJ PF NC WS TO VU PG CK GU','Middle East':'AE QA SA IL JO TR LB KW BH OM IR IQ YE SY','Africa':'ZA EG MA KE ET NG GH TZ SN CI TN DZ UG RW MU SC NA BW ZW MZ AO CM GA','Canada':'CA'};
function tagsFor(code){ var c=CC[code]; if(!c) return ['Abroad']; if(c==='US') return ['USA']; var t=[]; for(var g in GROUPS){ if((' '+GROUPS[g]+' ').indexOf(' '+c+' ')>=0){ t.push(g); if(g==='SE Asia'||g==='E Asia'||g==='S Asia'||g==='C Asia') t.push('Asia'); break; } } if(c!=='CA') t.push('Abroad'); return t; }
var REGIONS=['all','USA','Abroad','Asia','SE Asia','E Asia','S Asia','W Europe','E Europe','Nordic','S America','C America','Caribbean','Oceania','Middle East','Africa','Canada'];
function go(id){ return document.getElementById(id); }
var EX_TRIP='oneway', EX_WHEN='any', EX_REG='all', EX_DATA=[], EX_SHOWN=[], EX_ORIG=[], EX_P2P=false, EX_DATE='', EP_FROM_CODE='', EP_TO_CODE='', EX_ADD_CODE='';
function bucket(){ try{ return JSON.parse(localStorage.getItem('mf_bucket')||'[]'); }catch(e){ return []; } }
function saved(id){ return bucket().some(function(x){ return x.id===id; }); }
function renderOrigs(){ var box=go('ex-origs'); if(!box) return; box.innerHTML=EX_ORIG.map(function(c){ return '<button class="airchip on" data-o="'+c+'" title="remove">'+c+' &times;</button>'; }).join(''); }
window.exAddOrig=function(){ var raw=(go('ex-add').value||'').trim(); var v=EX_ADD_CODE||(/^[A-Za-z]{3}$/.test(raw)?raw.toUpperCase():(typeof resolveTo==='function'?resolveTo(raw):'')); if(!/^[A-Z]{3}$/.test(v)){ go('ex-add').focus(); return; } if(EX_ORIG.indexOf(v)<0) EX_ORIG.push(v); go('ex-add').value=''; EX_ADD_CODE=''; var _d=go('ex-add-ac'); if(_d) _d.style.display='none'; renderOrigs(); exSearch(); };
window.exSetTrip=function(t){ EX_TRIP=t; var rr=go('ex-rt-rt'),ro=go('ex-rt-ow'); if(rr)rr.classList.toggle('on',t==='round'); if(ro)ro.classList.toggle('on',t==='oneway'); exSearch(); };
window.exAllUS=function(){ var HUBS=['JFK','EWR','BOS','IAD','DCA','PHL','ATL','MIA','FLL','MCO','TPA','CLT','RDU','ORD','DTW','MSP','DFW','IAH','DEN','PHX','LAS','SLC','LAX','SFO','SEA','SAN','PDX','BNA','AUS']; HUBS.forEach(function(c){ if(EX_ORIG.indexOf(c)<0) EX_ORIG.push(c); }); renderOrigs(); exSearch(); };
window.exSetWhen=function(w){ EX_WHEN='any'; EX_DATE=''; var ms=go('ex-wh-month'); if(ms) ms.value=''; var ds=go('ex-wh-date'); if(ds) ds.value=''; go('ex-wh-any').classList.add('on'); exSearch(); };
window.exSetMonth=function(v){ var ds=go('ex-wh-date'); if(ds) ds.value=''; EX_DATE=v||''; go('ex-wh-any').classList.toggle('on', !EX_DATE); exSearch(); };
window.exSetDate=function(v){ var ms=go('ex-wh-month'); if(ms) ms.value=''; EX_DATE=v||''; go('ex-wh-any').classList.toggle('on', !EX_DATE); exSearch(); };
function exMonthFill(){ var sel=go('ex-wh-month'); if(!sel) return; var now=new Date(); var mn=['January','February','March','April','May','June','July','August','September','October','November','December']; var h='<option value="">Flexible month\u2026</option>'; for(var k=0;k<12;k++){ var dt=new Date(now.getFullYear(), now.getMonth()+k, 1); var v=dt.getFullYear()+'-'+('0'+(dt.getMonth()+1)).slice(-2); h+='<option value="'+v+'">'+mn[dt.getMonth()]+' '+dt.getFullYear()+'</option>'; } sel.innerHTML=h; }
function renderChips(){ go('ex-regions').innerHTML=REGIONS.map(function(r){ var lab=r==='all'?'All':r; return '<button class="airchip'+(EX_REG===r?' on':'')+'" data-r="'+r+'">'+lab+'</button>'; }).join(''); }
window.exSearch=function(){ var ow=(EX_TRIP==='oneway'?'true':'false'); var to=(EX_TO_CODE||resolveTo(go('ex-to').value)).toUpperCase(); var when=''; if(!EX_ORIG.length){ go('ex-regions').style.display='none'; go('ex-when').style.display='none'; go('ex-out').innerHTML='<div class="wl-hint">'+(to?('Add at least one <b>From</b> airport to search fares to '+to+'.'):'Add your home airport(s) above &mdash; then optionally a destination &mdash; and hit Find deals.')+'</div>'; return; } EX_P2P=/^[A-Z]{3}$/.test(to); go('ex-regions').style.display=EX_P2P?'none':'flex'; go('ex-when').style.display='block';
  if(EX_P2P){
    go('ex-out').innerHTML='<div class="wl-hint">Finding '+(EX_TRIP==='oneway'?'one-way':'round-trip')+' fares to '+to+' from '+EX_ORIG.join(', ')+(when?(' around '+when):'')+'&hellip;</div>';
    var calls=EX_ORIG.map(function(o){ return fetch('/api/search?origin='+o+'&destination='+to+'&one_way='+ow+'&sorting=route&limit=100'+(EX_DATE?'&departure_at='+EX_DATE:'')).then(function(r){return r.json();}).then(function(j){ return (j&&j.data)||[]; }).catch(function(){ return []; }); });
    Promise.all(calls).then(function(arrs){ var all=[]; arrs.forEach(function(d){ all=all.concat(d); }); all=all.filter(function(f){ return f.destination_airport===to && f.departure_at; }); var seen={}; all.forEach(function(f){ var key=f.origin_airport+'|'+(f.departure_at||'').slice(0,10); if(!seen[key]||f.price<seen[key].price) seen[key]=f; }); var list=Object.keys(seen).map(function(k){return seen[k];}); if(when){ var only=list.filter(function(f){ return (f.departure_at||'').slice(0,10)>=when; }); if(only.length) list=only; } list.sort(function(a,b){ var da=(a.departure_at||'').slice(0,10), db=(b.departure_at||'').slice(0,10); if(da!==db) return da<db?-1:1; return a.price-b.price; }); EX_DATA=list; EX_SHOWN=list.slice(0,40); exRender(); if(!list.length){ go('ex-out').innerHTML='<div class="wl-hint">We don&rsquo;t have cached fares for '+EX_ORIG.join('/')+' &rarr; '+to+' right now. Try a major hub (JFK, LAX, ORD) as a From airport, or remove the date.</div>'; } }).catch(function(){ go('ex-out').innerHTML='<div class="wl-hint">Couldn&rsquo;t load that route &mdash; try again.</div>'; });
    return;
  }
  go('ex-out').innerHTML='<div class="wl-hint">Finding the cheapest '+(EX_TRIP==='oneway'?'one-way':'round-trip')+' fares from '+EX_ORIG.join(', ')+'&hellip;</div>'; var origset={}; EX_ORIG.forEach(function(o){origset[o]=1;}); var calls2=EX_ORIG.map(function(o){ return fetch('/api/search?origin='+o+'&one_way='+ow+'&sorting=price&limit=600'+(EX_DATE?'&departure_at='+EX_DATE:'')).then(function(r){return r.json();}).then(function(j){ return (j&&j.data)||[]; }).catch(function(){ return []; }); }); Promise.all(calls2).then(function(arrs){ var best={}; arrs.forEach(function(data){ data.forEach(function(f){ var d=f.destination_airport; if(!d||origset[d]) return; if(!best[d]||f.price<best[d].price) best[d]=f; }); }); EX_DATA=Object.keys(best).map(function(k){return best[k];}).sort(function(a,b){return a.price-b.price;}); exFilter(); }).catch(function(){ go('ex-out').innerHTML='<div class="wl-hint">Couldn&rsquo;t load deals &mdash; try again.</div>'; }); };
function exFilter(){ var now=new Date(); var soon=new Date(); soon.setDate(soon.getDate()+16); var rows=EX_DATA.filter(function(f){ if(EX_REG!=='all' && tagsFor(f.destination_airport).indexOf(EX_REG)<0) return false; if(EX_WHEN==='soon'){ var dp=new Date((f.departure_at||'').slice(0,10)+'T00:00:00'); if(isNaN(dp)||dp<now||dp>soon) return false; } return true; }); EX_SHOWN=rows.slice(0,40); exRender(); }
var BM = __BMJS__;
function owFlag(d){ var cc=(CC[d]||'').toLowerCase(); return cc ? '<img class="flag" src="https://flagcdn.com/'+cc+'.svg" alt="" width="30" height="21" loading="lazy">' : '<span class="flag flag-na" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.7 2.6 15.3 0 18M12 3c-2.6 2.7-2.6 15.3 0 18"/></svg></span>'; }
function owMini(price, typ){ if(!typ||typ<=0) return ''; var lo=typ*0.6, hi=typ*1.4; if(hi<=lo) return ''; var frac=Math.max(2,Math.min(98,(price-lo)/(hi-lo)*100)); var c,v; if(price<=typ*0.9){c='g';v='Low';}else if(price<=typ*1.1){c='y';v='Typical';}else{c='r';v='High';} return '<div class="minibar"><div class="mb-track"><span class="mb-dot '+c+'" style="left:'+Math.round(frac)+'%"></span></div><span class="mb-lab '+c+'">'+v+'</span></div>'; }
var NAMES = __NAMESJS__; var MAJOR = __MAJORJS__; var MAJSET={}; for(var _mi=0;_mi<MAJOR.length;_mi++) MAJSET[MAJOR[_mi]]=1;
var EX_TO_CODE='';
function resolveTo(txt){ txt=(txt||'').trim(); if(!txt) return ''; if(/^[A-Za-z]{3}$/.test(txt)) return txt.toUpperCase(); var q=txt.toLowerCase(); var em='',ea='',sm='',sa=''; for(var c in NAMES){ var nm=(NAMES[c]||'').toLowerCase(); if(!nm) continue; if(nm===q){ if(MAJSET[c]){ if(!em) em=c; } else if(!ea) ea=c; } else if(nm.indexOf(q)===0){ if(MAJSET[c]){ if(!sm) sm=c; } else if(!sa) sa=c; } } return em||ea||sm||sa||''; }
window.exToAC=function(){ var inp=document.getElementById('ex-to'); var q=(inp.value||'').trim().toLowerCase(); var drop=document.getElementById('ex-to-ac'); EX_TO_CODE=''; if(q.length<2){ drop.style.display='none'; drop.innerHTML=''; return; } var starts=[],cont=[]; for(var c in NAMES){ var nm=NAMES[c]; if(!nm) continue; var i=nm.toLowerCase().indexOf(q); if(i<0) continue; (i===0?starts:cont).push([c,nm]); if(starts.length>60) break; } var mf=function(a,b){ return (MAJSET[a[0]]?0:1)-(MAJSET[b[0]]?0:1); }; starts.sort(mf); cont.sort(mf); var list=starts.concat(cont).slice(0,8); if(!list.length){ drop.style.display='none'; drop.innerHTML=''; return; } drop.innerHTML=list.map(function(x){ return '<div class="ac-item" data-code="'+x[0]+'" data-name="'+x[1].replace(/"/g,'&quot;')+'"><span>'+x[1]+'</span><span class="ac-code">'+x[0]+'</span></div>'; }).join(''); drop.style.display='block'; };
function exToBind(){ var d=document.getElementById('ex-to-ac'); if(d && !d._bound){ d._bound=1; d.addEventListener('click', function(e){ var it=e.target.closest('.ac-item'); if(!it) return; EX_TO_CODE=it.getAttribute('data-code'); document.getElementById('ex-to').value=it.getAttribute('data-name'); d.style.display='none'; window.exSearch(); }); document.addEventListener('click', function(e){ if(!e.target.closest('.ac-wrap')){ d.style.display='none'; } }); } }
function airportFilter(inp, drop){ if(!inp||!drop) return; var q=(inp.value||'').trim().toLowerCase(); if(q.length<2){ drop.style.display='none'; drop.innerHTML=''; return; } var starts=[],cont=[]; for(var c in NAMES){ var nm=NAMES[c]; if(!nm) continue; var i=nm.toLowerCase().indexOf(q); if(i<0) continue; (i===0?starts:cont).push([c,nm]); if(starts.length>60) break; } var mf=function(a,b){ return (MAJSET[a[0]]?0:1)-(MAJSET[b[0]]?0:1); }; starts.sort(mf); cont.sort(mf); var list=starts.concat(cont).slice(0,8); if(!list.length){ drop.style.display='none'; drop.innerHTML=''; return; } drop.innerHTML=list.map(function(x){ return '<div class="ac-item" data-code="'+x[0]+'" data-name="'+x[1].replace(/"/g,'&quot;')+'"><span>'+x[1]+'</span><span class="ac-code">'+x[0]+'</span></div>'; }).join(''); drop.style.display='block'; }
function bindAC(drop, inp, onpick){ if(!drop||!inp||drop._bound) return; drop._bound=1; drop.addEventListener('click', function(e){ var it=e.target.closest('.ac-item'); if(!it) return; inp.value=it.getAttribute('data-name'); drop.style.display='none'; onpick(it.getAttribute('data-code')); }); }
window.exAddAC=function(){ EX_ADD_CODE=''; airportFilter(go('ex-add'), go('ex-add-ac')); };
window.exFavDel=function(i){ var list=bucket(); list.splice(i,1); localStorage.setItem('mf_bucket', JSON.stringify(list)); if(window.renderBucket) window.renderBucket(); window.exFavRender(); };
window.exFavRender=function(){ var out=go('ex-fav-out'); if(!out) return; var list=bucket(); if(!list.length){ out.innerHTML='<div class="wl-hint">No favorites yet. Tap the star &#9734; on any deal here or on the <a href="market.html" style="color:var(--blue)">Market</a> to save it, then come back to track its price.</div>'; return; } out.innerHTML=list.map(function(f,i){ var d=f.d||'', o=f.o||'', p=f.price||0; var nm=(typeof NAMES!=='undefined'&&NAMES[d])?(' <span style="color:var(--muted);font-weight:400;font-size:13px">'+NAMES[d]+'</span>'):''; var owl=f.ow?'one-way':'round-trip'; return '<div class="mv-row"><button class="star on" title="remove" onclick="exFavDel('+i+')">&#9733;</button><div class="mv-dest">'+owFlag(d)+'<div class="mv-destcol"><div class="mv-name">'+o+' &rarr; '+d+nm+'</div><div class="mv-air">'+(f.date||'flexible')+' &middot; saved $'+p.toLocaleString()+' '+owl+'</div></div></div><div class="mv-right"><span class="mv-price" id="favp-'+i+'"><span class="lp-dot"></span>$'+p.toLocaleString()+'</span> <span class="ow-unit">'+owl+'</span>'+(f.link?'<a class="mini-book" href="'+f.link+'" target="_blank" rel="noopener">See live price &rarr;</a>':'')+'</div></div>'; }).join(''); list.forEach(function(f,i){ if(!f.o||!f.d) return; var ow=f.ow?'true':'false'; fetch('/api/search?origin='+f.o+'&destination='+f.d+'&one_way='+ow+'&sorting=price&limit=1').then(function(r){return r.json();}).then(function(j){ var ff=j&&j.data&&j.data[0]; var slot=go('favp-'+i); if(!slot||!ff||!ff.price) return; var np=Math.round(ff.price); var col=np<f.price?'var(--green)':(np>f.price?'var(--red)':'var(--ink)'); slot.innerHTML='<span class="lp-dot"></span><span style="color:'+col+'">$'+np.toLocaleString()+'</span>'+(np<f.price?' <span style="font-size:11px;color:var(--green)">&#9660;</span>':''); if(ff.link){ var lk=slot.parentNode.querySelector('.mini-book'); if(lk) lk.href=ff.link; } }).catch(function(){}); }); };
function exRender(){ var out=go('ex-out'); if(!EX_SHOWN.length){ out.innerHTML='<div class="wl-hint">'+(EX_P2P?'No fares found for that route/date. Try clearing the date or another destination.':'No fares match those filters. Try another region or Anytime.')+'</div>'; return; } var multi=EX_ORIG.length>1; out.innerHTML=EX_SHOWN.map(function(f,i){ var d=f.destination_airport, dp=(f.departure_at||'').slice(0,10), rt=(f.return_at||'').slice(0,10), p=Math.round(f.price); var typ=(BM&&BM[d])?BM[d]*(EX_TRIP==="oneway"?0.62:1):0; var oo=f.origin_airport; var id=oo+d+dp; var on=saved(id)?' on':''; var star=saved(id)?'&#9733;':'&#9734;'; var sub=oo+' &rarr; '+d+' &middot; '+dp+(EX_TRIP==='round'&&rt?(' &rarr; '+rt):''); var title=EX_P2P?dp:(d+(((typeof NAMES!=="undefined")&&NAMES[d])?(' <span style="color:var(--muted);font-weight:400;font-size:13px;margin-left:6px">'+NAMES[d]+'</span>'):'')+(multi?('<span style="display:inline-block;background:#efe5cd;border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-size:11px;color:var(--gold);margin-left:8px">from '+oo+'</span>'):'')); var rid='exret-'+oo+d+i; return '<div class="owr"><div class="mv-row"><button class="star'+on+'" onclick="exSave(this,'+i+')">'+star+'</button><div class="mv-dest">'+owFlag(d)+'<div class="mv-destcol"><div class="mv-name">'+title+'</div><div class="mv-air">'+sub+'</div><div class="pr-fresh"><i class="dotc"></i><span>tracked now</span></div></div></div><div class="mv-right"><span class="mv-price"><span class="lp-dot" title="Freshest tracked fare — your live, bookable price is confirmed on Aviasales"></span>$'+p.toLocaleString()+'</span> <span class="ow-unit">'+(EX_TRIP==='round'?'round-trip':'one-way')+'</span>'+(EX_TRIP==='round'?'':'<button class="addret-sm" type="button" data-exret="'+oo+'|'+d+'|'+i+'">+ return</button>')+'<a class="mini-book" href="'+f.link+'" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div></div><div class="owret" id="'+rid+'"></div></div>'; }).join(''); }
window.exRet=function(btn,o,d,i){ var box=go('exret-'+o+d+i); if(!box) return; if(box.classList.contains('show')){ box.classList.remove('show'); return; } if(box.getAttribute('data-done')){ box.classList.add('show'); return; } box.innerHTML='<span class="owret-lab">Finding round-trip&hellip;</span>'; box.classList.add('show'); fetch('/api/search?origin='+o+'&destination='+d+'&one_way=false&sorting=price&limit=1').then(function(r){return r.json();}).then(function(j){ var ff=j&&j.data&&j.data[0]; if(ff&&ff.price){ box.setAttribute('data-done','1'); box.innerHTML='<span class="owret-lab">Round-trip there &amp; back:</span> <span class="owret-rp">$'+Math.round(ff.price).toLocaleString()+'</span> <a class="owret-link" href="'+ff.link+'" target="_blank" rel="noopener">see round-trip &rarr;</a>'; } else { box.innerHTML='<span class="owret-lab">No round-trip fare found for this route right now.</span>'; } }).catch(function(){ box.innerHTML='<span class="owret-lab">Couldn&rsquo;t load round-trip &mdash; try again.</span>'; }); };
document.addEventListener('click', function(e){ var b=e.target.closest && e.target.closest('[data-exret]'); if(b){ var p=b.getAttribute('data-exret').split('|'); window.exRet(b,p[0],p[1],p[2]); } });
window.exSave=function(btn,i){ var f=EX_SHOWN[i]; if(!f) return; var list=bucket(); var id=f.origin_airport+f.destination_airport+(f.departure_at||'').slice(0,10); var idx=-1; for(var k=0;k<list.length;k++){ if(list[k].id===id){ idx=k; break; } } if(idx>=0){ list.splice(idx,1); btn.classList.remove('on'); btn.innerHTML='&#9734;'; } else { list.push({id:id,o:f.origin_airport,d:f.destination_airport,date:(f.departure_at||'').slice(0,10),ret:(f.return_at||'').slice(0,10),price:Math.round(f.price),link:f.link,ow:EX_TRIP==='oneway'?1:0}); btn.classList.add('on'); btn.innerHTML='&#9733;'; } localStorage.setItem('mf_bucket',JSON.stringify(list)); if(window.renderBucket) window.renderBucket(); };
var rb=go('ex-regions'); if(rb){ rb.addEventListener('click', function(e){ var b=e.target.closest('[data-r]'); if(b){ EX_REG=b.getAttribute('data-r'); renderChips(); exFilter(); } }); }
var ob=go('ex-origs'); if(ob){ ob.addEventListener('click', function(e){ var b=e.target.closest('[data-o]'); if(!b) return; var c=b.getAttribute('data-o'); EX_ORIG=EX_ORIG.filter(function(x){return x!==c;}); renderOrigs(); exSearch(); }); }
renderOrigs(); renderChips(); exToBind(); exMonthFill(); exSearch(); bindAC(go('ex-add-ac'), go('ex-add'), function(c){ go('ex-add').value=''; if(EX_ORIG.indexOf(c)<0) EX_ORIG.push(c); renderOrigs(); exSearch(); }); bindAC(go('mm-a-ac'), go('mm-a'), function(c){ MM_A_CODE=c; }); bindAC(go('mm-b-ac'), go('mm-b'), function(c){ MM_B_CODE=c; }); document.addEventListener('click', function(e){ if(!e.target.closest('.ac-wrap')){ var _ds=document.querySelectorAll('.ac-drop'); for(var _i=0;_i<_ds.length;_i++) _ds[_i].style.display='none'; } });
setTimeout(function(){ try{ var p=new URLSearchParams(location.search); var f=p.get('from'), t=p.get('to'); if(t){ var et2=go('ex-to'); if(et2) et2.value=((typeof NAMES!=='undefined'&&NAMES[t])?NAMES[t]:t); EX_TO_CODE=(''+t).toUpperCase(); EX_TRIP=(p.get('trip')==='round')?'round':'oneway'; var fc=''; if(f){ fc=(/^[A-Za-z]{3}$/.test(f))?f.toUpperCase():resolveTo(f); } EX_ORIG=(/^[A-Z]{3}$/.test(fc))?[fc]:['JFK','LAX','ORD','DFW','MIA','SFO']; renderOrigs(); if(window.exSetTrip)exSetTrip(EX_TRIP); if(window.exTab)exTab('explore'); if(window.exSearch)exSearch(); } }catch(e){} }, 0);
window.exTab=function(m){ go('ex-tab-explore').style.display=(m==='explore')?'':'none'; var _ar=go('ex-tab-air'); if(_ar) _ar.style.display=(m==='air')?'':'none'; var _fv=go('ex-tab-fav'); if(_fv) _fv.style.display=(m==='fav')?'':'none'; var _mt=go('ex-tab-meet'); if(_mt) _mt.style.display=(m==='meet')?'':'none'; go('ex-tab-explore-btn').classList.toggle('on',m==='explore'); var _ab=go('ex-tab-air-btn'); if(_ab) _ab.classList.toggle('on',m==='air'); var _fb=go('ex-tab-fav-btn'); if(_fb) _fb.classList.toggle('on',m==='fav'); var _mb=go('ex-tab-meet-btn'); if(_mb) _mb.classList.toggle('on',m==='meet'); if(m==='fav'&&window.exFavRender) window.exFavRender(); if(m==='air'){ if(window.renderCities) window.renderCities(); if(window.renderAirportWatch) window.renderAirportWatch(); } };
var MM_A_CODE='', MM_B_CODE='', MM_TRIP='round', MM_REG='all', MM_ROWS=[], MM_A='', MM_B='', MM_UNIT='round-trip';
window.mmAAC=function(){ MM_A_CODE=''; airportFilter(go('mm-a'), go('mm-a-ac')); };
window.mmBAC=function(){ MM_B_CODE=''; airportFilter(go('mm-b'), go('mm-b-ac')); };
window.mmTrip=function(t){ MM_TRIP=t; go('mm-rt').classList.toggle('on',t==='round'); go('mm-ow').classList.toggle('on',t==='oneway'); };
function mmInReg(code, r){ if(r==='all') return true; var t=tagsFor(code); function has(x){ return t.indexOf(x)>=0; } if(r==='Europe') return has('W Europe')||has('E Europe')||has('Nordic'); if(r==='Asia') return has('Asia')||has('SE Asia')||has('E Asia')||has('S Asia')||has('C Asia'); if(r==='Africa') return has('Africa'); if(r==='Americas') return has('S America')||has('C America')||has('Caribbean')||has('Canada')||has('USA'); if(r==='Middle East') return has('Middle East'); if(r==='Oceania') return has('Oceania'); return true; }
function mmRender(){ var out=go('mm-out'); var rb=go('mm-regions'); if(rb) rb.style.display=MM_ROWS.length?'flex':'none'; if(!MM_ROWS.length){ return; } var rows=MM_ROWS.filter(function(r){ return mmInReg(r.d, MM_REG); }); if(!rows.length){ out.innerHTML='<div class="wl-hint">No cheap meetups in '+MM_REG+' for '+MM_A+' and '+MM_B+' right now. Try Anywhere or another region.</div>'; return; } out.innerHTML=rows.slice(0,24).map(function(r,i){ var nm=(typeof NAMES!=='undefined'&&NAMES[r.d])?NAMES[r.d]:r.d; return '<div class="mm-card"'+(i===0?' data-best="1"':'')+'><div class="mm-head">'+owFlag(r.d)+'<div><div class="mm-city">'+nm+(i===0?' <span class="mm-badge">cheapest meetup</span>':'')+'</div><div class="mm-tot">$'+Math.round(r.total).toLocaleString()+' <span>combined &middot; '+MM_UNIT+'</span></div></div></div><div class="mm-legs"><a class="mm-leg" href="'+r.a.link+'" target="_blank" rel="noopener"><span class="mm-who">You</span><span class="mm-from">'+MM_A+' &rarr; '+r.d+'</span><span class="mm-price">$'+Math.round(r.a.price).toLocaleString()+'</span></a><a class="mm-leg" href="'+r.b.link+'" target="_blank" rel="noopener"><span class="mm-who">Them</span><span class="mm-from">'+MM_B+' &rarr; '+r.d+'</span><span class="mm-price">$'+Math.round(r.b.price).toLocaleString()+'</span></a></div></div>'; }).join(''); }
window.mmReg=function(r){ MM_REG=r; var cs=document.querySelectorAll('#mm-regions [data-mmr]'); for(var k=0;k<cs.length;k++){ cs[k].classList.toggle('on',cs[k].getAttribute('data-mmr')===r); } mmRender(); };
window.mmSearch=function(){ var ar=(go('mm-a').value||'').trim(), br=(go('mm-b').value||'').trim(); var a=MM_A_CODE||(/^[A-Za-z]{3}$/.test(ar)?ar.toUpperCase():resolveTo(ar)); var b=MM_B_CODE||(/^[A-Za-z]{3}$/.test(br)?br.toUpperCase():resolveTo(br)); var out=go('mm-out'); if(!/^[A-Z]{3}$/.test(a)){ out.innerHTML='<div class="wl-hint">Enter <b>your</b> home city or airport (e.g. New York or JFK).</div>'; return; } if(!/^[A-Z]{3}$/.test(b)){ out.innerHTML='<div class="wl-hint">Enter <b>their</b> home city or airport (e.g. Bangkok or BKK).</div>'; return; } if(a===b){ out.innerHTML='<div class="wl-hint">You&rsquo;re both in the same city already! Pick two different airports.</div>'; return; } MM_A=a; MM_B=b; MM_UNIT=(MM_TRIP==='oneway'?'one-way':'round-trip'); var ow=(MM_TRIP==='oneway'?'true':'false'); out.innerHTML='<div class="wl-hint">Finding the cheapest places for '+a+' and '+b+' to meet&hellip;</div>'; function grab(o){ return fetch('/api/search?origin='+o+'&one_way='+ow+'&sorting=price&limit=600').then(function(r){return r.json();}).then(function(j){ return (j&&j.data)||[]; }).catch(function(){ return []; }); } Promise.all([grab(a),grab(b)]).then(function(res){ var A={},B={}; res[0].forEach(function(f){ var d=f.destination_airport; if(!d||d===a||d===b) return; if(!A[d]||f.price<A[d].price) A[d]=f; }); res[1].forEach(function(f){ var d=f.destination_airport; if(!d||d===a||d===b) return; if(!B[d]||f.price<B[d].price) B[d]=f; }); var rows=[]; for(var d in A){ if(B[d]) rows.push({d:d,a:A[d],b:B[d],total:A[d].price+B[d].price}); } rows.sort(function(x,y){ return x.total-y.total; }); if(!rows.length){ MM_ROWS=[]; var rb=go('mm-regions'); if(rb) rb.style.display='none'; out.innerHTML='<div class="wl-hint">Not enough overlapping fares for '+a+' and '+b+' yet. Try two major hubs (JFK, LAX, LHR, BKK, DXB&hellip;).</div>'; return; } MM_ROWS=rows; mmRender(); }); };
})();
</script>"""
    return _html.replace("__AIRPORT_TAB_CARD__", _air_card)


def body_lastminute(lm):
    return f"""<div class="wrap">
  <div class="pagehead"><h1><svg class="hicon" viewBox="0 0 24 24" fill="none" stroke="#2f6b46" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7.2v5l3.2 2"/></svg> Last-minute one-ways</h1><p>Cheapest one-way fares leaving soon, from anywhere in the USA. Filter by region &mdash; tap one or several (USA for domestic).</p></div>
  <div class="airchips" style="margin:6px 0 16px;">{region_chip_bar("data-lmr", "toggleLMR")}</div>
  <div class="panel"><div id="lmlist"></div></div>
</div>"""


def body_airports(home):
    return f"""<div class="wrap">
  <div class="pagehead" id="airports"><h1>Cheap Flights From Your Home Airport</h1><p>Your home airports and tracked fares &mdash; a captain&rsquo;s log of raw data: coordinates, prices and deviations. Set your home airport to see the cheapest trips leaving from your city. Saved in this browser.</p></div>
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
    <button class="airchip on" data-actrip="rt" onclick="setACTrip('rt')">Round-trip</button>
    <button class="airchip" data-actrip="ow" onclick="setACTrip('ow')">One-way</button>
  </div>
  <div class="airchips" style="margin:0 0 14px;">{region_chip_bar("data-acr", "toggleACR")}</div>
  <div class="panel"><div id="citydeals"></div>
    <div class="wl-hint" id="city-hint">Add your home airport (e.g. Raleigh &mdash; RDU) to see the cheapest trips leaving from your city.</div></div>
</div>"""


def body_ask():
    return rf"""<div class="wrap" style="max-width:760px">
  <div class="pagehead"><h1>Ask Magellan</h1><p>Ask about our tracked one-way deals &mdash; what&rsquo;s below normal right now, deals to a region, or how the fare market looks. Answers come only from {BRAND}&rsquo;s live-tracked data &mdash; no made-up prices.</p></div>
  <div class="signup" style="margin:0 0 18px"><div class="signup-inner">
    <form onsubmit="return askSub(event)" style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center;max-width:560px;margin:0 auto">
      <input id="ask-q" type="text" required autocomplete="off" placeholder="e.g. Where can I fly cheap right now?" style="flex:1;min-width:240px;background:#fffdf6;color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:15px">
      <button class="book" type="submit" style="font-size:16px;padding:12px 26px">Ask &rarr;</button>
    </form>
    <div style="text-align:center;margin-top:10px;display:flex;gap:6px;flex-wrap:wrap;justify-content:center">
      <button type="button" class="btn-ghost" onclick="askEx('What are the best flight deals right now?')" style="font-size:12.5px;padding:6px 12px">Best deals now</button>
      <button type="button" class="btn-ghost" onclick="askEx('Which region is cheapest to fly to right now?')" style="font-size:12.5px;padding:6px 12px">Cheapest region</button>
      <button type="button" class="btn-ghost" onclick="askEx('Any cheap deals to Africa?')" style="font-size:12.5px;padding:6px 12px">Deals to Africa</button>
    </div>
  </div></div>
  <div id="ask-out"></div>
  <p class="finehint" style="text-align:center;margin-top:14px">Prices are the freshest fares we&rsquo;ve tracked, confirmed live on Aviasales. Magellan is one-way-led.</p>
  <script>
  function askEx(q){{var i=document.getElementById('ask-q');i.value=q;askSub(new Event('submit'));}}
  function askEsc(s){{return String(s).replace(/[&<>"]/g,function(c){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c];}});}}
  function askFmt(s){{return askEsc(s).replace(/https?:\/\/[^\s<]+/g,function(u){{return '<a href="'+u+'" target="_blank" rel="noopener nofollow sponsored" style="color:var(--gold);font-weight:600">Book on Aviasales &rarr;</a>';}}).replace(/\n/g,'<br>');}}
  function askSub(e){{if(e&&e.preventDefault)e.preventDefault();var q=(document.getElementById('ask-q').value||'').trim();if(!q)return false;var out=document.getElementById('ask-out');out.innerHTML='<div class="wl-hint">Thinking&hellip;</div>';fetch('/api/ask',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{question:q}})}}).then(function(r){{return r.json().catch(function(){{return{{}};}}).then(function(d){{return{{ok:r.ok,d:d}};}});}}).then(function(res){{if(!res.ok||!res.d||!res.d.ok){{out.innerHTML='<div class="wl-hint">'+askEsc((res.d&&res.d.error)||'Something went wrong &mdash; try again in a moment.')+'</div>';return;}}out.innerHTML='<div class="panel" style="padding:20px;line-height:1.6">'+askFmt(res.d.answer||'')+'</div>';}}).catch(function(){{out.innerHTML='<div class="wl-hint">Network error &mdash; please try again.</div>';}});return false;}}
  </script>
</div>"""


def body_essentials():
    return f"""<div class="wrap">
  <div class="pagehead"><h1>Travel essentials</h1><p>Everything else you need for the trip — hotels, data, insurance and more. Every booking supports {BRAND} at no extra cost to you.</p></div>
  <div class="grid">{essentials_cards()}</div>
  <div class="summary" style="margin-top:24px">Tip: the cheapest flight is just step one — booking your hotel, eSIM and activities here in one place keeps the whole trip organized.</div>
</div>"""


# Travel-card recommendations. The biggest revenue lever in flight media is the
# credit-card affiliate (up to ~$200 per approved card vs ~1% on a flight). This
# page is intentionally HONEST and GENERIC — it earns trust, not clicks. OWNER TODO:
# after you join a card-affiliate program (e.g. via a network), replace each card's
# "name" with the real product and set "href" to YOUR affiliate link. Keep it general
# information, not personalized financial advice.
TRAVEL_CARDS = [
    {"tag": "Best all-rounder", "name": "A flexible travel-rewards card",
     "good": "Earns transferable points on flights &amp; dining that move to airline partners, plus a large sign-up bonus that can cover a one-way or two.",
     "watch": "Has an annual fee — worth it only if you take a few trips a year.", "href": "#"},
    {"tag": "Best for beginners", "name": "A no-annual-fee starter card",
     "good": "No annual fee and simple flat rewards on travel — a safe first travel card while you learn the game.",
     "watch": "Smaller bonus and lower earn rate than premium cards.", "href": "#"},
    {"tag": "Best for international one-ways", "name": "A no-foreign-transaction-fee card",
     "good": "Skips the typical 3% foreign-transaction fee abroad — pairs perfectly with the cheap international one-ways we track.",
     "watch": "Check the annual fee and how it handles the exchange rate.", "href": "#"},
    {"tag": "Best for loyalists", "name": "An airline co-brand card",
     "good": "Free checked bag, priority boarding and bonus miles on the one airline you fly most.",
     "watch": "Miles are locked to that airline — less flexible than transferable points.", "href": "#"},
]


def travel_card_html(c):
    live = c["href"] and c["href"] != "#"
    btn = (f'<a class="book" href="{c["href"]}" target="_blank" rel="noopener sponsored" style="margin-top:14px;display:inline-block">See the card &amp; apply &rarr;</a>'
           if live else '<span class="cp-soon" style="margin-top:14px;display:inline-block;color:var(--muted);font-size:13px">Pick coming soon</span>')
    return (f'<div class="why-card"><span class="eyebrow" style="color:var(--green)">{c["tag"]}</span>'
            f'<h3 style="margin:6px 0 8px">{c["name"]}</h3>'
            f'<p style="margin:0 0 8px"><b style="color:var(--green)">Good for:</b> {c["good"]}</p>'
            f'<p style="margin:0;color:var(--muted)"><b>The catch:</b> {c["watch"]}</p>{btn}</div>')


def body_cards():
    cards = "".join(travel_card_html(c) for c in TRAVEL_CARDS)
    return f"""<div class="wrap" style="max-width:820px">
  <div class="pagehead"><h1>Travel cards, honestly</h1>
  <p>The right travel card can pay for a one-way flight or two with a single sign-up bonus — it&rsquo;s genuinely the biggest money-saver most deal-hunters ignore. So here&rsquo;s an honest, no-hype guide to the kinds of cards worth it, who each suits, and the catch.</p></div>

  <div class="summary" style="margin:0 0 22px"><b>Our promise:</b> we only list cards we&rsquo;d actually use, and we always tell you the catch. We may earn a referral if you&rsquo;re approved through our links &mdash; at no extra cost to you. This is general information, <b>not personalized financial advice</b>; always check each card&rsquo;s current terms and whether it fits your situation.</div>

  <div class="blog-sec"><h2>How a travel card pays for the flight</h2>
  <p>A flight booking earns an affiliate site about 1% of the fare. A travel card&rsquo;s sign-up bonus is often worth <b>hundreds of dollars in flights</b> — which is exactly why every honest deal site you trust funds itself this way. Used responsibly (pay it off monthly, never carry a balance), one bonus can cover several of the below-normal one-ways we track.</p></div>

  <div class="why-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin:8px 0 6px">{cards}</div>

  <div class="blog-sec" style="margin-top:22px"><h2>How to choose in 30 seconds</h2>
  <ul class="blog-list">
    <li><b>Travel a few times a year?</b> A flexible travel-rewards card&rsquo;s bonus usually beats its fee.</li>
    <li><b>New to this?</b> Start with a no-annual-fee card and keep it simple.</li>
    <li><b>Flying international one-ways?</b> Make sure it has no foreign-transaction fee.</li>
    <li><b>Loyal to one airline?</b> The co-brand card&rsquo;s perks (bag, boarding) can pay for themselves.</li>
    <li><b>Carrying a balance?</b> Skip rewards cards entirely — interest dwarfs any bonus.</li>
  </ul></div>

  <div class="signup" style="margin-top:24px"><div class="signup-inner">
    <h2>Get the deals to use it on</h2>
    <p>The weekly briefing sends the biggest below-normal one-ways from the USA — the perfect place to spend that sign-up bonus.</p>
    <a class="book" href="newsletter.html" style="display:inline-block;font-size:16px;padding:12px 28px;margin-top:6px">Get the free weekly briefing &rarr;</a>
  </div></div>
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
        "slug": "flight-deal-guide",
        "title": "The Flight Deal Guide: How to Book a Cheap Fare | Magellan Flights",
        "h1": "The Flight Deal Guide",
        "description": "A short, honest playbook for turning a cheap fare into a booked "
                       "trip: how to tell a real deal from a big number, and how to act "
                       "before the seat is gone.",
        "primary": "how to book a flight deal",
        "secondary": ["how to find flight deals", "how to know if a flight is a good deal",
                      "how to book cheap flights fast", "are cheap flight deals real"],
        "kicker": "Deal playbook",
        "published": "2026-07-12", "updated": "2026-07-12", "read_min": 4,
        "money_href": "market.html", "money_label": "today's cheapest flight deals",
        "lede": "A cheap fare is only the start. The real skill is telling a genuine deal "
                "from a big round number, and then moving before the seat is gone. This is "
                "the short playbook we use on every fare on the board, so you can do the "
                "same in a few minutes.",
        "quick_answer": "Judge a fare against its normal price, not the sticker. If it is "
                        "genuinely below normal and you would fly it, book it fast, because "
                        "the cheapest one-ways are often just a few seats. Stay flexible on "
                        "dates and airport, book the flight before the rest of the trip, and "
                        "always confirm the live price on Aviasales before you pay.",
        "sections": [
            ("Judge it against normal, not the sticker",
             "<p>A price on its own tells you almost nothing. $600 to Tokyo can be a steal "
             "or a rip-off depending on what that route usually costs. The only number that "
             "matters is how a fare compares to its own history.</p>"
             "<p>That is the whole idea behind the <a href='market.html'>deal board</a>: "
             "every fare is judged against its normal price, so you can see at a glance how "
             "far below normal it sits. A deal is a fare that has actually dropped, not just "
             "a big number.</p>"),
            ("If you would really fly it, book it fast",
             "<p>The cheapest one-ways are often a handful of seats at that price. Once they "
             "sell, the fare jumps back to normal. A genuine drop rarely waits for the "
             "weekend.</p>"
             "<p>So the test is simple: if it is a trip you would actually take, treat the "
             "seat like it is already gone and book it. Hesitating is the most common way "
             "people watch a real deal disappear.</p>"),
            ("Stay flexible on dates and airport",
             "<p>Flexibility is the cheapest upgrade you have. Shifting your departure by a "
             "day, or leaving from a nearby airport, is usually where the savings hide.</p>"
             "<ul class='blog-list'>"
             "<li>Check a day earlier and a day later before you settle on a date.</li>"
             "<li>Look at nearby hubs. A cheap flight to a big airport plus a short hop can "
             "beat a direct fare.</li>"
             "<li>Midweek departures (Tuesday, Wednesday) are usually cheaper than Friday "
             "or Sunday.</li></ul>"),
            ("Book the flight first, plan the rest after",
             "<p>The cheap one-way out is the hard part, and the thing most likely to "
             "vanish. Lock that in first. The return, the hotel, and the eSIM can all wait "
             "until you know the trip is on.</p>"
             "<p>Reversing that order, planning the whole trip before you book, is how "
             "people talk themselves out of a fare that was there the day before.</p>"),
            ("Confirm the live price before you pay",
             "<p>We show the freshest fare we have tracked, but prices move all day as seats "
             "sell. Your real, bookable price is always the one you see at checkout on the "
             "airline or on <a href='market.html'>Aviasales</a>.</p>"
             "<p>Click through, confirm the price and the dates match, then book. If it has "
             "moved a little, the same flexibility rules apply: a nearby date or airport "
             "often gets you back to the number you wanted.</p>"),
        ],
        "faqs": [
            ("How do I know if a flight is actually a good deal?",
             "Compare it to the route's normal price, not to a number in your head. A fare "
             "is a good deal when it has dropped below what that route usually costs. A "
             "tracker that shows each route's normal price makes this obvious at a glance."),
            ("Are cheap flight deals real, or a bait and switch?",
             "Real deals exist, but you have to confirm the live price before you pay. The "
             "fare in a deal list is the freshest price tracked; the bookable price is the "
             "one at checkout on the airline or Aviasales. Always verify there."),
            ("How fast do I need to book a flight deal?",
             "Fast. The cheapest fares are often only a few seats, and they can sell out "
             "within hours. If it is a trip you would take, book it rather than waiting for "
             "a better moment."),
            ("Should I book the flight or plan the trip first?",
             "Book the flight first. The cheap one-way is the scarce part and the most "
             "likely to disappear. You can add the return, hotel, and other bookings once "
             "the seat is locked in."),
        ],
    },
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
        "quick_answer": "The cheapest day to <i>book</i> a flight is usually Tuesday or "
                        "Wednesday, and the cheapest days to <i>fly</i> are Tuesday, Wednesday "
                        "and Saturday. But the bigger lever is your booking window: about "
                        "1&ndash;3 months ahead for domestic trips and 2&ndash;8 months for "
                        "international. Booking inside that window beats any &ldquo;magic "
                        "weekday.&rdquo;",
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
             "sometimes catch a fresh, slightly lower price. Large studies of airfare data "
             "&mdash; the kind the U.S. <a href=\"https://www.bts.gov/\" target=\"_blank\" "
             "rel=\"noopener\">Bureau of Transportation Statistics</a> publishes &mdash; keep "
             "landing in the same place: booking Tuesday or Wednesday saves a little versus a "
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
             "<a href='market.html'>international deal board</a> to see them move in real time. "
             "And if a booked fare changes on you, the U.S. DOT&rsquo;s "
             "<a href=\"https://www.transportation.gov/airconsumer\" target=\"_blank\" "
             "rel=\"noopener\">aviation consumer protection</a> office sets the rules on "
             "refunds and major schedule changes.</p>"),
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
    {
        "slug": "when-to-book-international-flights",
        "title": "When to Book International Flights for the Lowest Fare | Magellan Flights",
        "h1": "When to book international flights",
        "description": "Book international flights too early and you overpay; too late and "
                       "prices spike. The sweet spot is wider than you think — here's "
                       "exactly when to buy.",
        "primary": "best time to book international flights",
        "secondary": ["when to book flights to europe", "how far in advance to book international flights",
                      "best time to buy international plane tickets", "how many months ahead to book international flights"],
        "kicker": "Booking timing",
        "published": "2026-06-22", "updated": "2026-06-22", "read_min": 6,
        "money_href": "market.html", "money_label": "today's cheapest international fares",
        "lede": "Book an international flight too early and you overpay for the airline's peace of "
                "mind. Too late and you're funding their next jet. The good news: the sweet spot is "
                "wider than the internet makes it sound — here's where it actually sits, and how "
                "to land inside it.",
        "quick_answer": "Book most international flights about <b>2 to 8 months ahead</b>. For peak "
                        "summer and the winter holidays, aim earlier (5&ndash;8 months); for "
                        "off-peak trips, 2&ndash;4 months is plenty. The danger zone is the final "
                        "three weeks, when the cheap fare buckets are usually gone.",
        "sections": [
            ("The short answer",
             "<p>For international flights from the USA, the cheapest window is roughly "
             "<b>two to eight months before departure</b>. Where you land inside that window "
             "depends on demand:</p>"
             "<ul class='blog-list'>"
             "<li><b>Peak (summer, Christmas/New Year):</b> book 5&ndash;8 months out.</li>"
             "<li><b>Shoulder and off-peak:</b> 2&ndash;4 months is usually enough.</li>"
             "<li><b>Inside ~3 weeks:</b> the danger zone — prices climb fast.</li></ul>"),
            ("Why “as early as possible” is wrong",
             "<p>Airlines load seats for sale around 11 months out, but they open them at high "
             "introductory prices, betting eager planners will pay. Those fares usually drift "
             "<i>down</i> into the sweet spot before climbing again near departure. Booking the day "
             "the calendar opens often means overpaying for the privilege of being early.</p>"
             "<p>The exception is genuinely scarce travel — a tiny route, a festival week, peak "
             "holiday dates — where seats sell out and waiting backfires. When in doubt about a "
             "high-demand date, lean earlier.</p>"),
            ("The window shifts by season and destination",
             "<p>Summer in Western Europe and the winter holidays everywhere are the two big "
             "premium periods — treat those as “book early.” Shoulder seasons (spring "
             "and fall) give you more room to wait. And don't forget the un-sexy logistics: if your "
             "passport is expiring, the U.S. State Department's "
             "<a href='https://travel.state.gov/content/travel/en/passports.html' target='_blank' "
             "rel='noopener'>passport service</a> can take weeks, so sort that before you book a "
             "non-refundable international ticket.</p>"),
            ("What our live fares show",
             "<p>We track <b>{LIVE_ROUTES} routes</b> from the USA and log the price daily, so we "
             "can see each route's <i>normal</i> range — the only way to know whether today's "
             "international fare is actually a deal or just a number. Right now the standout on the "
             "board is <b>{LIVE_TOPCITY}</b>, about <b>{LIVE_TOPPCT}% below</b> its usual price. "
             "Watch international routes move in real time on our "
             "<a href='market.html'>deal board</a>.</p>"),
            ("A simple plan to book at the low",
             "<ul class='blog-list'>"
             "<li><b>Start watching early</b> — around 8 months out for peak trips, 4 for off-peak.</li>"
             "<li><b>Track the normal price</b> so you recognize a real dip instead of guessing.</li>"
             "<li><b>Be flexible by a few days</b> — mid-week and shoulder dates are cheaper.</li>"
             "<li><b>Book when it drops below normal</b>, and make sure your passport is valid "
             "(check the "
             "<a href='https://www.transportation.gov/airconsumer' target='_blank' rel='noopener'>"
             "DOT's consumer protection</a> page for your rights if a schedule changes after you book).</li></ul>"),
        ],
        "faqs": [
            ("How many months ahead should I book an international flight?",
             "About 2 to 8 months ahead for most trips. Lean toward 5-8 months for peak summer "
             "and the winter holidays, and 2-4 months for off-peak travel."),
            ("When should I book flights to Europe?",
             "For summer travel, book 5-6 months ahead. For spring, fall, or winter trips, 2-4 "
             "months is usually enough to catch a good fare."),
            ("Is it cheaper to book international flights far in advance?",
             "Only up to a point. Very early fares are often high introductory prices. The cheapest "
             "fares usually appear in the 2-8 month window, not the moment seats go on sale."),
            ("Does the day of the week matter for international flights?",
             "A little — mid-week departures are usually cheaper than weekends — but your "
             "booking window matters far more than which day you buy."),
        ],
    },
    {
        "slug": "cheapest-time-to-fly-to-europe",
        "title": "The Cheapest Time to Fly to Europe From the USA | Magellan Flights",
        "h1": "The cheapest time to fly to Europe",
        "description": "The cheapest time to fly to Europe from the USA is the off-season — "
                       "roughly mid-January to March and November to mid-December. Here's how to "
                       "save the most.",
        "primary": "cheapest time to fly to europe",
        "secondary": ["cheapest month to fly to europe", "when is the cheapest time to visit europe",
                      "cheapest time to fly to europe from usa", "off season travel to europe"],
        "kicker": "Where & when",
        "published": "2026-06-22", "updated": "2026-06-22", "read_min": 6,
        "money_href": "market.html", "money_label": "today's cheapest fares to Europe",
        "lede": "Europe in summer is gorgeous, crowded, and brutally overpriced to fly to. The "
                "secret most travelers miss: the exact same cities cost a fraction in the months "
                "just before and after — with shorter lines and better hotel rates thrown in. "
                "Here's when to go.",
        "quick_answer": "The cheapest time to fly to Europe from the USA is the off-season: roughly "
                        "<b>mid-January through March</b> and <b>November through mid-December</b> "
                        "(skip the holidays themselves). Summer (June&ndash;August) is the most "
                        "expensive. The <b>shoulder months</b> — April/May and September/October "
                        "— are the sweet spot: lower fares, great weather.",
        "sections": [
            ("The cheapest months, ranked",
             "<p>Roughly cheapest to priciest for transatlantic fares:</p>"
             "<ul class='blog-list'>"
             "<li><b>Cheapest:</b> mid-January, February, early March, and November to mid-December.</li>"
             "<li><b>Sweet spot (value + weather):</b> April, May, late September, October.</li>"
             "<li><b>Most expensive:</b> June, July, August, and the Christmas/New Year window.</li></ul>"
             "<p>Flying in February instead of July can cut a transatlantic round-trip by hundreds "
             "of dollars on the same route. The U.S. "
             "<a href='https://www.bts.gov/' target='_blank' rel='noopener'>Bureau of Transportation "
             "Statistics</a> tracks average international airfares if you want a route's ballpark.</p>"),
            ("Shoulder season is the real sweet spot",
             "<p>If winter feels too cold, the shoulder months are where savvy travelers live. "
             "Late April through May and September into October give you mild weather, thinner "
             "crowds at the big sights, and fares well below the summer peak. You get most of the "
             "summer experience for off-season money.</p>"),
            ("It varies by city",
             "<p>Southern Europe (Spain, Italy, Greece) stays warmer later, so its shoulder deals "
             "stretch into October and November. Northern Europe (London, Amsterdam, the Nordics) "
             "goes cheap earlier as the weather turns. Either way, check entry requirements for "
             "your passport on the State Department's "
             "<a href='https://travel.state.gov/content/travel/en/international-travel.html' "
             "target='_blank' rel='noopener'>international travel</a> pages before you commit.</p>"),
            ("What our live fares show",
             "<p>We track the cheapest fares from the USA to Europe every day across "
             "<b>{LIVE_ROUTES} routes</b>, so you can see the off-season dip happen in real time "
             "rather than taking our word for it. The cheapest “month” is really the day a "
             "specific route drops below its normal range — watch for it on our "
             "<a href='market.html'>live board</a> and book when it does.</p>"),
            ("How to lock in the lowest Europe fare",
             "<ul class='blog-list'>"
             "<li><b>Travel off-peak or shoulder</b> — the single biggest lever.</li>"
             "<li><b>Stay flexible on the city</b> — fly into the cheapest European hub and take "
             "a cheap train or budget flight onward.</li>"
             "<li><b>Book in the 2&ndash;5 month window</b> for off-peak Europe trips.</li>"
             "<li><b>Track the route</b> so you recognize a genuine drop.</li></ul>"),
        ],
        "faqs": [
            ("What is the cheapest month to fly to Europe?",
             "February is typically the cheapest, with January, early March, and November close "
             "behind. Summer months are the most expensive."),
            ("Is it cheaper to fly to Europe in winter?",
             "Yes — outside the Christmas/New Year holidays, winter (January to early March) "
             "has some of the lowest transatlantic fares of the year."),
            ("When is the cheapest time to visit Europe excluding the holidays?",
             "Mid-January through March and November to mid-December. These off-season weeks avoid "
             "both the summer peak and the holiday spike."),
            ("How much can you save flying to Europe off-season?",
             "Often hundreds of dollars round-trip versus summer on the same route, plus cheaper "
             "hotels and far smaller crowds."),
        ],
    },
    {
        "slug": "are-last-minute-flights-cheaper",
        "title": "Are Last-Minute Flights Cheaper? What the Data Says | Magellan Flights",
        "h1": "Are last-minute flights cheaper?",
        "description": "Usually no — last-minute flights are typically more expensive, not "
                       "cheaper. But there are specific cases where waiting pays off. Here's the "
                       "honest answer.",
        "primary": "are last minute flights cheaper",
        "secondary": ["how to get cheap last minute flights", "when do last minute flights get cheaper",
                      "do flight prices drop closer to departure", "cheap last minute flight tips"],
        "kicker": "Myth check",
        "published": "2026-06-22", "updated": "2026-06-22", "read_min": 5,
        "money_href": "explore.html", "money_label": "the cheapest one-ways from your airport",
        "lede": "There's a stubborn myth that airlines slash prices at the last second to fill empty "
                "seats. Mostly, the opposite is true — and believing it can cost you real money. "
                "But there's a real exception worth knowing. Here's the honest version.",
        "quick_answer": "Usually <b>not</b>. For most routes, last-minute flights are <i>more</i> "
                        "expensive — airlines know late buyers (often business travelers) will "
                        "pay up, so prices typically climb in the final two weeks. The exception: "
                        "off-peak leisure routes with empty seats, where genuine last-minute deals "
                        "occasionally appear.",
        "sections": [
            ("The short answer",
             "<p>For the vast majority of trips, waiting until the last minute costs you more, not "
             "less. Prices usually rise sharply inside the final two weeks. The cheap last-minute "
             "flight is the exception, not the rule — and you have to know where to look.</p>"),
            ("Why prices usually rise, not fall",
             "<p>Airlines sell seats in price tiers (“fare buckets”). The cheap buckets sell "
             "first, so as a flight fills, only pricier seats remain. On top of that, the people "
             "still booking a week out are disproportionately business travelers on expense accounts "
             "— exactly the customer airlines charge the most. Dropping prices for them would "
             "leave money on the table, so they don't.</p>"),
            ("When last-minute <i>can</i> be cheap",
             "<p>The myth isn't completely empty. Genuine last-minute deals show up when:</p>"
             "<ul class='blog-list'>"
             "<li>It's an <b>off-peak leisure route</b> the airline is struggling to fill.</li>"
             "<li>There's <b>overcapacity</b> — too many seats chasing too few travelers.</li>"
             "<li>You're <b>flexible</b> on destination and can pounce on whatever drops.</li></ul>"
             "<p>That's exactly what our <a href='market.html'>flight market</a> surfaces "
             "— the routes trading below their normal price right now, from your airport.</p>"),
            ("How to play it if you must book late",
             "<ul class='blog-list'>"
             "<li><b>Be flexible on dates and airports</b> — flexibility is your only leverage late.</li>"
             "<li><b>Watch a fare feed or set price alerts</b> instead of searching one route over and over.</li>"
             "<li><b>Fly mid-week</b> — Tuesday and Wednesday departures stay cheaper even late.</li>"
             "<li><b>Know your rights</b> if a flight is cancelled or changed — see the "
             "<a href='https://www.transportation.gov/airconsumer' target='_blank' rel='noopener'>"
             "DOT's aviation consumer protection</a> office.</li></ul>"),
            ("What our data shows",
             "<p>Across the <b>{LIVE_ROUTES} routes</b> we track — and in the national fare data the "
             "U.S. <a href='https://www.bts.gov/' target='_blank' rel='noopener'>Bureau of "
             "Transportation Statistics</a> publishes — the cheapest fares almost always "
             "belong to trips booked in the normal window, not the final scramble. When a real "
             "last-minute bargain does appear, it's because a specific route dropped below its "
             "normal range — which is the moment our tracker flags it.</p>"),
        ],
        "faqs": [
            ("Do flight prices drop closer to departure?",
             "Usually they rise, not drop. Cheap fare tiers sell out and late demand skews toward "
             "business travelers who pay more. Genuine last-minute drops are the exception."),
            ("When do last-minute flights get cheaper?",
             "Mainly on off-peak leisure routes with unsold seats. If a flight is undersold close to "
             "departure, an airline may release cheaper fares — but it's not reliable."),
            ("What is the cheapest day to book a last-minute flight?",
             "There's no magic day this late. Flexibility on your travel dates and airports matters "
             "far more than the day you buy."),
            ("Are same-day flights cheaper?",
             "Rarely. Same-day fares are typically among the most expensive, aimed at travelers who "
             "have no choice but to fly now."),
        ],
    },
    {
        "slug": "how-to-find-cheap-flights",
        "title": "How to Find Cheap Flights: 9 Tricks That Work | Magellan Flights",
        "h1": "How to find cheap flights",
        "description": "Nine tricks that actually work for finding cheap flights — the right "
                       "booking window, flexible dates, fare alerts, and spotting fares below their "
                       "normal price.",
        "primary": "how to find cheap flights",
        "secondary": ["how to get cheap flight tickets", "tricks to find cheap flights",
                      "how to search for cheap flights", "how to find cheap flights to anywhere"],
        "kicker": "How-to",
        "published": "2026-06-22", "updated": "2026-06-22", "read_min": 7,
        "money_href": "index.html", "money_label": "today's cheapest fares",
        "lede": "Finding cheap flights isn't luck and it isn't a secret “hack” — it's a "
                "handful of habits that stack up. Do these nine things and you'll pay less than the "
                "person in the next seat almost every time. The biggest one? Knowing what a fare is "
                "<i>supposed</i> to cost.",
        "quick_answer": "To find cheap flights: book in the sweet spot (<b>1&ndash;3 months</b> "
                        "domestic, <b>2&ndash;8 months</b> international), stay flexible on dates and "
                        "airports, fly mid-week, use a fare tracker so you recognize a real drop, and "
                        "act fast when a fare falls below its normal range. Knowing the normal price "
                        "is the biggest lever.",
        "sections": [
            ("9 tricks that actually work",
             "<ol class='blog-list'>"
             "<li><b>Book in the sweet spot</b> — 1&ndash;3 months ahead for domestic, "
             "2&ndash;8 for international. Too early or too late both cost more.</li>"
             "<li><b>Know the normal price.</b> You can't spot a deal without a baseline. Track a "
             "route so you know whether today's fare is genuinely low.</li>"
             "<li><b>Be flexible on dates.</b> Shifting a day or two — especially to Tuesday, "
             "Wednesday, or Saturday — often beats every other trick.</li>"
             "<li><b>Be flexible on airports.</b> A nearby airport, or a cheap hub plus an onward "
             "budget flight, can slash the total.</li>"
             "<li><b>Fly the cheap season.</b> Off-peak and shoulder months are dramatically cheaper "
             "for the same destination.</li>"
             "<li><b>Set fare alerts.</b> Let the price come to you instead of refreshing searches.</li>"
             "<li><b>Consider two one-ways.</b> Mixing airlines on a one-way each direction is "
             "sometimes cheaper than a single round-trip.</li>"
             "<li><b>Search anywhere.</b> If you're flexible on <i>where</i>, let the cheapest "
             "destination pick itself.</li>"
             "<li><b>Act fast on real drops.</b> The best fares vanish in hours — when one falls "
             "below its normal range, book it.</li></ol>"
             "<p>Want shortcuts? Our <a href='index.html'>live board</a> already does the "
             "tracking, the “search anywhere,” and the “below-normal” flag for you.</p>"),
            ("The one trick that beats the rest",
             "<p>If you only do one thing: <b>know the normal price.</b> Every other tip is noise "
             "without a baseline. A “$600 flight to Rome” means nothing until you know that "
             "route usually runs $750 — then it's a buy. That's the entire idea behind tracking "
             "fares like a market, and it's why a tracker beats endless manual searching. The U.S. "
             "<a href='https://www.bts.gov/' target='_blank' rel='noopener'>Bureau of Transportation "
             "Statistics</a> publishes average-fare data if you want to sanity-check a route's "
             "ballpark.</p>"),
            ("What our live data adds",
             "<p>We watch <b>{LIVE_ROUTES} routes</b> from the USA and log every price daily, so the "
             "deals you see are already filtered to the ones below their normal range. The current "
             "standout is <b>{LIVE_TOPCITY}</b>, about <b>{LIVE_TOPPCT}% under</b> its usual fare. "
             "If a flight is cancelled or delayed after you book, the "
             "<a href='https://www.transportation.gov/airconsumer' target='_blank' rel='noopener'>"
             "DOT's consumer protection</a> office explains what you're owed.</p>"),
        ],
        "faqs": [
            ("What is the cheapest way to find flights?",
             "Track the route so you know its normal price, stay flexible on dates and airports, and "
             "book when a fare drops below normal. A fare tracker beats searching one route "
             "repeatedly."),
            ("What is the best site to find cheap flights?",
             "Use a tool that shows a route's price history and flags fares below normal, so you can "
             "tell a real deal from a random number — that context matters more than the search "
             "box itself."),
            ("How do I find cheap flights to anywhere?",
             "Search 'anywhere' from your home airport and let the cheapest destination surface, then "
             "build a trip around the deal instead of picking the destination first."),
            ("Does searching in incognito mode find cheaper flights?",
             "No — that's a myth. Clearing cookies or using incognito doesn't meaningfully lower "
             "fares. Timing, flexibility, and knowing the normal price are what actually work."),
        ],
        "howto": {
            "name": "How to find cheap flights",
            "steps": [
                {"name": "Book in the sweet spot", "text": "Aim for 1-3 months ahead for domestic flights and 2-8 months for international."},
                {"name": "Know the normal price", "text": "Track the route so you have a baseline and can tell whether today's fare is genuinely low."},
                {"name": "Stay flexible on dates", "text": "Shift a day or two; mid-week (Tuesday, Wednesday, Saturday) departures are usually cheaper."},
                {"name": "Stay flexible on airports", "text": "Check nearby airports, or fly to a cheap hub and take an onward budget flight."},
                {"name": "Set fare alerts", "text": "Let a tracker notify you when the price drops instead of searching repeatedly."},
                {"name": "Act fast on real drops", "text": "When a fare falls below its normal range, book it — the best fares disappear within hours."},
            ],
        },
    },
    {
        "slug": "what-is-a-mistake-fare",
        "title": "What Is a Mistake Fare? (And How to Catch One) | Magellan Flights",
        "h1": "What is a mistake fare?",
        "description": "A mistake fare is a flight priced far below normal because of an airline "
                       "error. They're real and bookable — but rare, fleeting, and not always "
                       "honored. Here's how they work.",
        "primary": "what is a mistake fare",
        "secondary": ["error fare flights", "are mistake fares legal",
                      "how to find mistake fares", "mistake fare meaning"],
        "kicker": "Explainer",
        "published": "2026-06-22", "updated": "2026-06-22", "read_min": 5,
        "money_href": "index.html", "money_label": "the live deal board",
        "lede": "Every so often a flight pops up at a price that looks like a typo — New York to "
                "Milan for $180, business class to Asia for the price of economy. Sometimes it <i>is</i> "
                "a typo. These are mistake fares, and catching one is the closest thing travel has to "
                "winning a small lottery. Here's how they work — and the catch.",
        "quick_answer": "A mistake fare (or “error fare”) is a flight accidentally priced far "
                        "below normal — from a currency slip, a missing fuel surcharge, or a plain "
                        "typo. They're real and often bookable, but <b>rare, gone within hours, and "
                        "not always honored</b>, so book a refundable fare and don't make other plans "
                        "until it's confirmed.",
        "sections": [
            ("Mistake fare, in plain English",
             "<p>A mistake fare is exactly what it sounds like: a fare an airline (or its software) "
             "published by accident, priced well below what the route should cost. “Error "
             "fare” means the same thing. They can be 50%, 70%, even 90% off normal — which "
             "is why deal hunters chase them.</p>"),
            ("How mistake fares happen",
             "<ul class='blog-list'>"
             "<li><b>Currency slip-ups</b> — a fare loaded in the wrong currency or a bad "
             "conversion.</li>"
             "<li><b>Missing fuel surcharge</b> — a big chunk of the price simply doesn't get "
             "added.</li>"
             "<li><b>Typos</b> — a fare filed with a digit dropped.</li>"
             "<li><b>System glitches</b> — promo codes or pricing rules misfiring.</li></ul>"),
            ("Are mistake fares legal? Will the airline honor it?",
             "<p>Booking one is perfectly legal — you're accepting a price the airline published. "
             "The catch is whether they'll <i>honor</i> it. Sometimes airlines quietly let mistake "
             "fares stand as goodwill; other times they cancel and refund them, and the rules around "
             "this have shifted over the years. So the golden rule: <b>book a refundable fare, pay "
             "with a card, and don't buy non-refundable hotels or onward flights until the ticket is "
             "confirmed.</b> If an airline cancels on you, the "
             "<a href='https://www.transportation.gov/airconsumer' target='_blank' rel='noopener'>"
             "DOT's aviation consumer protection</a> office is the place to understand your options.</p>"),
            ("How to catch one",
             "<ul class='blog-list'>"
             "<li><b>Move fast</b> — mistake fares often last only hours before they're pulled.</li>"
             "<li><b>Watch a deal tracker</b> rather than hunting manually — by the time a fare "
             "trends on social media, it's usually dead.</li>"
             "<li><b>Don't add non-refundable plans</b> until the airline confirms the ticket.</li>"
             "<li><b>Be ready to be flexible</b> on dates — you take the error fare's terms, not "
             "your ideal schedule (and if it's international, confirm your "
             "<a href='https://travel.state.gov/content/travel/en/passports.html' target='_blank' "
             "rel='noopener'>passport</a> is valid).</li></ul>"),
            ("What our tracker does",
             "<p>The whole point of tracking <b>{LIVE_ROUTES} routes</b> like a market is to catch "
             "the moment a fare falls far below its normal range — which is exactly what a mistake "
             "fare looks like in the data. Keep an eye on our <a href='index.html'>live board</a>; "
             "when something drops that far, it surfaces fast.</p>"),
        ],
        "faqs": [
            ("Are mistake fares legal to book?",
             "Yes. You're accepting a price the airline published. What's uncertain is whether the "
             "airline will honor it or cancel and refund — so book refundable and wait before "
             "making other plans."),
            ("Will airlines honor a mistake fare?",
             "Sometimes. Some airlines let them stand as goodwill; others cancel and refund. There's "
             "no guarantee, so never book non-refundable plans around one until it's confirmed."),
            ("How do I find mistake fares?",
             "Watch a deal tracker that flags fares far below their normal range and be ready to "
             "book within hours — mistake fares disappear fast once they spread."),
            ("What does 'error fare' mean?",
             "It's another name for a mistake fare — a flight accidentally priced far below "
             "normal because of a currency, surcharge, or typo error."),
        ],
    },
    {
        "slug": "how-to-finance-a-trip",
        "title": "How to Finance a Trip the Smart Way (Without the Debt Trap) | Magellan Flights",
        "h1": "How to finance a trip without the debt trap",
        "description": "Buy-now-pay-later and travel loans can spread the cost of a "
                       "trip - but they can also quietly cost you hundreds. Here's how "
                       "travel financing really works, when it makes sense, and how to "
                       "do it without paying interest.",
        "primary": "how to finance a trip",
        "secondary": ["travel financing", "buy now pay later flights", "pay monthly for flights",
                      "finance a vacation", "is affirm worth it for travel", "uplift travel review"],
        "kicker": "Paying for travel",
        "published": "2026-06-24", "updated": "2026-06-24", "read_min": 7,
        "money_href": "market.html", "money_label": "today&rsquo;s cheapest flight deals",
        "lede": "&ldquo;Book now, pay over time&rdquo; is everywhere at travel checkout now "
                "&mdash; Affirm, Uplift, Klarna, Afterpay. Spreading a trip over a few months "
                "can be genuinely useful, or it can quietly tack hundreds of dollars onto a "
                "vacation you&rsquo;re still paying off long after the tan fades. Here&rsquo;s "
                "the honest version: how travel financing actually works, when it&rsquo;s "
                "smart, and how to use it without paying a cent of interest.",
        "quick_answer": "Travel financing lets you split a trip into monthly payments through "
                        "&ldquo;buy now, pay later&rdquo; services (Affirm, Uplift, Klarna) or "
                        "a personal loan. It&rsquo;s a reasonable tool <i>if</i> you get a 0% "
                        "APR offer, can comfortably afford the payments, and you&rsquo;d have "
                        "taken the trip anyway. It works against you when the APR is high "
                        "(often 10&ndash;36%), because you end up paying extra for a trip "
                        "that&rsquo;s already over. The cheapest way to &ldquo;finance&rdquo; "
                        "a trip is still to pay less for the flight in the first place.",
        "key_takeaways": [
            "Buy now, pay later splits a trip into installments &mdash; sometimes at 0%, "
            "often at 10&ndash;36% APR. Always check which one you&rsquo;re being offered.",
            "A 0% plan you can comfortably afford is fine. An interest-bearing plan means "
            "you pay <i>more</i> than the trip&rsquo;s sticker price.",
            "Never finance a trip you couldn&rsquo;t afford to cancel &mdash; the debt "
            "outlives the vacation.",
            "The biggest saving isn&rsquo;t the payment plan; it&rsquo;s catching the flight "
            "while it&rsquo;s below its normal price.",
        ],
        "sections": [
            ("What &ldquo;travel financing&rdquo; actually means",
             "<p>Travel financing is just borrowing to pay for a trip and repaying it over "
             "time. In 2026 it mostly shows up in two forms:</p>"
             "<ul class='blog-list'>"
             "<li><b>Buy now, pay later (BNPL)</b> &mdash; services like "
             "<a href=\"https://www.affirm.com/\" target=\"_blank\" rel=\"noopener\">Affirm</a>, "
             "<a href=\"https://www.uplift.com/\" target=\"_blank\" rel=\"noopener\">Uplift</a> "
             "(now Flex Pay), <a href=\"https://www.klarna.com/\" target=\"_blank\" "
             "rel=\"noopener\">Klarna</a> and Afterpay. You see them at checkout on airline, "
             "hotel and cruise sites, splitting the total into monthly or biweekly payments.</li>"
             "<li><b>Personal loans and travel loans</b> &mdash; a lump sum from a bank or "
             "lender that you repay in fixed monthly installments, usable for any trip.</li></ul>"
             "<p>Both do the same thing: they move money you don&rsquo;t have yet into a trip "
             "you want now. Whether that&rsquo;s smart comes down almost entirely to one "
             "number &mdash; the interest rate.</p>"),
            ("The one number that decides everything: APR",
             "<p>APR is the yearly cost of borrowing. With travel BNPL it usually lands in one "
             "of two buckets, and they&rsquo;re worlds apart:</p>"
             "<ul class='blog-list'>"
             "<li><b>0% APR promotional plans.</b> Some BNPL offers, for well-qualified "
             "buyers on shorter terms, charge no interest at all. Here financing is close to "
             "free: you pay the same sticker price, just spread out. If the math works and you "
             "can cover the payments, this is the only kind worth taking lightly.</li>"
             "<li><b>Interest-bearing plans (roughly 10&ndash;36% APR).</b> This is the common "
             "case. A $1,200 trip financed at, say, 25% APR over a year can cost well over "
             "$1,300 by the time you&rsquo;re done &mdash; you&rsquo;re paying a premium for a "
             "vacation that ended months ago.</li></ul>"
             "<p>Before you tap &ldquo;pay monthly,&rdquo; find the APR and the total amount "
             "you&rsquo;ll repay. If a checkout shows you a tidy monthly figure but hides the "
             "total, that&rsquo;s your cue to slow down. The U.S. "
             "<a href=\"https://www.consumerfinance.gov/consumer-tools/buy-now-pay-later/\" "
             "target=\"_blank\" rel=\"noopener\">Consumer Financial Protection Bureau</a> "
             "has a plain-English rundown of how BNPL works and where the catches are.</p>"),
            ("When financing a trip actually makes sense",
             "<p>It&rsquo;s not always a bad idea. Financing can be reasonable when:</p>"
             "<ul class='blog-list'>"
             "<li><b>You qualify for a genuine 0% plan</b> and the payments fit your budget "
             "with room to spare.</li>"
             "<li><b>You could pay cash, but timing the payments helps cash flow</b> &mdash; "
             "you&rsquo;d rather not drain savings the same month a fare drops.</li>"
             "<li><b>It&rsquo;s a fixed-rate plan you can finish on schedule</b>, not a "
             "revolving balance that lingers.</li></ul>"
             "<p>In those cases BNPL is mostly a convenience &mdash; a way to grab a cheap "
             "fare the day it appears instead of the day your paycheck lands.</p>"),
            ("When to walk away from the &ldquo;pay monthly&rdquo; button",
             "<p>Be honest with yourself here. Financing is working against you when:</p>"
             "<ul class='blog-list'>"
             "<li><b>You couldn&rsquo;t afford the trip without it.</b> If the only way to "
             "go is to borrow, the trip is telling you something. The debt will still be here "
             "when the trip isn&rsquo;t.</li>"
             "<li><b>The APR is high and the term is long.</b> Interest on a vacation is money "
             "you&rsquo;ll never see again, for something you&rsquo;ve already used.</li>"
             "<li><b>You&rsquo;re stacking plans.</b> Several BNPL balances at once are easy "
             "to lose track of, and missed payments can mean fees and a credit-score hit.</li></ul>"
             "<p>A simple gut check: if you&rsquo;d be uncomfortable paying the full price on a "
             "card today, financing doesn&rsquo;t make the trip more affordable &mdash; it just "
             "spreads the discomfort out and adds interest on top.</p>"),
            ("The cheaper kind of &ldquo;financing&rdquo;: pay less for the flight",
             "<p>Here&rsquo;s the part the checkout button won&rsquo;t tell you. The biggest "
             "lever on what a trip costs isn&rsquo;t how you spread the payments &mdash; "
             "it&rsquo;s the price you lock in. Catching a fare 30% below its normal range "
             "saves you more, instantly, than any payment plan, and there&rsquo;s nothing to "
             "pay back.</p>"
             "<p>That&rsquo;s the whole idea behind what we do. Magellan Flights tracks "
             "<b>{LIVE_ROUTES} routes</b> from the USA and logs the price every day, so you "
             "can see each route&rsquo;s normal price and pounce when one dips below it. Right "
             "now the standout on the board is <b>{LIVE_TOPCITY}</b>, about <b>{LIVE_TOPPCT}% "
             "below</b> its usual fare. Buy a trip at a real low and you may not need to "
             "finance much of anything &mdash; watch them move on "
             "<a href='market.html'>today&rsquo;s deal board</a>.</p>"),
            ("A 60-second checklist before you finance",
             "<p>If you do decide to spread the cost, run through this first:</p>"
             "<ul class='blog-list'>"
             "<li><b>Find the APR</b> &mdash; 0% changes the math completely; 25% changes it "
             "the other way.</li>"
             "<li><b>Read the total repaid</b>, not just the monthly number.</li>"
             "<li><b>Check the late-fee and missed-payment terms.</b></li>"
             "<li><b>Confirm you could still make the payments</b> if your income dipped for a "
             "month.</li>"
             "<li><b>Lower the price first</b> &mdash; start from a fare that&rsquo;s already "
             "below normal on the <a href='market.html'>international board</a> so "
             "there&rsquo;s less to finance at all.</li></ul>"
             "<p>Used carefully, on a fare you grabbed at a low, financing is a convenience. "
             "Used to reach a trip you can&rsquo;t really afford, it&rsquo;s an expensive way "
             "to make a cheap fare costly again.</p>"),
        ],
        "faqs": [
            ("Is it a good idea to finance a vacation?",
             "It can be, if you get a 0% plan, can comfortably afford the payments, and would "
             "have taken the trip anyway. It's a poor idea if the only way you can afford the "
             "trip is to borrow at a high APR, because the interest makes an already-finished "
             "vacation cost more."),
            ("What is the cheapest way to pay for a flight over time?",
             "A genuine 0% APR buy-now-pay-later plan, or a 0% intro-APR credit card you pay "
             "off before the promo ends, costs nothing extra. Any interest-bearing plan adds "
             "to the price. Cheaper still is buying the fare while it's below its normal range "
             "so there's less to finance."),
            ("Does buy now, pay later for flights affect my credit score?",
             "It can. Some BNPL providers run credit checks and report missed payments, and "
             "stacking several plans makes balances easy to miss. On-time payments on a "
             "reporting plan may help; late ones can hurt. Check each provider's terms."),
            ("Is Affirm or Uplift better for travel?",
             "Both split travel purchases into monthly payments; Uplift (Flex Pay) is "
             "travel-specific and appears on many airline and cruise sites, while Affirm is "
             "broader. The provider matters less than the APR you're offered - compare the "
             "rate and total repaid, not the brand."),
            ("Can I finance a flight I book through a deal site?",
             "Financing is offered at the checkout of whoever you book with, so it depends on "
             "that airline or travel site supporting a provider like Affirm or Uplift. A deal "
             "tracker's job is to get you the lowest fare; how you pay it off happens at the "
             "booking site."),
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
    # AI-SEO: an answer-first box (extractable for Google AI Overviews / ChatGPT).
    answer_html = ""
    if a.get("quick_answer"):
        answer_html = ('<div class="art-answer"><div class="aa-label">Quick answer</div>'
                       f'<p>{a["quick_answer"]}</p></div>')
    takeaways_html = ""
    if a.get("key_takeaways"):
        lis = "".join(f"<li>{t}</li>" for t in a["key_takeaways"])
        takeaways_html = ('<div class="art-takeaways"><div class="aa-label">Key takeaways</div>'
                          f'<ul>{lis}</ul></div>')
    out = f"""<div class="wrap blog-wrap">
  <nav class="crumbs"><a href="guides.html">Guides</a> &rsaquo; {html.escape(a["h1"])}</nav>
  <div class="blog-eyebrow">{html.escape(a["kicker"])}</div>
  <h1 class="blog-title">{html.escape(a["h1"])}</h1>
  <div class="art-meta">Updated {a["updated"]} &middot; {a["read_min"]} min read &middot; {BRAND}</div>
  <p class="art-lede">{a["lede"]}</p>
  {answer_html}
  {takeaways_html}
  {cta}
  {secs}
  {faq_html}
  {cta}
  {rel_html}
  {NL_CTA}
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
  <div class="pagehead"><h1>Flight deal guides</h1><p>Straight answers on when to book, where to go, and how to catch a deal &mdash; backed by the fares we track every day.</p></div>
  <div class="guide-grid">{cards}</div>
</div>"""


# --------------------------------------------------------------------------- #
# Money pages (service-page matrix): one static, indexable page per departure
# airport — "Cheap flights from {City} ({CODE})" — server-rendered from live
# homebase data so each page has unique, crawlable fares (not a thin template).
# See seo/money_pages_matrix.md. Booking links stay Aviasales (marker 741311).
# --------------------------------------------------------------------------- #
MONEY_AIRPORTS = [
    ("ATL", "Atlanta"), ("LAX", "Los Angeles"), ("ORD", "Chicago"), ("DFW", "Dallas"),
    ("DEN", "Denver"), ("JFK", "New York"), ("SFO", "San Francisco"), ("SEA", "Seattle"),
    ("LAS", "Las Vegas"), ("MCO", "Orlando"), ("MIA", "Miami"), ("CLT", "Charlotte"),
    ("PHX", "Phoenix"), ("IAH", "Houston"), ("BOS", "Boston"), ("MSP", "Minneapolis"),
    ("FLL", "Fort Lauderdale"), ("DTW", "Detroit"), ("PHL", "Philadelphia"), ("LGA", "New York"),
    ("BWI", "Baltimore"), ("SLC", "Salt Lake City"), ("DCA", "Washington"), ("SAN", "San Diego"),
    ("TPA", "Tampa"),
]
MONEY_PAGES = []          # populated in main() from homebase data
MONEY_BY_FILE = {}


def _slugify(s):
    import re
    s = re.sub(r"\([^)]*\)", "", str(s)).strip().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def money_targets(home):
    out = []
    for code, city in MONEY_AIRPORTS:
        info = home.get(code)
        if not info:
            continue
        deals = sorted(info.get("deals", []), key=lambda x: x.get("price", 1e9))
        if len(deals) < 5:
            continue
        slug = f"cheap-flights-from-{_slugify(city)}-{code.lower()}"
        low = deals[0]; topdest = low["name"].split(",")[0]
        out.append({
            "code": code, "city": city, "slug": slug, "fname": slug + ".html",
            "title": f"Cheap Flights from {city} ({code}) — Live Deals | {BRAND}",
            "description": (f"Today's cheapest flights from {city} ({code}): real, bookable "
                            f"fares to {topdest} from ${low['price']:,.0f} and more, updated daily."),
            "h1": f"Cheap flights from {city} ({code})",
            "deals": deals,
        })
    return out


def money_faqs(p):
    low = p["deals"][0]; topdest = low["name"].split(",")[0]
    return [
        (f"What is the cheapest place to fly from {p['city']} right now?",
         f"Right now it's {topdest} at ${low['price']:,.0f} from {p['code']}. The cheapest "
         f"destination shifts as fares move, so this page refreshes daily with the current lows."),
        (f"Are these {p['city']} flight deals real and bookable?",
         "Yes. Every fare is re-checked against live pricing before it's shown, and each Book "
         "link goes to a secure booking page for that exact flight."),
        (f"How often do the fares from {p['code']} update?",
         "Several times a day, so the prices here reflect what's actually bookable right now."),
    ]


def body_moneypage(p, today):
    deals = p["deals"][:20]
    rows = []
    for d in deals:
        nm = html.escape(d["name"].split(",")[0])
        dates = html.escape(d.get("depart", ""))
        if d.get("return"):
            dates += " &rarr; " + html.escape(d.get("return", ""))
        link = html.escape(d["link"], quote=True)
        rows.append(
            f'<tr data-lp data-o="{p["code"]}" data-d="{d["code"]}" data-ow="{0 if d.get("return") else 1}"><td class="dt-dest">{flag_img(d["code"], "flag")} {nm} '
            f'<span class="dt-code">{d["code"]}</span></td>'
            f'<td class="dt-dates">{dates}</td>'
            f'<td class="dt-price">${d["price"]:,.0f}</td>'
            f'<td><a class="book" href="{link}" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></td></tr>')
    table = ('<table class="deal-table"><thead><tr><th>Destination</th><th>Dates</th>'
             '<th>Price</th><th></th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")
    low = p["deals"][0]; topdest = html.escape(low["name"].split(",")[0])
    faq_items = "".join(
        f'<details class="art-q"><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>'
        for q, a in money_faqs(p))
    faq_html = f'<section class="blog-sec"><h2>Frequently asked questions</h2>{faq_items}</section>'
    route_links = [q for q in globals().get("ROUTE_PAGES", []) if q["origin"] == p["code"]]
    routes_html = ""
    if route_links:
        routes_html = ('<section class="blog-sec"><h2>Popular routes from ' + html.escape(p["city"]) +
                       '</h2><ul class="blog-list">' + "".join(
                           f'<li><a href="{q["fname"]}">Cheap flights from {html.escape(q["ocity"])} to {html.escape(q["dcity"])}</a></li>'
                           for q in route_links[:12]) + "</ul></section>")
    others = [q for q in MONEY_PAGES if q["code"] != p["code"]][:8]
    others_html = (
        '<section class="blog-sec"><h2>Cheap flights from other cities</h2>'
        '<ul class="blog-list">' + "".join(
            f'<li><a href="{q["fname"]}">Cheap flights from {html.escape(q["city"])} ({q["code"]})</a></li>'
            for q in others) + "</ul></section>")
    cta = ('<div class="art-cta"><div class="art-cta-txt"><b>Heads up:</b> these fares move fast. '
           'Every price here is re-checked against live pricing and links straight to a secure '
           'booking page &mdash; if you see one you love, grab it.</div>'
           '<a class="book" href="explore.html">Explore everywhere &rarr;</a></div>')
    return f"""<div class="wrap blog-wrap">
  <nav class="crumbs"><a href="cheap-flights.html">Cheap flights</a> &rsaquo; from {html.escape(p['city'])}</nav>
  <div class="blog-eyebrow">Departure city</div>
  <h1 class="blog-title">{html.escape(p['h1'])}</h1>
  <div class="art-meta">Updated {today} &middot; live fares &middot; {BRAND}</div>
  <div class="art-answer"><div class="aa-label">Quick answer</div>
    <p>The cheapest flight from {html.escape(p['city'])} ({p['code']}) right now is
    <b>${low['price']:,.0f} to {topdest}</b>. Below are the {len(deals)} cheapest destinations
    we're tracking from {p['code']} &mdash; all real, bookable, and refreshed through the day.</p></div>
  {cta}
  {table}
  {routes_html}
  {faq_html}
  {others_html}
</div>"""


def body_money_hub(pages):
    cards = "".join(
        f'<a class="guide-card" href="{p["fname"]}">'
        f'<div class="gc-kick">Departure city</div>'
        f'<div class="gc-title">Cheap flights from {html.escape(p["city"])} ({p["code"]})</div>'
        f'<div class="gc-desc">From ${p["deals"][0]["price"]:,.0f} &mdash; live deals to '
        f'{min(len(p["deals"]), 20)} destinations</div>'
        f'<div class="gc-more">See deals &rarr;</div></a>' for p in pages)
    return f"""<div class="wrap">
  <div class="pagehead"><h1>Cheap flights by departure city</h1><p>Pick your home airport for a live list of the cheapest places to fly right now &mdash; real, bookable fares from {len(pages)} US cities, refreshed daily.</p></div>
  <div class="guide-grid">{cards}</div>
</div>"""


# --------------------------------------------------------------------------- #
# Evergreen per-city guide pages — the permanent home for each city's deal,
# video, and travel guide (the content flywheel: deal -> video -> guide -> share)
# --------------------------------------------------------------------------- #
# code -> (City display name, Country, url slug). One page per CITY_GUIDE city.
CITY_META = {
    "LON": ("London", "United Kingdom", "london"),
    "SJU": ("San Juan", "Puerto Rico", "san-juan"),
    "SJD": ("Los Cabos", "Mexico", "los-cabos"),
    "CUN": ("Cancun", "Mexico", "cancun"),
    "MEX": ("Mexico City", "Mexico", "mexico-city"),
    "PUJ": ("Punta Cana", "Dominican Republic", "punta-cana"),
    "MBJ": ("Montego Bay", "Jamaica", "montego-bay"),
    "AUA": ("Aruba", "Aruba", "aruba"),
    "BOG": ("Bogota", "Colombia", "bogota"),
    "LIS": ("Lisbon", "Portugal", "lisbon"),
    "KEF": ("Reykjavik", "Iceland", "reykjavik"),
    "DUB": ("Dublin", "Ireland", "dublin"),
    "BKK": ("Bangkok", "Thailand", "bangkok"),
    "ATH": ("Athens", "Greece", "athens"),
    "IST": ("Istanbul", "Turkey", "istanbul"),
    "DXB": ("Dubai", "United Arab Emirates", "dubai"),
    "RAK": ("Marrakech", "Morocco", "marrakech"),
    "CAI": ("Cairo", "Egypt", "cairo"),
    "BCN": ("Barcelona", "Spain", "barcelona"),
    "CTG": ("Cartagena", "Colombia", "cartagena"),
    "MDE": ("Medellin", "Colombia", "medellin"),
    "ANC": ("Anchorage", "Alaska, USA", "anchorage"),
    "GOH": ("Nuuk", "Greenland", "nuuk"),
    "SJO": ("San Jose", "Costa Rica", "san-jose"),
}


def _build_city_guides():
    out = []
    for code, (city, country, slug) in CITY_META.items():
        if code not in CITY_GUIDE:
            continue
        out.append({
            "code": code, "city": city, "country": country, "slug": slug,
            "fname": f"cheap-flights-to-{slug}-{code.lower()}.html",
            "h1": f"Cheap Flights to {city} + {city} Travel Guide",
            "title": f"Cheap Flights to {city} ({code}) + Travel Guide | {BRAND}",
            "description": (f"The cheapest flights to {city}, {country} from the USA right now, "
                            f"plus the best time to go, top things to do, safety and culture "
                            f"— your complete {city} travel guide."),
        })
    return out


CITY_GUIDES = _build_city_guides()
CITYGUIDE_BY_FILE = {g["fname"]: g for g in CITY_GUIDES}
CODE_TO_CITYPAGE = {g["code"]: g["fname"] for g in CITY_GUIDES}


def find_city_deal(code, market):
    cand = [m for m in market if m.get("code") == code]
    return min(cand, key=lambda m: m["price"]) if cand else None


def city_watch_html(code, cityshort):
    _vid = YT_VIDEOS.get(code, "")
    _sub = (YT_CHANNEL + ("&" if "?" in YT_CHANNEL else "?") + "sub_confirmation=1") if YT_CHANNEL else ""
    if _vid:
        return (f'<div class="blog-embed"><iframe src="https://www.youtube.com/embed/{_vid}" '
                f'title="{html.escape(cityshort)} travel guide" loading="lazy" frameborder="0" '
                f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" '
                f'allowfullscreen></iframe></div>'
                f'<a class="yt-sub" href="{_sub}" target="_blank" rel="noopener">&#9654; Subscribe on YouTube</a>')
    if YT_CHANNEL:
        return (f'<a class="blog-video" href="{_sub}" target="_blank" rel="noopener">'
                f'<span class="bv-play">&#9654;</span><span class="bv-text">A <b>{html.escape(cityshort)}</b> '
                f'video guide is on the way &mdash; <b style="color:var(--gold)">subscribe</b> '
                f'so you don&rsquo;t miss it.</span></a>')
    return '<div class="blog-soon">Video guide coming soon</div>'


def city_faqs(g, deal, best, info):
    city, country, code = g["city"], g["country"], g["code"]
    faqs = []
    if deal:
        faqs.append((f"How much is a flight to {city}?",
                     f"The cheapest round-trip we're tracking to {city} ({code}) from the USA is about "
                     f"${deal['price']:,.0f} right now. Live fares move through the day, so confirm the "
                     f"current price before you book."))
    faqs.append((f"When is the best time to visit {city}?",
                 f"The best time to fly to {city} is generally {best}. Shoulder-season trips often pair "
                 f"good weather with lower fares."))
    faqs.append((f"Is {city} safe for tourists?",
                 f"{info.get('safe', 'Check the latest travel advisory')}. As anywhere, watch your "
                 f"belongings in crowds and check your government's current advisory before you go."))
    faqs.append((f"Do US citizens need a visa for {country}?",
                 f"Visa for US passports: {info.get('visa', 'check entry requirements')}. Always confirm "
                 f"the latest entry rules with official sources before booking."))
    return faqs


def body_cityguide(g, market, today):
    code, city, country = g["code"], g["city"], g["country"]
    cg = CITY_GUIDE.get(code, {})
    info = DEST_INFO.get(code, {"lang": "the local language", "eng": "varies",
                                "visa": "Check entry requirements for US passports",
                                "safe": "Check your government's latest travel advisory",
                                "note": "Verify details before booking"})
    best = BEST_TIME.get(code, "year-round")
    deal = find_city_deal(code, market)
    if deal:
        dates = (f'{html.escape(deal.get("depart",""))} &rarr; {html.escape(deal.get("return",""))}'
                 if deal.get("return") else html.escape(deal.get("depart", "")))
        sig, pct = signal_for(deal["price"], deal["benchmark"])
        link = html.escape(deal["link"], quote=True)
        deal_block = (
            f'<div class="blog-deal" data-lp data-o="{html.escape(deal["origin"], quote=True)}" data-d="{code}" data-ow="0">'
            f'<div><div class="blog-deal-label">Round-trip to {city} from {html.escape(deal["origin"])}</div>'
            f'<div class="blog-deal-dates">{dates} &middot; best time to go: {html.escape(best)}</div></div>'
            f'<div class="blog-deal-right"><span class="blog-price">${deal["price"]:,.0f}</span>'
            f'<span class="blog-was">was ~${deal["benchmark"]:,.0f}</span>'
            f'<span class="sig s-book">{sig} &middot; {pct:.0f}% off</span>'
            f'<a class="book" href="{link}" target="_blank" rel="noopener">See live price &amp; book &rarr;</a></div></div>')
        cheapest_line = (f"The cheapest round-trip to {city} from the USA right now is "
                         f"<b>${deal['price']:,.0f}</b> (from {html.escape(deal['origin'])}).")
    else:
        deal_block = ('<div class="art-cta"><div class="art-cta-txt"><b>No standout fare to '
                      f'{city} on the board this minute.</b> Fares move all day &mdash; set a free '
                      'alert and we&rsquo;ll ping you the moment one drops.</div>'
                      '<a class="book" href="index.html#alerts">Get free alerts &rarr;</a></div>')
        cheapest_line = (f"We track flights to {city} from across the USA every day &mdash; check back "
                         "or set an alert for the next drop.")
    todo = "".join(f"<li>{html.escape(t)}</li>" for t in cg.get("todo", []))
    todo_block = f'<ul class="blog-list">{todo}</ul>' if todo else ""
    watch = city_watch_html(code, city)
    overview = cg.get("overview", f"{city} is one of the destinations we track from the USA every day.")
    history = cg.get("history", "")
    culture = cg.get("culture", "")
    faqs = city_faqs(g, deal, best, info)
    faq_items = "".join(
        f'<details class="art-q"><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>'
        for q, a in faqs)
    others = [o for o in CITY_GUIDES if o["code"] != code][:6]
    others_html = "".join(
        f'<li><a href="{o["fname"]}">Cheap flights to {html.escape(o["city"])}</a></li>' for o in others)
    share_url = BASE_URL + "/" + g["fname"]
    share_txt = quote_plus(f"Cheap flights to {city} + a {city} travel guide — from {BRAND}")
    su = quote_plus(share_url)
    share = (
        '<div class="share-row"><span class="share-lbl">Share this guide</span>'
        f'<a class="share-btn" target="_blank" rel="noopener" href="https://twitter.com/intent/tweet?url={su}&text={share_txt}">X</a>'
        f'<a class="share-btn" target="_blank" rel="noopener" href="https://www.facebook.com/sharer/sharer.php?u={su}">Facebook</a>'
        f'<a class="share-btn" target="_blank" rel="noopener" href="https://api.whatsapp.com/send?text={share_txt}%20{su}">WhatsApp</a>'
        f'<a class="share-btn" target="_blank" rel="noopener" href="mailto:?subject={quote_plus("Cheap flights to "+city)}&body={share_txt}%20{su}">Email</a></div>')
    hist_block = (f'<section class="blog-sec"><h2>A bit of history</h2><p>{html.escape(history)}</p></section>'
                  if history else "")
    cult_block = (f'<section class="blog-sec"><h2>Culture &amp; language</h2><p>{html.escape(culture)}</p>'
                  f'<p class="blog-lang"><b>Language:</b> {html.escape(info.get("lang","—"))} &middot; '
                  f'<b>English spoken:</b> {html.escape(info.get("eng","—"))}</p></section>') if culture else ""
    return f"""<div class="wrap blog-wrap">
  <nav class="crumbs"><a href="city-guides.html">City guides</a> &rsaquo; {html.escape(city)}</nav>
  <div class="blog-eyebrow">{html.escape(country)} &middot; flight deal + travel guide</div>
  <h1 class="blog-title">{g['h1']}</h1>
  <div class="art-meta">Updated {today} &middot; live fares &middot; {BRAND}</div>
  <div class="art-answer"><div class="aa-label">Quick answer</div><p>{cheapest_line} Below: a quick video, when to go, what to do, safety and culture.</p></div>
  {deal_block}
  <section class="blog-sec"><h2>Watch: {html.escape(city)} in a couple of minutes</h2>{watch}</section>
  <section class="blog-sec"><h2>The overview</h2><p>{html.escape(overview)}</p></section>
  <section class="blog-sec"><h2>Top things to do in {html.escape(city)}</h2>{todo_block}</section>
  <section class="blog-sec"><h2>Best time to visit</h2><p>The sweet spot for {html.escape(city)} is generally <b>{html.escape(best)}</b> &mdash; and the cheapest fares often land just outside peak season.</p></section>
  <section class="blog-sec"><h2>Is it safe?</h2><p>{html.escape(info.get('safe','Check the latest travel advisory'))}. Watch your belongings in crowds and tourist areas, and check your government&rsquo;s current advisory before you go. Visa for US passports: {html.escape(info.get('visa','check entry requirements'))}.</p></section>
  {hist_block}
  {cult_block}
  {share}
  <section class="blog-sec"><h2>Frequently asked questions</h2>{faq_items}</section>
  <div class="blog-cta"><a class="btn-primary" href="{html.escape(deal['link'], quote=True) if deal else 'explore.html'}" {'target="_blank" rel="noopener"' if deal else ''}>{'Grab the '+city+' deal &rarr;' if deal else 'Find your own deal &rarr;'}</a><a class="btn-ghost" href="index.html#alerts">Get price-drop alerts</a></div>
  <section class="blog-sec"><h2>More city guides</h2><ul class="blog-list">{others_html}</ul></section>
  {NL_CTA}
  <p class="finehint" style="text-align:center;margin-top:8px">Prices are recently-tracked fares &mdash; your live, bookable price is confirmed on Aviasales. Safety and visa notes are general guidance for US travelers; verify official sources before booking.</p>
</div>"""


def body_cityguide_hub(guides, market):
    cards = []
    for g in guides:
        deal = find_city_deal(g["code"], market)
        price = f'From ${deal["price"]:,.0f}' if deal else "Set an alert"
        cards.append(
            f'<a class="guide-card" href="{g["fname"]}">'
            f'<div class="gc-kick">{html.escape(g["country"])}</div>'
            f'<div class="gc-title">{html.escape(g["city"])}</div>'
            f'<div class="gc-desc">{price} &middot; video, things to do, safety &amp; culture</div>'
            f'<div class="gc-more">Read guide &rarr;</div></a>')
    return f"""<div class="wrap">
  <div class="pagehead"><h1>City guides</h1><p>Deal of the day, a quick video, and a real travel guide for each city &mdash; what to do, when to go, safety and culture. {len(guides)} destinations and growing.</p></div>
  <div class="guide-grid">{"".join(cards)}</div>
</div>"""


# --------------------------------------------------------------------------- #
# Programmatic origin->destination route pages, built from real tracked fares
# (market_latest). Quality-gated to destinations we have guide data for, so each
# page has a real fare + best time + things to do + visa info (not thin).
# To widen the surface later, expand CITY_GUIDE / dealsgen DEST_INFO coverage.
# --------------------------------------------------------------------------- #
ROUTE_PAGES = []
ROUTE_BY_FILE = {}


def _city_country(name):
    parts = [x.strip() for x in str(name).split(",")]
    return parts[0], (parts[-1] if len(parts) > 1 else "")


def route_targets(market):
    out, seen = [], set()
    for r in market:
        code = r.get("code"); origin = r.get("origin")
        if not code or not origin:
            continue
        if code not in CITY_GUIDE and code not in BEST_TIME:   # quality gate
            continue
        oname = AIRPORT_NAMES.get(origin, origin); ocity = oname.split(",")[0]
        dcity, dcountry = _city_country(r.get("name", code))
        slug = f"cheap-flights-from-{_slugify(ocity)}-to-{_slugify(dcity)}"
        if slug in seen:
            slug = f"{slug}-{code.lower()}"
        seen.add(slug)
        try:
            price = float(r.get("price", 0))
        except Exception:
            price = 0.0
        out.append({**r, "ocity": ocity, "dcity": dcity, "dcountry": dcountry, "price": price,
                    "slug": slug, "fname": slug + ".html",
                    "title": f"Cheap Flights from {ocity} to {dcity} ({code}) | {BRAND}",
                    "description": (f"Cheapest flights from {ocity} ({origin}) to {dcity}: a real, "
                                    f"bookable fare from ${price:,.0f}, plus the best time to visit. "
                                    f"Updated daily."),
                    "h1": f"Cheap flights from {ocity} to {dcity}"})
    return out


def route_faqs(p):
    best = BEST_TIME.get(p["code"], ""); info = DEST_INFO.get(p["code"], {})
    faqs = [
        (f"How much is a flight from {p['ocity']} to {p['dcity']}?",
         f"The cheapest fare we're tracking from {p['ocity']} ({p['origin']}) to {p['dcity']} is "
         f"${p['price']:,.0f}, departing {p.get('depart','')}. Fares move daily, so this page "
         f"refreshes with the current low."),
        (f"Are these {p['ocity']} to {p['dcity']} fares real and bookable?",
         "Yes. Every fare is re-checked against live pricing and links to a secure booking page "
         "for that exact flight."),
    ]
    if best:
        faqs.append((f"When is the cheapest time to fly to {p['dcity']}?",
                     f"The sweet spot for {p['dcity']} is generally {best} - and the cheapest fares "
                     f"often land just outside peak season."))
    if info.get("visa"):
        faqs.append((f"Do US citizens need a visa for {p['dcountry'] or p['dcity']}?",
                     f"{info.get('visa')}. Always confirm current entry requirements before you book."))
    return faqs


def body_route(p, market, today):
    code = p["code"]; link = html.escape(p.get("link", ""), quote=True)
    try:
        sav = int(float(p.get("savings_pct", 0)))
    except Exception:
        sav = 0
    if sav >= 12:
        deal_line = f"about <b>{sav}% below</b> its typical price"
    elif sav <= -12:
        deal_line = "running a touch <b>above</b> its usual price"
    else:
        deal_line = "around its <b>typical</b> price"
    bar = price_bar(code, p["price"], p.get("benchmark", 0))
    dates = html.escape(p.get("depart", ""))
    if p.get("return"):
        dates += " &rarr; " + html.escape(p.get("return", ""))
    cg = CITY_GUIDE.get(code, {}); info = DEST_INFO.get(code, {}); best = BEST_TIME.get(code, "")
    about = (f'<section class="blog-sec"><h2>About {html.escape(p["dcity"])}</h2>'
             f'<p>{html.escape(cg["overview"])}</p></section>') if cg.get("overview") else ""
    besttime = (f'<section class="blog-sec"><h2>Best time to visit {html.escape(p["dcity"])}</h2>'
                f'<p>The sweet spot is generally <b>{html.escape(best)}</b> &mdash; and the cheapest '
                f'fares often land just outside peak season.</p></section>') if best else ""
    todo = ('<section class="blog-sec"><h2>Top things to do in ' + html.escape(p["dcity"]) +
            '</h2><ul class="blog-list">' + "".join(f"<li>{html.escape(t)}</li>" for t in cg["todo"][:5]) +
            "</ul></section>") if cg.get("todo") else ""
    bits = []
    if info.get("safe"):
        bits.append(html.escape(info["safe"]))
    if info.get("lang"):
        bits.append("Language: " + html.escape(info["lang"]))
    if info.get("visa"):
        bits.append("Visa for US passports: " + html.escape(info["visa"]))
    safe = (f'<section class="blog-sec"><h2>Good to know</h2><p>{". ".join(bits)}.</p></section>') if bits else ""
    faq_items = "".join(f'<details class="art-q"><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>'
                        for q, a in route_faqs(p))
    faq_html = f'<section class="blog-sec"><h2>Frequently asked questions</h2>{faq_items}</section>'
    links = []
    mp = next((q for q in MONEY_PAGES if q["code"] == p["origin"]), None)
    if mp:
        links.append(f'<li><a href="{mp["fname"]}">All cheap flights from {html.escape(p["ocity"])} ({p["origin"]})</a></li>')
    cgp = next((g for g in CITY_GUIDES if g["code"] == code), None)
    if cgp:
        links.append(f'<li><a href="{cgp["fname"]}">{html.escape(p["dcity"])} travel guide</a></li>')
    related = [q for q in ROUTE_PAGES if q["code"] != code and (q["origin"] == p["origin"] or q["dcity"] == p["dcity"])][:6]
    for q in related:
        links.append(f'<li><a href="{q["fname"]}">Cheap flights from {html.escape(q["ocity"])} to {html.escape(q["dcity"])}</a></li>')
    links.append('<li><a href="around-the-world.html">Build a round-the-world trip</a></li>')
    links_html = '<section class="blog-sec"><h2>Keep exploring</h2><ul class="blog-list">' + "".join(links) + '</ul></section>'
    cta = (f'<div class="art-cta"><div class="art-cta-txt"><b>See it live:</b> this '
           f'{html.escape(p["ocity"])}&ndash;{html.escape(p["dcity"])} fare is re-checked against live '
           f'pricing and links straight to booking.</div>'
           f'<a class="book" href="{link}" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div>')
    return f"""<div class="wrap blog-wrap">
  <nav class="crumbs"><a href="cheap-flights.html">Cheap flights</a> &rsaquo; {html.escape(p['ocity'])} to {html.escape(p['dcity'])}</nav>
  <div class="blog-eyebrow">Route</div>
  <h1 class="blog-title">{html.escape(p['h1'])}</h1>
  <div class="art-meta">Updated {today} &middot; live fare &middot; {BRAND}</div>
  <div class="art-answer"><div class="aa-label">Quick answer</div>
    <p>The cheapest flight from <b>{html.escape(p['ocity'])} ({p['origin']})</b> to <b>{html.escape(p['dcity'])} ({code})</b> we&rsquo;re tracking is
    <b>${p['price']:,.0f}</b>, {deal_line}, departing {dates or 'soon'}. It&rsquo;s real and bookable &mdash; refreshed daily.</p></div>
  {('<div class="blog-spark">'+bar+'</div>') if bar else ''}
  {cta}
  {about}{besttime}{todo}{safe}
  {faq_html}
  {links_html}
</div>"""


# --------------------------------------------------------------------------- #
# The Magellan Cheap Flight Index — a living data study built from live fares.
# Designed as a citable, linkable PR asset (refreshes with the daily build).
# --------------------------------------------------------------------------- #
_CFI_DOMESTIC = ("usa", "united states", "puerto rico", "u.s. virgin islands",
                 "us virgin islands", "guam", "u.s.", " u.s")


def _cfi_intl(name):
    n = str(name).strip().lower()
    return not any(n.endswith(s) for s in _CFI_DOMESTIC)


def _cfi_sav(r):
    b = r.get("benchmark") or 0
    try:
        return (b - r["price"]) / b * 100 if b > 0 else 0.0
    except Exception:
        return 0.0


def _cfi_dcity(name):
    return str(name).split(",")[0]


def body_cflindex(market, today):
    import statistics as _st
    rows = [r for r in market if r.get("price")]
    n = len(rows)
    if n < 10:
        return ('<div class="wrap"><div class="pagehead"><h1>The Magellan Cheap Flight Index</h1>'
                '<p>The index updates after the next data refresh &mdash; check back shortly.</p></div></div>')
    prices = [r["price"] for r in rows]
    med = int(_st.median(prices)); avg = int(_st.mean(prices))
    intls = [r for r in rows if _cfi_intl(r["name"])]
    cheapest_intl = min(intls, key=lambda r: r["price"]) if intls else None
    cheapest_all = min(rows, key=lambda r: r["price"])
    below = [r for r in rows if (r.get("benchmark") or 0) > 0 and r["price"] < r["benchmark"]]
    pct_below = round(100 * len(below) / n)
    big = max(rows, key=_cfi_sav)
    big_sav = round(_cfi_sav(big))
    avg_below = round(_st.mean([_cfi_sav(r) for r in below])) if below else 0
    deep = [r for r in rows if _cfi_sav(r) >= 15]

    def origin_city(o):
        return AIRPORT_NAMES.get(o, o).split(",")[0]

    # headline stat grid
    stats = [
        (f"${cheapest_intl['price']:,.0f}", f"cheapest international fare<br><b>{html.escape(_cfi_dcity(cheapest_intl['name']))}</b> from {cheapest_intl['origin']}") if cheapest_intl else None,
        (f"${med:,}", "median fare across all tracked routes"),
        (f"{pct_below}%", "of routes are below their normal price"),
        (f"{big_sav}%", f"biggest discount today<br><b>{html.escape(_cfi_dcity(big['name']))}</b>"),
        (f"{n:,}", f"routes tracked from {len(set(r['origin'] for r in rows))} US airports"),
        (f"${cheapest_all['price']:,.0f}", f"cheapest fare anywhere<br><b>{html.escape(_cfi_dcity(cheapest_all['name']))}</b> from {cheapest_all['origin']}"),
    ]
    stat_html = "".join(
        f'<div class="cfi-stat"><div class="cfi-num">{v}</div><div class="cfi-lab">{lab}</div></div>'
        for s in stats if s for v, lab in [s])

    # cheapest international destinations (top 12)
    intl_sorted = sorted(intls, key=lambda r: r["price"])[:12]
    intl_rows = "".join(
        f'<tr><td class="dt-dest">{flag_img(r["code"], "flag")} {html.escape(_cfi_dcity(r["name"]))} '
        f'<span class="dt-code">{r["code"]}</span></td><td class="dt-dates">from {r["origin"]}</td>'
        f'<td class="dt-price">${r["price"]:,.0f}</td>'
        f'<td>{("&minus;"+str(round(_cfi_sav(r)))+"%") if _cfi_sav(r) >= 1 else "&mdash;"}</td></tr>'
        for r in intl_sorted)
    intl_table = ('<table class="deal-table"><thead><tr><th>Destination</th><th>From</th>'
                  '<th>Price</th><th>vs normal</th></tr></thead><tbody>' + intl_rows + '</tbody></table>')

    # cheapest US airports to fly abroad from (rank origins by cheapest intl fare)
    by_o = {}
    for r in intls:
        o = r["origin"]
        if o not in by_o or r["price"] < by_o[o]["price"]:
            by_o[o] = r
    air_sorted = sorted(by_o.values(), key=lambda r: r["price"])[:12]
    air_rows = "".join(
        f'<tr><td>{i}</td><td class="dt-dest"><b>{html.escape(origin_city(r["origin"]))}</b> '
        f'<span class="dt-code">{r["origin"]}</span></td>'
        f'<td class="dt-dates">{html.escape(_cfi_dcity(r["name"]))}</td>'
        f'<td class="dt-price">${r["price"]:,.0f}</td></tr>'
        for i, r in enumerate(air_sorted, 1))
    air_table = ('<table class="deal-table"><thead><tr><th>#</th><th>US airport</th>'
                 '<th>Cheapest abroad</th><th>Price</th></tr></thead><tbody>' + air_rows + '</tbody></table>')

    # cheapest by region
    from collections import defaultdict as _dd
    reg = _dd(list)
    for r in rows:
        reg[continent_of(r["code"])].append(r)
    region_order = ["Europe", "Asia", "SE Asia", "E Asia", "S Asia", "Caribbean", "C America",
                    "S America", "Oceania", "Middle East", "Africa", "N America"]
    seen_r = []
    reg_blocks = []
    for rg in region_order + [k for k in reg if k not in region_order]:
        if rg not in reg or rg in seen_r or rg == "Other":
            continue
        seen_r.append(rg)
        top = sorted(reg[rg], key=lambda r: r["price"])[:3]
        if not top:
            continue
        items = "".join(
            f'<li>{flag_img(r["code"], "flag")} {html.escape(_cfi_dcity(r["name"]))} '
            f'&mdash; <b>${r["price"]:,.0f}</b> <span class="dt-dates">from {r["origin"]}</span></li>'
            for r in top)
        reg_blocks.append(f'<div class="cfi-reg"><h3>{html.escape(rg)}</h3><ul class="blog-list">{items}</ul></div>')
    region_html = '<div class="cfi-reggrid">' + "".join(reg_blocks) + '</div>'

    cite_url = BASE_URL + "/cheap-flight-index.html"
    return f"""<div class="wrap blog-wrap">
  <nav class="crumbs"><a href="guides.html">Guides</a> &rsaquo; Cheap Flight Index</nav>
  <div class="blog-eyebrow">Data study &middot; updated {today}</div>
  <h1 class="blog-title">The Magellan Cheap Flight Index</h1>
  <div class="art-meta">Updated {today} &middot; live data &middot; {BRAND}</div>
  <p class="art-lede">Every day we track the cheapest real, bookable fares from {len(set(r['origin'] for r in rows))} US airports to hundreds of destinations worldwide. This index turns that live data into a snapshot of what it actually costs to fly out of the USA right now &mdash; and where the deals are. Free to cite with a link.</p>
  <div class="cfi-grid">{stat_html}</div>

  <section class="blog-sec"><h2>Cheapest international destinations from the USA right now</h2>
  <p>The lowest current fares to destinations abroad, across all tracked US origins.</p>{intl_table}</section>

  <section class="blog-sec"><h2>Cheapest US airports to fly abroad from</h2>
  <p>Ranked by each city&rsquo;s single cheapest international fare available today.</p>{air_table}</section>

  <section class="blog-sec"><h2>Cheapest destinations by region</h2>{region_html}</section>

  <section class="blog-sec"><h2>How big are today&rsquo;s deals?</h2>
  <p>Of {n:,} tracked routes, <b>{pct_below}%</b> are currently priced below their normal range. Among those, fares sit about <b>{avg_below}% below</b> typical on average, and <b>{len(deep)}</b> routes are 15% or more below normal &mdash; the genuine deals worth grabbing.</p></section>

  <section class="blog-sec"><h2>Methodology</h2>
  <p>Figures come from {BRAND}&rsquo;s live fare tracker, which checks the cheapest real, bookable round-trip and one-way fares from major US airports several times a day. &ldquo;Normal price&rdquo; is each route&rsquo;s tracked baseline; a fare is &ldquo;below normal&rdquo; when it&rsquo;s under that baseline. Prices are in USD and change constantly &mdash; this page reflects the most recent refresh on {today}.</p></section>

  <div class="art-answer"><div class="aa-label">Cite this study</div>
  <p>Source: <b>{BRAND} Cheap Flight Index</b>, {today}. <a href="{cite_url}">{cite_url}</a>. Free to reference with a link back.</p></div>

  <section class="blog-sec"><h2>Explore the live data</h2><ul class="blog-list">
  <li><a href="market.html">Today&rsquo;s full cheap-flight board</a></li>
  <li><a href="explore.html">Search cheap flights from your airport</a></li>
  <li><a href="around-the-world.html">Build the cheapest around-the-world trip</a></li>
  <li><a href="guides.html">Flight deal guides &amp; tips</a></li></ul></section>
</div>"""


# --------------------------------------------------------------------------- #
# Static "Cheapest <Continent> Tour" SEO pages — server-rendered from live fares
# with the same greedy regional-circuit engine as the interactive builder.
# --------------------------------------------------------------------------- #
RTW_HUB_INFO2 = {
    "LON": ("Apr-Jun & Sep", "Visa-free, up to 6 months"),
    "PAR": ("Apr-Jun & Sep-Oct", "Visa-free, 90 days (Schengen)"),
    "TYO": ("Mar-May & Oct-Nov", "Visa-free, 90 days"),
    "ZRH": ("May-Sep", "Visa-free, 90 days (Schengen)"),
    "VIE": ("Apr-Oct", "Visa-free, 90 days (Schengen)"),
    "MUC": ("May-Sep", "Visa-free, 90 days (Schengen)"),
    "AUH": ("Nov-Mar", "Visa on arrival, 30 days"),
    "CGK": ("May-Sep (dry season)", "Visa on arrival, 30 days"),
    "YTO": ("May-Oct", "eTA required"), "YVR": ("Jun-Sep", "eTA required"),
}

REGION_TOURS = [
    {"key": "EUROPE", "name": "Europe", "slug": "cheap-europe-trip", "n": 4,
     "hubs": ["LON","PAR","FRA","AMS","MAD","BCN","FCO","IST","LIS","DUB","ZRH","VIE","CPH","MUC","ATH"],
     "intro": "Hop between Europe's great cities on cheap one-way fares &mdash; a multi-city tour for the price most people pay for one round-trip."},
    {"key": "ASIA", "name": "Asia", "slug": "cheap-asia-trip", "n": 4,
     "hubs": ["SIN","BKK","HKG","TYO","ICN","DEL","BOM","KUL","TPE","MNL","CGK","SGN"],
     "intro": "From street-food capitals to temple cities, string together a cheap multi-city Asia tour using the lowest one-way fares we track."},
    {"key": "LATAM", "name": "Latin America", "slug": "cheap-latin-america-trip", "n": 4,
     "hubs": ["MEX","GRU","BOG","EZE","LIM"],
     "intro": "Tour Latin America's biggest cities &mdash; Mexico City, Bogot&aacute;, Lima, S&atilde;o Paulo, Buenos Aires &mdash; on the cheapest one-ways we can find."},
    {"key": "AFRME", "name": "Africa & the Middle East", "slug": "cheap-africa-middle-east-trip", "n": 4,
     "hubs": ["JNB","CAI","NBO","CMN","DXB","DOH","AUH","TLV"],
     "intro": "From the pyramids to the Gulf's gleaming hubs, build a cheap multi-city Africa &amp; Middle East tour from live one-way fares."},
    {"key": "NORTHAM", "name": "North America", "slug": "cheap-north-america-trip", "n": 4,
     "hubs": ["ANC","YVR","YTO","SEA","SFO","DEN","ORD","MIA","MEX","SJO","KEF","GOH"],
     "intro": "From Alaska’s glaciers to Iceland’s volcanoes and Costa Rica’s cloud forests, string together a cheap multi-city North America &amp; North Atlantic trip on the lowest one-way fares we track."},
]
REGION_TOUR_BY_FILE = {}


def _hub_detail(code):
    best = BEST_TIME.get(code, "") or RTW_HUB_INFO2.get(code, ("", ""))[0]
    visa = DEST_INFO.get(code, {}).get("visa", "") or RTW_HUB_INFO2.get(code, ("", ""))[1]
    blurb = CITY_GUIDE.get(code, {}).get("overview", "")
    gfile = next((g["fname"] for g in CITY_GUIDES if g["code"] == code), "")
    return best, visa, blurb, gfile


def region_tour(world, hub_list, n_cities):
    allhubs = set(hub_list) | set(RTW_US_STARTS)
    leg = {}
    for r in world:
        a, b = r.get("o"), r.get("c")
        if a in allhubs and b in allhubs and a != b:
            if (a, b) not in leg or r["price"] < leg[(a, b)]["price"]:
                leg[(a, b)] = r
    pool = [h for h in hub_list if any((h, x) in leg for x in hub_list) or any((x, h) in leg for x in hub_list)]
    if len(pool) < 1:
        return None
    n = min(n_cities, len(pool))
    starts = [s for s in RTW_US_STARTS if s in allhubs]
    best = None
    for s in starts:
        for entry in pool:
            inL = leg.get((s, entry))
            if not inL:
                continue
            route = [entry]; used = {entry}; cur = entry; total = inL["price"]; legs = [inL]; ok = True
            for _ in range(n - 1):
                nb = None; nbL = None
                for c in pool:
                    if c in used:
                        continue
                    L = leg.get((cur, c))
                    if L and (nbL is None or L["price"] < nbL["price"]):
                        nbL = L; nb = c
                if nb is None:
                    ok = False; break
                route.append(nb); used.add(nb); legs.append(nbL); total += nbL["price"]; cur = nb
            if not ok:
                continue
            outL = leg.get((cur, s))
            if not outL:
                continue
            legs.append(outL); total += outL["price"]
            full = [s] + route + [s]
            if best is None or total < best[0]:
                best = (total, full, legs)
    if not best:
        return None
    total, route, legs = best
    out = []
    for i in range(len(route) - 1):
        a, b = route[i], route[i + 1]; L = legs[i]
        out.append({"from": a, "from_name": WORLD_HUBS.get(a, a), "to": b, "to_name": WORLD_HUBS.get(b, b),
                    "price": L["price"], "link": L.get("link", ""), "depart": L.get("depart", "")})
    return {"total": total, "cities": len(route) - 2, "route": route, "legs": out,
            "start": route[0], "start_name": WORLD_HUBS.get(route[0], route[0])}


def region_tour_faqs(m, trip):
    name = m["name"]
    if trip:
        cost_clause = f"about ${trip['total']:,.0f} in flights"
        ncities = trip["cities"]
    else:
        cost_clause = "based on the cheapest live one-way fares we can chain together"
        ncities = 4
    return [
        (f"How much does it cost for a trip around {name}?",
         f"Right now the cheapest {ncities}-city {name} trip we can build from live "
         f"one-way fares is {cost_clause}. It changes daily as fares move &mdash; this page refreshes "
         f"with the current low."),
        (f"What's the cheapest way to travel around {name}?",
         "Fly one-way between cities instead of booking separate round-trips. Chaining cheap one-ways into a loop "
         "is almost always cheaper, and it's exactly what this tool finds."),
        (f"Can I build my own {name} trip?",
         f"Yes &mdash; use the interactive builder to set the number of cities, your budget, and a must-visit "
         f"city, then share your route."),
    ]


def body_region_tour(m, world, today):
    trip = region_tour(world, m["hubs"], m["n"])
    builder = f'around-the-world.html?scope={m["key"]}'
    if not trip:
        return (f'<div class="wrap blog-wrap"><div class="pagehead"><h1>Cheap {html.escape(m["name"])} Trip</h1>'
                f'<p>We couldn&rsquo;t assemble a full {html.escape(m["name"])} loop from today&rsquo;s fares &mdash; '
                f'try the <a href="{builder}" style="color:var(--gold)">interactive builder</a> or check back after the '
                f'next refresh.</p></div></div>')
    rows = []
    for i, l in enumerate(trip["legs"], 1):
        best, visa, blurb, gfile = _hub_detail(l["to"])
        meta = []
        if best:
            meta.append("Best time: " + html.escape(best))
        if visa:
            meta.append(html.escape(visa))
        g = f' <a href="{gfile}" style="color:var(--gold)">city guide &rarr;</a>' if gfile else ""
        blurb_html = ('<span class="rtw-blurb">' + html.escape(blurb[:170]) + '</span> ') if blurb else ""
        meta_html = ('<span class="rtw-meta">' + " &middot; ".join(meta) + '</span>') if meta else ""
        detail = ('<div class="rtw-detail">' + blurb_html + meta_html + g + '</div>') if (blurb or meta or g) else ""
        lk = html.escape(l["link"], quote=True)
        rows.append(
            f'<div class="rtw-leg"><span class="rtw-num">{i}</span>'
            f'<div class="rtw-cities">{flag_img(l["from"])}<span class="rtw-city">{html.escape(l["from_name"])}</span>'
            f'<span class="rtw-arrow">&rarr;</span>{flag_img(l["to"])}<span class="rtw-city">{html.escape(l["to_name"])}</span></div>'
            f'<div class="rtw-legright"><span class="rtw-legprice">${l["price"]:,.0f}</span>'
            f'<span class="rtw-legunit">one-way</span>'
            f'<a class="mini-book" href="{lk}" target="_blank" rel="noopener">See live price on Aviasales &rarr;</a></div></div>'
            + detail)
    first_link = html.escape(trip["legs"][0]["link"], quote=True)
    faq_items = "".join(f'<details class="art-q"><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>'
                        for q, a in region_tour_faqs(m, trip))
    others = [x for x in REGION_TOURS if x["key"] != m["key"]]
    other_links = "".join(f'<li><a href="{x["slug"]}.html">Cheap {html.escape(x["name"])} trip</a></li>' for x in others)
    return f"""<div class="wrap blog-wrap">
  <nav class="crumbs"><a href="around-the-world.html">Around the World</a> &rsaquo; {html.escape(m['name'])} trip</nav>
  <div class="blog-eyebrow">Multi-city trip &middot; updated {today}</div>
  <h1 class="blog-title">Cheap {html.escape(m['name'])} Trip</h1>
  <div class="art-meta">Updated {today} &middot; live fares &middot; {BRAND}</div>
  <p class="art-lede">{m['intro']}</p>
  <div class="rtw-hero"><div class="rtw-hero-label">Trip around {html.escape(m['name'])} from</div>
    <div class="rtw-hero-price">${trip['total']:,.0f}</div>
    <div class="rtw-hero-sub">{len(trip['legs'])} one-way flights &middot; {trip['cities']} cities in {html.escape(m['name'])} &middot; round-trip from {html.escape(trip['start_name'])}</div></div>
  <div class="rtw-route">{"".join(rows)}</div>
  <div class="blog-cta"><a class="btn-primary" href="{first_link}" target="_blank" rel="noopener">Start the trip &mdash; book leg 1 &rarr;</a>
    <a class="btn-ghost" href="{builder}">Customize this trip &rarr;</a></div>
  <section class="blog-sec"><h2>How this trip works</h2><p>This total is the full round-trip from <b>{html.escape(trip['start_name'])}</b> ({trip['start']}) &mdash; we fly you into {html.escape(m['name'])}, hop between {trip['cities']} cities on cheap one-ways, and fly you home. Want a different home airport? Pick yours in the <a href="{builder}" style="color:var(--gold)">builder</a>.</p></section>
  <section class="blog-sec"><h2>Frequently asked questions</h2>{faq_items}</section>
  <section class="blog-sec"><h2>More trips</h2><ul class="blog-list">{other_links}<li><a href="around-the-world.html">Build a full around-the-world loop</a></li></ul></section>
  <p class="finehint" style="text-align:center;margin-top:18px">Trips are built from recently-tracked one-way fares and refresh daily; each leg&rsquo;s live price is confirmed on Aviasales. Build your own pace, budget and must-visit city in the <a href="{builder}" style="color:var(--gold)">interactive builder</a>.</p>
</div>"""


# --------------------------------------------------------------------------- #
# Newsletter — dedicated signup/landing page + a deals RSS feed that the email
# platform (Beehiiv) can auto-send a weekly digest from. Form posts to the
# interim capture endpoint until the Beehiiv embed is wired in (one-line swap).
# --------------------------------------------------------------------------- #
def newsletter_rss(market):
    items = sorted(market, key=lambda m: m.get("price", 1e9))[:15]
    now = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<rss version="2.0"><channel>',
             f'<title>{BRAND} — Today\'s Cheapest Flights</title>',
             f'<link>{BASE_URL}/</link>',
             '<description>The cheapest real, bookable flights from the USA, refreshed daily.</description>',
             f'<lastBuildDate>{now}</lastBuildDate>']
    for m in items:
        city = html.escape(str(m.get("name", "")).split(",")[0])
        link = html.escape(m.get("link", BASE_URL), quote=True)
        price = m.get("price", 0)
        parts.append(
            f'<item><title>{city} from ${price:,.0f} (from {m.get("origin","")})</title>'
            f'<link>{link}</link>'
            f'<description>Cheap one-way to {city} — ${price:,.0f} from {m.get("origin","")}, '
            f'departing {html.escape(str(m.get("depart","")))}. Real, bookable fare tracked by {BRAND}.</description>'
            f'<guid isPermaLink="false">{m.get("origin","")}-{m.get("code","")}-{price:.0f}</guid>'
            f'<pubDate>{now}</pubDate></item>')
    parts.append('</channel></rss>')
    return "\n".join(parts)


def newsletter_weekly_rss(oneway, market):
    """Weekly digest feed for automated sending. Exactly ONE <item> per ISO week,
    whose <content:encoded> IS the full briefing. Point Beehiiv's RSS-to-send
    automation at this feed and each new week's item auto-builds and sends the
    email — no copy-paste. The guid is the ISO week, so it sends once per week
    even though the feed is regenerated on every daily build."""
    now_dt = datetime.now()
    yr, wk, _ = now_dt.isocalendar()
    guid = f"{yr}-W{wk:02d}"
    pub = now_dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
    # Subject line = a curiosity-gap hook led by the single best deal's number + city
    # (front-loaded so it survives mobile truncation). Falls back to a plain title.
    top = _hm_items(oneway, market)[:5]
    if top:
        _, _to, _tp = top[0]
        _tcity = str(_to.get("name", _to["code"])).split(",")[0]
        title = f"How is {_tcity} ${_tp:,.0f} right now? (+ this week's biggest drops)"
    else:
        title = f"The flight market this week — {now_dt.strftime('%b %d, %Y')}"
    issue = newsletter_issue_html(oneway, market)
    summary = "; ".join(
        f'{str(o.get("name", o["code"])).split(",")[0]} ${p:,.0f} ({pct:.0f}% below)'
        for pct, o, p in top)
    return "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">',
        '<channel>',
        f'<title>{BRAND} — Weekly Flight-Market Briefing</title>',
        f'<link>{BASE_URL}/newsletter.html</link>',
        '<description>One email a week: the biggest below-normal one-way drops from the USA, by region, plus one trip to book now.</description>',
        f'<lastBuildDate>{pub}</lastBuildDate>',
        '<item>',
        f'<title>{html.escape(title)}</title>',
        f'<link>{BASE_URL}/newsletter.html</link>',
        f'<guid isPermaLink="false">{guid}</guid>',
        f'<pubDate>{pub}</pubDate>',
        f'<description>{html.escape("This week's biggest below-normal one-way drops: " + summary + ".")}</description>',
        f'<content:encoded><![CDATA[{issue}]]></content:encoded>',
        '</item>',
        '</channel></rss>',
    ])


def body_newsletter(market, oneway, home=None):
    sample = sorted(market, key=lambda m: m.get("price", 1e9))[:5]
    sample_rows = "".join(
        f'<li>{flag_img(m["code"], "flag")} {html.escape(str(m["name"]).split(",")[0])} '
        f'&mdash; <b>${m["price"]:,.0f}</b> <span class="dt-dates">from {m["origin"]}</span></li>'
        for m in sample)
    faqs = [
        ("Is the newsletter free?", "Yes, completely free. We may earn a commission when you book through our links, at no extra cost to you."),
        ("How often will I hear from you?", "Once a week — a short research digest of the market's moves and one trip worth booking. No spam, ever."),
        ("What's in each issue?", "A research digest: how each country's fares moved week-over-week, the biggest movers judged against each route's own history, past and current top performers, and one recommended trip to book now while it's below normal."),
        ("How do you decide a fare is “below normal”?", "We compare the lowest one-way we've tracked for a route to that route's usual price — estimated from round-trip fares and the route's own price history. The bigger the gap, the better the deal. It's an honest research guide, not a guarantee or a prediction, and your live price is always confirmed on Aviasales before you book."),
        ("Can I unsubscribe anytime?", "Of course — one click in any email and you're off the list, no hard feelings."),
    ]
    faq_html = "".join(f'<details class="art-q"><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>'
                       for q, a in faqs)
    return f"""<div class="wrap" style="max-width:720px">
  <div class="pagehead"><h1>The weekly flight-market briefing</h1>
  <p>The only newsletter that treats airfare like a market. Every week you get the research: how each country&rsquo;s fares moved, what&rsquo;s below normal right now, and the one trip worth booking this week &mdash; from the {BRAND} data we track every single day. Free, one email a week, unsubscribe anytime.</p></div>
  <div class="signup" style="margin:0 0 22px"><div class="signup-inner">
    <h2>Get the weekly briefing</h2>
    <p>Free forever &middot; one email a week &middot; the week&rsquo;s movers + one trip to book now.</p>
    <form onsubmit="return nlSub(event)" style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center;max-width:440px;margin:8px auto 0">
      <input id="nl-email" type="email" required placeholder="you@email.com" autocomplete="email" style="flex:1;min-width:210px;background:#fffdf6;color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:15px">
      <select id="nl-airport" aria-label="Your home airport (optional)" style="flex:1;min-width:210px;background:#fffdf6;color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:15px">{city_options(home or {})}</select>
      <button class="book" type="submit" style="font-size:16px;padding:12px 26px">Join free &rarr;</button>
    </form>
    <p style="font-size:12.5px;color:var(--muted);margin-top:10px">Free &middot; one email a week &middot; unsubscribe anytime &middot; add your home airport for deals from your city.</p>
    <script>
    (function(){{try{{var h=JSON.parse(localStorage.getItem('fs_home')||'[]');if(h&&h.length){{var s=document.getElementById('nl-airport');if(s)s.value=h[0];}}}}catch(e){{}}}})();
    function nlSub(e){{e.preventDefault();var f=e.target;var v=(document.getElementById('nl-email').value||'').trim();if(!v)return false;var ap=(document.getElementById('nl-airport')||{{}}).value||'';if(ap){{try{{localStorage.setItem('fs_home',JSON.stringify([ap]));}}catch(e){{}}}}var fb=function(){{var u="{BEEHIIV_URL}";var q=u+(u.indexOf('?')<0?'?':'&')+'email='+encodeURIComponent(v);if(ap)q+='&home_airport='+encodeURIComponent(ap);window.location.href=q;}};fetch('/api/subscribe',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:v,home_airport:ap}})}}).then(function(r){{if(!r.ok)throw 0;f.innerHTML='<p style="font-size:1.05rem;color:var(--green);font-weight:600;margin:6px 0">&#10003; You&rsquo;re in! Check your inbox to confirm.</p>';}}).catch(function(){{fb();}});return false;}}</script>
  </div></div>
  <div class="blog-sec"><h2>How it works</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-top:6px">
    <div class="why-card"><span class="eyebrow" style="color:var(--green)">Step 1</span><h3 style="margin:6px 0 6px">We track airfare daily</h3><p style="margin:0;color:var(--muted)">Every day we scan U.S. fares to everywhere on earth &mdash; like a stock market for flights.</p></div>
    <div class="why-card"><span class="eyebrow" style="color:var(--green)">Step 2</span><h3 style="margin:6px 0 6px">We flag below-normal</h3><p style="margin:0;color:var(--muted)">When a fare drops under its usual price, we catch it &mdash; so a &ldquo;deal&rdquo; actually means below normal.</p></div>
    <div class="why-card"><span class="eyebrow" style="color:var(--green)">Step 3</span><h3 style="margin:6px 0 6px">You get the best, weekly</h3><p style="margin:0;color:var(--muted)">One short email a week: the biggest drops and the one trip worth booking right now.</p></div>
  </div></div>
  <div class="blog-sec"><h2>See a sample issue</h2>
  <p style="font-size:13.5px;color:var(--muted);margin-bottom:14px">Exactly what lands in your inbox &mdash; a recent issue, built from live data:</p>
  <div style="border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:0 10px 30px rgba(12,22,34,.10)">{newsletter_issue_html(oneway, market)}</div></div>
  <div class="blog-sec"><h2>What you get every week</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-top:6px">
    <div class="why-card"><h3 style="margin:0 0 8px">&#128205; One trip to book now</h3><p style="margin:0;color:var(--muted)">The single best below-normal one-way, with the normal price shown so you see the real saving.</p></div>
    <div class="why-card"><h3 style="margin:0 0 8px">&#129517; Deals from your part of the country</h3><p style="margin:0;color:var(--muted)">A standout fare from the East, the Middle, and the West &mdash; so there&rsquo;s always one near you.</p></div>
    <div class="why-card"><h3 style="margin:0 0 8px">&#128202; Honest research, not hype</h3><p style="margin:0;color:var(--muted)">Every fare judged against its own normal price. No fake &ldquo;90% off&rdquo; &mdash; just the truth.</p></div>
  </div>
  <p style="font-size:13px;color:var(--muted);margin-top:12px">Plus the market by region, this week&rsquo;s biggest movers, and plain-English takeaways &mdash; in one email, unsubscribe in a click.</p></div>
  <div class="blog-sec"><h2>A peek at this week&rsquo;s movers</h2>
  <ul class="blog-list">{sample_rows}</ul>
  <p style="font-size:13px;color:var(--muted)">A sample of what lands in your inbox &mdash; see the full board on the <a href="market.html" style="color:var(--gold)">Market</a>.</p></div>
  <div class="blog-sec"><h2>Frequently asked questions</h2>{faq_html}</div>
  <div class="signup" style="margin-top:10px"><div class="signup-inner">
    <h2>Catch your dream trip when the price drops</h2>
    <p>The biggest below-normal flight deals from the USA &mdash; and the one to book now. Free, once a week.</p>
    <a class="book" href="javascript:void(0)" onclick="var e=document.getElementById('nl-email');if(e){{e.scrollIntoView({{behavior:'smooth',block:'center'}});e.focus();}}return false;" style="display:inline-block;font-size:16px;padding:12px 28px;margin-top:6px">Join free &rarr;</a>
  </div></div>
</div>"""


def _credible_wow(series, avg):
    """Week-over-week move in a region's avg one-way, ONLY when it can be trusted:
    a prior point at least 5 days old, and a magnitude small enough that it reflects
    real price movement rather than a change in which routes are tracked. Returns the
    signed dollar delta, or None to suppress (young/unstable history)."""
    if len(series) < 2:
        return None
    try:
        latest = datetime.strptime(series[-1][0], "%Y-%m-%d")
    except ValueError:
        return None
    prior = None
    for ds, v in series[:-1]:
        try:
            if (latest - datetime.strptime(ds, "%Y-%m-%d")).days >= 5:
                prior = v
        except ValueError:
            continue
    if prior is None:
        return None
    delta = series[-1][1] - prior
    if abs(delta) > max(80.0, 0.30 * avg):   # composition artifact, not a real move
        return None
    return delta


def _email_region_index(oneway, market):
    """Per-region research signal for the briefing's market table. Built from the
    graded deal set so every number is honest today: avg one-way, deal density
    (share of routes below their normal price), route count, and a week-over-week
    move only when it's credible. Returns [(region, avg, density, n, delta), ...]."""
    agg = defaultdict(lambda: {"prices": [], "below": 0, "n": 0})
    for pct, o, p in _hm_items(oneway, market):
        reg = continent_of(o["code"])
        if reg not in INDEX_REGIONS:
            continue
        a = agg[reg]
        a["prices"].append(p)
        a["n"] += 1
        if pct > 0:
            a["below"] += 1
    hist = oneway_index_history()
    out = []
    for reg in INDEX_REGIONS:
        a = agg.get(reg)
        if not a or a["n"] == 0:
            continue
        avg = sum(a["prices"]) / a["n"]
        density = a["below"] / a["n"]
        out.append((reg, avg, density, a["n"], _credible_wow(hist.get(reg, []), avg)))
    return sorted(out, key=lambda r: -r[2])   # densest deals first


def _email_move_suffix(delta):
    """Small inline week-over-week tag appended after the avg; empty when not credible."""
    if delta is None:
        return ""
    if abs(delta) < 1:
        return ' &middot; <span style="color:#9b9582;font-size:12px">flat wk</span>'
    if delta < 0:
        return f' &middot; <span style="color:#2f6b46;font-size:12px;font-weight:bold">&#9660;${abs(delta):,.0f} wk</span>'
    return f' &middot; <span style="color:#b4532f;font-size:12px;font-weight:bold">&#9650;${abs(delta):,.0f} wk</span>'


_US_WEST = {"LAX","SFO","SEA","SAN","LAS","PHX","PDX","SJC","OAK","SLC","SMF","SNA","ONT","BUR","RNO","BOI","GEG","TUS","ANC","HNL","OGG","PSP","FAT","LGB","COS"}
_US_CENTRAL = {"ORD","MDW","DFW","DAL","IAH","HOU","DEN","MSP","STL","MCI","AUS","SAT","OKC","TUL","OMA","ICT","DSM","MKE","MSN","XNA","BNA","MEM","MSY","ABQ","ELP","LIT","JAN","SDF","CMH","IND","CVG"}
_US_EAST = {"JFK","EWR","LGA","BOS","IAD","DCA","BWI","PHL","MIA","FLL","MCO","ATL","CLT","RDU","TPA","PIT","BUF","PVD","BDL","ORF","JAX","SAV","CHS","RIC","CLE","DTW","GSP","PBI","RSW","GSO","ROC","SYR","ALB","MHT","PWM","DAB","MYR"}


def _us_region(code):
    """Coarse US region of a departure airport, for the newsletter's 'closest to you' block."""
    c = (code or "").upper()
    if c in _US_WEST:
        return "the West Coast"
    if c in _US_CENTRAL:
        return "the Middle"
    if c in _US_EAST:
        return "the East Coast"
    return None


def _flag_email(cc):
    """Small country-flag <img> for the email (flagcdn.com, loads in all clients).
    Empty string if the country code is missing/invalid."""
    cc = (cc or "").strip().lower()
    if len(cc) != 2 or not cc.isalpha():
        return ""
    return (f'<img src="https://flagcdn.com/w40/{cc}.png" width="24" height="18" alt="" '
            'style="vertical-align:middle;border-radius:3px;border:1px solid rgba(0,0,0,.12);margin-right:9px">')


def _pct_badge(pct):
    """Savings pill. Green '▼ NN% below' for real deals; a quiet 'near normal' tag
    when a fare isn't actually below normal (so we never show '▼ -5% below')."""
    if pct < 8:
        return ('<span style="background:#cbbf9e;color:#5b5440;font-family:Arial,Helvetica,sans-serif;font-size:11px;'
                'font-weight:bold;padding:3px 9px;border-radius:11px;white-space:nowrap">near normal</span>')
    return ('<span style="background:#2f6b46;color:#ffffff;font-family:Arial,Helvetica,sans-serif;font-size:11px;'
            f'font-weight:bold;padding:3px 9px;border-radius:11px;white-space:nowrap">&#9660; {pct:.0f}% below</span>')


def _email_tile_color(pct):
    """(bg, name_color, price_color) for a fare-heatmap tile — greener = more below
    normal. Email-safe solid fills, all in the Atlas green family."""
    if pct >= 40:
        return ("#2f6b46", "#ffffff", "#cfe8d8")
    if pct >= 30:
        return ("#3f8159", "#ffffff", "#d7ecdf")
    if pct >= 18:
        return ("#5e9a78", "#ffffff", "#eaf3ee")
    if pct >= 8:
        return ("#7fb195", "#1f3d2b", "#234f34")
    return ("#cdddca", "#3a5c47", "#6a7a64")


def _email_heatmap(items):
    """A compact 'fare heatmap' teaser: the top tracked fares as a grid of colored
    tiles (greener = further below normal), linking to the full live heatmap. A
    visual 'research tool' moment that drives clicks without a heavy image."""
    pool = [x for x in items if x[0] >= 5][:42]      # real below-normal deals only
    if len(pool) < 8:
        pool = items[:12]
    if len(pool) < 4:
        return ""
    n = len(pool)
    # Sample 12 evenly across the range so the grid shows a real gradient
    # (deepest-green best deals -> lighter good ones), like the live heatmap.
    idxs = sorted(set(int(round(i * (n - 1) / 11.0)) for i in range(12)))
    tiles = [pool[i] for i in idxs]
    cells = []
    for pct, o, p in tiles:
        bg, tc, pc = _email_tile_color(pct)
        city = html.escape(str(o.get("name", o["code"])).split(",")[0])
        cells.append(
            f'<td width="25%" style="background:{bg};border-radius:7px;padding:11px 5px;text-align:center">'
            f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:11.5px;font-weight:bold;color:{tc};line-height:1.25">{city}</div>'
            f'<div style="font-family:\'Courier New\',Courier,monospace;font-size:13px;color:{pc}">${p:,.0f}</div></td>')
    rows = ""
    for i in range(0, len(cells), 4):
        row = cells[i:i + 4]
        row += ['<td width="25%"></td>'] * (4 - len(row))
        rows += f'<tr>{"".join(row)}</tr>'
    hm = f"{BASE_URL}/heatmap.html"
    return (
        _email_section("The fare heatmap",
                       "Every tracked fare at a glance. The greener the tile, the further below normal.")
        + f'<a href="{hm}" style="text-decoration:none;color:inherit"><table width="100%" cellpadding="0" cellspacing="0" '
          f'style="border-collapse:separate;border-spacing:5px;margin:0 0 4px">{rows}</table></a>'
        + f'<div style="text-align:center;margin-top:12px"><a href="{hm}" style="background:#2c2a1e;color:#ffffff;'
          'text-decoration:none;padding:13px 28px;border-radius:9px;font-size:14px;font-weight:bold;display:inline-block;'
          'font-family:Arial,Helvetica,sans-serif">See the full live heatmap &rarr;</a></div>')


def _email_section(label, sub):
    """Editorial section header: an uppercase letter-spaced kicker over a brass
    hairline (the cartographer's ruling), with a quiet descriptive line."""
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 12px"><tr>'
        '<td style="border-bottom:1px solid #d8c9a3;padding-bottom:8px">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;letter-spacing:2.5px;'
        f'text-transform:uppercase;color:#2f6b46;font-weight:bold">{label}</div>'
        f'<div style="font-size:12.5px;color:#9b9582;margin-top:4px;line-height:1.5">{sub}</div>'
        '</td></tr></table>')


DEAL_GUIDE_TIPS = [
    ("Judge it against normal, not the sticker.",
     "A price only means something next to the route&rsquo;s usual fare. The board shows how far below normal each one sits, so a deal is actually a deal and not just a big number."),
    ("If you&rsquo;d really fly it, book it fast.",
     "The cheapest one-ways are often a handful of seats. A genuine drop rarely waits for the weekend, so treat it like the seat is already gone."),
    ("Stay flexible on dates and airport.",
     "Shifting your departure by a day, or leaving from a nearby hub, is usually where the savings hide. Flexibility is the cheapest upgrade you have."),
    ("Book the flight first, plan the rest after.",
     "The cheap one-way out is the hard part. Lock the seat, then add the return, the hotel, and the eSIM once you know the trip is on."),
    ("Confirm the live price before you pay.",
     "We show the freshest fare we&rsquo;ve tracked. Your real, bookable price is always the one on Aviasales, so check it there before you commit."),
]


def _email_deal_guide():
    """Highlight for the week: a compact teaser for the standalone Flight Deal Guide
    (published in Guides), with the five headlines and a link to the full page."""
    rows = []
    for i, (head, _body) in enumerate(DEAL_GUIDE_TIPS, 1):
        rows.append(
            '<tr>'
            '<td width="30" valign="top" style="padding:0 0 10px">'
            '<div style="width:24px;height:24px;border-radius:50%;background:#2f6b46;color:#ffffff;'
            'font-family:Georgia,serif;font-size:13px;font-weight:bold;text-align:center;line-height:24px">'
            f'{i}</div></td>'
            '<td valign="top" style="padding:0 0 10px">'
            f'<div style="font-family:Georgia,serif;font-size:14.5px;font-weight:bold;color:#2c2a1e">{head}</div>'
            '</td></tr>')
    return (
        _email_section("This week&rsquo;s guide: The Flight Deal Guide",
                       "Five things that turn a cheap fare into a booked trip.")
        + '<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 26px"><tr>'
        '<td style="border:1px solid #d8c9a3;border-radius:12px;padding:20px 22px 16px;background:#ffffff">'
        '<table cellpadding="0" cellspacing="0" width="100%">'
        + "".join(rows)
        + '</table>'
        '<div style="text-align:center;margin-top:6px">'
        f'<a href="{BASE_URL}/flight-deal-guide.html" style="background:#2f6b46;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:9px;font-size:14px;font-weight:bold;display:inline-block;font-family:Arial,Helvetica,sans-serif">Read the full guide &rarr;</a>'
        '</div></td></tr></table>')


_HERO_PHOTO_CACHE = {}


def _hero_photo(city):
    """(image_url, short_blurb, coords) for a destination, from Wikipedia's REST
    summary. Build-time + in-memory cached, wrapped so ANY failure just returns
    ('','','') and the hero renders without it. Never breaks the build. coords is
    a navigation-style 'NN.N°N  NN.N°E' string (the 'explorer's dateline')."""
    key = (city or "").strip()
    if not key:
        return ("", "", "")
    if key in _HERO_PHOTO_CACHE:
        return _HERO_PHOTO_CACHE[key]
    out = ("", "", "")
    try:
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(key.replace(" ", "_"))
        req = urllib.request.Request(url, headers={"User-Agent": "MagellanFlights-newsletter/1.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read().decode("utf-8"))
        # Use the API's thumbnail URL EXACTLY as given. Wikimedia only serves a
        # fixed (and unpredictable) list of thumbnail widths, so any width edit can
        # 400; the API-provided URL is always valid. ~320px, soft on a wide banner
        # but it reliably loads.
        img = (data.get("thumbnail") or {}).get("source", "")
        blurb = (data.get("extract") or "").strip()
        if blurb:
            first = blurb.split(". ")[0].strip().rstrip(".")
            blurb = (first + ".")[:190]
        coords = ""
        c = data.get("coordinates") or {}
        if c.get("lat") is not None and c.get("lon") is not None:
            la, lo = float(c["lat"]), float(c["lon"])
            coords = (f"{abs(la):.1f}°{'N' if la >= 0 else 'S'}  "
                      f"{abs(lo):.1f}°{'E' if lo >= 0 else 'W'}")
        out = (img, blurb, coords)
    except Exception:
        out = ("", "", "")
    _HERO_PHOTO_CACHE[key] = out
    return out


def _mistake_fare(oneway, market):
    """Spotlight the single most exceptional one-way of the week — a *possible*
    mistake/error fare. Judged against each route's OWN recent one-way history
    (ONEWAY_PRICE_HISTORY), NOT a global benchmark: the benchmark assumes a typical
    one-way/round-trip ratio and so over-flags routes whose one-ways are structurally
    cheap (Kutaisi's one-way is always ~$240 — not a mistake). A route trips this only
    when today's fare is dramatically below what THAT route's own one-way usually costs.

    Returns {o, price, typ, pct, code} or None. It needs a few of the route's own
    observations before it will say anything, so it stays silent until that baseline
    accrues — silence is the correct, honest default, not a bug. (The 4x/day CI runs
    fill the baseline within a couple of days.)"""
    cheapest = {}                                # cheapest CURRENT one-way per non-US destination
    for o in oneway:
        if (o.get("cc") or "").upper() == "US":
            continue
        code = o.get("code")
        if not code:
            continue
        try:
            p = float(o["price"])
        except (TypeError, ValueError):
            continue
        if p <= 0:
            continue
        if code not in cheapest or p < float(cheapest[code]["price"]):
            cheapest[code] = o
    best = None
    for code, o in cheapest.items():
        try:
            p = float(o["price"])
        except (TypeError, ValueError):
            continue
        series = [v for v in ONEWAY_PRICE_HISTORY.get(code, []) if v and v > 0]
        if len(series) < 5:                      # not enough of THIS route's own history yet -> stay silent
            continue
        s = sorted(series)
        med = s[len(s) // 2]                      # the route's own normal one-way (robust to a stray low)
        if med <= 0 or p <= 0:
            continue
        if p < med * 0.15:                        # absurdly below even its own normal -> phantom, not a fare
            continue
        if p > med * 0.60:                        # not dramatically below its own normal -> not a mistake
            continue
        pct = (med - p) / med * 100.0
        if pct > 70.0:                            # cap; never over-claim a discount we can't stand behind
            pct = 70.0
        if best is None or pct > best["pct"]:
            best = {"o": o, "price": p, "typ": med, "pct": pct, "code": code}
    return best


def _email_rare_fare(mf):
    """The 'Rare Fare' alert — only rendered when _mistake_fare finds one. Framed
    honestly: an exceptional drop that *may* be a pricing error and won't last, with a
    verify-before-you-book caveat, so we never over-promise on a fare we can't re-check."""
    if not mf:
        return ""
    o = mf["o"]
    city = html.escape(str(o.get("name", o["code"])).split(",")[0])
    country = html.escape(country_from_name(str(o.get("name", ""))))
    loc = f"{city}, {country}" if country and country != city else city
    origin = html.escape(o.get("origin", ""))
    link = html.escape(o.get("link", BASE_URL + "/market.html"), quote=True)
    p, typ = mf["price"], mf["typ"]
    normally = (f'<s style="color:#9b9582;font-weight:normal;font-size:15px">normally ~${typ:,.0f}</s>'
                if typ > p else '')
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 0 26px">'
        '<tr><td style="border:2px solid #2f6b46;border-radius:14px;background:#ffffff;padding:0">'
        '<div style="background:#2f6b46;border-radius:11px 11px 0 0;padding:9px 18px">'
        '<span style="font-family:Arial,Helvetica,sans-serif;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#ffffff;font-weight:bold">Rare Fare Alert</span>'
        '<span style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#bfe0cb;margin-left:8px">possible mistake fare</span>'
        '</div>'
        '<div style="padding:20px 22px">'
        f'<div style="font-size:25px;font-weight:bold;color:#2c2a1e;line-height:1.15;margin-bottom:2px">{_flag_email(o.get("cc"))}{loc}</div>'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#9b9582;margin-bottom:12px">one-way from {origin}</div>'
        '<table cellpadding="0" cellspacing="0" style="margin:0 0 14px"><tr>'
        f'<td style="font-family:Georgia,serif;font-size:44px;font-weight:bold;color:#2f6b46;line-height:0.9;vertical-align:middle">${p:,.0f}</td>'
        f'<td style="padding-left:14px;vertical-align:middle">{normally}'
        '<div style="margin-top:5px"><span style="background:#2f6b46;color:#ffffff;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:bold;padding:3px 9px;border-radius:11px;white-space:nowrap">&#9660; more than half off</span></div></td>'
        '</tr></table>'
        '<div style="font-size:13px;color:#5b5440;font-style:italic;line-height:1.55;margin-bottom:16px">A fare this far below normal is the kind that&rsquo;s sometimes an airline pricing error, and those can vanish within hours. We can&rsquo;t guarantee it&rsquo;ll still be live; confirm the price on the next screen before you book.</div>'
        f'<a href="{link}" style="background:#2f6b46;color:#ffffff;text-decoration:none;padding:14px 30px;border-radius:9px;font-size:15px;font-weight:bold;display:inline-block;font-family:Arial,Helvetica,sans-serif">Verify &amp; book now &rarr;</a>'
        '</div>'
        '</td></tr></table>')


def newsletter_issue_html(oneway, market, world=None):
    """Email-safe (inline-styled) research briefing: a book-now pick, a featured
    around-the-world loop, the market by region, and this week's biggest drops."""
    items = _hm_items(oneway, market)
    issued = datetime.now().strftime("%B %d, %Y")

    # --- Rare Fare alert: one exceptional, possible-mistake fare (usually None) ---
    mf = _mistake_fare(oneway, market)
    mf_code = mf["o"].get("code") if mf else None
    if mf_code:                                   # spotlight it once; drop it from the normal sections
        items = [it for it in items if it[1].get("code") != mf_code]
    rare_fare_section = _email_rare_fare(mf)

    # --- Fare Watch: a one-line market-mood signature (the honest home for "research") ---
    graded = [pct for pct, _, _ in items]
    share = (sum(1 for x in graded if x > 0) / len(graded) * 100) if graded else 0
    if share >= 75:
        mood = "a strong week to buy"
    elif share >= 55:
        mood = "a good week to buy"
    elif share >= 35:
        mood = "a mixed week, be picky"
    else:
        mood = "a quiet week, wait for drops"
    fare_watch = (
        '<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px"><tr>'
        '<td style="background:#eef4ec;border:1px solid #cfe0d2;border-radius:8px;padding:9px 14px;font-family:Georgia,serif;font-size:13px;color:#2c2a1e">'
        f'<b style="color:#2f6b46">Fare Watch:</b> {share:.0f}% of the routes we track are below their normal price right now, {mood}.'
        '</td></tr></table>') if graded else ""

    # --- Section: one trip to book now (the single best below-normal fare) ---
    hero_html = ""
    if items:
        hpct, ho, hp = items[0]
        hcity = html.escape(str(ho.get("name", ho["code"])).split(",")[0])
        hcountry = html.escape(country_from_name(str(ho.get("name", ""))))
        horigin = html.escape(ho.get("origin", ""))
        hlink = html.escape(ho.get("link", BASE_URL + "/market.html"), quote=True)
        loc = f"{hcity}, {hcountry}" if hcountry and hcountry != hcity else hcity
        hnorm = hp / (1 - hpct / 100.0) if 0 < hpct < 90 else 0
        norm_str = (f' <s style="color:#9b9582;font-weight:normal;font-size:16px;vertical-align:middle">normally ~${hnorm:,.0f}</s>'
                    if hnorm > hp else '')
        photo_url, blurb, coords = _hero_photo(hcity)
        photo_banner = (
            f'<img src="{html.escape(photo_url, quote=True)}" width="600" alt="{hcity}" '
            'style="display:block;width:100%;height:190px;object-fit:cover;border-radius:13px 13px 0 0">'
        ) if photo_url else ''
        blurb_html = (
            f'<div style="font-size:13.5px;color:#5b5440;font-style:italic;line-height:1.55;margin:2px 0 16px">{html.escape(blurb)}</div>'
        ) if blurb else ''
        coords_cell = (
            f'<td align="right" style="font-family:Arial,Helvetica,sans-serif;font-size:10.5px;letter-spacing:1.5px;color:#b0a173;white-space:nowrap;vertical-align:middle">{html.escape(coords)}</td>'
        ) if coords else ''
        normally = (f'<div style="font-size:12px;color:#9b9582;text-decoration:line-through;margin-bottom:6px">normally ~${hnorm:,.0f}</div>'
                    if hnorm > hp else '')
        body_radius = '0 0 13px 13px' if photo_banner else '14px'
        hero_html = (
            '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;margin:0 0 28px">'
            '<tr><td style="border:1px solid #2f6b46;border-radius:14px;padding:0">'
            f'{photo_banner}'
            f'<div style="background:#ffffff;padding:22px 24px;border-radius:{body_radius}">'
            '<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 2px"><tr>'
            '<td style="font-family:Arial,Helvetica,sans-serif;font-size:11px;letter-spacing:2.5px;text-transform:uppercase;color:#2f6b46;font-weight:bold;vertical-align:middle">Book this week</td>'
            f'{coords_cell}'
            '</tr></table>'
            f'<div style="font-size:27px;font-weight:bold;margin:7px 0 2px;color:#2c2a1e;line-height:1.15">{_flag_email(ho.get("cc"))}{loc}</div>'
            f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#9b9582;margin:0 0 12px">one-way from {horigin}</div>'
            f'{blurb_html}'
            '<table cellpadding="0" cellspacing="0" style="margin:0 0 18px"><tr>'
            f'<td style="font-family:Georgia,serif;font-size:46px;font-weight:bold;color:#2f6b46;line-height:0.9;vertical-align:middle">${hp:,.0f}</td>'
            f'<td style="padding-left:14px;vertical-align:middle;font-family:Arial,Helvetica,sans-serif">{normally}{_pct_badge(hpct)}</td>'
            '</tr></table>'
            f'<a href="{hlink}" style="background:#2f6b46;color:#ffffff;text-decoration:none;padding:14px 30px;border-radius:9px;font-size:15px;font-weight:bold;display:inline-block;font-family:Arial,Helvetica,sans-serif">See live price &amp; book &rarr;</a>'
            '</div>'
            '</td></tr></table>')

    # --- Section: cheapest one-way to EACH region (actionable geographic spread) ---
    rc = {}
    for pct, o, p in items:
        reg = continent_of(o.get("code", ""))
        if reg not in INDEX_REGIONS:
            continue
        if reg not in rc or p < rc[reg][2]:
            rc[reg] = (pct, o, p)
    reg_rows = ""
    for reg in sorted(rc, key=lambda r: rc[r][2]):          # cheapest region first
        pct, o, p = rc[reg]
        city = html.escape(str(o.get("name", o["code"])).split(",")[0])
        origin = html.escape(o.get("origin", ""))
        link = html.escape(o.get("link", ""), quote=True)
        reg_rows += (
            '<tr>'
            f'<td style="padding:11px 0;border-bottom:1px solid #e0d4b3;font-family:Arial,Helvetica,sans-serif;font-size:10.5px;letter-spacing:1px;text-transform:uppercase;color:#9b9582;white-space:nowrap;vertical-align:middle">{html.escape(reg)}</td>'
            f'<td style="padding:11px 0 11px 14px;border-bottom:1px solid #e0d4b3;font-family:Georgia,serif;font-size:15px;color:#2c2a1e">'
            f'{_flag_email(o.get("cc"))}<a href="{link}" style="color:#2c2a1e;text-decoration:none;font-weight:bold">{city}</a> '
            f'<span style="color:#9b9582;font-size:12px">from {origin}</span></td>'
            f'<td align="right" style="padding:11px 0;border-bottom:1px solid #e0d4b3;font-family:Georgia,serif;white-space:nowrap"><span style="font-size:16px;font-weight:bold;color:#2c2a1e">${p:,.0f}</span> &nbsp;{_pct_badge(pct)}</td>'
            '</tr>')
    market_section = (
        _email_section("Cheapest to each region",
                       "The single lowest below-normal one-way to each part of the world right now.")
        + f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px">{reg_rows}</table>') if reg_rows else ""

    # --- Section: the fare heatmap (compact teaser -> full live heatmap) ---
    heatmap_section = _email_heatmap(items)

    # --- Section: this week's biggest below-normal drops (excludes the hero) ---
    rows = ""
    for i, (pct, o, p) in enumerate(items[1:8]):
        city = html.escape(str(o.get("name", o["code"])).split(",")[0])
        origin = html.escape(o.get("origin", ""))
        link = html.escape(o.get("link", ""), quote=True)
        bg = "#ffffff" if i % 2 == 0 else "#f7f0dd"
        rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:13px 14px;font-family:Georgia,serif;font-size:16px;color:#2c2a1e">'
            f'{_flag_email(o.get("cc"))}<a href="{link}" style="color:#2c2a1e;text-decoration:none;font-weight:bold">{city}</a> '
            f'<span style="color:#9b9582;font-size:12px">from {origin}</span></td>'
            f'<td align="right" style="padding:13px 14px;font-family:Georgia,serif;white-space:nowrap">'
            f'<span style="font-size:19px;font-weight:bold;color:#2c2a1e">${p:,.0f}</span> &nbsp; {_pct_badge(pct)}</td></tr>')
    drops_section = ""
    if rows:
        # Honest framing: these are the steepest below-NORMAL fares (vs each route's
        # benchmark), not week-over-week drops — genuine drops get their own section.
        drops_section = (
            _email_section("Cheapest below normal right now",
                           "The steepest below-normal one-ways from the USA right now. Tap a city to book.")
            + f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #e3d8b8;border-radius:12px;overflow:hidden;margin:0 0 26px">{rows}</table>')

    # --- Section: fares that GENUINELY dropped vs their own recent price history ---
    # Uses each route's own one-way price log (ONEWAY_PRICE_HISTORY), so "dropped"
    # means the fare actually fell this week — not merely cheap vs a broad benchmark.
    fell_rows = ""
    skip_codes = {mf_code} | ({items[0][1].get("code")} if items else set())
    fell = []
    for o in oneway:
        code = o.get("code")
        if not code or code in skip_codes:
            continue
        series = [v for v in ONEWAY_PRICE_HISTORY.get(code, []) if v and v > 0]
        if len(series) < 10:
            continue
        base_pool = sorted(series[:-3])
        base = base_pool[len(base_pool) // 2]
        try:
            now = float(o.get("price") or series[-1])
        except (TypeError, ValueError):
            continue
        if base and now < base * 0.85 and (base - now) >= 30:
            fell.append((round((base - now) / base * 100), o, now, base))
    fell.sort(key=lambda t: -t[0])
    for i, (dpct, o, now, base) in enumerate(fell[:3]):
        city = html.escape(str(o.get("name", o["code"])).split(",")[0])
        origin = html.escape(o.get("origin", ""))
        link = html.escape(o.get("link", ""), quote=True)
        bg = "#ffffff" if i % 2 == 0 else "#f7f0dd"
        fell_rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:13px 14px;font-family:Georgia,serif;font-size:16px;color:#2c2a1e">'
            f'{_flag_email(o.get("cc"))}<a href="{link}" style="color:#2c2a1e;text-decoration:none;font-weight:bold">{city}</a> '
            f'<span style="color:#9b9582;font-size:12px">from {origin}</span></td>'
            f'<td align="right" style="padding:13px 14px;font-family:Georgia,serif;white-space:nowrap">'
            f'<s style="color:#9b9582;font-size:13px">${base:,.0f}</s> '
            f'<span style="font-size:19px;font-weight:bold;color:#2f6b46">${now:,.0f}</span> '
            f'<span style="font-family:Arial,Helvetica,sans-serif;font-size:11.5px;font-weight:bold;color:#2f6b46">&#9660;{dpct}%</span></td></tr>')
    fell_section = ""
    if fell_rows:
        fell_section = (
            _email_section("Dropped this week",
                           "Fares that actually fell against their own recent price history. Watch these.")
            + f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid #cfe0d2;border-radius:12px;overflow:hidden;margin:0 0 26px">{fell_rows}</table>')

    # --- Section: deals from YOUR airport (CTA to the live, interactive page) ---
    # Email can't take live input, so we route the personalization to the site.
    airport_section = (
        '<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px"><tr>'
        '<td style="background:#eef4ec;border:1px solid #cfe0d2;border-radius:12px;padding:22px 20px;text-align:center">'
        '<div style="font-size:17px;font-weight:bold;color:#2c2a1e;margin-bottom:5px">Want deals from <i>your</i> airport?</div>'
        '<div style="font-size:13.5px;color:#5b5440;margin-bottom:14px;line-height:1.55">Pick your home airport and see the cheapest routes abroad leaving from near you, live and updated every day.</div>'
        f'<a href="{BASE_URL}/airports.html" style="background:#2f6b46;color:#ffffff;text-decoration:none;padding:13px 26px;border-radius:9px;font-size:14px;font-weight:bold;display:inline-block">See cheapest routes from your airport &rarr;</a>'
        '</td></tr></table>')

    # --- Section: Trip of the week — the cheapest around-the-world loop ---
    if world is None:
        try:
            world = read_world(kind="any")
        except Exception:
            world = []
    atw_section = ""
    try:
        _trip = round_the_world(world) if world else None
    except Exception:
        _trip = None
    if _trip:
        _route = " &rarr; ".join(html.escape(c) for c in ([_trip["start"]] + [L["to"] for L in _trip["legs"]]))
        atw_section = (
            _email_section("Trip of the week: around the world",
                           "The cheapest full loop we can build right now, every leg a real, bookable one-way.")
            + '<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 26px"><tr>'
            '<td style="border:1px solid #2f6b46;border-radius:12px;padding:20px 22px;background:#ffffff">'
            f'<div style="font-family:Georgia,serif;font-size:21px;font-weight:bold;color:#2c2a1e;margin:0 0 3px">{html.escape(_trip["start_name"])} &rarr; around the world &rarr; home</div>'
            f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#9b9582;margin:0 0 12px">{_trip["stops"]} stops &middot; {_trip["flights"]} one-way flights</div>'
            '<table cellpadding="0" cellspacing="0" style="margin:0 0 14px"><tr>'
            f'<td style="font-family:Georgia,serif;font-size:40px;font-weight:bold;color:#2f6b46;line-height:0.9;vertical-align:middle">${_trip["total"]:,.0f}</td>'
            '<td style="padding-left:12px;vertical-align:middle;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#9b9582">for the<br>whole loop</td>'
            '</tr></table>'
            f'<div style="font-family:Georgia,serif;font-size:13.5px;color:#5b5440;line-height:1.6;margin:0 0 14px">{_route}</div>'
            f'<a href="{BASE_URL}/around-the-world.html?start={html.escape(_trip["start"], quote=True)}" style="background:#2f6b46;color:#ffffff;text-decoration:none;padding:13px 26px;border-radius:9px;font-size:14px;font-weight:bold;display:inline-block;font-family:Arial,Helvetica,sans-serif">Build this trip &rarr;</a>'
            '</td></tr></table>')

    return (
        '<div style="max-width:600px;margin:0 auto;font-family:Georgia,serif;color:#2c2a1e">'
        '<div style="background:#2f6b46;padding:30px 26px 26px;text-align:center;border-radius:16px 16px 0 0">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;letter-spacing:4px;text-transform:uppercase;color:#bfe0cb;font-weight:bold">Magellan Flights</div>'
        '<div style="font-family:Georgia,serif;font-size:34px;font-weight:bold;color:#ffffff;margin:11px 0 9px;letter-spacing:.5px">The Flight Market</div>'
        '<div style="font-size:1px;line-height:1px"><span style="display:inline-block;width:84px;border-top:1px solid #7bb392">&nbsp;</span></div>'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:10.5px;letter-spacing:2.5px;text-transform:uppercase;color:#9fd0b0;margin-top:9px">Weekly Briefing &middot; {issued}</div>'
        '</div>'
        '<div style="background:#f3ecd8;padding:24px 26px">'
        f'{fare_watch}'
        f'{rare_fare_section}'
        f'{hero_html}'
        f'{atw_section}'
        f'{fell_section}'
        f'{drops_section}'
        f'{airport_section}'
        f'{market_section}'
        f'{heatmap_section}'
        f'{_email_deal_guide()}'
        '<table width="100%" cellpadding="0" cellspacing="0" style="margin:18px 0 0"><tr><td style="background:#ffffff;border:1px dashed #c9b88e;border-radius:12px;padding:18px 20px;text-align:center">'
        '<div style="font-size:15px;color:#2c2a1e;font-weight:bold;margin-bottom:4px">Know a fellow deal-hunter?</div>'
        '<div style="font-size:13px;color:#7a715a;margin-bottom:10px;line-height:1.5">Forward this email. They can get the weekly briefing free, and the more of us watching the market, the better it gets.</div>'
        f'<a href="{BASE_URL}/newsletter.html" style="color:#2f6b46;text-decoration:none;font-weight:bold;font-size:13px">Send a friend to magellanflights.com/newsletter &rarr;</a>'
        '</td></tr></table>'
        '</div>'
        '<div style="background:#e7ddc6;padding:18px 26px;border-radius:0 0 16px 16px;font-size:11.5px;color:#7a715a;text-align:center;line-height:1.6">'
        '<b style="color:#2c2a1e">How we judge &ldquo;below normal&rdquo;:</b> we compare the cheapest one-way we&rsquo;ve tracked to that route&rsquo;s usual price (estimated from round-trip fares and its own price history). An honest guide, not a guarantee. Your live price is always confirmed on Aviasales.'
        f'<br><br>You&rsquo;re getting this because you joined Magellan Flights at <a href="{BASE_URL}" style="color:#2f6b46">magellanflights.com</a>. Unsubscribe anytime.'
        '</div>'
        '</div>')


def body_newsletter_issue(oneway, market):
    issue = newsletter_issue_html(oneway, market)
    return f"""<div class="wrap" style="max-width:720px">
  <div class="pagehead"><h1>Weekly issue generator</h1><p><b>Automated:</b> Beehiiv&rsquo;s RSS-to-send pulls this issue from <a href="newsletter.xml" style="color:var(--gold)">newsletter.xml</a> and emails it once a week with no copy-paste. Set it up once under <i>Automations &rarr; RSS</i> in Beehiiv (feed URL: <code>magellanflights.com/newsletter.xml</code>). <b>Manual fallback:</b> click <b>Copy issue</b>, open Beehiiv, create a new post, paste (Ctrl/Cmd-V), and send. Either way it refreshes automatically as the deals update. (Owner tool, not linked publicly.)</p></div>
  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:0 0 16px">
    <button class="book" id="nlcopy" onclick="nlCopy()" style="font-size:15px;padding:12px 26px;border:0;cursor:pointer">Copy issue</button>
    <span id="nlcopied" style="color:#2f6b46;font-weight:600"></span>
  </div>
  <div style="border:1px solid var(--line);border-radius:12px;overflow:hidden"><div id="nlpreview">{issue}</div></div>
  <script>
  function nlDone(){{ document.getElementById('nlcopied').textContent='Copied — paste into a new Beehiiv post.'; }}
  function nlCopy(){{ var el=document.getElementById('nlpreview'); try{{ var r=document.createRange(); r.selectNodeContents(el); var sel=window.getSelection(); sel.removeAllRanges(); sel.addRange(r); document.execCommand('copy'); sel.removeAllRanges(); nlDone(); }}catch(e){{ if(navigator.clipboard){{ navigator.clipboard.writeText(el.innerHTML).then(nlDone); }} }} }}
  </script>
</div>"""


# Owner tool: turn today's best fares into ready-to-post tweets. X killed free
# API posting, so this is the practical free path - one click opens the tweet
# pre-filled in X (or Copy to paste anywhere). Each links to the deal on the
# Market, which renders a rich Twitter card. Grounded voice: hedged "% below
# normal", no hype, no emoji.
DEAL_TWEET_HOOKS = [
    "{o} to {city}: ${p} one-way right now, about {pct}% below its usual price. We track fares daily so you catch the dip.",
    "Cheap one-way: {o} to {city} for ${p}, roughly {pct}% under its normal fare.",
    "{city} for ${p} one-way from {o}. About {pct}% below its typical price, tracked live.",
    "Fare watch: {o} to {city} is down to ${p} one-way, around {pct}% below normal.",
]


def body_deal_tweets(oneway, market):
    items = [it for it in _hm_items(oneway, market) if it[0] >= 12][:8]
    cards = []
    for i, (pct, o, price) in enumerate(items):
        code = o.get("code") or ""
        origin = o.get("origin") or ""
        city = (o.get("name") or code).split(",")[0].strip()
        if not code or not origin:
            continue
        url = f"{BASE_URL}/market.html?deal={origin}-{code}"
        line = DEAL_TWEET_HOOKS[i % len(DEAL_TWEET_HOOKS)].format(
            o=origin, city=city, p=f"{price:,.0f}", pct=round(pct))
        tweet = f"{line} {url}\n\n#cheapflights #travel #flightdeals"
        intent = "https://twitter.com/intent/tweet?text=" + quote(tweet)
        tid = f"tw{i}"
        cards.append(
            '<div class="panel" style="margin:0 0 14px;padding:16px 18px">'
            f'<div id="{tid}" style="font-size:15px;line-height:1.55;white-space:pre-wrap;color:var(--ink)">{html.escape(tweet)}</div>'
            '<div style="display:flex;gap:10px;margin-top:12px;flex-wrap:wrap">'
            f'<a class="book" href="{html.escape(intent, quote=True)}" target="_blank" rel="noopener" style="font-size:14px;padding:9px 18px">Post on X &rarr;</a>'
            f'<button class="btn-ghost" type="button" onclick="twCopy(\'{tid}\',this)" style="font-size:14px;padding:9px 16px;cursor:pointer">Copy</button>'
            '</div></div>')
    body_cards = "".join(cards) if cards else '<div class="wl-hint">No standout deals to tweet right now. Check back after the next data refresh.</div>'
    return f"""<div class="wrap" style="max-width:680px">
  <div class="pagehead"><h1>Deal tweets</h1><p>Ready-to-post tweets for today&rsquo;s best fares, biggest drop first. Click <b>Post on X</b> to open the tweet pre-filled (review it, then post), or <b>Copy</b> to paste anywhere. Each links to the deal on the Market, which renders a rich card on X. Posting 2 to 3 a week is the cheapest way to bring new eyes to the site. (Owner tool, not linked publicly.)</p></div>
  {body_cards}
  <script>
  function twCopy(id, btn){{ var el=document.getElementById(id); if(!el) return; var t=el.textContent; function done(){{ var o=btn.textContent; btn.textContent='Copied'; setTimeout(function(){{ btn.textContent=o; }},1500); }} function fb(){{ var ta=document.createElement('textarea'); ta.value=t; ta.style.position='fixed'; ta.style.opacity='0'; document.body.appendChild(ta); ta.select(); try{{document.execCommand('copy');}}catch(e){{}} ta.remove(); done(); }} if(navigator.clipboard&&navigator.clipboard.writeText){{ navigator.clipboard.writeText(t).then(done).catch(fb); }} else {{ fb(); }} }}
  </script>
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
    # Derive per-airport ONE-WAY deals from the global one-way dataset so the
    # "From my airport" board can toggle between round-trip and one-way pricing
    # (no extra scrape needed - reuses the one-ways we already track).
    ow_by_origin = {}
    for o in oneway:
        ow_by_origin.setdefault(o.get("origin", ""), []).append(o)
    for code, c in home.items():
        rows = sorted(ow_by_origin.get(code, []), key=lambda x: float(x["price"]))
        seen, owlist = set(), []
        for o in rows:
            dc = o.get("code")
            if not dc or dc in seen:
                continue
            seen.add(dc)
            cc = o.get("cc", "")
            owlist.append({"code": dc, "name": o.get("name", dc), "price": round(float(o["price"])),
                           "cc": cc, "depart": o.get("depart", ""), "link": o.get("link", "#"),
                           "t": lm_tags(cc)})
        c["oneway"] = owlist[:60]
    update_oneway_index_log(oneway)
    update_oneway_price_log(oneway)
    hist = oneway_index_history()
    global HIST_SERIES, ONEWAY_PRICE_HISTORY, FEATURED_VERIFIED, MONEY_PAGES, MONEY_BY_FILE, ROUTE_PAGES, ROUTE_BY_FILE, REGION_TOUR_BY_FILE, DAILY_WINNER
    HIST_SERIES = read_history_series()
    ONEWAY_PRICE_HISTORY = read_oneway_price_series()
    DAILY_WINNER = compute_daily_winner(market, HIST_SERIES)
    update_winners_log(DAILY_WINNER)
    try:
        FEATURED_VERIFIED = json.load(open(os.path.join(DATA_DIR, "featured_verified.json"), encoding="utf-8"))
    except Exception:
        FEATURED_VERIFIED = {}
    MONEY_PAGES = money_targets(home)
    MONEY_BY_FILE = {p["fname"]: p for p in MONEY_PAGES}
    ROUTE_PAGES = route_targets(market)
    ROUTE_BY_FILE = {p["fname"]: p for p in ROUTE_PAGES}
    REGION_TOUR_BY_FILE = {m["slug"] + ".html": m for m in REGION_TOURS}
    today = datetime.now().strftime("%B %d, %Y")
    summary = market_summary(market)
    cards_src = sorted(market, key=lambda m: signal_for(m["price"], m["benchmark"])[1], reverse=True)[:8]
    cards = "\n".join(card_html(m) for m in cards_src)

    pages = {
        "index.html": ("Home", body_home(market, hist, cards, lastmin, oneway, summary, world, home)),
        "market.html": ("Market", body_market(market, hist, cards, lastmin, oneway)),
        "heatmap.html": ("The Heatmap", body_heatmap(oneway, market)),
        "explore.html": ("Explore", body_explore(home)),
        "ask.html": ("Ask Magellan", body_ask()),
        "blog.html": ("Daily Guide", body_blog(market, oneway)),
        "around-the-world.html": ("Ferdinand's World Loop", body_rtw(world)),
        "consultant.html": ("Hire a Trip Consultant", body_consultant()),
        "newsletter.html": ("Free Newsletter", body_newsletter(market, oneway, home)),
        "newsletter-issue.html": ("Weekly issue", body_newsletter_issue(oneway, market)),
        "deal-tweets.html": ("Deal tweets", body_deal_tweets(oneway, market)),
        "airports.html": ("Captain's Log", body_airports(home)),
        "watchlist.html": ("Watchlist", body_watchlist(market)),
        "essentials.html": ("Travel essentials", body_essentials()),
        "travel-cards.html": ("Travel cards", body_cards()),
        "guides.html": ("Guides", body_guides(market)),
        "cheap-flights.html": ("By airport", body_money_hub(MONEY_PAGES)),
        "cheap-flight-index.html": ("Cheap Flight Index", body_cflindex(market, today)),
        "city-guides.html": ("City guides", body_cityguide_hub(CITY_GUIDES, market)),
        "our-story.html": ("Our Story", body_story(market, oneway, world)),
    }

    os.makedirs(SITE_DIR, exist_ok=True)
    for fname, (title, body) in pages.items():
        doc = render_page(fname, title, body, market, oneway, onewaylm, home, lastmin, world, worldlm, today)
        with open(os.path.join(SITE_DIR, fname), "w", encoding="utf-8") as f:
            f.write(doc)

    # Retired pages -> redirect stubs (old links + SEO survive; not in sitemap).
    REDIRECTS = {"world.html": "explore.html", "lastminute.html": "explore.html",
                 "trip.html": "around-the-world.html",
                 "cheap-europe-tour.html": "cheap-europe-trip.html",
                 "cheap-asia-tour.html": "cheap-asia-trip.html",
                 "cheap-latin-america-tour.html": "cheap-latin-america-trip.html",
                 "cheap-africa-middle-east-tour.html": "cheap-africa-middle-east-trip.html"}
    for old_f, target in REDIRECTS.items():
        stub = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
                "<title>Redirecting\u2026</title>\n"
                f"<link rel=\"canonical\" href=\"{BASE_URL}/{target}\">\n"
                f"<meta http-equiv=\"refresh\" content=\"0; url={target}\">\n"
                "<meta name=\"robots\" content=\"noindex\">\n"
                f"<script>location.replace(\"{target}\");</script>\n"
                f"</head>\n<body>Redirecting to <a href=\"{target}\">{target}</a>\u2026</body>\n</html>")
        with open(os.path.join(SITE_DIR, old_f), "w", encoding="utf-8") as f:
            f.write(stub)

    # Evergreen blog articles (one page per cluster).
    for a in ARTICLES:
        fname = a["slug"] + ".html"
        doc = render_page(fname, a["h1"], body_article(a, market), market,
                          oneway, onewaylm, home, lastmin, world, worldlm, today)
        with open(os.path.join(SITE_DIR, fname), "w", encoding="utf-8") as f:
            f.write(doc)

    # Money pages (one per departure airport).
    for p in MONEY_PAGES:
        doc = render_page(p["fname"], p["h1"], body_moneypage(p, today), market,
                          oneway, onewaylm, home, lastmin, world, worldlm, today)
        with open(os.path.join(SITE_DIR, p["fname"]), "w", encoding="utf-8") as f:
            f.write(doc)
    for p in ROUTE_PAGES:
        doc = render_page(p["fname"], p["h1"], body_route(p, market, today), market,
                          oneway, onewaylm, home, lastmin, world, worldlm, today)
        with open(os.path.join(SITE_DIR, p["fname"]), "w", encoding="utf-8") as f:
            f.write(doc)
    for m in REGION_TOURS:
        doc = render_page(m["slug"] + ".html", f"Cheap {m['name']} Trip", body_region_tour(m, world, today), market,
                          oneway, onewaylm, home, lastmin, world, worldlm, today)
        with open(os.path.join(SITE_DIR, m["slug"] + ".html"), "w", encoding="utf-8") as f:
            f.write(doc)

    # Evergreen per-city guide pages (deal + video + travel guide).
    for g in CITY_GUIDES:
        doc = render_page(g["fname"], g["h1"], body_cityguide(g, market, today), market,
                          oneway, onewaylm, home, lastmin, world, worldlm, today)
        with open(os.path.join(SITE_DIR, g["fname"]), "w", encoding="utf-8") as f:
            f.write(doc)

    all_files = (list(pages) + [a["slug"] + ".html" for a in ARTICLES]
                 + [p["fname"] for p in MONEY_PAGES]
                 + [g["fname"] for g in CITY_GUIDES]
                 + [p["fname"] for p in ROUTE_PAGES]
                 + [m["slug"] + ".html" for m in REGION_TOURS])
    # EVERGREEN ROUTE PAGES (SEO loop run 1, 2026-07-10): route pages are picked from
    # today's cheap fares, so they rotate daily and older ones drop out of the sitemap even
    # though the full page is still live in the repo. Include EVERY route-page file on disk so
    # our highest buyer-intent money pages ("cheap-flights-from-<city>-to-<dest>") stay indexed
    # instead of orphaning. Deduped; only adds files that already exist on disk.
    _seen = set(all_files)
    for _f in sorted(glob.glob(os.path.join(SITE_DIR, "cheap-flights-from-*-to-*.html"))):
        _b = os.path.basename(_f)
        if _b not in _seen:
            all_files.append(_b)
            _seen.add(_b)
    with open(os.path.join(SITE_DIR, "deals.xml"), "w", encoding="utf-8") as f:
        f.write(newsletter_rss(market))
    with open(os.path.join(SITE_DIR, "newsletter.xml"), "w", encoding="utf-8") as f:
        f.write(newsletter_weekly_rss(oneway, market))
    write_seo_files(all_files)
    print(f"Built {len(pages)} pages + {len(ARTICLES)} articles + {len(MONEY_PAGES)} money pages "
          f"+ {len(CITY_GUIDES)} city guides + {len(ROUTE_PAGES)} route pages + sitemap/robots -> {SITE_DIR}  "
          f"({len(market)} routes, {len(oneway)} one-ways, {len(home)} home airports)")


def write_seo_files(pages):
    """Emit sitemap.xml + robots.txt so search engines can crawl efficiently.

    `pages` is an iterable of page filenames to include in the sitemap.
    """
    lastmod = datetime.now().strftime("%Y-%m-%d")
    # Rough priority: home highest, then the deal boards, then helper pages.
    prio = {"index.html": "1.0", "market.html": "0.9", "world.html": "0.8",
            "explore.html": "0.8", "cheap-flights.html": "0.8",
            "city-guides.html": "0.8", "cheap-flight-index.html": "0.8", "newsletter.html": "0.7", "guides.html": "0.7", "blog.html": "0.7",
            "airports.html": "0.6"}
    article_files = set(globals().get("ARTICLE_BY_FILE", {}))
    money_files = set(globals().get("MONEY_BY_FILE", {}))
    route_files = set(globals().get("ROUTE_BY_FILE", {}))
    tour_files = set(globals().get("REGION_TOUR_BY_FILE", {}))
    cityguide_files = set(globals().get("CITYGUIDE_BY_FILE", {}))
    urls = []
    for fname in pages:
        if fname in ("newsletter-issue.html", "deal-tweets.html"):
            continue  # owner tools — keep out of sitemap
        loc = BASE_URL + "/" + ("" if fname == "index.html" else fname)
        cf = ("monthly" if fname in article_files
              else "weekly" if fname in cityguide_files or fname in route_files or fname in tour_files else "daily")
        dp = ("0.6" if fname in article_files or fname in route_files
              else "0.7" if fname in money_files or fname in cityguide_files or fname in tour_files else "0.5")
        urls.append(
            f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{cf}</changefreq>\n"
            f"    <priority>{prio.get(fname, dp)}</priority>\n  </url>")
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "\n".join(urls) + "\n</urlset>\n")
    with open(os.path.join(SITE_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap)
    _ai_bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Perplexity-User",
               "ClaudeBot", "Claude-Web", "Google-Extended", "Applebot-Extended", "CCBot"]
    _ai_block = "".join(f"User-agent: {bot}\nAllow: /\n\n" for bot in _ai_bots)
    robots = (f"User-agent: *\nAllow: /\nDisallow: /newsletter-issue.html\n\n"
              "# AI answer engines are welcome to read and cite our pages.\n"
              f"{_ai_block}"
              f"Sitemap: {BASE_URL}/sitemap.xml\n")
    with open(os.path.join(SITE_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots)

    # llms.txt — a curated map so AI crawlers (ChatGPT, Claude, Gemini) can find
    # our best answers directly. https://llmstxt.org spec.
    lines = [f"# {BRAND}", "", f"> {TAGLINE}", "",
             "Magellan Flights tracks the cheapest flights from the USA every day, "
             "like a stock market, so travelers book at the low. Every fare is real "
             "and links to booking.", "", "## Key pages"]
    for fn in ["index.html", "market.html", "explore.html", "around-the-world.html", "cheap-flights.html", "cheap-flight-index.html", "newsletter.html",
               "airports.html", "guides.html"]:
        if fn in SEO:
            t, desc = SEO[fn]
            loc = BASE_URL + "/" + ("" if fn == "index.html" else fn)
            lines.append(f"- [{t.split(' | ')[0]}]({loc}): {desc}")
    if ARTICLES:
        lines += ["", "## Guides"]
        for a in ARTICLES:
            lines.append(f"- [{a['h1']}]({BASE_URL}/{a['slug']}.html): {a['description']}")
    if REGION_TOURS:
        lines += ["", "## Continent trips"]
        for m in REGION_TOURS:
            lines.append(f"- [Cheap {m['name']} Trip]({BASE_URL}/{m['slug']}.html): The cheapest multi-city {m['name']} trip, built from live one-way fares.")
    lines.append("")
    with open(os.path.join(SITE_DIR, "llms.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
