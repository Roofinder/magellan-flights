#!/usr/bin/env python3
"""
FlightFinder - "Cheapest way to anywhere" flight search.

Answers questions like: "What's the absolute cheapest way to get to Bangkok
from ANYWHERE in the USA?" by fanning out across many US origin airports in
parallel, pulling the cheapest fares from the Travelpayouts (Aviasales) Flight
Data API, and ranking the results.

Uses only the Python standard library - nothing to pip install.

Usage:
    py flightfinder.py --to BKK --depart 2026-09 --return 2026-10
    py flightfinder.py --to BKK --depart 2026-09-15            (one-way)
    py flightfinder.py --to BKK --depart 2026-09 --oneway-vs-roundtrip --return 2026-10
    py flightfinder.py --to LHR --depart 2026-10 --origins JFK,LAX,SFO,ORD

Dates can be a whole month ("2026-09") to find the cheapest day in that month,
or an exact day ("2026-09-15").

Setup: put your Travelpayouts api_token + marker in config.json (already done
if Claude set this up for you). See README.md.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
API_BASE = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
AVIASALES = "https://www.aviasales.com"

# Major US international gateway airports. Searching literally every US airport
# would be slow and noisy, so we use the realistic gateways that actually carry
# cheap long-haul international fares. Edit freely or pass --origins.
DEFAULT_US_ORIGINS = [
    "JFK", "EWR", "LGA",   # New York area
    "BOS",                  # Boston
    "IAD", "DCA",          # Washington DC
    "ATL",                  # Atlanta
    "MIA", "FLL",          # Miami / Fort Lauderdale
    "ORD",                  # Chicago
    "DFW", "IAH",          # Dallas / Houston
    "DEN",                  # Denver
    "LAX", "SFO", "SEA",   # West coast
    "LAS", "PHX",          # Las Vegas / Phoenix
]

AIRPORT_NAMES = {
    "JFK": "New York (JFK)", "EWR": "Newark", "LGA": "New York (LaGuardia)",
    "BOS": "Boston", "IAD": "Washington Dulles", "DCA": "Washington Reagan",
    "ATL": "Atlanta", "MIA": "Miami", "FLL": "Fort Lauderdale",
    "ORD": "Chicago O'Hare", "DFW": "Dallas", "IAH": "Houston",
    "DEN": "Denver", "LAX": "Los Angeles", "SFO": "San Francisco",
    "SEA": "Seattle", "LAS": "Las Vegas", "PHX": "Phoenix",
}


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit(
            "ERROR: config.json not found.\n"
            "  Create config.json with your Travelpayouts api_token and marker.\n"
            "  See README.md.\n"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not cfg.get("api_token") or "YOUR_" in cfg.get("api_token", ""):
        sys.exit("ERROR: Put your real Travelpayouts api_token in config.json.")
    cfg.setdefault("currency", "usd")
    cfg.setdefault("market", "us")
    cfg.setdefault("marker", "")
    return cfg


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def search_one_origin(cfg, origin, dest, depart, ret, one_way, limit=30):
    """Query Travelpayouts prices_for_dates for a single origin. Returns the
    cheapest fare dict (or an 'error'/'no results' marker)."""
    params = {
        "origin": origin,
        "destination": dest,
        "departure_at": depart,
        "currency": cfg["currency"],
        "market": cfg["market"],
        "one_way": "true" if one_way else "false",
        "direct": "false",
        "sorting": "price",
        "limit": str(limit),
        "token": cfg["api_token"],
    }
    if ret and not one_way:
        params["return_at"] = ret

    url = API_BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("X-Access-Token", cfg["api_token"])

    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                payload = json.load(resp)
            if not payload.get("success", True):
                return {"origin": origin, "status": f"api error: {payload.get('error')}"}
            data = payload.get("data", [])
            if not data:
                return {"origin": origin, "status": "no results"}
            best = min(data, key=lambda d: float(d["price"]))
            return {"origin": origin, "status": "ok",
                    "price": float(best["price"]),
                    "currency": payload.get("currency", cfg["currency"]).upper(),
                    "fare": best}
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limited - back off and retry
                time.sleep(1.5 * (attempt + 1))
                continue
            return {"origin": origin, "status": f"error {e.code}"}
        except Exception as e:  # noqa: BLE001
            return {"origin": origin, "status": f"error: {e}"}
    return {"origin": origin, "status": "rate-limited"}


def describe_fare(r):
    f = r["fare"]
    dep = f.get("departure_at", "")[:10]
    ret = f.get("return_at", "")
    ret = ret[:10] if ret else ""
    out_stops = f.get("transfers", 0)
    back_stops = f.get("return_transfers", 0)
    airline = f.get("airline", "?")
    parts = [f"depart {dep}", f"{out_stops} stop{'s' if out_stops != 1 else ''} out"]
    if ret:
        parts.append(f"return {ret}")
        parts.append(f"{back_stops} stop{'s' if back_stops != 1 else ''} back")
    parts.append(f"airline {airline}")
    return ", ".join(parts)


def booking_link(cfg, r):
    """Build a clickable Aviasales link (with your affiliate marker if set)."""
    link = r["fare"].get("link", "")
    if not link:
        return ""
    url = AVIASALES + link
    if cfg.get("marker"):
        sep = "&" if "?" in url else "?"
        url += f"{sep}marker={cfg['marker']}"
    return url


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_search(cfg, origins, dest, depart, ret, one_way, label):
    mode = "one-way" if one_way else (f"round-trip (return {ret})" if ret else "round-trip")
    print(f"\nSearching {label}: {len(origins)} US origins -> {dest} "
          f"(depart {depart}, {mode})...")
    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(search_one_origin, cfg, o, dest, depart, ret, one_way): o
                   for o in origins}
        for fut in as_completed(futures):
            results.append(fut.result())
    ok = [r for r in results if r["status"] == "ok"]
    ok.sort(key=lambda r: r["price"])
    return ok, results


def print_results(cfg, ok, results, dest):
    if not ok:
        print("\nNo priced results came back. Common reasons:")
        print("  - This is cached fare data; some thin routes/dates have no cache yet")
        print("  - Try a whole month (e.g. --depart 2026-09) instead of an exact day")
        print("  - Make sure your config.json api_token is correct")
        statuses = {}
        for r in results:
            statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        print("  Status breakdown:", statuses)
        return
    cur = ok[0]["currency"]
    print(f"\n{'='*78}\n  CHEAPEST WAYS TO {dest}  (ranked, prices in {cur})\n{'='*78}")
    for i, r in enumerate(ok, 1):
        name = AIRPORT_NAMES.get(r["origin"], r["origin"])
        print(f"\n{i:>2}. ${r['price']:>8,.2f}  from {name} [{r['origin']}]")
        print(f"        {describe_fare(r)}")
        link = booking_link(cfg, r)
        if link:
            print(f"        book: {link}")
    cheapest = ok[0]
    print(f"\n{'='*78}")
    print(f"  >>> ABSOLUTE CHEAPEST: ${cheapest['price']:,.2f} from "
          f"{AIRPORT_NAMES.get(cheapest['origin'], cheapest['origin'])} "
          f"[{cheapest['origin']}]")
    print(f"{'='*78}")


def save_csv(cfg, ok, dest, depart, ret):
    if not ok:
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = os.path.join(HERE, f"results_{dest}_{stamp}.csv")
    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "origin", "origin_name", "price", "currency",
                    "destination", "depart", "return", "details", "booking_link"])
        for i, r in enumerate(ok, 1):
            w.writerow([i, r["origin"], AIRPORT_NAMES.get(r["origin"], r["origin"]),
                        f"{r['price']:.2f}", r["currency"], dest, depart,
                        ret or "", describe_fare(r), booking_link(cfg, r)])
    print(f"\nSaved full results to: {fname}")


def main():
    p = argparse.ArgumentParser(description="Find the cheapest way to fly anywhere from the USA.")
    p.add_argument("--to", required=True, help="Destination airport code, e.g. BKK")
    p.add_argument("--depart", required=True, help="Departure date YYYY-MM-DD or whole month YYYY-MM")
    p.add_argument("--return", dest="ret", help="Return date YYYY-MM-DD or YYYY-MM (omit for one-way)")
    p.add_argument("--origins", help="Comma-separated origin codes (default: major US gateways)")
    p.add_argument("--oneway-vs-roundtrip", action="store_true",
                   help="Run both one-way and round-trip and compare (needs --return)")
    args = p.parse_args()

    dest = args.to.upper().strip()
    origins = ([o.strip().upper() for o in args.origins.split(",")]
               if args.origins else DEFAULT_US_ORIGINS)

    cfg = load_config()
    print(f"Using Travelpayouts Flight Data API, currency {cfg['currency'].upper()}, market {cfg['market'].upper()}.")

    if args.oneway_vs_roundtrip:
        if not args.ret:
            sys.exit("--oneway-vs-roundtrip needs a --return date to compare against.")
        ow_ok, _ = run_search(cfg, origins, dest, args.depart, None, True, "ONE-WAY")
        print_results(cfg, ow_ok, ow_ok, dest)
        rt_ok, _ = run_search(cfg, origins, dest, args.depart, args.ret, False, "ROUND-TRIP")
        print_results(cfg, rt_ok, rt_ok, dest)
        if ow_ok and rt_ok:
            print(f"\nCheapest one-way:    ${ow_ok[0]['price']:,.2f} from {ow_ok[0]['origin']}")
            print(f"Cheapest round-trip: ${rt_ok[0]['price']:,.2f} from {rt_ok[0]['origin']}")
            print(f"Two one-ways (2x cheapest): ${ow_ok[0]['price']*2:,.2f}  "
                  f"-> {'CHEAPER than round-trip!' if ow_ok[0]['price']*2 < rt_ok[0]['price'] else 'round-trip wins'}")
        save_csv(cfg, rt_ok, dest, args.depart, args.ret)
    else:
        one_way = not args.ret
        ok, results = run_search(cfg, origins, dest, args.depart, args.ret, one_way, "SEARCH")
        print_results(cfg, ok, results, dest)
        save_csv(cfg, ok, dest, args.depart, args.ret)


if __name__ == "__main__":
    main()
