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

def _robust(fares):
    """Pick a trustworthy cheapest fare. Prefer today's cache; drop phantom
    singletons that sit far below the next-cheapest."""
    if not fares: return None
    fresh = [f for f in fares if ("search_date=" + TODAY_SD) in (f.get("link","") or "")]
    pool = fresh if fresh else fares
    pool = sorted(pool, key=lambda f: float(f["price"]))
    while len(pool) > 1 and float(pool[0]["price"]) < PHANTOM * float(pool[1]["price"]):
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
    f = _robust(data)
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

rows = list(csv.DictReader(open(SNAP, encoding="utf-8")))
fields = list(rows[0].keys()) if rows else []
print(f"Re-pricing {len(rows)} routes (robust: today-pref + phantom-reject)...")
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
