#!/usr/bin/env python3
"""
LastMinute - cheapest ROUND-TRIP getaways departing THIS WEEK, USA -> anywhere.

For each major US gateway, finds the cheapest round-trip fares that depart within
the next few days, to anywhere it knows about, then ranks the cheapest spontaneous
getaways.

    py lastminute.py
    py lastminute.py --within-days 10 --top 40
    py lastminute.py --international          (exclude US domestic)
    py lastminute.py --max-price 400

Output: a ranked list + lastminute_YYYYMMDD.csv with booking links.
Uses only the Python standard library. Reuses config.json + explore.py helpers.
"""

import argparse
import csv
import json
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import flightfinder as ff
import explore as ex

HERE = os.path.dirname(os.path.abspath(__file__))
LATEST_URL = "https://api.travelpayouts.com/v2/prices/latest"
AVIASALES = "https://www.aviasales.com"


def latest_roundtrip(cfg, origin, limit=1000):
    params = {
        "currency": cfg["currency"], "origin": origin, "one_way": "false",
        "period_type": "month", "show_to_affiliates": "true", "sorting": "price",
        "limit": str(limit), "page": "1", "token": cfg["api_token"],
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


def booking_link(cfg, origin, dest, depart, ret):
    def ddmm(d):
        try:
            return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d%m")
        except Exception:  # noqa: BLE001
            return ""
    url = f"{AVIASALES}/search/{origin}{ddmm(depart)}{dest}{ddmm(ret)}1"
    if cfg.get("marker"):
        url += f"?marker={cfg['marker']}"
    return url


def main():
    p = argparse.ArgumentParser(description="Cheapest last-minute round-trip getaways from the USA.")
    p.add_argument("--within-days", type=int, default=7, help="Departing within this many days (default 7)")
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--max-price", type=float)
    p.add_argument("--origins")
    p.add_argument("--international", action="store_true", help="Exclude US domestic destinations")
    args = p.parse_args()

    cfg = ff.load_config()
    origins = ([o.strip().upper() for o in args.origins.split(",")]
               if args.origins else ex.DEFAULT_ORIGINS)

    today = date.today()
    horizon = today + timedelta(days=args.within_days)
    print(f"Finding cheapest ROUND-TRIP getaways from {len(origins)} US origins,")
    print(f"departing between {today} and {horizon} (this week)...")

    ref = ex.ensure_refdata()
    namer, country_of = ex.build_namer(ref)

    best = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(latest_roundtrip, cfg, o): o for o in origins}
        for fut in as_completed(futs):
            origin = futs[fut]
            for item in fut.result():
                dep = item.get("depart_date", "")[:10]
                ret = item.get("return_date", "")[:10]
                if not dep or not ret:
                    continue
                if dep < today.isoformat() or dep > horizon.isoformat():
                    continue
                dest = item.get("destination")
                price = item.get("value")
                if not dest or price is None:
                    continue
                cc = country_of(dest)
                if args.international and cc == "US":
                    continue
                price = float(price)
                cur = best.get(dest)
                if cur is None or price < cur["price"]:
                    best[dest] = {"dest": dest, "price": price, "origin": origin,
                                  "depart": dep, "return": ret,
                                  "stops": item.get("number_of_changes", 0)}

    deals = sorted(best.values(), key=lambda d: d["price"])
    if args.max_price is not None:
        deals = [d for d in deals if d["price"] <= args.max_price]
    if not deals:
        print("\nNo last-minute round-trips found this week. Try --within-days 14.")
        return

    cur = cfg["currency"].upper()
    shown = deals[:args.top]
    print(f"\n{'='*84}")
    print(f"  LAST-MINUTE ROUND-TRIPS: USA -> ANYWHERE (depart within {args.within_days} days, {cur})")
    print(f"{'='*84}")
    for i, d in enumerate(shown, 1):
        name = namer(d["dest"])[:40]
        print(f"  {i:>2}. ${d['price']:>7,.0f}  {d['origin']:<4} {d['depart']} -> {d['return']}  "
              f"{name} [{d['dest']}]")
    print(f"{'='*84}")
    print(f"  >>> CHEAPEST GETAWAY: ${shown[0]['price']:,.0f} round-trip from "
          f"{shown[0]['origin']} to {namer(shown[0]['dest'])}, "
          f"{shown[0]['depart']} -> {shown[0]['return']}")
    print(f"{'='*84}")

    kind = "intl" if args.international else "all"
    stamp = datetime.now().strftime("%Y%m%d")
    fname = os.path.join(HERE, f"lastminute_{kind}_{stamp}.csv")
    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "price", "currency", "origin", "destination_code",
                    "destination_name", "country_code", "depart", "return", "stops", "booking_link"])
        for i, d in enumerate(deals, 1):
            w.writerow([i, f"{d['price']:.0f}", cur, d["origin"], d["dest"],
                        namer(d["dest"]), country_of(d["dest"]), d["depart"], d["return"], d["stops"],
                        booking_link(cfg, d["origin"], d["dest"], d["depart"], d["return"])])
    print(f"\nSaved {len(deals)} getaways to: {fname}")


if __name__ == "__main__":
    main()
