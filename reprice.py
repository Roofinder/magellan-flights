#!/usr/bin/env python3
"""Re-price every row in data/market_latest.csv against the LIVE Travelpayouts
prices_for_dates API for each route's EXACT dates, choosing a ROBUST price:
- prefer fares cached today (freshest),
- reject lone "phantom" singletons (a cheapest fare far below the next one),
so the price shown is one a user can actually book. Recomputes savings_pct vs
the existing benchmark and drops routes with no verifiable fare. Run after
market.py and before buildsite.py."""
import os, csv, json, time, datetime
import urllib.parse as up, urllib.request as ur
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "data", "market_latest.csv")
AVIASALES = "https://www.aviasales.com"
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
TOKEN = cfg["api_token"]; MARKER = cfg.get("marker", "")
CUR = cfg.get("currency", "usd"); MKT = cfg.get("market", "us")
TODAY = datetime.date.today().isoformat()
TODAY_SD = datetime.date.today().strftime("%d%m%Y")   # search_date format in links
PHANTOM = 0.70   # a cheapest below 70% of the next-cheapest is treated as a phantom
MEDIAN_FLOOR = 0.55  # a cheapest below 55% of the route's own recent median is treated as stale

# Per-route recent median price from data/pricehistory.csv. The neighbor-based
# PHANTOM filter only catches a low that sits far below its cache neighbors; when
# the WHOLE cached pool is uniformly stale-low, there's no neighbor outlier to
# catch. This median (from real history) lets _robust also reject a cheapest that
# sits far below the route's own established typical price.
HIST = os.path.join(HERE, "data", "pricehistory.csv")

def _load_medians():
    by_code = {}
    try:
        for r in csv.DictReader(open(HIST, encoding="utf-8")):
            try:
                by_code.setdefault(r["code"], []).append(float(r["price"]))
            except Exception:
                continue
    except Exception:
        return {}
    out = {}
    for code, vals in by_code.items():
        if len(vals) >= 3:           # need a few snapshots before trusting it
            s = sorted(vals)
            out[code] = s[len(s) // 2]
    return out

HIST_MEDIAN = _load_medians()

def _call(params):
    params = dict(params); params.update({"currency": CUR, "market": MKT,
        "one_way": "false", "sorting": "price", "limit": "30", "token": TOKEN})
    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates?" + up.urlencode(params)
    req = ur.Request(url); req.add_header("X-Access-Token", TOKEN)
    for _ in range(4):
        try:
            with ur.urlopen(req, timeout=25) as z:
                return json.load(z).get("data", [])
        except Exception:
            time.sleep(0.6)
    return None

def _link(rel):
    if not rel: return ""
    u = AVIASALES + rel
    if MARKER and "marker=" not in u:
        u += ("&" if "?" in u else "?") + "marker=" + str(MARKER)
    return u

def _robust(fares, median=0.0):
    """Pick a trustworthy cheapest fare. Prefer today's cache; drop phantom
    singletons that sit far below the next-cheapest OR far below the route's own
    recent history median. Never empties the pool — keeps the least-bad fare."""
    if not fares: return None
    fresh = [f for f in fares if ("search_date=" + TODAY_SD) in (f.get("link","") or "")]
    pool = fresh if fresh else fares
    pool = sorted(pool, key=lambda f: float(f["price"]))
    while len(pool) > 1 and (
        float(pool[0]["price"]) < PHANTOM * float(pool[1]["price"])
        or (median and float(pool[0]["price"]) < MEDIAN_FLOOR * median)
    ):
        pool.pop(0)
    return pool[0]

def reprice(row):
    o, d = row["origin"], row["code"]
    dep, ret = row.get("depart",""), row.get("return","")
    try: bench = float(row["benchmark"])
    except: bench = 0.0
    data = None
    if dep and ret:
        data = _call({"origin": o, "destination": d, "departure_at": dep, "return_at": ret})
    used = "exact"
    if not data:
        nd = _call({"origin": o, "destination": d})
        if nd:
            data = nd; used = "fallback"
        elif data is None or nd is None:
            return ("keep", row)
        else:
            return ("drop", row)
    f = _robust(data, HIST_MEDIAN.get(d, 0.0))
    if not f:
        return ("drop", row)
    price = float(f["price"])
    row["price"] = f"{price:.0f}"
    row["airline"] = f.get("airline", row.get("airline",""))
    row["depart"] = (f.get("departure_at","") or dep)[:10]
    row["return"] = (f.get("return_at","") or ret)[:10]
    row["booking_link"] = _link(f.get("link",""))
    row["savings_pct"] = str(round((bench - price)/bench*100) if bench else 0)
    row["date"] = TODAY
    return (used, row)

def main():
    rows = list(csv.DictReader(open(SNAP, encoding="utf-8")))
    fields = list(rows[0].keys()) if rows else []
    print(f"Re-pricing {len(rows)} routes (robust: today-pref + phantom-reject + history-median)...")
    out, stats = [], {"exact":0,"fallback":0,"drop":0,"keep":0}
    with ThreadPoolExecutor(max_workers=12) as pool:
        for status, row in pool.map(reprice, rows):
            stats[status] += 1
            if status != "drop":
                out.append(row)
    with open(SNAP, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader(); w.writerows(out)
    print("Done:", stats, f"-> {len(out)} rows")


if __name__ == "__main__":
    main()
