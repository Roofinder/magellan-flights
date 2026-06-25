#!/usr/bin/env python3
"""
World - cheapest one-way flights ANYWHERE -> ANYWHERE (incl. international origins).

Unlike the rest of the site (which departs the USA), this scans ~30 major GLOBAL
hubs and finds the cheapest one-ways from each to anywhere. Powers the "World"
page where you can pick any origin city (London, Dubai, Tokyo, Sydney...) and see
the cheapest places to fly.

    py world.py
    py world.py --top 50

Output: world_YYYYMMDD.csv with booking links.
Uses only the Python standard library. Reuses config.json + explore.py helpers.
"""

import argparse
import csv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import flightfinder as ff
import explore as ex

HERE = os.path.dirname(os.path.abspath(__file__))

# Major world hubs to scan as origins (city/airport codes).
GLOBAL_ORIGINS = {
    # North America
    "JFK": "New York", "LAX": "Los Angeles", "MIA": "Miami", "ORD": "Chicago",
    "SFO": "San Francisco", "BOS": "Boston", "ATL": "Atlanta", "SEA": "Seattle",
    "YTO": "Toronto", "YVR": "Vancouver",
    "DTW": "Detroit", "IAH": "Houston", "DEN": "Denver", "DFW": "Dallas", "TPA": "Tampa", "HNL": "Honolulu", "PHX": "Phoenix", "LAS": "Las Vegas",
    "RDU": "Raleigh", "CLT": "Charlotte", "MCO": "Orlando", "BNA": "Nashville", "CMH": "Columbus",
    # Europe
    "LON": "London", "PAR": "Paris", "FRA": "Frankfurt", "AMS": "Amsterdam",
    "MAD": "Madrid", "BCN": "Barcelona", "FCO": "Rome", "IST": "Istanbul",
    "LIS": "Lisbon", "DUB": "Dublin", "ZRH": "Zurich", "VIE": "Vienna",
    "CPH": "Copenhagen", "MUC": "Munich", "ATH": "Athens",
    # Middle East
    "DXB": "Dubai", "DOH": "Doha", "AUH": "Abu Dhabi", "TLV": "Tel Aviv",
    # Asia
    "SIN": "Singapore", "BKK": "Bangkok", "HKG": "Hong Kong", "TYO": "Tokyo",
    "ICN": "Seoul", "DEL": "Delhi", "BOM": "Mumbai", "KUL": "Kuala Lumpur",
    "TPE": "Taipei", "MNL": "Manila", "CGK": "Jakarta", "SGN": "Ho Chi Minh",
    # Oceania
    "SYD": "Sydney", "MEL": "Melbourne", "AKL": "Auckland",
    # Latin America
    "MEX": "Mexico City", "GRU": "Sao Paulo", "BOG": "Bogota", "EZE": "Buenos Aires",
    "LIM": "Lima",
    # Africa
    "JNB": "Johannesburg", "CAI": "Cairo", "NBO": "Nairobi", "CMN": "Casablanca",
}

# Major destinations to GUARANTEE coverage from every hub (incl. US long-haul),
# which the cheapest-fare cache alone never reaches.
WORLD_DESTS = ("JFK LAX MIA ORD SFO DTW IAH DEN DFW TPA HNL PHX LAS RDU CLT MCO BNA CMH YTO MEX GRU BOG LIM LON PAR FCO FRA MAD IST "
               "DXB DOH SIN BKK HKG TYO ICN DEL SYD JNB CAI").split()


def main():
    p = argparse.ArgumentParser(description="Cheapest one-ways from global hubs to anywhere.")
    p.add_argument("--top", type=int, default=200, help="Destinations per origin (default 200)")
    p.add_argument("--months", type=int, default=12, help="Look this many months ahead")
    p.add_argument("--lastminute", action="store_true", help="Only fares departing within --within-days")
    p.add_argument("--within-days", type=int, default=14, help="Last-minute window (default 14)")
    args = p.parse_args()

    cfg = ff.load_config()
    ref = ex.ensure_refdata()
    namer, country_of = ex.build_namer(ref)
    today = date.today()
    period_type = "month" if args.lastminute else "year"
    kind = "lm" if args.lastminute else "any"
    horizon = today + timedelta(days=(args.within_days if args.lastminute else int(args.months * 30.4)))
    if args.lastminute:
        depart_month = today.strftime("%Y-%m")
    else:
        mo = today.month - 1 + 3
        depart_month = date(today.year + mo // 12, mo % 12 + 1, 1).strftime("%Y-%m")
    print(f"Scanning {len(GLOBAL_ORIGINS)} global hubs ({kind}) for cheapest one-ways to anywhere...")

    def work(origin):
        best = {}

        def consider(dest, price, dep, link):
            if not dest or dest == origin or not dep:
                return
            if dep < today.isoformat() or dep > horizon.isoformat():
                return
            if dest not in best or price < best[dest]["price"]:
                best[dest] = {"dest": dest, "price": price, "depart": dep, "link": link}

        # 1) cheap "anywhere" variety from the latest-prices cache
        for item in ex.latest_from_origin(cfg, origin, period_type):
            dep = item.get("depart_date", "")[:10]
            dest = item.get("destination")
            val = item.get("value")
            if dest and val is not None:
                consider(dest, float(val), dep, ex.booking_link(cfg, origin, dest, dep))

        # 2) guarantee coverage to major world destinations (incl. US) the cheap
        #    cache never reaches — query each explicitly.
        for dest in WORLD_DESTS:
            if dest == origin or dest in best:
                continue
            r = ff.search_one_origin(cfg, origin, dest, depart_month, None, True)
            if r.get("status") == "ok":
                fare = r.get("fare", {})
                dep = (fare.get("departure_at", "") or "")[:10]
                consider(dest, r["price"], dep, ff.booking_link(cfg, r))

        # always keep the major-destination coverage; fill the rest with cheapest
        major = set(WORLD_DESTS)
        covered = [best[d] for d in WORLD_DESTS if d in best]
        rest = sorted((v for k, v in best.items() if k not in major),
                      key=lambda d: d["price"])[:args.top]
        return origin, sorted(covered + rest, key=lambda d: d["price"])

    all_rows = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(work, o) for o in GLOBAL_ORIGINS]
        for fut in as_completed(futs):
            origin, rows = fut.result()
            for d in rows:
                all_rows.append((origin, d["dest"], d["price"], d["depart"], d["link"]))

    cur = cfg["currency"].upper()
    stamp = datetime.now().strftime("%Y%m%d")
    fname = os.path.join(HERE, f"world_{kind}_{stamp}.csv")
    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["origin", "origin_name", "destination_code", "destination_name",
                    "country_code", "currency", "price", "depart", "booking_link"])
        for origin, dest, price, dep, link in all_rows:
            w.writerow([origin, GLOBAL_ORIGINS[origin], dest, namer(dest),
                        country_of(dest), cur, f"{price:.0f}", dep, link])
    print(f"Wrote {len(all_rows)} routes from {len(GLOBAL_ORIGINS)} hubs -> {fname}")


if __name__ == "__main__":
    main()
