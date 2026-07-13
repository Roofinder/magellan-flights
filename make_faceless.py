"""Faceless destination SHORTS generator for Magellan Flights.

py make_faceless.py LON --origin=MCO --direct   -> spotlight one tracked route
py make_faceless.py ATH                         -> city short from best tracked fare
py make_faceless.py --auto                      -> today's best guide-city deal

Output: videos/CODE-YYYYMMDD/short.mp4 (1080x1920 vertical, ~50s) + script.txt
(description text + required music attribution).

Shorts-first: vertical 9:16, hook in the first two seconds, six-stop photo tour,
faint location-matched music under the open and close (Kevin MacLeod, CC BY 4.0),
captions raised above the Shorts UI. Static slides + crossfades only - zoompan
jitters ("shaky") and is banned. Verify by extracting frames and reading them.

Voice: en-US-AndrewNeural. Copy stays hedged and grounded. No emojis, no em dashes.
The 16:9 cuts (final.mp4, rendered 2026-07-13) remain for city-guide page embeds.
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import date
from urllib.parse import quote as _q

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildsite as b  # noqa: E402

FFMPEG = r"C:\Program Files\Shotcut\ffmpeg.exe"
FPS = 30
W, H = 1080, 1920
CAPY = H - 450            # caption overlay: above the Shorts bottom UI
XFADE = 0.5
VOICE = "en-US-AndrewNeural"
RATE = "+2%"              # a touch quicker for Shorts pacing
CREAM = (243, 236, 216)
INK = (44, 42, 30)
MUTED = (122, 113, 90)
GREEN = (47, 107, 70)
MINT = (126, 217, 165)
PALE = (235, 231, 220)

F_HEAD = r"C:\Windows\Fonts\georgiab.ttf"
F_BODY = r"C:\Windows\Fonts\arial.ttf"
F_BOLD = r"C:\Windows\Fonts\arialbd.ttf"

# Background music, faint under open + close only. Kevin MacLeod (incompetech.com),
# CC BY 4.0 - attribution is appended to script.txt and MUST stay in the description.
MUSIC = {
    "LON": ("music/sovereign.mp3", "Sovereign"),
    "ATH": ("music/master-of-the-feast.mp3", "Master of the Feast"),
    "default": ("music/deliberate-thought.mp3", "Deliberate Thought"),
}

# Quick-tour stops: (spoken line, Wikipedia page for the photo, display name)
TOURS = {
    "LON": [
        ("Tower Bridge, the Victorian icon over the Thames.", "Tower Bridge", "Tower Bridge"),
        ("The British Museum. World history, and it is free.", "British Museum", "British Museum"),
        ("Buckingham Palace and the changing of the guard.", "Buckingham Palace", "Buckingham Palace"),
        ("Westminster, Big Ben, and the Houses of Parliament.", "Palace of Westminster", "Westminster and Big Ben"),
        ("Borough Market for the food halls.", "Borough Market", "Borough Market"),
        ("And a West End show to end the night.", "West End theatre", "The West End"),
    ],
    "ATH": [
        ("The Acropolis and the Parthenon at first light.", "Acropolis of Athens", "The Acropolis"),
        ("The Acropolis Museum, right below the rock.", "Acropolis Museum", "Acropolis Museum"),
        ("Plaka, the old town under the hill.", "Plaka", "Plaka"),
        ("Monastiraki square and its flea market.", "Monastiraki", "Monastiraki"),
        ("The Temple of Olympian Zeus.", "Temple of Olympian Zeus, Athens", "Temple of Olympian Zeus"),
        ("And sunset from Lycabettus Hill.", "Mount Lycabettus", "Lycabettus Hill"),
    ],
}


# ----------------------------------------------------------------------------- data
def pick_city(code=None, origin=None):
    market = b.read_snapshot()
    oneway = b.read_oneway()
    items = b._hm_items(oneway, market)
    if code and origin:
        rows = [o for o in oneway if o.get("origin") == origin and o.get("code") == code]
        if not rows:
            raise SystemExit(f"no tracked one-way {origin}->{code}; check the data")
        row = min(rows, key=lambda r: float(r["price"]))
        price = float(row["price"])
        by_code = {m["code"]: m for m in market if m.get("code")}
        pct = None
        rt = by_code.get(code)
        if rt and rt.get("benchmark"):
            typ = float(rt["benchmark"]) * 0.46
            if typ > 0 and price >= float(rt["benchmark"]) * 0.12:
                pct = min((typ - price) / typ * 100.0, 55.0)
                if pct < 1:
                    pct = None
        return code, pct, row, price
    if code:
        for pct, o, price in items:
            if o.get("code") == code:
                return code, pct, o, price
        return code, None, None, None
    for pct, o, price in items:
        if o.get("code") in b.CITY_GUIDE and o.get("code") in b.CITY_META:
            return o["code"], pct, o, price
    raise SystemExit("no guide-city deal found; pass a code explicitly")


def human_date(iso):
    try:
        y, m, d = iso.split("-")
        months = ["January", "February", "March", "April", "May", "June", "July",
                  "August", "September", "October", "November", "December"]
        return f"{months[int(m) - 1]} {int(d)}"
    except Exception:
        return iso


def wiki_photo(term):
    try:
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + _q(term.replace(" ", "_"))
        req = urllib.request.Request(url, headers={"User-Agent": "MagellanFlights-video/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        return (data.get("originalimage") or {}).get("source") or \
               (data.get("thumbnail") or {}).get("source", "")
    except Exception:
        return ""


def fetch(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "MagellanFlights-video/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r, open(path, "wb") as f:
        f.write(r.read())
    return path


# ----------------------------------------------------------------------------- script
def build_script(code, pct, o, price, origin_name=None, direct=False):
    """Shorts pacing: hook fast, one-sentence overview, 6 quick stops, tight close."""
    name, country, slug = b.CITY_META[code]
    g = b.CITY_GUIDE.get(code, {})
    info = b.DEST_INFO.get(code, {})
    best = b.BEST_TIME.get(code, "year-round")
    date_h = human_date(o["depart"]) if (o and o.get("depart")) else ""
    ns = "direct " if direct else ""

    sections = []
    if price and origin_name:
        hook = (f"We have tracked a {ns}flight from {origin_name} to {name} for {int(round(price))} dollars "
                f"one way. The link is in the description. The flight takes place {date_h}"
                + (", and it is a direct flight." if direct else "."))
    elif price:
        hook = (f"We have tracked {name} at about {int(round(price))} dollars one way. "
                f"The link is in the description.")
    else:
        hook = f"{name}, {country}. Here is how to catch it cheap."
    sections.append(("hook", hook))
    ov = g.get("overview", f"{name} is one of the destinations we track every day.")
    first = ov.split(". ")[0].rstrip(".") + "."
    sections.append(("overview", first))
    for i, (line, _page, _disp) in enumerate(TOURS.get(code, [])):
        sections.append((f"tour{i}", line))
    facts = f"Best time to go: {best}."
    if info.get("visa"):
        facts += f" Visa for US passports: {info['visa']}."
    sections.append(("facts", facts))
    route = f"{origin_name} to {name}" if origin_name else name
    when = f", {date_h}" if date_h else ""
    if price:
        deal = (f"That fare again: {int(round(price))} dollars one way, {route}"
                + (", direct" if direct else "") + f"{when}. "
                + (f"About {int(round(pct))} percent below its usual price. " if pct and pct >= 8 else "")
                + "Often just a few seats. The link is in the description.")
    else:
        deal = f"We track {name} fares every day, so you can see when a real drop lands."
    sections.append(("deal", deal))
    sections.append(("cta", "Magellan Flights tracks fares like a market, updated daily, free to use. "
                            "And for more deals like this, join our free weekly newsletter at "
                            "magellan flights dot com."))
    return name, country, sections


# ----------------------------------------------------------------------------- tts
async def tts(sections, out_mp3):
    import edge_tts
    text = " ".join(s[1] for s in sections)
    words = []
    com = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary")
    with open(out_mp3, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"t": chunk["offset"] / 1e7, "d": chunk["duration"] / 1e7,
                              "w": chunk["text"]})
    return text, words


def section_spans(sections, words):
    spans, wi = [], 0
    for _, txt in sections:
        n = len([w for w in txt.split() if w.strip()])
        seg = words[wi:wi + n]
        if not seg:
            seg = words[-1:]
        spans.append((seg[0]["t"], seg[-1]["t"] + seg[-1]["d"]))
        wi += n
    return spans


# ----------------------------------------------------------------------------- slides
def _fit(img, w, h):
    from PIL import Image
    r = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * r) + 1, int(img.height * r) + 1), Image.LANCZOS)
    x = (img.width - w) // 2
    y = (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def _shade(img, top=120, bottom=215):
    from PIL import Image
    ov = Image.new("L", (1, img.height))
    for y in range(img.height):
        ov.putpixel((0, y), int(top + (bottom - top) * (y / img.height)))
    black = Image.new("RGB", img.size, (10, 14, 11))
    img.paste(black, (0, 0), ov.resize(img.size))
    return img


def _wrap(draw, txt, font, maxw):
    out, line = [], ""
    for w in txt.split():
        t = (line + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw:
            line = t
        else:
            out.append(line)
            line = w
    if line:
        out.append(line)
    return out


def _load_photo(path):
    from PIL import Image
    if path and os.path.exists(path):
        try:
            return _shade(_fit(Image.open(path).convert("RGB"), W, H))
        except Exception:
            return None
    return None


def make_slides(outdir, name, country, sections, photos, price, pct, meta=None):
    from PIL import Image, ImageDraw, ImageFont
    hero = _load_photo(photos.get("hero"))
    tour = TOURS.get(meta.get("code", ""), []) if meta else []
    MX = 90                              # side margin
    paths = []
    for i, (kind, txt) in enumerate(sections):
        photo = None
        if kind.startswith("tour"):
            photo = _load_photo(photos.get(kind)) or hero
        elif kind in ("hook", "overview", "deal"):
            photo = hero
        if photo is not None:
            img = photo.copy()
            ink, mut, accent = (255, 255, 255), PALE, MINT
        else:
            img = Image.new("RGB", (W, H), CREAM)
            ink, mut, accent = INK, MUTED, GREEN
        d = ImageDraw.Draw(img)
        d.text((MX, 100), "MAGELLAN FLIGHTS", font=ImageFont.truetype(F_BOLD, 34), fill=accent)
        if kind == "hook":
            y = 420
            for line in _wrap(d, name, ImageFont.truetype(F_HEAD, 130), W - 2 * MX)[:2]:
                d.text((MX, y), line, font=ImageFont.truetype(F_HEAD, 130), fill=ink)
                y += 150
            d.text((MX + 4, y + 6), country, font=ImageFont.truetype(F_HEAD, 54), fill=mut)
            y += 120
            if price:
                d.text((MX, y), f"${int(round(price)):,}", font=ImageFont.truetype(F_HEAD, 170), fill=ink)
                y += 210
                sub = "one-way" + (", direct" if meta and meta.get("direct") else "")
                d.text((MX, y), sub, font=ImageFont.truetype(F_BOLD, 56), fill=accent)
                y += 90
                if meta and meta.get("route"):
                    line = meta["route"] + (", " + meta["date"] if meta.get("date") else "")
                    for ln in _wrap(d, line, ImageFont.truetype(F_BOLD, 46), W - 2 * MX)[:2]:
                        d.text((MX, y), ln, font=ImageFont.truetype(F_BOLD, 46), fill=ink)
                        y += 62
                d.text((MX, y + 10), "link in the description", font=ImageFont.truetype(F_BODY, 42), fill=mut)
        elif kind.startswith("tour"):
            idx = int(kind[4:])
            disp = tour[idx][2] if idx < len(tour) else txt
            d.text((MX, H - 780), f"THE QUICK TOUR  |  STOP {idx + 1} OF {len(tour)}",
                   font=ImageFont.truetype(F_BOLD, 32), fill=accent)
            y = H - 710
            for line in _wrap(d, disp, ImageFont.truetype(F_HEAD, 96), W - 2 * MX)[:2]:
                d.text((MX, y), line, font=ImageFont.truetype(F_HEAD, 96), fill=ink)
                y += 112
        elif kind == "cta":
            d.text((MX, 500), "Catch the cheap ones", font=ImageFont.truetype(F_HEAD, 80), fill=ink)
            d.text((MX, 610), "before they vanish", font=ImageFont.truetype(F_HEAD, 80), fill=ink)
            d.rectangle((MX, 800, W - MX, 916), fill=GREEN)
            d.text((MX + 34, 828), "magellanflights.com", font=ImageFont.truetype(F_BOLD, 52), fill=(255, 255, 255))
            for j, ln in enumerate(_wrap(d, "Subscribe to the free weekly newsletter for more deals like this.",
                                         ImageFont.truetype(F_BODY, 40), W - 2 * MX)[:3]):
                d.text((MX, 980 + j * 56), ln, font=ImageFont.truetype(F_BODY, 40), fill=mut)
        elif kind == "deal" and price:
            d.text((MX, 320), "The fare right now", font=ImageFont.truetype(F_HEAD, 56), fill=accent)
            d.text((MX, 430), f"${int(round(price)):,}", font=ImageFont.truetype(F_HEAD, 180), fill=ink)
            y = 660
            sub = (f"one-way, about {int(round(pct))}% below its usual price" if pct
                   else "one-way, tracked today")
            for ln in _wrap(d, sub, ImageFont.truetype(F_BOLD, 48), W - 2 * MX)[:2]:
                d.text((MX, y), ln, font=ImageFont.truetype(F_BOLD, 48), fill=accent)
                y += 64
            if meta and meta.get("route"):
                line = meta["route"] + (", " + meta["date"] if meta.get("date") else "") \
                       + (", direct" if meta.get("direct") else "")
                for ln in _wrap(d, line, ImageFont.truetype(F_BOLD, 46), W - 2 * MX)[:2]:
                    d.text((MX, y + 12), ln, font=ImageFont.truetype(F_BOLD, 46), fill=ink)
                    y += 62
            d.text((MX, y + 26), "link in the description", font=ImageFont.truetype(F_BODY, 42), fill=mut)
        else:  # overview / facts
            head = f"{name}, {country}" if kind == "overview" else "Know before you go"
            d.text((MX, 320), head, font=ImageFont.truetype(F_HEAD, 56), fill=accent)
            y = 440
            for line in _wrap(d, txt, ImageFont.truetype(F_HEAD, 58), W - 2 * MX)[:10]:
                d.text((MX, y), line, font=ImageFont.truetype(F_HEAD, 58), fill=ink)
                y += 80
        p = os.path.join(outdir, f"slide{i}.png")
        img.save(p)
        paths.append(p)
    return paths


def make_captions(outdir, words, chunk=3):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(F_BOLD, 50)
    cards, i = [], 0
    while i < len(words):
        seg = words[i:i + chunk]
        txt = " ".join(w["w"] for w in seg)
        img = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        tw = d.textlength(txt, font=font)
        if tw > W - 120:
            font_s = ImageFont.truetype(F_BOLD, 42)
            tw = d.textlength(txt, font=font_s)
            use = font_s
        else:
            use = font
        x0 = max(int((W - tw) / 2) - 26, 10)
        d.rounded_rectangle((x0, 8, min(x0 + tw + 52, W - 10), 108), 18, fill=(12, 18, 14, 200))
        d.text((x0 + 26, 28), txt, font=use, fill=(255, 255, 255, 255))
        p = os.path.join(outdir, f"cap{len(cards)}.png")
        img.save(p)
        cards.append({"p": p, "s": seg[0]["t"], "e": seg[-1]["t"] + seg[-1]["d"] + 0.04})
        i += chunk
    return cards


# ----------------------------------------------------------------------------- ffmpeg
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg failed:\n" + (r.stderr or "")[-1600:])


def assemble(outdir, slides, spans, audio, caps, total, music=None):
    segs = []
    for i, ((s0, s1), png) in enumerate(zip(spans, slides)):
        dur = max(2.0, (s1 - s0) + (XFADE if i < len(slides) - 1 else 1.0))
        seg = os.path.join(outdir, f"seg{i}.mp4")
        run([FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.2f}", "-i", png,
             "-vf", f"scale={W}:{H}", "-r", str(FPS),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", seg])
        segs.append((seg, dur))
    inputs = []
    for seg, _ in segs:
        inputs += ["-i", seg]
    fc, prev, t = [], "[0:v]", 0.0
    for i in range(1, len(segs)):
        t += segs[i - 1][1] - XFADE
        out = f"[v{i}]"
        fc.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XFADE}:offset={t:.2f}{out}")
        prev = out
    base = os.path.join(outdir, "base.mp4")
    run([FFMPEG, "-y", *inputs, "-filter_complex", ";".join(fc), "-map", prev,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", base])

    use_music = bool(music and os.path.exists(music))
    inputs = ["-i", base, "-i", audio]
    if use_music:
        inputs += ["-i", music, "-i", music]
    cap0 = 4 if use_music else 2
    fc, prev = [], "[0:v]"
    for i, c in enumerate(caps):
        inputs += ["-i", c["p"]]
        out = f"[o{i}]"
        fc.append(f"{prev}[{i + cap0}:v]overlay=0:{CAPY}:enable='between(t,{c['s']:.2f},{c['e']:.2f})'{out}")
        prev = out
    end = total + 1.2
    if use_music:
        oplen = min(spans[0][1] + 2.8, end)
        clstart = max(spans[-1][0] - 1.5, 0)
        cllen = max(end - clstart, 3.0)
        afc = (f"[1:a]loudnorm=I=-16:TP=-1.5[va];"
               f"[2:a]atrim=0:{oplen:.2f},asetpts=PTS-STARTPTS,"
               f"afade=t=in:st=0:d=1.2,afade=t=out:st={max(oplen - 2.8, 0):.2f}:d=2.8,volume=0.12[mo];"
               f"[3:a]atrim=0:{cllen:.2f},asetpts=PTS-STARTPTS,"
               f"afade=t=in:st=0:d=2.2,afade=t=out:st={max(cllen - 2.4, 0):.2f}:d=2.4,volume=0.12,"
               f"adelay={int(clstart * 1000)}:all=1[mc];"
               f"[va][mo][mc]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.97[a]")
    else:
        afc = "[1:a]loudnorm=I=-16:TP=-1.5[a]"
    final = os.path.join(outdir, "short.mp4")
    run([FFMPEG, "-y", *inputs, "-filter_complex",
         ";".join(fc) + ";" + afc,
         "-map", prev, "-map", "[a]", "-t", f"{end:.2f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", final])
    return final


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    code = args[0].upper() if args else None
    auto = "--auto" in sys.argv or not code
    origin = next((a.split("=", 1)[1].upper() for a in sys.argv if a.startswith("--origin=")), None)
    direct = "--direct" in sys.argv
    code, pct, o, price = pick_city(None if auto and not code else code, origin=origin)
    if code not in b.CITY_META:
        raise SystemExit(f"{code} has no CITY_META entry; add it first so the video has a guide page.")
    origin_name = b.WORLD_HUBS.get(origin, origin) if origin else None
    name, country, sections = build_script(code, pct, o, price, origin_name=origin_name, direct=direct)
    meta = {"code": code,
            "route": f"{origin_name} to {name}" if origin_name else "",
            "date": human_date(o["depart"]) if (o and o.get("depart")) else "",
            "direct": direct}
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "videos",
                          f"{code}-{date.today().strftime('%Y%m%d')}")
    os.makedirs(outdir, exist_ok=True)
    print(f"[1/6] city: {name}, {country}  fare: " +
          (f"${price:.0f}" + (f" ({pct:.0f}% below)" if pct else "") if price else "none live"))
    photos = {}
    src = wiki_photo(name)
    if src:
        try:
            photos["hero"] = fetch(src, os.path.join(outdir, "hero.jpg"))
        except Exception:
            pass
    got = 0
    for i, (_line, page, _disp) in enumerate(TOURS.get(code, [])):
        src = wiki_photo(page)
        if not src:
            continue
        for attempt in (1, 2):
            try:
                photos[f"tour{i}"] = fetch(src, os.path.join(outdir, f"tour{i}.jpg"))
                got += 1
                break
            except Exception:
                continue
    print(f"[2/6] photos: hero={'yes' if 'hero' in photos else 'NO'} + {got} tour stops")
    audio = os.path.join(outdir, "voice.mp3")
    text, words = asyncio.run(tts(sections, audio))
    total = words[-1]["t"] + words[-1]["d"]
    print(f"[3/6] voiceover: {total:.1f}s, {len(words)} words, {len(sections)} sections")
    spans = section_spans(sections, words)
    slides = make_slides(outdir, name, country, sections, photos, price, pct, meta=meta)
    print(f"[4/6] slides: {len(slides)}")
    caps = make_captions(outdir, words)
    print(f"[5/6] captions: {len(caps)}")
    mpath, mname = MUSIC.get(code, MUSIC["default"])
    mfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), mpath)
    final = assemble(outdir, slides, spans, audio, caps, total, music=mfile)
    print(f"[6/6] DONE -> {final}  (music: {mname})")
    with open(os.path.join(outdir, "script.txt"), "w", encoding="utf-8") as f:
        attribution = (
            '\n\nMusic: "' + mname + '" Kevin MacLeod (incompetech.com)\n'
            "Licensed under Creative Commons: By Attribution 4.0\n"
            "https://creativecommons.org/licenses/by/4.0/\n"
        )
        f.write(text + attribution)


if __name__ == "__main__":
    main()
