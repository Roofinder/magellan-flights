#!/usr/bin/env python3
"""Accuracy pass for the ONE-WAY / last-minute lists (TODO C).

reprice.py validates round-trip `market_latest.csv`. This does the same robust
exact-date re-query + phantom-rejection for the one-way + last-minute CSVs that
feed Explore / World / Last-minute, so the cheapest fares users actually see are
trustworthy and bookable.

To stay within the free API budget it only re-validates the CHEAPEST N rows of
each file (the ones shown at the top of every filtered view); the long, pricier
tail is left as-is. Keeps the Aviasales booking link (+marker). Run after the
generators (explore/world/lastminute) and before buildsite.py.
"""
import os, csv, json, time, datetime, glob
import urllib.parse as up, urllib.request as ur
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
AVIASALES = "https://www.aviasales.com"
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
TOKEN = cfg["api_token"]; MARKER = cfg.get("marker", "")
CUR = cfg.get("currency", "usd"); MKT = cfg.get("market", "us")
TODAY = datetime.date.today().isoformat()
TODAY_SD = datetime.date.today().strftime("%d%m%Y")
PHANTOM = 0.70
N_PER_FILE = int(os.environ.get("ONEWAY_VALIDATE_N", "180"))  # cheapest rows to check

# (filename glob, how many cheapest rows to validate)
FILES = [
    ("explore_oneway_6m_*.csv", N_PER_FILE),
    ("explore_oneway_lm_*.csv", N_PER_FILE),
    ("lastminute_all_*.csv",    N_PER_FILE),
    ("lastminute_intl_*.csv",   N_PER_FILE),
    ("world_any_*.csv",         N_PER_FILE),
    ("world_lm_*.csv",          N_PER_FILE),
]


def _latest(pat):
    g = sorted(glob.glob(os.path.join(HERE, pat)))
    return g[-1] if g else None


def _call(origin, dest, dep, ret):
    params = {"origin": origin, "destination": dest, "departure_at": dep,
              "currency": CUR, "market": MKT, "sorting": "price", "limit": "30",
              "one_way": "false" if ret else "true", "token": TOKEN}
    if ret:
        params["return_at"] = ret
    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates?" + up.urlencode(params)
    req = ur.Request(url); req.add_header("X-Access-Token", TOKEN)
    for _ in range(3):
        try:
            with ur.urlopen(req, timeout=25) as z:
                return json.load(z).get("data", [])
        except Exception:
            time.sleep(0.5)
    return None


def _link(rel):
    if not rel:
        return ""
    u = AVIASALES + rel if rel.startswith("/") else rel
    if MARKER and "marker=" not in u:
        u += ("&" if "?" in u else "?") + "marker=" + str(MARKER)
    return u


def _robust(fares):
    if not fares:
        return None
    fresh = [f for f in fares if ("search_date=" + TODAY_SD) in (f.get("link", "") or "")]
    pool = sorted(fresh if fresh else fares, key=lambda f: float(f["price"]))
    while len(pool) > 1 and float(pool[0]["price"]) < PHANTOM * float(pool[1]["price"]):
        pool.pop(0)
    return pool[0]


def _cols(fieldnames):
    """Map this file's schema to the columns we need."""
    fn = set(fieldnames)
    dest = "destination_code" if "destination_code" in fn else ("code" if "code" in fn else None)
    ret = "return" if "return" in fn else None
    link = "booking_link" if "booking_link" in fn else None
    have = all(c in fn for c in ("origin", "price")) and dest and link
    return (have, dest, ret, link)


def process(path, N):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        return path, (0, 0, 0)
    fields = list(rows[0].keys())
    have, DCOL, RCOL, LCOL = _cols(fields)
    if not have:
        return path, (0, 0, 0)
    # index rows by price; validate the cheapest N
    order = sorted(range(len(rows)), key=lambda i: float(rows[i]["price"] or 1e9))
    target = set(order[:N])

    def fix(i):
        r = rows[i]
        o, d = (r.get("origin") or "").upper(), (r.get(DCOL) or "").upper()
        dep = (r.get("depart") or "")[:10]
        ret = (r.get(RCOL) or "")[:10] if RCOL else ""
        if not (o and d and dep):
            return i, "keep"
        data = _call(o, d, dep, ret)
        if data is None:
            return i, "keep"      # transient API failure — leave row untouched
        f = _robust(data)
        if not f:
            return i, "drop"      # no verifiable fare — phantom / sold out
        r["price"] = f"{float(f['price']):.0f}"
        r[LCOL] = _link(f.get("link", ""))
        if "depart" in r:
            r["depart"] = (f.get("departure_at", "") or dep)[:10]
        if RCOL and r.get(RCOL):
            r[RCOL] = (f.get("return_at", "") or ret)[:10]
        return i, "fixed"

    drop, fixed = set(), 0
    with ThreadPoolExecutor(max_workers=12) as pool:
        for i, status in pool.map(fix, target):
            if status == "drop":
                drop.add(i)
            elif status == "fixed":
                fixed += 1

    out = [r for j, r in enumerate(rows) if j not in drop]
    with open(path, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader(); w.writerows(out)
    return path, (len(target), fixed, len(drop))


if __name__ == "__main__":
    for pat, n in FILES:
        p = _latest(pat)
        if not p:
            print(f"skip {pat} (not found)")
            continue
        _, (checked, fixed, dropped) = process(p, n)
        print(f"{os.path.basename(p)}: checked {checked}, repriced {fixed}, dropped {dropped} phantom(s)")
    print("One-way accuracy pass done.")
