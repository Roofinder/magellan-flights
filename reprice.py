#!/usr/bin/env python3
"""Re-price every row in data/market_latest.csv against the LIVE Travelpayouts
prices_for_dates API for each route's EXACT dates, so the price shown on the
site equals what a user actually pays when they click. Recomputes savings_pct
vs the existing benchmark. Rows that can't be verified (no current fare for the
exact dates, and none for the route at all) are dropped rather than shown stale.
Run after market.py and before buildsite.py."""
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

def _call(params):
    params = dict(params); params.update({"currency": CUR, "market": MKT,
        "one_way": "false", "sorting": "price", "token": TOKEN})
    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates?" + up.urlencode(params)
    req = ur.Request(url); req.add_header("X-Access-Token", TOKEN)
    for _ in range(3):
        try:
            with ur.urlopen(req, timeout=25) as z:
                return json.load(z).get("data", [])
        except Exception:
            time.sleep(0.6)
    return None  # None = network failure (keep old row), [] = no fare

def _link(rel):
    if not rel: return ""
    u = AVIASALES + rel
    if MARKER and "marker=" not in u:
        u += ("&" if "?" in u else "?") + "marker=" + str(MARKER)
    return u

def reprice(row):
    o, d = row["origin"], row["code"]
    dep, ret = row.get("depart",""), row.get("return","")
    try: bench = float(row["benchmark"])
    except: bench = 0.0
    # 1) exact dates
    data = None
    if dep and ret:
        data = _call({"origin": o, "destination": d, "departure_at": dep, "return_at": ret, "limit": "1"})
    used = "exact"
    # 2) fallback: current cheapest for the route (any dates)
    if not data:
        nd = _call({"origin": o, "destination": d, "limit": "1"})
        if nd:
            data = nd; used = "fallback"
        elif data is None or nd is None:
            return ("keep", row)      # network hiccup -> don't lose the row
        else:
            return ("drop", row)      # genuinely no fare bookable -> drop
    f = data[0]
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
fields = rows[0].keys() if rows else []
print(f"Re-pricing {len(rows)} routes against live exact-date fares...")
out, stats = [], {"exact":0,"fallback":0,"drop":0,"keep":0}
deltas = []
with ThreadPoolExecutor(max_workers=6) as pool:
    for status, row in pool.map(reprice, rows):
        stats[status] += 1
        if status != "drop":
            out.append(row)

# preserve original column order
with open(SNAP, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(fields))
    w.writeheader(); w.writerows(out)
print("Done:", stats, f"-> {len(out)} rows written")
