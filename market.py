#!/usr/bin/env python3
"""
Market - the "stock market for flights" engine.

Run this every day. It:
  1. Scans cheapest fares to every tracked destination (across US gateways).
  2. LOGS today's prices to data/pricehistory.csv  (this is your time series -
     the thing that makes charts and 'buy vs wait' signals possible).
  3. Prints a CNBC-style market report: region indices, biggest movers, and a
     BOOK / WATCH / WAIT signal per destination.

Day 1 signals lean on typical-price benchmarks. Once you have ~1-2 weeks of
history, signals switch to your own real averages and you can chart trends.

    py market.py
    py market.py --depart 2026-10 --return 2026-11

Uses only the Python standard library. Reuses config.json, flightfinder.py,
and the destination list in dealsgen.py.
"""

import argparse
import csv
import os
import statistics
from collections import defaultdict
from datetime import date, datetime

import flightfinder as ff
import dealsgen as dg

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
HISTORY = os.path.join(DATA_DIR, "pricehistory.csv")

# Group destinations into "indices" like S&P sectors.
REGIONS = {
    "Asia": ["BKK", "DPS", "HKT", "SGN", "HAN", "NRT", "KIX", "ICN", "SIN", "KUL",
             "MNL", "DEL", "BOM", "HKG", "TPE", "KTM", "PEK", "PVG", "CAN", "CTU",
             "CGK", "REP", "PNH", "CMB", "MLE", "BLR", "MAA", "FUK", "CEB", "KHH", "CTS", "OKA", "CNX", "DAD", "USM", "GOI", "COK", "PEN", "SUB"],
    "Middle East": ["DXB", "DOH", "IST", "TLV", "AUH", "RUH", "JED", "AMM", "BEY", "MCT", "KWI", "BAH", "GYD", "TBS", "EVN"],
    "Europe": ["LHR", "CDG", "FCO", "BCN", "MAD", "LIS", "AMS", "FRA", "ATH", "DUB",
               "KEF", "PRG", "CPH", "MUC", "ZRH", "VIE", "BRU", "MXP", "VCE", "NCE",
               "EDI", "MAN", "GVA", "OSL", "ARN", "HEL", "WAW", "BUD", "KRK", "OPO", "HAM", "DUS", "BER", "STR", "CGN", "SOF", "OTP", "BEG", "ZAG", "SPU", "DBV", "TLL", "RIX", "VNO", "BLQ", "FLR", "NAP", "CTA", "AGP", "SVQ", "VLC", "FAO", "LYS", "MRS", "GLA", "BHX"],
    "Americas": ["MEX", "CUN", "SJD", "PTY", "SJO", "SJU", "PUJ", "NAS", "BOG", "LIM",
                 "GRU", "EZE", "SCL", "GIG", "UIO", "CTG", "MDE", "GUA", "MBJ", "AUA",
                 "CUR", "BGI", "KIN", "GCM", "BZE", "SDQ", "STT", "LIR", "YYZ", "YVR", "YUL", "YYC", "SAL", "TGU", "MGA", "GYE", "FOR", "REC", "SSA", "FLN", "SXM", "ANU", "UVF", "GND", "POS", "PLS", "FPO"],
    "Oceania": ["SYD", "MEL", "AKL", "NAN", "BNE", "PER", "CHC", "PPT", "CNS", "ADL", "WLG", "ZQN"],
    "Africa": ["CAI", "CMN", "JNB", "NBO", "RAK", "ACC", "LOS", "ADD", "CPT", "DKR", "TUN", "AGA", "HRG", "SSH", "MBA", "ZNZ", "JRO", "MRU"],
}
CODE_REGION = {c: reg for reg, codes in REGIONS.items() for c in codes}


LATEST_SNAP = os.path.join(DATA_DIR, "market_latest.csv")


def log_today(deals, today):
    os.makedirs(DATA_DIR, exist_ok=True)
    new = not os.path.exists(HISTORY)
    with open(HISTORY, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "code", "name", "origin", "price", "benchmark"])
        for d in deals:
            w.writerow([today, d["code"], d["name"], d["origin"],
                        f"{d['price']:.0f}", d["benchmark"]])


def write_market_latest(cfg, deals, today):
    """Overwrite a rich snapshot of today's prices (with airline + booking link)
    that the website reads for its ticker, movers, cards and watchlist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LATEST_SNAP, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "code", "name", "origin", "price", "benchmark",
                    "savings_pct", "airline", "depart", "return", "booking_link"])
        for d in deals:
            fare = d.get("fare", {})
            w.writerow([today, d["code"], d["name"], d["origin"],
                        f"{d['price']:.0f}", f"{d['benchmark']:.0f}",
                        d.get("savings_pct", ""), fare.get("airline", ""),
                        (fare.get("departure_at", "") or "")[:10],
                        (fare.get("return_at", "") or "")[:10],
                        ff.booking_link(cfg, d)])


def load_history():
    """Return {code: {date: price}} from the log (most recent price per day)."""
    hist = defaultdict(dict)
    if not os.path.exists(HISTORY):
        return hist
    with open(HISTORY, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            hist[row["code"]][row["date"]] = float(row["price"])
    return hist


def signal_for(code, price, benchmark, hist, today):
    """Decide BOOK / WATCH / WAIT and a short reason."""
    past = {dt: p for dt, p in hist.get(code, {}).items() if dt != today}
    days = len(past)
    if days >= 5:
        baseline = statistics.mean(past.values())
        basis = f"{days}-day avg ${baseline:,.0f}"
    else:
        baseline = benchmark
        basis = f"typical ${benchmark:,.0f}"
    pct = (baseline - price) / baseline * 100 if baseline else 0
    all_prices = list(past.values()) + [price]
    hist_min = min(all_prices)

    if pct >= 20 or price <= hist_min * 1.02:
        sig = "BOOK"
    elif pct >= 8:
        sig = "WATCH"
    else:
        sig = "WAIT"
    return sig, pct, basis, days


def trend_arrow(code, price, hist, today):
    past = sorted((dt, p) for dt, p in hist.get(code, {}).items() if dt != today)
    if not past:
        return "  new"
    prev = past[-1][1]
    diff = price - prev
    if abs(diff) < 1:
        return "  flat"
    return f"  {'▼' if diff < 0 else '▲'}${abs(diff):,.0f} d/d"


def gather_bulk(cfg):
    """Hybrid auto-discovery scan. One bulk prices_for_dates call per US gateway
    returns the cheapest round-trip to MANY destinations. We keep the curated
    destinations (with their hand-set baselines) AND auto-discover the rest, up
    to ~500 routes total, naming them from airportsdata and pricing the baseline
    from each route's own price history (once it has data) or a distance estimate."""
    import json as _json, urllib.parse as _up, urllib.request as _ur, time as _t, csv as _csv, math as _M
    from concurrent.futures import ThreadPoolExecutor as _Pool
    HERE = os.path.dirname(os.path.abspath(__file__))
    MAXR = 500
    curated = {c: (name, emoji, bench) for c, name, emoji, bench in dg.DESTINATIONS}

    def _load(fn):
        try:
            with open(os.path.join(HERE, fn), encoding="utf-8") as f:
                return _json.load(f)
        except Exception:
            return {}
    NAMES = _load("airport_names.json")
    COORDS = _load("airport_coords.json")
    CCJ = _load("code_cc.json")

    hist = {}
    hp = os.path.join(HERE, "data", "pricehistory.csv")
    if os.path.exists(hp):
        agg = {}
        for r in _csv.DictReader(open(hp, encoding="utf-8")):
            try:
                agg.setdefault(r["code"], []).append(float(r["price"]))
            except Exception:
                pass
        for c, v in agg.items():
            if len(v) >= 4:
                hist[c] = sum(v) / len(v)

    def bulk(o):
        params = {"origin": o, "currency": cfg["currency"], "market": cfg["market"],
                  "one_way": "false", "sorting": "price", "limit": "1000", "token": cfg["api_token"]}
        url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates?" + _up.urlencode(params)
        req = _ur.Request(url); req.add_header("X-Access-Token", cfg["api_token"])
        for _ in range(3):
            try:
                with _ur.urlopen(req, timeout=40) as z:
                    return o, _json.load(z).get("data", [])
            except Exception:
                _t.sleep(1)
        return o, []

    best = {}; ocount = {}
    with _Pool(max_workers=len(dg.DEALS_ORIGINS)) as pool:
        for o, data in pool.map(bulk, dg.DEALS_ORIGINS):
            for x in data:
                d = x.get("destination_airport")
                if not d or not x.get("return_at"):
                    continue
                ocount[d] = ocount.get(d, 0) + 1
                pr = float(x["price"])
                if d not in best or pr < float(best[d]["price"]):
                    best[d] = x

    sel = [c for c in best if c in curated]
    disc = sorted([c for c in best if c not in curated and CCJ.get(c) != "US"],
                  key=lambda c: (-ocount.get(c, 0), float(best[c]["price"])))
    for c in disc:
        if len(sel) >= MAXR:
            break
        sel.append(c)

    def hav(a, b):
        try:
            la1, lo1 = COORDS[a]; la2, lo2 = COORDS[b]
        except Exception:
            return None
        R = 6371.0
        p1 = _M.radians(la1); p2 = _M.radians(la2)
        dp = _M.radians(la2 - la1); dl = _M.radians(lo2 - lo1)
        h = _M.sin(dp/2)**2 + _M.cos(p1)*_M.cos(p2)*_M.sin(dl/2)**2
        return 2*R*_M.asin(min(1.0, _M.sqrt(h)))

    deals = []
    for code in sel:
        fare = best[code]; price = float(fare["price"]); o = fare.get("origin_airport", "")
        if code in curated:
            name, emoji, bench = curated[code]
            if code in hist:
                bench = hist[code]
        else:
            name = NAMES.get(code, code); emoji = "\U0001F30D"
            if code in hist:
                bench = hist[code]
            else:
                dkm = hav(o, code)
                bench = round((180 + 0.11 * dkm) / 10) * 10 if dkm else round(price * 1.4)
        bench = max(int(bench), 1)
        sav = round((bench - price) / bench * 100) if bench else 0
        deals.append({"code": code, "name": name, "emoji": emoji, "origin": o,
                      "price": price, "benchmark": bench, "savings_pct": sav,
                      "status": "ok", "fare": fare})
    deals.sort(key=lambda d: d["savings_pct"], reverse=True)
    return deals


def main():
    p = argparse.ArgumentParser(description="Daily flight 'market' report + price logger.")
    dep_default, ret_default = dg.default_months()
    p.add_argument("--depart", default=dep_default)
    p.add_argument("--return", dest="ret", default=ret_default)
    args = p.parse_args()

    cfg = ff.load_config()
    today = date.today().isoformat()

    # Fast bulk scan across US gateways (keeps ~100 tracked routes).
    deals = gather_bulk(cfg)
    if not deals:
        print("No prices returned; try a different month.")
        return

    log_today(deals, today)
    write_market_latest(cfg, deals, today)
    hist = load_history()
    by_code = {d["code"]: d for d in deals}

    # ---- Region indices (average cheapest fare in each region today) ----
    print(f"\n{'='*70}")
    print(f"  FARE MARKET REPORT  -  {datetime.now().strftime('%A, %B %d, %Y')}")
    print(f"{'='*70}")
    print("\n  REGION INDICES (avg cheapest round-trip today)")
    for reg, codes in REGIONS.items():
        prices = [by_code[c]["price"] for c in codes if c in by_code]
        if prices:
            print(f"    {reg:<14} ${statistics.mean(prices):>7,.0f}   ({len(prices)} routes)")

    # ---- Movers / signals ----
    rows = []
    for d in deals:
        sig, pct, basis, days = signal_for(d["code"], d["price"], d["benchmark"], hist, today)
        rows.append((d, sig, pct, basis, days))
    rows.sort(key=lambda r: r[2], reverse=True)  # biggest % below baseline first

    print("\n  TODAY'S BIGGEST MOVERS (vs baseline)")
    print(f"    {'DEST':<22}{'PRICE':>9}  {'SIGNAL':<7}{'BELOW BASELINE':>16}   TREND")
    for d, sig, pct, basis, days in rows[:12]:
        name = d["name"][:20]
        print(f"    {name:<22}${d['price']:>7,.0f}  {sig:<7}{pct:>13.0f}%   "
              f"{trend_arrow(d['code'], d['price'], hist, today).strip()}")

    book = [r for r in rows if r[1] == "BOOK"]
    print(f"\n  >>> {len(book)} routes flag BOOK today. Top pick: "
          f"{book[0][0]['name']} ${book[0][0]['price']:,.0f} from {book[0][0]['origin']}"
          if book else "\n  >>> No strong BOOK signals today - mostly WATCH/WAIT.")

    distinct_days = len({dt for c in hist for dt in hist[c]})
    print(f"\n  History: {distinct_days} day(s) logged in data/pricehistory.csv.")
    if distinct_days < 7:
        print(f"  (Run daily - after ~7 days, signals use YOUR real averages, not benchmarks.)")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
