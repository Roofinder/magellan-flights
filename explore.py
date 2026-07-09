#!/usr/bin/env python3
"""
Explore - cheapest ONE-WAY flights from the USA to ANYWHERE in the next 6 months.

For each major US gateway, this asks Travelpayouts for the cheapest one-way
fares to every destination it knows about, keeps only departures within the next
~6 months, then ranks the cheapest way to reach each place on earth.

    py explore.py
    py explore.py --months 6 --top 40
    py explore.py --max-price 300        (only show one-ways under $300)
    py explore.py --origins LAX,SFO,SEA  (only from the west coast)

Output: a ranked list + explore_oneway_YYYYMMDD.csv with booking links.

Uses only the Python standard library. Reuses config.json.
"""

import argparse
import csv
import json
import os
import urllib.parse
import urllib.request
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import flightfinder as ff

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
LATEST_URL = "https://api.travelpayouts.com/v2/prices/latest"
AVIASALES = "https://www.aviasales.com"

# Reference data (airport/city/country names) cached locally after first run.
REF_FILES = {
    "airports": "https://api.travelpayouts.com/data/en/airports.json",
    "cities": "https://api.travelpayouts.com/data/en/cities.json",
    "countries": "https://api.travelpayouts.com/data/en/countries.json",
}

DEFAULT_ORIGINS = ["JFK", "EWR", "BOS", "IAD", "ATL", "MIA", "ORD",
                   "DFW", "IAH", "DEN", "LAX", "SFO", "SEA", "LAS", "PHX",
                   "DTW", "MSP", "CLT", "RDU", "PHL", "MCO", "SLC", "SAN",
                   "BNA", "PDX", "TPA", "FLL", "DCA", "AUS"]


# --------------------------------------------------------------------------- #
# Reference data (turn codes like BKK into "Bangkok, Thailand")
# --------------------------------------------------------------------------- #
def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "FlightFinder/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def ensure_refdata():
    os.makedirs(DATA_DIR, exist_ok=True)
    data = {}
    for key, url in REF_FILES.items():
        path = os.path.join(DATA_DIR, key + ".json")
        if not os.path.exists(path):
            try:
                print(f"  (downloading {key} reference data, one time only...)")
                obj = _fetch_json(url)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(obj, f)
            except Exception as e:  # noqa: BLE001
                print(f"  (couldn't fetch {key}: {e}; will show codes instead)")
                data[key] = []
                continue
        with open(path, encoding="utf-8") as f:
            data[key] = json.load(f)
    return data


def build_namer(ref):
    city_name = {c["code"]: c.get("name", c["code"]) for c in ref.get("cities", [])}
    country_name = {c["code"]: c.get("name", "") for c in ref.get("countries", [])}
    place = {}    # airport/city code -> "City, Country"
    country = {}  # airport/city code -> country_code (e.g. "US", "TH")
    for c in ref.get("cities", []):
        cc = c.get("country_code", "")
        place[c["code"]] = f"{c.get('name', c['code'])}, {country_name.get(cc, '')}".rstrip(", ")
        country[c["code"]] = cc
    for a in ref.get("airports", []):
        code = a["code"]
        cc = a.get("country_code", "")
        country.setdefault(code, cc)
        if code in place:
            continue
        city = city_name.get(a.get("city_code", ""), a.get("name", code))
        place[code] = f"{city}, {country_name.get(cc, '')}".rstrip(", ")

    def namer(code):
        return place.get(code, code)

    def country_of(code):
        return country.get(code, "")
    return namer, country_of


# --------------------------------------------------------------------------- #
# Search: cheapest one-ways from one origin to anywhere
# --------------------------------------------------------------------------- #
def latest_from_origin(cfg, origin, period_type="year", limit=1000):
    params = {
        "currency": cfg["currency"],
        "origin": origin,
        "one_way": "true",
        "period_type": period_type,
        "show_to_affiliates": "true",
        "sorting": "price",
        "limit": str(limit),
        "page": "1",
        "token": cfg["api_token"],
    }
    url = LATEST_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("X-Access-Token", cfg["api_token"])
    try:
        with urllib.request.urlopen(req, timeout=50) as resp:
            payload = json.load(resp)
        return payload.get("data", []) if payload.get("success", True) else []
    except Exception:  # noqa: BLE001
        return []


def booking_link(cfg, origin, dest, depart_date):
    """Build an Aviasales one-way deep link carrying your affiliate marker."""
    try:
        dt = datetime.strptime(depart_date[:10], "%Y-%m-%d")
        ddmm = dt.strftime("%d%m")
    except Exception:  # noqa: BLE001
        ddmm = ""
    url = f"{AVIASALES}/search/{origin}{ddmm}{dest}1"
    if cfg.get("marker"):
        url += f"?marker={cfg['marker']}"
    return url


def main():
    p = argparse.ArgumentParser(description="Cheapest one-way flights from the USA to anywhere.")
    p.add_argument("--months", type=int, default=6, help="Look this many months ahead (default 6)")
    p.add_argument("--top", type=int, default=40, help="How many destinations to show (default 40)")
    p.add_argument("--max-price", type=float, help="Only show one-ways at or below this price")
    p.add_argument("--origins", help="Comma-separated US origins (default: major gateways)")
    p.add_argument("--international", action="store_true",
                   help="Only show international destinations (exclude US domestic)")
    p.add_argument("--country", help="Only show this destination country code, e.g. TH, JP, FR")
    p.add_argument("--lastminute", action="store_true",
                   help="Last-minute mode: one-ways departing within --within-days")
    p.add_argument("--within-days", type=int, default=10, help="Last-minute window (default 10)")
    args = p.parse_args()

    cfg = ff.load_config()
    origins = ([o.strip().upper() for o in args.origins.split(",")]
               if args.origins else DEFAULT_ORIGINS)

    today = date.today()
    period_type = "month" if args.lastminute else "year"
    kind = "lm" if args.lastminute else "6m"
    horizon = today + timedelta(days=(args.within_days if args.lastminute else int(args.months * 30.4)))
    window = f"{args.within_days} days" if args.lastminute else f"~{args.months} months"
    print(f"Finding cheapest ONE-WAY flights from {len(origins)} US origins to anywhere,")
    print(f"departing between {today} and {horizon} ({window})...")

    ref = ensure_refdata()
    namer, country_of = build_namer(ref)
    want_country = args.country.upper() if args.country else None

    # Pull cheapest one-ways from every origin in parallel.
    best = {}  # dest code -> best record
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(latest_from_origin, cfg, o, period_type): o for o in origins}
        for fut in as_completed(futs):
            origin = futs[fut]
            for item in fut.result():
                dep = item.get("depart_date", "")[:10]
                if not dep or dep < today.isoformat() or dep > horizon.isoformat():
                    continue
                dest = item.get("destination")
                price = item.get("value")
                if not dest or price is None:
                    continue
                cc = country_of(dest)
                if args.international and cc == "US":
                    continue
                if want_country and cc != want_country:
                    continue
                price = float(price)
                cur = best.get(dest)
                if cur is None or price < cur["price"]:
                    best[dest] = {
                        "dest": dest, "price": price, "origin": origin,
                        "depart": dep, "stops": item.get("number_of_changes", 0),
                    }

    deals = sorted(best.values(), key=lambda d: d["price"])
    if args.max_price is not None:
        deals = [d for d in deals if d["price"] <= args.max_price]
    if not deals:
        print("\nNo one-way fares came back for that window. Try --months 12 or different origins.")
        return

    cur = cfg["currency"].upper()
    shown = deals[:args.top]
    print(f"\n{'='*82}")
    print(f"  CHEAPEST ONE-WAY FLIGHTS: USA -> ANYWHERE ({window}, {cur})")
    print(f"{'='*82}")
    print(f"  {'#':>2}  {'PRICE':>8}  {'FROM':<5} {'DEPART':<11} DESTINATION")
    for i, d in enumerate(shown, 1):
        name = namer(d["dest"])[:42]
        print(f"  {i:>2}. ${d['price']:>7,.0f}  {d['origin']:<5} {d['depart']:<11} {name} [{d['dest']}]")
    print(f"{'='*82}")
    print(f"  >>> CHEAPEST ESCAPE: ${shown[0]['price']:,.0f} one-way from "
          f"{shown[0]['origin']} to {namer(shown[0]['dest'])} on {shown[0]['depart']}")
    print(f"{'='*82}")

    # Save CSV with booking links.
    stamp = datetime.now().strftime("%Y%m%d")
    fname = os.path.join(HERE, f"explore_oneway_{kind}_{stamp}.csv")
    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "price", "currency", "origin", "destination_code",
                    "destination_name", "country_code", "depart", "stops", "booking_link"])
        for i, d in enumerate(deals, 1):
            w.writerow([i, f"{d['price']:.0f}", cur, d["origin"], d["dest"],
                        namer(d["dest"]), country_of(d["dest"]), d["depart"], d["stops"],
                        booking_link(cfg, d["origin"], d["dest"], d["depart"])])
    print(f"\nSaved {len(deals)} destinations to: {fname}")


if __name__ == "__main__":
    main()
