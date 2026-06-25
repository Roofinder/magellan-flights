#!/usr/bin/env python3
"""
DealsGen - Daily cheap-flight DEALS generator for social media + newsletter.

Scans popular bucket-list destinations from across the USA, finds genuine
bargains (priced below a typical benchmark fare), and writes ready-to-post
content for every channel, with YOUR Travelpayouts affiliate booking links
baked in:

    deals_YYYYMMDD/
        instagram_facebook.txt   - caption per deal + a roundup carousel caption
        tiktok.txt               - short captions for TikTok / Reels / Shorts
        video_scripts.txt        - scene-by-scene scripts for short videos
        newsletter.md            - a full weekly deals email
        newsletter.html          - same, ready to paste into your email tool
        deals.csv                - the raw data

Run it:
    py dealsgen.py
    py dealsgen.py --depart 2026-10 --return 2026-11
    py dealsgen.py --top 8 --min-savings 15

Uses only the Python standard library. Reuses your config.json + the search
engine in flightfinder.py.
"""

import argparse
import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

import flightfinder as ff  # reuse config + search engine

HERE = os.path.dirname(os.path.abspath(__file__))

# Origins we scan for deals (major US international gateways). Fewer than the
# full list keeps a daily run fast; widen if you like.
DEALS_ORIGINS = [
    "JFK", "EWR", "LGA", "BOS", "IAD", "DCA", "BWI", "PHL", "ATL", "MIA",
    "FLL", "MCO", "TPA", "ORD", "MDW", "DTW", "MSP", "CLT", "RDU", "BNA",
    "IAH", "DFW", "DAL", "AUS", "SAT", "MSY", "DEN", "PHX", "LAS", "SLC",
    "LAX", "SFO", "SAN", "SJC", "OAK", "SNA", "SEA", "PDX", "STL", "MCI",
    "CLE", "CVG", "PIT", "IND", "CMH", "MKE", "RSW", "SMF", "HNL", "ANC",
]

# Curated bucket-list destinations with a rough "typical" round-trip economy
# benchmark from the US (USD). We flag a DEAL when the found price beats this.
# Benchmarks are deliberately conservative; tune them as you learn real prices.
DESTINATIONS = [
    # code   name                     emoji  benchmark
    # --- Asia ---
    ("BKK", "Bangkok, Thailand",      "🇹🇭", 1100),
    ("DPS", "Bali, Indonesia",        "🌴", 1300),
    ("HKT", "Phuket, Thailand",       "🏝️", 1200),
    ("SGN", "Ho Chi Minh, Vietnam",   "🇻🇳", 1100),
    ("HAN", "Hanoi, Vietnam",         "🇻🇳", 1150),
    ("NRT", "Tokyo, Japan",           "🗼", 1200),
    ("KIX", "Osaka, Japan",           "🏯", 1250),
    ("ICN", "Seoul, South Korea",     "🇰🇷", 1100),
    ("SIN", "Singapore",              "🇸🇬", 1200),
    ("KUL", "Kuala Lumpur, Malaysia", "🇲🇾", 1200),
    ("MNL", "Manila, Philippines",    "🇵🇭", 1100),
    ("DEL", "Delhi, India",           "🇮🇳", 1200),
    ("BOM", "Mumbai, India",          "🇮🇳", 1300),
    ("HKG", "Hong Kong",              "🇭🇰", 1100),
    ("TPE", "Taipei, Taiwan",         "🇹🇼", 1050),
    ("KTM", "Kathmandu, Nepal",       "🏔️", 1400),
    # --- Middle East ---
    ("DXB", "Dubai, UAE",             "🏜️", 1100),
    ("DOH", "Doha, Qatar",            "🇶🇦", 1150),
    ("IST", "Istanbul, Turkey",       "🇹🇷", 900),
    ("TLV", "Tel Aviv, Israel",       "🇮🇱", 1200),
    # --- Europe ---
    ("LHR", "London, UK",             "🇬🇧", 750),
    ("CDG", "Paris, France",          "🗼", 800),
    ("FCO", "Rome, Italy",            "🇮🇹", 850),
    ("BCN", "Barcelona, Spain",       "🇪🇸", 800),
    ("MAD", "Madrid, Spain",          "🇪🇸", 820),
    ("LIS", "Lisbon, Portugal",       "🇵🇹", 750),
    ("AMS", "Amsterdam, Netherlands", "🇳🇱", 760),
    ("FRA", "Frankfurt, Germany",     "🇩🇪", 800),
    ("ATH", "Athens, Greece",         "🏛️", 900),
    ("DUB", "Dublin, Ireland",        "🇮🇪", 700),
    ("KEF", "Reykjavik, Iceland",     "🌋", 600),
    ("PRG", "Prague, Czechia",        "🇨🇿", 850),
    ("CPH", "Copenhagen, Denmark",    "🇩🇰", 860),
    # --- Americas (Latin America / Caribbean) ---
    ("MEX", "Mexico City, Mexico",    "🌮", 450),
    ("CUN", "Cancun, Mexico",         "🏖️", 450),
    ("SJD", "Los Cabos, Mexico",      "🏖️", 520),
    ("PTY", "Panama City, Panama",    "🇵🇦", 550),
    ("SJO", "San Jose, Costa Rica",   "🇨🇷", 560),
    ("SJU", "San Juan, Puerto Rico",  "🇵🇷", 400),
    ("PUJ", "Punta Cana, Dom. Rep.",  "🌴", 520),
    ("NAS", "Nassau, Bahamas",        "🏝️", 450),
    ("BOG", "Bogota, Colombia",       "🇨🇴", 550),
    ("LIM", "Lima, Peru",             "🇵🇪", 650),
    ("GRU", "Sao Paulo, Brazil",      "🇧🇷", 900),
    ("EZE", "Buenos Aires, Argentina","🇦🇷", 950),
    ("SCL", "Santiago, Chile",        "🇨🇱", 820),
    # --- Oceania ---
    ("SYD", "Sydney, Australia",      "🇦🇺", 1500),
    ("MEL", "Melbourne, Australia",   "🇦🇺", 1500),
    ("AKL", "Auckland, New Zealand",  "🇳🇿", 1450),
    ("NAN", "Nadi, Fiji",             "🇫🇯", 1300),
    # --- Africa ---
    ("CAI", "Cairo, Egypt",           "🇪🇬", 1100),
    ("CMN", "Casablanca, Morocco",    "🇲🇦", 900),
    ("JNB", "Johannesburg, S. Africa","🇿🇦", 1300),
    ("NBO", "Nairobi, Kenya",         "🇰🇪", 1300),
    # --- Expanded tracking set (added to reach 100+ routes) ---
    # Europe
    ("MUC", "Munich, Germany",        "🇩🇪", 820),
    ("ZRH", "Zurich, Switzerland",    "🇨🇭", 860),
    ("VIE", "Vienna, Austria",        "🇦🇹", 860),
    ("BRU", "Brussels, Belgium",      "🇧🇪", 800),
    ("MXP", "Milan, Italy",           "🇮🇹", 820),
    ("VCE", "Venice, Italy",          "🛶", 880),
    ("NCE", "Nice, France",           "🇫🇷", 880),
    ("EDI", "Edinburgh, Scotland",    "🏴", 770),
    ("MAN", "Manchester, UK",         "🇬🇧", 750),
    ("GVA", "Geneva, Switzerland",    "🏔", 880),
    ("OSL", "Oslo, Norway",           "🇳🇴", 830),
    ("ARN", "Stockholm, Sweden",      "🇸🇪", 830),
    ("HEL", "Helsinki, Finland",      "🇫🇮", 860),
    ("WAW", "Warsaw, Poland",         "🇵🇱", 800),
    ("BUD", "Budapest, Hungary",      "🇭🇺", 850),
    ("KRK", "Krakow, Poland",         "🇵🇱", 830),
    ("OPO", "Porto, Portugal",        "🇵🇹", 770),
    # Asia
    ("PEK", "Beijing, China",         "🇨🇳", 1100),
    ("PVG", "Shanghai, China",        "🇨🇳", 1100),
    ("CAN", "Guangzhou, China",       "🇨🇳", 1150),
    ("CTU", "Chengdu, China",         "🐼", 1250),
    ("CGK", "Jakarta, Indonesia",     "🇮🇩", 1250),
    ("REP", "Siem Reap, Cambodia",    "🛕", 1250),
    ("PNH", "Phnom Penh, Cambodia",   "🇰🇭", 1250),
    ("CMB", "Colombo, Sri Lanka",     "🇱🇰", 1300),
    ("MLE", "Male, Maldives",         "🏝", 1350),
    ("BLR", "Bangalore, India",       "🇮🇳", 1300),
    ("MAA", "Chennai, India",         "🇮🇳", 1300),
    ("FUK", "Fukuoka, Japan",         "🇯🇵", 1300),
    ("CEB", "Cebu, Philippines",      "🇵🇭", 1200),
    ("KHH", "Kaohsiung, Taiwan",      "🇹🇼", 1150),
    # Middle East
    ("AUH", "Abu Dhabi, UAE",         "🇦🇪", 1100),
    ("RUH", "Riyadh, Saudi Arabia",   "🇸🇦", 1250),
    ("JED", "Jeddah, Saudi Arabia",   "🇸🇦", 1300),
    ("AMM", "Amman, Jordan",          "🇯🇴", 1200),
    ("BEY", "Beirut, Lebanon",        "🇱🇧", 1250),
    ("MCT", "Muscat, Oman",           "🇴🇲", 1250),
    # Americas
    ("GIG", "Rio de Janeiro, Brazil", "🇧🇷", 950),
    ("UIO", "Quito, Ecuador",         "🇪🇨", 700),
    ("CTG", "Cartagena, Colombia",    "🇨🇴", 600),
    ("MDE", "Medellin, Colombia",     "🇨🇴", 600),
    ("GUA", "Guatemala City",         "🇬🇹", 550),
    ("MBJ", "Montego Bay, Jamaica",   "🇯🇲", 520),
    ("AUA", "Aruba",                  "🇦🇼", 600),
    ("CUR", "Curacao",                "🇨🇼", 650),
    ("BGI", "Bridgetown, Barbados",   "🇧🇧", 750),
    ("KIN", "Kingston, Jamaica",      "🇯🇲", 560),
    ("GCM", "Grand Cayman",           "🇰🇾", 600),
    ("BZE", "Belize City, Belize",    "🇧🇿", 560),
    ("SDQ", "Santo Domingo, Dom. Rep.","🇩🇴", 520),
    ("STT", "St. Thomas, USVI",       "🇻🇮", 560),
    ("LIR", "Liberia, Costa Rica",    "🇨🇷", 600),
    # Oceania
    ("BNE", "Brisbane, Australia",    "🇦🇺", 1500),
    ("PER", "Perth, Australia",       "🇦🇺", 1700),
    ("CHC", "Christchurch, NZ",       "🇳🇿", 1550),
    ("PPT", "Papeete, Tahiti",        "🏝", 1350),
    # Africa
    ("RAK", "Marrakech, Morocco",     "🇲🇦", 980),
    ("ACC", "Accra, Ghana",           "🇬🇭", 1300),
    ("LOS", "Lagos, Nigeria",         "🇳🇬", 1350),
    ("ADD", "Addis Ababa, Ethiopia",  "🇪🇹", 1350),
    ("CPT", "Cape Town, S. Africa",   "🇿🇦", 1450),
    ("DKR", "Dakar, Senegal",         "🇸🇳", 1150),
    # --- Expansion to ~150 routes ---
    ("CTS", "Sapporo, Japan",            "🌍", 1300),
    ("OKA", "Okinawa, Japan",            "🌍", 1300),
    ("CNX", "Chiang Mai, Thailand",      "🌍", 1200),
    ("DAD", "Da Nang, Vietnam",          "🌍", 1150),
    ("USM", "Koh Samui, Thailand",       "🌍", 1250),
    ("GOI", "Goa, India",                "🌍", 1300),
    ("COK", "Kochi, India",              "🌍", 1300),
    ("PEN", "Penang, Malaysia",          "🌍", 1200),
    ("SUB", "Surabaya, Indonesia",       "🌍", 1250),
    ("KWI", "Kuwait City",               "🌍", 1200),
    ("BAH", "Bahrain",                   "🌍", 1200),
    ("GYD", "Baku, Azerbaijan",          "🌍", 1150),
    ("TBS", "Tbilisi, Georgia",          "🌍", 1150),
    ("EVN", "Yerevan, Armenia",          "🌍", 1150),
    ("HAM", "Hamburg, Germany",          "🌍", 820),
    ("DUS", "Dusseldorf, Germany",       "🌍", 820),
    ("BER", "Berlin, Germany",           "🌍", 800),
    ("STR", "Stuttgart, Germany",        "🌍", 840),
    ("CGN", "Cologne, Germany",          "🌍", 820),
    ("SOF", "Sofia, Bulgaria",           "🌍", 850),
    ("OTP", "Bucharest, Romania",        "🌍", 820),
    ("BEG", "Belgrade, Serbia",          "🌍", 830),
    ("ZAG", "Zagreb, Croatia",           "🌍", 880),
    ("SPU", "Split, Croatia",            "🌍", 920),
    ("DBV", "Dubrovnik, Croatia",        "🌍", 950),
    ("TLL", "Tallinn, Estonia",          "🌍", 880),
    ("RIX", "Riga, Latvia",              "🌍", 870),
    ("VNO", "Vilnius, Lithuania",        "🌍", 870),
    ("BLQ", "Bologna, Italy",            "🌍", 880),
    ("FLR", "Florence, Italy",           "🌍", 900),
    ("NAP", "Naples, Italy",             "🌍", 900),
    ("CTA", "Catania, Italy",            "🌍", 920),
    ("AGP", "Malaga, Spain",             "🌍", 840),
    ("SVQ", "Seville, Spain",            "🌍", 860),
    ("VLC", "Valencia, Spain",           "🌍", 840),
    ("FAO", "Faro, Portugal",            "🌍", 800),
    ("LYS", "Lyon, France",              "🌍", 860),
    ("MRS", "Marseille, France",         "🌍", 870),
    ("GLA", "Glasgow, Scotland",         "🌍", 780),
    ("BHX", "Birmingham, UK",            "🌍", 770),
    ("YYZ", "Toronto, Canada",           "🌍", 350),
    ("YVR", "Vancouver, Canada",         "🌍", 450),
    ("YUL", "Montreal, Canada",          "🌍", 350),
    ("YYC", "Calgary, Canada",           "🌍", 450),
    ("SAL", "San Salvador",              "🌍", 500),
    ("TGU", "Tegucigalpa, Honduras",     "🌍", 550),
    ("MGA", "Managua, Nicaragua",        "🌍", 550),
    ("GYE", "Guayaquil, Ecuador",        "🌍", 700),
    ("FOR", "Fortaleza, Brazil",         "🌍", 950),
    ("REC", "Recife, Brazil",            "🌍", 950),
    ("SSA", "Salvador, Brazil",          "🌍", 950),
    ("FLN", "Florianopolis, Brazil",     "🌍", 1000),
    ("SXM", "St. Maarten",               "🌍", 600),
    ("ANU", "Antigua",                   "🌍", 650),
    ("UVF", "St. Lucia",                 "🌍", 700),
    ("GND", "Grenada",                   "🌍", 700),
    ("POS", "Port of Spain, Trinidad",   "🌍", 700),
    ("PLS", "Providenciales, Turks",     "🌍", 550),
    ("FPO", "Freeport, Bahamas",         "🌍", 480),
    ("CNS", "Cairns, Australia",         "🌍", 1500),
    ("ADL", "Adelaide, Australia",       "🌍", 1550),
    ("WLG", "Wellington, NZ",            "🌍", 1500),
    ("ZQN", "Queenstown, NZ",            "🌍", 1550),
    ("TUN", "Tunis, Tunisia",            "🌍", 950),
    ("AGA", "Agadir, Morocco",           "🌍", 980),
    ("HRG", "Hurghada, Egypt",           "🌍", 1100),
    ("SSH", "Sharm El Sheikh, Egypt",    "🌍", 1100),
    ("MBA", "Mombasa, Kenya",            "🌍", 1350),
    ("ZNZ", "Zanzibar, Tanzania",        "🌍", 1450),
    ("JRO", "Kilimanjaro, Tanzania",     "🌍", 1400),
    ("MRU", "Mauritius",                 "🌍", 1500),
]

# Best time to visit (general averages) — shown to travelers and used by the bot.
BEST_TIME = {
    "BKK": "Nov–Mar (cool & dry)", "DPS": "Apr–Oct (dry season)",
    "HKT": "Nov–Apr (dry)", "SGN": "Dec–Apr (dry)", "HAN": "Oct–Apr (cooler)",
    "NRT": "Mar–May (blossoms) & Oct–Nov (fall)", "KIX": "Mar–May & Oct–Nov",
    "ICN": "Apr–Jun & Sep–Nov", "SIN": "Feb–Apr (driest)", "KUL": "May–Jul (drier)",
    "MNL": "Dec–Apr (dry)", "DEL": "Oct–Mar (cooler)", "BOM": "Nov–Feb (cool, dry)",
    "HKG": "Oct–Dec (mild, dry)", "TPE": "Oct–Apr (cooler, drier)",
    "KTM": "Oct–Nov & Mar–Apr (clear skies)",
    "DXB": "Nov–Mar (mild)", "DOH": "Nov–Mar (mild)", "IST": "Apr–May & Sep–Oct",
    "TLV": "Apr–Jun & Sep–Nov",
    "LHR": "May–Sep (warmest); Apr/Oct cheaper", "CDG": "Apr–Jun & Sep–Oct",
    "FCO": "Apr–Jun & Sep–Oct", "BCN": "May–Jun & Sep", "MAD": "Mar–May & Sep–Nov",
    "LIS": "Mar–May & Sep–Oct", "AMS": "Apr–May (tulips) & Sep", "FRA": "May–Sep",
    "ATH": "Apr–Jun & Sep–Oct", "DUB": "May–Sep", "KEF": "Jun–Aug (mild) / Sep–Mar (auroras)",
    "PRG": "May–Jun & Sep", "CPH": "Jun–Aug (summer)",
    "MEX": "Mar–May (dry)", "CUN": "Dec–Apr (dry season)", "SJD": "Oct–May",
    "PTY": "Dec–Apr (dry)", "SJO": "Dec–Apr (dry)", "SJU": "Dec–Apr (peak); Apr–Jun value",
    "ANC": "Jun–Aug (long days) / Sep–Mar (auroras)", "GOH": "Jun–Sep (mild, ice-free fjords)",
    "PUJ": "Dec–Apr (dry)", "NAS": "Dec–Apr", "BOG": "Dec–Mar & Jul–Aug (drier)",
    "LIM": "May–Oct (dry; best for Machu Picchu)", "GRU": "Apr–Oct (cooler, drier)",
    "EZE": "Mar–May & Sep–Nov", "SCL": "Sep–Nov & Mar–May",
    "SYD": "Sep–Nov & Mar–May", "MEL": "Mar–May & Sep–Nov", "AKL": "Dec–Mar (summer)",
    "NAN": "May–Oct (dry season)",
    "CAI": "Oct–Apr (cooler)", "CMN": "Apr–Jun & Sep–Nov",
    "JNB": "May–Sep (dry, safari)", "NBO": "Jun–Oct (dry, migration)",
}

# "Things to know before you go" per destination. Visa is for US passport holders.
# General guidance only — travelers should verify official sources.
def _i(lang, eng, visa, safe, note):
    return {"lang": lang, "eng": eng, "visa": visa, "safe": safe, "note": note}


DEST_INFO = {
    "BKK": _i("Thai", "Common in tourist areas", "Visa-free, 60 days", "Generally safe", "Carry cash; dress modestly at temples"),
    "DPS": _i("Indonesian / Balinese", "Widely spoken in Bali", "Visa on arrival (~$35)", "Generally safe", "Mind the traffic; cash for small vendors"),
    "HKT": _i("Thai", "Common in tourist areas", "Visa-free, 60 days", "Generally safe", "Beware jet-ski/scam rentals"),
    "SGN": _i("Vietnamese", "Limited outside cities", "eVisa required", "Generally safe", "Use cash; cross streets at a steady pace"),
    "HAN": _i("Vietnamese", "Limited outside cities", "eVisa required", "Generally safe", "Bargain at markets; cash is king"),
    "NRT": _i("Japanese", "Limited, but English signage", "Visa-free, 90 days", "Very safe", "Cash still common; get an IC transit card"),
    "KIX": _i("Japanese", "Limited, but English signage", "Visa-free, 90 days", "Very safe", "ICOCA card for trains"),
    "ICN": _i("Korean", "Common among younger people", "K-ETA / visa-free 90 days", "Very safe", "T-money card for transit"),
    "SIN": _i("English, Malay, Mandarin, Tamil", "Official language", "Visa-free, 90 days", "Very safe", "Strict laws and fines; spotless city"),
    "KUL": _i("Malay", "Widely spoken", "Visa-free, 90 days", "Generally safe", "Modest dress at mosques"),
    "MNL": _i("Filipino, English", "Widely spoken", "Visa-free, 30 days", "Use caution in some areas", "Heed regional advisories (Mindanao)"),
    "DEL": _i("Hindi, English", "Widely spoken", "eVisa required", "Use caution", "Bottled water; solo women take extra care"),
    "BOM": _i("Hindi, English", "Widely spoken", "eVisa required", "Use caution", "Use ride apps; bottled water"),
    "HKG": _i("Cantonese, English", "Widely spoken", "Visa-free, 90 days", "Generally safe", "Octopus card for transit"),
    "TPE": _i("Mandarin", "Limited, but English signage", "Visa-free, 90 days", "Very safe", "EasyCard for transit"),
    "KTM": _i("Nepali", "Common in tourism", "Visa on arrival", "Generally safe", "Acclimatize before trekking"),
    "DXB": _i("Arabic", "Widely spoken", "Visa-free, 30 days", "Very safe", "Modest dress; strict alcohol/drug laws"),
    "DOH": _i("Arabic", "Widely spoken", "Visa-free, 30 days", "Very safe", "Modest dress in public"),
    "IST": _i("Turkish", "Common in tourist areas", "Visa-free, 90 days", "Generally safe", "Avoid border regions; bargain in bazaars"),
    "TLV": _i("Hebrew, Arabic", "Widely spoken", "Visa-free, 90 days", "Check current advisories", "Verify regional travel advisories first"),
    "LHR": _i("English", "Native", "ETA required (apply online)", "Generally safe", "Contactless pay everywhere"),
    "CDG": _i("French", "Common in Paris", "Visa-free, 90 days", "Generally safe", "Watch for pickpockets at sights"),
    "FCO": _i("Italian", "Common in tourist areas", "Visa-free, 90 days", "Generally safe", "Validate train tickets; mind pickpockets"),
    "BCN": _i("Spanish, Catalan", "Common in tourist areas", "Visa-free, 90 days", "Generally safe", "Pickpockets are common — guard bags"),
    "MAD": _i("Spanish", "Common in tourist areas", "Visa-free, 90 days", "Generally safe", "Late dinners; siesta hours"),
    "LIS": _i("Portuguese", "Widely spoken", "Visa-free, 90 days", "Very safe", "Hilly streets; great value"),
    "AMS": _i("Dutch", "Almost universal", "Visa-free, 90 days", "Very safe", "Never walk in the bike lanes"),
    "FRA": _i("German", "Widely spoken", "Visa-free, 90 days", "Very safe", "Carry some cash"),
    "ATH": _i("Greek", "Common in tourism", "Visa-free, 90 days", "Generally safe", "Book island ferries early"),
    "DUB": _i("English", "Native", "Visa-free, 90 days", "Very safe", "Weather changes fast — layers"),
    "KEF": _i("Icelandic", "Almost universal", "Visa-free, 90 days", "Very safe", "Pricey; rent a car to explore"),
    "PRG": _i("Czech", "Common in Prague", "Visa-free, 90 days", "Very safe", "Pay in koruna; use trams"),
    "CPH": _i("Danish", "Almost universal", "Visa-free, 90 days", "Very safe", "Card-only in many spots; pricey"),
    "MEX": _i("Spanish", "Common in tourist areas", "Visa-free, up to 180 days", "Use caution; varies by region", "Use Uber / registered taxis"),
    "CUN": _i("Spanish", "Common in resort areas", "Visa-free, up to 180 days", "Resort areas generally safe", "Stick to known zones at night"),
    "SJD": _i("Spanish", "Common in resort areas", "Visa-free, up to 180 days", "Generally safe", "USD widely accepted"),
    "PTY": _i("Spanish", "Common in the city", "Visa-free, 180 days", "Generally safe", "USD is the currency"),
    "SJO": _i("Spanish", "Common in tourism", "Visa-free, 90 days", "Generally safe", "Rainy season May–Nov"),
    "ANC": _i("English", "Native", "None for US citizens (Alaska is a US state)", "Very safe; weather & wildlife are the main cautions", "Pack layers year-round; endless summer daylight, winter auroras"),
    "GOH": _i("Greenlandic & Danish", "Common in tourism", "Visa-free for US citizens (Kingdom of Denmark)", "Very safe; plan for changeable Arctic weather", "Flights are seasonal & weather-dependent — book flexible"),
    "SJU": _i("Spanish, English", "Widely spoken", "US territory — no passport for US citizens", "Generally safe", "No passport needed for US travelers"),
    "PUJ": _i("Spanish", "Common in resorts", "Visa-free (tourist card)", "Resort areas generally safe", "Stay within resort areas"),
    "NAS": _i("English", "Native", "Visa-free, 90 days", "Generally safe", "USD accepted alongside local $"),
    "BOG": _i("Spanish", "Limited", "Visa-free, 90 days", "Use caution", "Don't flash valuables; use ride apps"),
    "LIM": _i("Spanish", "Limited", "Visa-free, 90 days", "Use caution", "Altitude in Cusco; bottled water"),
    "GRU": _i("Portuguese", "Limited", "Visa-free, 90 days", "Use caution in cities", "Guard valuables; use taxi apps"),
    "EZE": _i("Spanish", "Limited", "Visa-free, 90 days", "Generally safe", "Bring USD; great steak/wine"),
    "SCL": _i("Spanish", "Limited", "Visa-free, 90 days", "Generally safe", "Watch bags in central Santiago"),
    "SYD": _i("English", "Native", "ETA / eVisitor (online)", "Very safe", "Strong sun — wear SPF"),
    "MEL": _i("English", "Native", "ETA / eVisitor (online)", "Very safe", "Four seasons in a day — layers"),
    "AKL": _i("English, Maori", "Native", "NZeTA required (online)", "Very safe", "Drive on the left"),
    "NAN": _i("English, Fijian", "Widely spoken", "Visa-free, 4 months", "Generally safe", "Respect village customs (sevusevu)"),
    "CAI": _i("Arabic", "Common in tourism", "eVisa / visa on arrival", "Use caution; check advisories", "Cover shoulders at religious sites"),
    "CMN": _i("Arabic, French", "Limited", "Visa-free, 90 days", "Generally safe", "Bargain in souks; modest dress"),
    "JNB": _i("English + others", "Widely spoken", "Visa-free, 90 days", "Use caution; crime in some areas", "Avoid walking at night; pre-book transfers"),
    "NBO": _i("Swahili, English", "Widely spoken", "eTA required", "Use caution; check advisories", "Malaria precautions for safari"),
}

GENERIC_HASHTAGS = (
    "#cheapflights #flightdeals #traveldeals #budgettravel #wanderlust "
    "#traveltok #airfare #travelhacks #flightalert #cheapflightalert"
)

# Short FTC-style affiliate disclosure. Keep this on your posts/newsletter.
DISCLOSURE = "Affiliate link — we may earn a small commission at no extra cost to you."


def default_months():
    """Pick a depart month ~3 months out and return the month after."""
    today = date.today()
    m = today.month - 1 + 3
    y = today.year + m // 12
    dep = date(y, m % 12 + 1, 1)
    m2 = dep.month - 1 + 1
    y2 = dep.year + m2 // 12
    ret = date(y2, m2 % 12 + 1, 1)
    return dep.strftime("%Y-%m"), ret.strftime("%Y-%m")


def find_deals(cfg, depart, ret, min_savings):
    """For each destination, search all DEALS_ORIGINS and keep the cheapest.
    Returns a list of deal dicts sorted best-savings-first."""
    tasks = []  # (origin, code, name, emoji, benchmark)
    for code, name, emoji, bench in DESTINATIONS:
        for origin in DEALS_ORIGINS:
            tasks.append((origin, code, name, emoji, bench))

    best_per_dest = {}  # code -> best result
    print(f"Scanning {len(DESTINATIONS)} destinations from {len(DEALS_ORIGINS)} "
          f"US origins ({len(tasks)} searches)...")

    def work(t):
        origin, code, name, emoji, bench = t
        r = ff.search_one_origin(cfg, origin, code, depart, ret, one_way=False)
        return (code, name, emoji, bench, r)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = [pool.submit(work, t) for t in tasks]
        for fut in as_completed(futs):
            code, name, emoji, bench, r = fut.result()
            if r.get("status") != "ok":
                continue
            cur = best_per_dest.get(code)
            if cur is None or r["price"] < cur["price"]:
                best_per_dest[code] = {
                    "code": code, "name": name, "emoji": emoji,
                    "benchmark": bench, **r,
                }

    deals = []
    for code, d in best_per_dest.items():
        savings = d["benchmark"] - d["price"]
        pct = round(savings / d["benchmark"] * 100) if d["benchmark"] else 0
        d["savings"] = savings
        d["savings_pct"] = pct
        deals.append(d)

    deals.sort(key=lambda d: d["savings_pct"], reverse=True)
    qualified = [d for d in deals if d["savings_pct"] >= min_savings]
    # If nothing clears the bar, still surface the best few so you always post.
    return (qualified if qualified else deals[:5]), deals


def fmt_dates(d):
    f = d["fare"]
    dep = f.get("departure_at", "")[:10]
    ret = f.get("return_at", "")[:10]
    return dep, ret


def instagram_caption(cfg, d):
    dep, ret = fmt_dates(d)
    origin = ff.AIRPORT_NAMES.get(d["origin"], d["origin"])
    link = ff.booking_link(cfg, d)
    pct = d["savings_pct"]
    hook = (f"\U0001F6A8 FLIGHT DEAL: {d['name']} {d['emoji']} for ${d['price']:,.0f} round-trip!"
            if pct > 0 else
            f"✈️ {d['name']} {d['emoji']} — ${d['price']:,.0f} round-trip")
    body = [
        hook, "",
        f"\U0001F4CD From: {origin} ({d['origin']})",
        f"\U0001F4B0 Price: ${d['price']:,.0f} round-trip"
        + (f"  (normally ~${d['benchmark']:,.0f} — save ~{pct}%!)" if pct > 0 else ""),
        f"\U0001F4C5 Sample dates: {dep} → {ret}",
        "",
        "\U0001F517 Book / see live price (link in bio or below):",
        link, "",
        "⚡ Fares change fast — grab it before it's gone!",
        DISCLOSURE, "",
        f"#{d['name'].split(',')[0].replace(' ', '').lower()} " + GENERIC_HASHTAGS,
    ]
    return "\n".join(body)


def roundup_caption(cfg, deals):
    lines = ["\U0001F30D THIS WEEK'S CHEAPEST ESCAPES FROM THE USA \U0001F9F3✨", ""]
    for i, d in enumerate(deals, 1):
        pct = d["savings_pct"]
        tag = f" (save ~{pct}%)" if pct > 0 else ""
        lines.append(f"{i}. {d['emoji']} {d['name']} — ${d['price']:,.0f} RT "
                     f"from {d['origin']}{tag}")
    lines += [
        "", "\U0001F449 Booking links in our newsletter / bio.",
        "⚡ Prices change fast. Set a fare alert so you never miss one!",
        DISCLOSURE, "", GENERIC_HASHTAGS,
    ]
    return "\n".join(lines)


def tiktok_caption(cfg, d):
    origin = d["origin"]
    pct = d["savings_pct"]
    save = f" (normally ${d['benchmark']:,.0f}!)" if pct > 0 else ""
    return (f"POV: you can fly to {d['name'].split(',')[0]} {d['emoji']} for "
            f"${d['price']:,.0f} round-trip from {origin}{save} "
            f"\U0001F62E Link in bio to book \U0001F517 {GENERIC_HASHTAGS}")


def video_script(cfg, deals):
    out = []
    for d in deals[:3]:
        dep, ret = fmt_dates(d)
        city = d["name"].split(",")[0]
        pct = d["savings_pct"]
        out.append(f"""=== SHORT VIDEO: {city} deal (15-25 sec) ===
HOOK (0-3s)
  On-screen text: "Fly to {city} {d['emoji']} for ${d['price']:,.0f}?!"
  Voiceover: "Stop scrolling — you can fly round-trip to {city} for just ${d['price']:,.0f}."
  B-roll: scenic clip of {city}.

DETAILS (3-12s)
  On-screen text:
    • From: {ff.AIRPORT_NAMES.get(d['origin'], d['origin'])}
    • ${d['price']:,.0f} round-trip{f' (normally ~${d["benchmark"]:,.0f}, ~{pct}% off)' if pct>0 else ''}
    • Sample dates: {dep} to {ret}
  Voiceover: "That's from {ff.AIRPORT_NAMES.get(d['origin'], d['origin'])}, """
        + (f"about {pct}% below the usual price." if pct > 0 else "a great fare right now.") + f"""\"

CTA (12-20s)
  On-screen text: "Link in bio to book \U0001F517 Follow for daily deals!"
  Voiceover: "Booking link's in my bio. Follow so you never miss a deal like this."
  {DISCLOSURE}
""")
    return "\n".join(out)


def newsletter_md(cfg, deals, depart, ret):
    today = datetime.now().strftime("%B %d, %Y")
    lines = [f"# ✈️ This Week's Cheapest Flights from the USA",
             f"*{today}*", "",
             "Here are the best fares we found across major US airports this week. "
             "Prices are round-trip and change fast — book soon if you see one you love.", ""]
    for d in deals:
        dep, rt = fmt_dates(d)
        origin = ff.AIRPORT_NAMES.get(d["origin"], d["origin"])
        pct = d["savings_pct"]
        save = f" — **save ~{pct}%** (normally ~${d['benchmark']:,.0f})" if pct > 0 else ""
        link = ff.booking_link(cfg, d)
        lines += [
            f"## {d['emoji']} {d['name']} — ${d['price']:,.0f} round-trip{save}",
            f"- **From:** {origin} ({d['origin']})",
            f"- **Sample dates:** {dep} → {rt}",
            f"- **[Book / check live price]({link})**", "",
        ]
    lines += ["---", f"*{DISCLOSURE}*",
              "*Fares were found on " + today + " and may change at any time.*"]
    return "\n".join(lines)


def newsletter_html(cfg, deals):
    today = datetime.now().strftime("%B %d, %Y")
    rows = []
    for d in deals:
        dep, rt = fmt_dates(d)
        origin = ff.AIRPORT_NAMES.get(d["origin"], d["origin"])
        pct = d["savings_pct"]
        save = (f" &mdash; <span style='color:#1a8917'>save ~{pct}%</span>"
                if pct > 0 else "")
        link = ff.booking_link(cfg, d)
        rows.append(f"""
  <div style="border:1px solid #e5e5e5;border-radius:10px;padding:16px;margin:12px 0;font-family:Arial,sans-serif">
    <h2 style="margin:0 0 8px">{d['emoji']} {d['name']} &mdash; ${d['price']:,.0f} round-trip{save}</h2>
    <p style="margin:4px 0;color:#444">From: {origin} ({d['origin']})<br>Sample dates: {dep} &rarr; {rt}</p>
    <a href="{link}" style="display:inline-block;background:#0a66ff;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:bold">Book / check live price</a>
  </div>""")
    return f"""<div style="max-width:600px;margin:auto;font-family:Arial,sans-serif">
  <h1 style="font-family:Arial,sans-serif">✈️ This Week's Cheapest Flights from the USA</h1>
  <p style="color:#666">{today}</p>
  <p>Here are the best fares we found across major US airports this week. Round-trip prices change fast &mdash; book soon!</p>
  {''.join(rows)}
  <p style="color:#999;font-size:12px">{DISCLOSURE}<br>Fares found on {today} and may change at any time.</p>
</div>"""


def main():
    p = argparse.ArgumentParser(description="Generate daily cheap-flight deal content.")
    dep_default, ret_default = default_months()
    p.add_argument("--depart", default=dep_default, help=f"Depart month/date (default {dep_default})")
    p.add_argument("--return", dest="ret", default=ret_default, help=f"Return month/date (default {ret_default})")
    p.add_argument("--top", type=int, default=8, help="Max deals to feature (default 8)")
    p.add_argument("--min-savings", type=int, default=10,
                   help="Only feature deals at least this %% below benchmark (default 10)")
    args = p.parse_args()

    cfg = ff.load_config()
    if not cfg.get("marker"):
        print("WARNING: no 'marker' in config.json — booking links won't earn commission!")

    featured, all_deals = find_deals(cfg, args.depart, args.ret, args.min_savings)
    featured = featured[:args.top]
    if not featured:
        sys.exit("No deals found. Try a different month with --depart / --return.")

    outdir = os.path.join(HERE, "deals_" + datetime.now().strftime("%Y%m%d"))
    os.makedirs(outdir, exist_ok=True)

    # Instagram / Facebook
    with open(os.path.join(outdir, "instagram_facebook.txt"), "w", encoding="utf-8") as f:
        f.write("========== ROUNDUP / CAROUSEL CAPTION ==========\n\n")
        f.write(roundup_caption(cfg, featured) + "\n\n\n")
        for i, d in enumerate(featured, 1):
            f.write(f"========== POST {i}: {d['name']} ==========\n\n")
            f.write(instagram_caption(cfg, d) + "\n\n\n")

    # TikTok / Reels / Shorts captions
    with open(os.path.join(outdir, "tiktok.txt"), "w", encoding="utf-8") as f:
        for d in featured:
            f.write(tiktok_caption(cfg, d) + "\n\n")

    # Video scripts
    with open(os.path.join(outdir, "video_scripts.txt"), "w", encoding="utf-8") as f:
        f.write(video_script(cfg, featured))

    # Newsletter
    with open(os.path.join(outdir, "newsletter.md"), "w", encoding="utf-8") as f:
        f.write(newsletter_md(cfg, featured, args.depart, args.ret))
    with open(os.path.join(outdir, "newsletter.html"), "w", encoding="utf-8") as f:
        f.write(newsletter_html(cfg, featured))

    # Raw data
    with open(os.path.join(outdir, "deals.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["destination", "name", "origin", "price", "benchmark",
                    "savings_pct", "depart", "return", "booking_link"])
        for d in featured:
            dep, rt = fmt_dates(d)
            w.writerow([d["code"], d["name"], d["origin"], f"{d['price']:.0f}",
                        d["benchmark"], d["savings_pct"], dep, rt, ff.booking_link(cfg, d)])

    # Console summary
    print(f"\n{'='*70}\n  TODAY'S TOP DEALS\n{'='*70}")
    for i, d in enumerate(featured, 1):
        pct = d["savings_pct"]
        tag = f"  (save ~{pct}%)" if pct > 0 else ""
        print(f"{i:>2}. {d['name']:<24} ${d['price']:>7,.0f} RT  from {d['origin']}{tag}")
    print(f"\nAll content written to: {outdir}")
    print("Files: instagram_facebook.txt, tiktok.txt, video_scripts.txt, "
          "newsletter.md, newsletter.html, deals.csv")


if __name__ == "__main__":
    main()
