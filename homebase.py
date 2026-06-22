#!/usr/bin/env python3
"""
HomeBase - precomputes cheapest round-trip deals FROM many US home airports,
so the website can offer a personalized "My cities" view (e.g. set Raleigh/RDU
as your home and see the best deals leaving from there).

Writes data/homebase.json:
  { "RDU": {"name": "Raleigh/Durham", "deals": [ {code,name,price,depart,return,link}, ... ] }, ... }

    py homebase.py
    py homebase.py --top 18

Uses only the Python standard library. Reuses config.json + explore.py helpers.
"""

import argparse
import json
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import flightfinder as ff
import explore as ex

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
OUT = os.path.join(DATA_DIR, "homebase.json")
LATEST_URL = "https://api.travelpayouts.com/v2/prices/latest"
AVIASALES = "https://www.aviasales.com"

# A broad spread of US home airports people actually fly from (incl. mid-size).
HOME_AIRPORTS = {
    "JFK": "New York (JFK)", "EWR": "Newark", "LGA": "New York (LaGuardia)",
    "BOS": "Boston", "PHL": "Philadelphia", "IAD": "Washington Dulles",
    "DCA": "Washington Reagan", "BWI": "Baltimore", "RDU": "Raleigh/Durham",
    "CLT": "Charlotte", "ATL": "Atlanta", "MIA": "Miami", "FLL": "Fort Lauderdale",
    "MCO": "Orlando", "TPA": "Tampa", "BNA": "Nashville", "MEM": "Memphis",
    "ORD": "Chicago O'Hare", "MDW": "Chicago Midway", "DTW": "Detroit",
    "MSP": "Minneapolis", "STL": "St. Louis", "MCI": "Kansas City",
    "CLE": "Cleveland", "CMH": "Columbus", "IND": "Indianapolis", "PIT": "Pittsburgh",
    "CVG": "Cincinnati", "MKE": "Milwaukee", "DFW": "Dallas", "IAH": "Houston",
    "AUS": "Austin", "SAT": "San Antonio", "MSY": "New Orleans", "DEN": "Denver",
    "SLC": "Salt Lake City", "PHX": "Phoenix", "LAS": "Las Vegas", "LAX": "Los Angeles",
    "SAN": "San Diego", "SFO": "San Francisco", "SJC": "San Jose", "OAK": "Oakland",
    "SMF": "Sacramento", "SEA": "Seattle", "PDX": "Portland", "HNL": "Honolulu",
}


# Region coverage: keep the cheapest few PER REGION so every region is represented
# (otherwise an airport's top-N cheapest is all domestic/nearby and Europe etc. drop off).
PER_REGION = 5
MAX_PER_AIRPORT = 90
LM_REGIONS = ["USA", "Asia", "SE Asia", "E Asia", "S Asia", "W Europe", "E Europe",
              "Nordic", "S America", "C America", "Caribbean", "Oceania",
              "Middle East", "Africa", "Canada"]
_GROUPS = {
    "SE Asia": "TH VN ID SG MY PH KH LA MM BN TL".split(),
    "E Asia": "JP KR CN TW HK MO MN".split(),
    "S Asia": "IN LK NP PK BD MV BT AF".split(),
    "W Europe": "FR GB DE NL BE IE ES PT IT CH AT LU MC AD LI MT".split(),
    "Nordic": "SE NO DK FI IS".split(),
    "E Europe": "PL CZ HU RO BG GR HR RS SK SI UA EE LV LT AL BA MK ME MD BY RU CY".split(),
    "S America": "BR AR CL CO PE EC UY PY BO VE GF SR GY".split(),
    "C America": "MX GT BZ SV HN NI CR PA".split(),
    "Caribbean": "DO JM BS CU HT PR TT BB AW CW GP MQ KY BM AG LC GD VC DM KN TC VG AI MS SX BQ".split(),
    "Oceania": "AU NZ FJ PF NC WS TO VU PG CK GU".split(),
    "Middle East": "AE QA SA IL JO TR LB KW BH OM IR IQ YE SY".split(),
    "Africa": "ZA EG MA KE ET NG GH TZ SN CI TN DZ UG RW MU SC NA BW ZW MZ AO CM GA".split(),
    "Canada": "CA".split(),
}


def lmtags(cc):
    cc = (cc or "").upper()
    if cc == "US":
        return ["USA"]
    for grp, codes in _GROUPS.items():
        if cc in codes:
            tags = [grp]
            if grp in ("SE Asia", "E Asia", "S Asia"):
                tags.append("Asia")
            return tags
    return []


def cheapest_from(cfg, origin, period_type="year", limit=1000):
    params = {
        "currency": cfg["currency"], "origin": origin, "one_way": "false",
        "period_type": period_type, "show_to_affiliates": "true", "sorting": "price",
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


def link_for(cfg, origin, dest, depart, ret):
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
    p = argparse.ArgumentParser(description="Precompute cheapest deals from US home airports.")
    p.add_argument("--top", type=int, default=15, help="Deals to keep per airport (default 15)")
    p.add_argument("--within-days", type=int, default=10, help="Last-minute window (default 10)")
    args = p.parse_args()

    cfg = ff.load_config()
    ref = ex.ensure_refdata()
    namer, country_of = ex.build_namer(ref)
    today = date.today().isoformat()

    print(f"Building personalized deals for {len(HOME_AIRPORTS)} US home airports...")

    horizon = (date.today() + timedelta(days=args.within_days)).isoformat()

    def collect(origin, items, within_window):
        best = {}
        for item in items:
            dep = item.get("depart_date", "")[:10]
            ret = item.get("return_date", "")[:10]
            dest = item.get("destination")
            price = item.get("value")
            if not dest or price is None or not dep or not ret or dep < today or dest == origin:
                continue
            if within_window and dep > horizon:
                continue
            price = float(price)
            if dest not in best or price < best[dest]["price"]:
                best[dest] = {"code": dest, "name": namer(dest), "price": round(price),
                              "cc": country_of(dest), "depart": dep, "return": ret,
                              "link": link_for(cfg, origin, dest, dep, ret)}
        return best  # full dict; pick() ensures regional coverage

    def pick(best):
        sd = sorted(best.values(), key=lambda d: d["price"])
        out, seen = [], set()
        for region in LM_REGIONS:          # ensure cheapest few per region
            cnt = 0
            for d in sd:
                if d["code"] in seen:
                    continue
                if region in lmtags(d["cc"]):
                    out.append(d); seen.add(d["code"]); cnt += 1
                    if cnt >= PER_REGION:
                        break
        for d in sd:                       # then fill with overall cheapest
            if d["code"] not in seen:
                out.append(d); seen.add(d["code"])
                if len(out) >= args.top:
                    break
        out.sort(key=lambda d: d["price"])
        return out[:MAX_PER_AIRPORT]

    def work(origin):
        deals = pick(collect(origin, cheapest_from(cfg, origin, "year"), False))
        lastminute = pick(collect(origin, cheapest_from(cfg, origin, "month"), True))
        return origin, deals, lastminute

    result = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(work, o) for o in HOME_AIRPORTS]
        for fut in as_completed(futs):
            origin, deals, lastminute = fut.result()
            if deals or lastminute:
                result[origin] = {"name": HOME_AIRPORTS[origin], "deals": deals,
                                  "lastminute": lastminute}

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f)
    total = sum(len(v["deals"]) for v in result.values())
    print(f"Wrote {len(result)} airports / {total} deals -> {OUT}")


if __name__ == "__main__":
    main()
