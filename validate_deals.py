#!/usr/bin/env python3
"""Top-down deal validator — FREE, Travelpayouts-only (idea #1).

Coverage is already free: market.py + reprice.py give a price for EVERY route.
The remaining risk is that some CHEAP cached fares are stale phantoms — and a
phantom only hurts when it ranks high enough to be SHOWN. So instead of trying
to live-check all 1,000+ routes, we validate the ranking TOP-DOWN, only as deep
as we display:

  For the highest-savings candidates, cross-check each listed fare against the
  ROUTE'S OWN MONTH of fares from Travelpayouts (one extra query returns ~a
  month of prices — a free, broad sample). A real deal sits within that month's
  distribution (or is corroborated by other nearby-low fares); an isolated low
  far below the whole month is a phantom. We CONFIRM the real ones and REPRICE
  the phantoms to the cheapest *credible* fare from the same month (keeping an
  Aviasales booking link), then stop after MAX_CHECKS so calls stay bounded and
  within Travelpayouts' rate limits.

Adds a `confirmed` column to data/market_latest.csv (1 = cross-checked & trusted;
blank = not deep enough in the ranking to matter). buildsite can prefer/badge it.

Run AFTER reprice.py, BEFORE verify_featured.py.
"""
import os, csv, json, time, datetime, statistics
import urllib.parse as up, urllib.request as ur
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "data", "market_latest.csv")
AVIASALES = "https://www.aviasales.com"
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
TOKEN = cfg["api_token"]; MARKER = cfg.get("marker", "")
CUR = cfg.get("currency", "usd"); MKT = cfg.get("market", "us")
TODAY = datetime.date.today().isoformat()

MAX_CHECKS = int(os.environ.get("VALIDATE_MAX", "120"))  # how deep into the ranking to validate
FLOOR = float(os.environ.get("VALIDATE_FLOOR", "0.60"))  # a lone fare < 60% of its month's median = phantom
NEAR = 1.15            # "near the low" = within 15% of the listed fare
MIN_SAMPLES = 5        # need at least this many month fares to judge at all


def _call(params):
    params = dict(params); params.update({"currency": CUR, "market": MKT,
        "one_way": "false", "sorting": "price", "limit": "30", "token": TOKEN})
    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates?" + up.urlencode(params)
    req = ur.Request(url); req.add_header("X-Access-Token", TOKEN)
    for _ in range(3):
        try:
            with ur.urlopen(req, timeout=25) as z:
                return json.load(z).get("data", [])
        except Exception:
            time.sleep(0.6)
    return []


def _link(rel):
    if not rel:
        return ""
    u = AVIASALES + rel
    if MARKER and "marker=" not in u:
        u += ("&" if "?" in u else "?") + "marker=" + str(MARKER)
    return u


def _month(o, d, dep, ret):
    """A month's worth of fares for the route (cheap, broad sample)."""
    params = {"origin": o, "destination": d, "departure_at": dep[:7]}
    if ret:
        params["return_at"] = ret[:7]
    return _call(params)


def judge(listed, fares, floor=FLOOR, near=NEAR, min_samples=MIN_SAMPLES):
    """Cross-check `listed` (the shown fare) against `fares` (the route's month).

    Returns (verdict, fare_or_None):
      - ("confirmed", None): listed sits within the month's distribution, or its
        low is corroborated by >=2 other nearby-low fares -> trust it as-is.
      - ("repriced", fare): listed is an ISOLATED low far below the whole month
        -> a phantom; `fare` is the cheapest *credible* fare to show instead.
      - ("unknown", None): not enough month data to judge -> leave it untouched
        (do NOT claim it's confirmed).
    """
    prices = sorted(float(f["price"]) for f in fares if f.get("price"))
    if len(prices) < min_samples:
        return ("unknown", None)
    med = statistics.median(prices)
    if not med:
        return ("unknown", None)
    corroboration = sum(1 for p in prices if p <= listed * near)
    if listed >= floor * med or corroboration >= 2:
        return ("confirmed", None)
    # Isolated phantom: choose the cheapest fare that is itself credible.
    credible = sorted((f for f in fares
                       if f.get("price") and float(f["price"]) >= floor * med),
                      key=lambda f: float(f["price"]))
    return ("repriced", credible[0] if credible else None)


def _savings(r):
    try:
        return float(r.get("savings_pct") or 0)
    except Exception:
        return 0.0


def main():
    rows = list(csv.DictReader(open(SNAP, encoding="utf-8")))
    if not rows:
        print("validate_deals: no rows; nothing to do.")
        return
    fields = list(rows[0].keys())
    if "confirmed" not in fields:
        fields.append("confirmed")
    for r in rows:
        r.setdefault("confirmed", "")

    # Validate top-down: only the highest-ranked candidates can be "best deals".
    cands = sorted(rows, key=_savings, reverse=True)[:MAX_CHECKS]
    print(f"validate_deals: cross-checking top {len(cands)} of {len(rows)} routes "
          f"against each route's month (free Travelpayouts)...")

    def fetch(r):
        dep, ret = r.get("depart", ""), r.get("return", "")
        if not dep:
            return (r, [])
        return (r, _month(r["origin"], r["code"], dep, ret))

    stats = {"confirmed": 0, "repriced": 0, "unknown": 0}
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(fetch, cands))

    for r, fares in results:
        try:
            listed = float(r["price"])
        except Exception:
            continue
        verdict, fare = judge(listed, fares)
        if verdict == "confirmed":
            r["confirmed"] = "1"
            stats["confirmed"] += 1
        elif verdict == "repriced" and fare:
            price = float(fare["price"])
            try:
                bench = float(r.get("benchmark") or 0)
            except Exception:
                bench = 0.0
            r["price"] = f"{price:.0f}"
            r["airline"] = fare.get("airline", r.get("airline", ""))
            r["depart"] = (fare.get("departure_at", "") or r.get("depart", ""))[:10]
            r["return"] = (fare.get("return_at", "") or r.get("return", ""))[:10]
            r["booking_link"] = _link(fare.get("link", "")) or r.get("booking_link", "")
            r["savings_pct"] = str(round((bench - price) / bench * 100) if bench else 0)
            r["confirmed"] = "1"   # repriced to a credible fare -> now trustworthy
            stats["repriced"] += 1
        else:
            stats["unknown"] += 1   # leave confirmed blank

    with open(SNAP, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    print(f"validate_deals: done. confirmed={stats['confirmed']}, "
          f"repriced(phantoms fixed)={stats['repriced']}, "
          f"unknown(left as-is)={stats['unknown']}.")


if __name__ == "__main__":
    main()
