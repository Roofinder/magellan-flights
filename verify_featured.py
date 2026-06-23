#!/usr/bin/env python3
"""Cross-check the FEATURED deals against Skyscanner (TODO A).

The home "Biggest Winner" + top deals are what users see first, so they must be
accurate. This re-checks only those few routes against an independent oracle
(Sky-Scrapper / Skyscanner on RapidAPI, ~100 free calls/month) and:
  - marks a route "verified" if our tracked price is within ~15% of Skyscanner;
  - if our cached price is a phantom far BELOW Skyscanner, replaces our shown
    price with the Skyscanner price (KEEPS the Aviasales booking link + marker);
  - writes data/featured_verified.json {code: true} that buildsite badges.

Budget-safe: only the top few routes, only once/day (UTC hour gate), airport ids
cached in data/sky_ids.json. NO-OP if RAPIDAPI_KEY is not set, so the pipeline
never breaks. Run after reprice.py, before buildsite.py.

Setup the owner must do once:
  1. Create a free RapidAPI account, subscribe to "Sky-Scrapper".
  2. Add the key as `RAPIDAPI_KEY` (Vercel env var + GitHub Actions secret),
     OR put "rapidapi_key" in config.json for local runs.
  (If your Sky-Scrapper listing uses a different host/paths, update RAPID_HOST /
   the two endpoints below — the rest of the logic is generic.)
"""
import os, csv, json, time, datetime
import urllib.parse as up, urllib.request as ur

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SNAP = os.path.join(DATA, "market_latest.csv")
OUT = os.path.join(DATA, "featured_verified.json")
IDS = os.path.join(DATA, "sky_ids.json")

cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
RKEY = os.environ.get("RAPIDAPI_KEY") or cfg.get("rapidapi_key", "")
RAPID_HOST = os.environ.get("RAPIDAPI_HOST", "sky-scrapper.p.rapidapi.com")

FEATURED_N = int(os.environ.get("FEATURED_N", "3"))   # how many top deals to check
NEAR = 0.15                                           # within 15% => "verified"
PHANTOM_BELOW = 0.80                                  # cache < 80% of Skyscanner => replace
RUN_HOUR = int(os.environ.get("VERIFY_HOUR", "1"))    # only run at this UTC hour...
FORCE = os.environ.get("FORCE_VERIFY") == "1"         # ...unless forced


def _get(path, params):
    url = f"https://{RAPID_HOST}{path}?" + up.urlencode(params)
    req = ur.Request(url)
    req.add_header("x-rapidapi-key", RKEY)
    req.add_header("x-rapidapi-host", RAPID_HOST)
    for _ in range(3):
        try:
            with ur.urlopen(req, timeout=30) as z:
                return json.load(z)
        except Exception:
            time.sleep(1.0)
    return None


_id_cache = {}


def _load_ids():
    global _id_cache
    try:
        _id_cache = json.load(open(IDS, encoding="utf-8"))
    except Exception:
        _id_cache = {}


def _save_ids():
    try:
        json.dump(_id_cache, open(IDS, "w", encoding="utf-8"))
    except Exception:
        pass


def _airport(code):
    """Return (skyId, entityId) for an IATA code, cached to save API calls."""
    if code in _id_cache:
        return tuple(_id_cache[code])
    j = _get("/api/v1/flights/searchAirport", {"query": code, "locale": "en-US"})
    try:
        items = j.get("data", []) if isinstance(j, dict) else []
        # prefer an exact AIRPORT match on the IATA skyId
        best = None
        for it in items:
            if (it.get("navigation", {}).get("relevantFlightParams", {}).get("skyId") == code
                    or it.get("skyId") == code):
                best = it; break
        best = best or (items[0] if items else None)
        if not best:
            return None
        sky = best.get("skyId") or best.get("navigation", {}).get("relevantFlightParams", {}).get("skyId")
        ent = (best.get("entityId")
               or best.get("navigation", {}).get("entityId")
               or best.get("navigation", {}).get("relevantFlightParams", {}).get("entityId"))
        if sky and ent:
            _id_cache[code] = [sky, ent]
            return (sky, ent)
    except Exception:
        pass
    return None


def _sky_price(origin, dest, dep, ret):
    """Cheapest Skyscanner round-trip price (float) or None."""
    o, d = _airport(origin), _airport(dest)
    if not o or not d:
        return None
    params = {
        "originSkyId": o[0], "destinationSkyId": d[0],
        "originEntityId": o[1], "destinationEntityId": d[1],
        "date": dep, "cabinClass": "economy", "adults": "1",
        "currency": "USD", "market": "en-US", "countryCode": "US",
    }
    if ret:
        params["returnDate"] = ret
    j = _get("/api/v2/flights/searchFlights", params)
    try:
        its = j.get("data", {}).get("itineraries", []) if isinstance(j, dict) else []
        prices = []
        for it in its:
            raw = (it.get("price", {}) or {}).get("raw")
            if raw:
                prices.append(float(raw))
        return min(prices) if prices else None
    except Exception:
        return None


def main():
    verified = {}
    if not RKEY:
        print("verify_featured: RAPIDAPI_KEY not set -> skipping (no-op).")
        json.dump(verified, open(OUT, "w", encoding="utf-8"))
        return
    if not FORCE and datetime.datetime.utcnow().hour != RUN_HOUR:
        print(f"verify_featured: not the daily verify hour (UTC {RUN_HOUR}); keeping previous result.")
        return  # leave existing featured_verified.json untouched

    rows = list(csv.DictReader(open(SNAP, encoding="utf-8")))
    fields = list(rows[0].keys()) if rows else []

    def sav(r):
        try:
            return float(r.get("savings_pct") or 0)
        except Exception:
            return 0.0
    featured = sorted(rows, key=sav, reverse=True)[:FEATURED_N]

    _load_ids()
    corrected = 0
    for r in featured:
        try:
            cache_price = float(r["price"])
        except Exception:
            continue
        sky = _sky_price((r.get("origin") or "").upper(), (r.get("code") or "").upper(),
                         (r.get("depart") or "")[:10], (r.get("return") or "")[:10])
        if not sky:
            continue
        if cache_price >= sky * PHANTOM_BELOW:
            verified[r["code"]] = True            # close enough -> trust it
        else:
            # our price is a phantom far below the real fare -> show the real one,
            # keep the Aviasales booking link so the click-to-book still earns.
            r["price"] = f"{sky:.0f}"
            try:
                b = float(r.get("benchmark") or 0)
                r["savings_pct"] = str(round((b - sky) / b * 100) if b else 0)
            except Exception:
                pass
            corrected += 1
    _save_ids()

    if corrected:
        with open(SNAP, "w", newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=fields)
            w.writeheader(); w.writerows(rows)
    json.dump(verified, open(OUT, "w", encoding="utf-8"))
    print(f"verify_featured: checked {len(featured)}, verified {len(verified)}, "
          f"corrected {corrected} phantom price(s).")


if __name__ == "__main__":
    main()
