"""Faceless destination video generator for Magellan Flights.

py make_faceless.py CUN          -> videos/CUN-YYYYMMDD/final.mp4  (1920x1080 YouTube)
py make_faceless.py --auto       -> picks today's best below-normal deal that has a city guide
py make_faceless.py CUN --vertical  -> also renders 1080x1920 Shorts version

Pipeline: live fare data + CITY_GUIDE content -> grounded script -> edge-tts neural
voiceover (word timings from the TTS stream, no re-transcription) -> Pillow slides
(Wikipedia hero photo + Atlas-brand cards) -> ffmpeg zoompan/xfade assembly with
burned caption chunks -> frame verification is done by the caller (extract fps).

Voice: en-US-AndrewNeural (calm male). All copy is hedged and grounded: "about X%
below its usual price", never a guarantee. No emojis, no em dashes.
"""
import asyncio
import json
import math
import os
import re
import subprocess
import sys
import urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildsite as b  # noqa: E402  (module-level data loads are cheap)

FFMPEG = r"C:\Program Files\Shotcut\ffmpeg.exe"
FPS = 30
W, H = 1920, 1080
XFADE = 0.5
VOICE = "en-US-AndrewNeural"
CREAM = (243, 236, 216)   # --bg
CARD = (251, 246, 233)    # --card
INK = (44, 42, 30)        # --ink
MUTED = (122, 113, 90)    # --muted
GREEN = (47, 107, 70)     # accent
DGREEN = (36, 85, 55)

F_HEAD = r"C:\Windows\Fonts\georgiab.ttf"
F_BODY = r"C:\Windows\Fonts\arial.ttf"
F_BOLD = r"C:\Windows\Fonts\arialbd.ttf"


# ----------------------------------------------------------------------------- data
def pick_city(code=None, origin=None):
    market = b.read_snapshot()
    oneway = b.read_oneway()
    items = b._hm_items(oneway, market)
    if code and origin:
        # highlight a SPECIFIC route: cheapest row for origin->code
        rows = [o for o in oneway if o.get("origin") == origin and o.get("code") == code]
        if not rows:
            raise SystemExit(f"no tracked one-way {origin}->{code}; check the data")
        row = min(rows, key=lambda r: float(r["price"]))
        price = float(row["price"])
        # honest pct vs the route's usual price (same formula as _hm_items)
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
        # no live deal for that code: still make the video, fare-free
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


def wiki_photo(name, country):
    """Full-res 'originalimage' from Wikipedia REST summary (freely licensed)."""
    for key in (name, f"{name}, {country}", country):
        try:
            url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.request.quote(key.replace(" ", "_"))
        except AttributeError:
            from urllib.parse import quote as _q
            url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + _q(key.replace(" ", "_"))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MagellanFlights-video/1.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.loads(r.read().decode("utf-8"))
            src = (data.get("originalimage") or {}).get("source") or (data.get("thumbnail") or {}).get("source", "")
            if src:
                return src
        except Exception:
            continue
    return ""


def fetch(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "MagellanFlights-video/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r, open(path, "wb") as f:
        f.write(r.read())
    return path


# ----------------------------------------------------------------------------- script
def build_script(code, pct, o, price, origin_name=None, direct=False):
    name, country, slug = b.CITY_META[code]
    g = b.CITY_GUIDE.get(code, {})
    info = b.DEST_INFO.get(code, {})
    best = b.BEST_TIME.get(code, "year-round")
    todo = [re.sub(r"\s*\(.*?\)", "", t) for t in g.get("todo", [])[:3]]
    date_h = human_date(o["depart"]) if (o and o.get("depart")) else ""
    ns = ", nonstop" if direct else ""

    sections = []
    if price and origin_name:
        hook = (f"Right now you can fly from {origin_name} to {name} for about {int(round(price))} dollars "
                f"one way{ns}. Here is what that gets you.")
    elif price:
        hook = f"Right now you can fly to {name} for about {int(round(price))} dollars one way. Here is what that gets you."
    else:
        hook = f"{name}, {country}. Here is what a trip there actually looks like, and how to catch it cheap."
    sections.append(("hook", hook))
    ov = g.get("overview", f"{name} is one of the destinations we track every day.")
    sections.append(("overview", ov))
    if todo:
        sections.append(("todo", "While you are there: " + ". ".join(todo) + "."))
    facts = f"Best time to go: {best}."
    if info.get("visa"):
        facts += f" Visa for US passports: {info['visa']}."
    sections.append(("facts", facts))
    route = f"from {origin_name} " if origin_name else ""
    when = f", departing {date_h}" if (origin_name and date_h) else ""
    if price and pct and pct >= 8:
        deal = (f"On the fare side, we are tracking {name} {route}at about {int(round(price))} dollars one way"
                f"{ns}{when}, roughly {int(round(pct))} percent below its usual price. Fares like this are often "
                f"a few seats, so if you would fly it, check it soon.")
    elif price:
        deal = (f"We are tracking {name} {route}at about {int(round(price))} dollars one way{ns}{when}. "
                f"Fares like this are often a few seats, so if you would fly it, check it soon.")
    else:
        deal = f"We track {name} fares every day, so you can see when a real drop lands."
    sections.append(("deal", deal))
    sections.append(("cta", "Magellan Flights tracks fares like a market, updated daily, free to use. "
                            "Find this deal and more at magellan flights dot com."))
    return name, country, sections


# ----------------------------------------------------------------------------- tts
async def tts(sections, out_mp3):
    import edge_tts
    text = " ".join(s[1] for s in sections)
    words = []
    com = edge_tts.Communicate(text, VOICE, rate="-4%", boundary="WordBoundary")
    with open(out_mp3, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"t": chunk["offset"] / 1e7, "d": chunk["duration"] / 1e7,
                              "w": chunk["text"]})
    return text, words


def section_spans(sections, words):
    """Map each section to (start, end) using cumulative word counts."""
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


def _shade(img, top=110, bottom=200):
    from PIL import Image
    ov = Image.new("L", (1, img.height))
    for y in range(img.height):
        a = int(top + (bottom - top) * (y / img.height))
        ov.putpixel((0, y), a)
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


def make_slides(outdir, name, country, sections, photo_path, price, pct, meta=None):
    from PIL import Image, ImageDraw, ImageFont
    heads = {"hook": None, "overview": f"{name}, {country}", "todo": "While you are there",
             "facts": "Know before you go", "deal": "The fare right now", "cta": "magellanflights.com"}
    photo = None
    if photo_path and os.path.exists(photo_path):
        try:
            photo = _shade(_fit(Image.open(photo_path).convert("RGB"), W, H))
        except Exception:
            photo = None
    paths = []
    for i, (kind, txt) in enumerate(sections):
        if photo is not None and kind in ("hook", "overview", "todo", "deal"):
            img = photo.copy()
            ink, mut = (255, 255, 255), (222, 218, 205)
        else:
            img = Image.new("RGB", (W, H), CREAM)
            ink, mut = INK, MUTED
        d = ImageDraw.Draw(img)
        fh = ImageFont.truetype(F_HEAD, 92)
        fs = ImageFont.truetype(F_HEAD, 58)
        fb = ImageFont.truetype(F_BODY, 44)
        d.text((150, 80), "MAGELLAN FLIGHTS", font=ImageFont.truetype(F_BOLD, 30),
               fill=(GREEN if img.getpixel((10, 10)) == CREAM else (150, 205, 170)))
        y = 300
        if kind == "hook":
            d.text((150, y), name, font=ImageFont.truetype(F_HEAD, 150), fill=ink)
            y += 190
            d.text((154, y), country, font=fs, fill=mut)
            if price:
                y += 130
                d.text((150, y), f"from ${int(round(price)):,} one-way",
                       font=ImageFont.truetype(F_BOLD, 74), fill=(126, 217, 165))
        elif kind == "cta":
            d.text((150, y - 40), "Catch the cheap ones", font=fh, fill=ink)
            d.text((150, y + 90), "before they vanish", font=fh, fill=ink)
            d.rectangle((150, y + 250, 1210, y + 370), fill=GREEN)
            d.text((180, y + 278), "magellanflights.com", font=ImageFont.truetype(F_BOLD, 56), fill=(255, 255, 255))
            d.text((150, y + 420), "Free weekly briefing. Unsubscribe anytime.", font=fb, fill=mut)
        else:
            if heads.get(kind):
                d.text((150, 210), heads[kind], font=fs, fill=(126, 217, 165) if img.getpixel((10, 10)) != CREAM else GREEN)
            body = txt
            if kind == "todo" and body.lower().startswith("while you are there: "):
                body = body[len("while you are there: "):]
            if kind == "deal" and price:
                d.text((150, y), f"${int(round(price)):,}", font=ImageFont.truetype(F_HEAD, 170), fill=ink)
                sub = (f"one-way, about {int(round(pct))}% below its usual price" if pct
                       else "one-way, tracked today")
                d.text((160, y + 210), sub, font=ImageFont.truetype(F_BOLD, 52), fill=(126, 217, 165))
                route_line = ""
                if meta and meta.get("route"):
                    route_line = meta["route"]
                    if meta.get("date"):
                        route_line += ", " + meta["date"]
                    if meta.get("direct"):
                        route_line += ", nonstop"
                if route_line:
                    d.text((160, y + 300), route_line, font=ImageFont.truetype(F_BOLD, 46), fill=ink)
                    d.text((160, y + 380), "tracked daily, book on Aviasales", font=fb, fill=mut)
                else:
                    d.text((160, y + 300), "tracked daily, book on Aviasales", font=fb, fill=mut)
            else:
                yy = y
                for line in _wrap(d, body, ImageFont.truetype(F_HEAD, 62), W - 460)[:7]:
                    d.text((150, yy), line, font=ImageFont.truetype(F_HEAD, 62), fill=ink)
                    yy += 86
        p = os.path.join(outdir, f"slide{i}.png")
        img.save(p)
        paths.append(p)
    return paths


def make_captions(outdir, words, chunk=4):
    """2-4 word caption cards, bottom-center, timed to the TTS word boundaries."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(F_BOLD, 54)
    cards = []
    i = 0
    while i < len(words):
        seg = words[i:i + chunk]
        txt = " ".join(w["w"] for w in seg)
        img = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        tw = d.textlength(txt, font=font)
        x0 = int((W - tw) / 2) - 28
        d.rounded_rectangle((x0, 8, x0 + tw + 56, 104), 18, fill=(12, 18, 14, 196))
        d.text((x0 + 28, 26), txt, font=font, fill=(255, 255, 255, 255))
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


def assemble(outdir, slides, spans, audio, caps, total):
    # Pass A: per-slide motion segments (slow Ken Burns), then xfade chain.
    segs = []
    for i, ((s0, s1), png) in enumerate(zip(spans, slides)):
        dur = max(2.2, (s1 - s0) + (XFADE if i < len(slides) - 1 else 0.9))
        seg = os.path.join(outdir, f"seg{i}.mp4")
        frames = int(dur * FPS)
        z = "min(zoom+0.00055,1.10)" if i % 2 == 0 else "if(lte(on,1),1.10,max(zoom-0.00055,1.0))"
        # Single still in -> zoompan emits exactly `frames` output frames. Do NOT
        # loop the input: with -loop each input frame multiplies by d and a 5s
        # segment balloons into 10+ minutes of video.
        run([FFMPEG, "-y", "-i", png, "-vf",
             f"scale=2400:-2,zoompan=z='{z}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}",
             "-frames:v", str(frames),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", seg])
        segs.append((seg, dur))
    # xfade chain
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
    # Pass B: captions + audio.
    inputs = ["-i", base, "-i", audio]
    fc, prev = [], "[0:v]"
    for i, c in enumerate(caps):
        inputs += ["-i", c["p"]]
        out = f"[o{i}]"
        fc.append(f"{prev}[{i + 2}:v]overlay=0:{H - 170}:enable='between(t,{c['s']:.2f},{c['e']:.2f})'{out}")
        prev = out
    final = os.path.join(outdir, "final.mp4")
    run([FFMPEG, "-y", *inputs, "-filter_complex",
         ";".join(fc) + f";[1:a]loudnorm=I=-16:TP=-1.5[a]",
         "-map", prev, "-map", "[a]", "-t", f"{total + 1.0:.2f}",
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
    meta = {"route": f"{origin_name} to {name}" if origin_name else "",
            "date": human_date(o["depart"]) if (o and o.get("depart")) else "",
            "direct": direct}
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "videos",
                          f"{code}-{date.today().strftime('%Y%m%d')}")
    os.makedirs(outdir, exist_ok=True)
    print(f"[1/6] city: {name}, {country}  deal: " +
          (f"${price:.0f} ({pct:.0f}% below)" if price else "none live"))
    photo = ""
    src = wiki_photo(name, country)
    if src:
        try:
            photo = fetch(src, os.path.join(outdir, "hero" + os.path.splitext(src)[1][:5]))
            print("[2/6] hero photo:", os.path.basename(photo))
        except Exception as e:
            print("[2/6] no photo:", e)
    audio = os.path.join(outdir, "voice.mp3")
    text, words = asyncio.run(tts(sections, audio))
    total = words[-1]["t"] + words[-1]["d"]
    print(f"[3/6] voiceover: {total:.1f}s, {len(words)} words")
    spans = section_spans(sections, words)
    slides = make_slides(outdir, name, country, sections, photo, price, pct, meta=meta)
    print(f"[4/6] slides: {len(slides)}")
    caps = make_captions(outdir, words)
    print(f"[5/6] captions: {len(caps)}")
    final = assemble(outdir, slides, spans, audio, caps, total)
    print(f"[6/6] DONE -> {final}")
    with open(os.path.join(outdir, "script.txt"), "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
