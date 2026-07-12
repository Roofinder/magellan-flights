#!/usr/bin/env python
"""Magellan weekly batch — ONE command produces everything you need for the week, so
your whole Magellan time collapses into a single ~2-hour sitting.

Run:  python weekly.py

Writes weekly-batch/week-YYYYMMDD/ containing:
  00-CHECKLIST.md   the brainless weekly to-do
  1-scripts.md      5 short-video scripts (voiceover + overlays + captions)
  2-newsletter.html the week's email, ready to paste into Beehiiv
  3-schedule.md     which clip posts which weekday, with its caption

Owner tool — run locally; output is not part of the published site.
"""
import os
from datetime import datetime, timedelta

import buildsite as B
import daily_deals as DD

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def main():
    today = datetime.now()
    wk = os.path.join(B.HERE, "weekly-batch", "week-" + today.strftime("%Y%m%d"))
    os.makedirs(wk, exist_ok=True)

    market = B.read_snapshot()
    if not market:
        print("No data/market_latest.csv yet. Run 'python market.py' first.")
        return
    oneway = B.read_oneway(kind="6m")
    # globals the newsletter builder reads (rare-fare detector + history)
    B.HIST_SERIES = B.read_history_series()
    B.ONEWAY_PRICE_HISTORY = B.read_oneway_price_series()

    ranked = B._hm_items(oneway, market)
    items = [it for it in ranked if it[0] >= 12][:5]
    if len(items) < 5:
        seen = {id(it) for it in items}
        items += [it for it in ranked if id(it) not in seen][:5 - len(items)]
    deals = [DD.script_for(pct, o, p) for (pct, o, p) in items]

    # ---- 1) scripts.md ----
    s = [f"# Video scripts — week of {today.strftime('%Y-%m-%d')}", "",
         "Record each voiceover, drop the photo + overlays into your CapCut template, export 9:16.", ""]
    for i, d in enumerate(deals, 1):
        head = f"## {i}. {d['loc']} — ${DD.num(d['price'])}"
        if d["has_pct"]:
            head += f"  ({d['pct']}% below normal)"
        s += [head, "",
              f"- **Photo:** {d['img'] or '(use your own b-roll)'}",
              f"- **Booking link:** {d['link']}",
              f"- **VO:** ~{d['words']} words (~{round(d['words'] / DD.WPS)}s)", "",
              "**Voiceover**", "", f"> {d['voiceover']}", "", "**On-screen overlays**", ""]
        s += [f"- **{label}:**  {text}" for label, text in d["overlays"]]
        s += ["", "**Caption**", "", "```", d["caption"], "```", "", "---", ""]
    _write(wk, "1-scripts.md", "\n".join(s))

    # ---- 2) newsletter.html ----
    issue = B.newsletter_issue_html(oneway, market)
    doc = ("<!doctype html><html><head><meta charset=\"utf-8\">"
           "<title>Magellan weekly issue</title></head>"
           "<body style=\"margin:0;background:#d9d2c2;padding:24px 0\">" + issue + "</body></html>")
    _write(wk, "2-newsletter.html", doc)

    # ---- 3) schedule.md ----
    start = today
    sch = [f"# Posting schedule — week of {today.strftime('%Y-%m-%d')}", "",
           "Schedule each clip natively to Reels + TikTok + Shorts. One bio link → the newsletter.", "",
           "| Day | Deal | Caption hook |", "|---|---|---|"]
    for i, d in enumerate(deals):
        day = WEEKDAYS[(start.weekday() + i) % 7]
        date = (start + timedelta(days=i)).strftime("%b %d")
        hook = f"${DD.num(d['price'])} to {d['loc']}" + (f", {d['pct']}% below" if d["has_pct"] else "")
        sch.append(f"| {day} {date} | #{i + 1} {d['loc']} | {hook} |")
    sch += ["", "Full captions are in `1-scripts.md`. Newsletter goes out once this week (see checklist)."]
    _write(wk, "3-schedule.md", "\n".join(sch))

    # ---- 0) checklist ----
    chk = [f"# Magellan weekly batch — {today.strftime('%Y-%m-%d')}", "",
           "**Goal: finish all of this in one ~2-hour sitting, then don't touch Magellan till next week.**", "",
           "## Do once a week (this session)", "",
           "- [ ] **Record 5 voiceovers** from `1-scripts.md` (read them straight; ~25s each).",
           "- [ ] **Assemble 5 clips** in your CapCut template (photo + overlays + voiceover + music).",
           "- [ ] **Schedule them** across the week per `3-schedule.md` (Reels + TikTok + Shorts, native).",
           "- [ ] **Send the newsletter:** open `2-newsletter.html`, copy it into a new Beehiiv post, schedule the send (Fri is good).",
           "- [ ] Done. Close the laptop.", "",
           "## Set up ONCE (then never again)", "",
           "- [ ] Beehiiv **Recommendations** ON (swap with travel/budget/finance newsletters).",
           "- [ ] Beehiiv **referral program** ON (subscribers earn for referring friends).",
           "- [ ] Bio link on every social profile → the newsletter signup.", "",
           "## Runs with ZERO of your time (already automated)", "",
           "- Site rebuilds + reprices 4x/day (GitHub Actions).",
           "- SEO pages / city guides / blog compound on their own.",
           "- Newsletter content + Rare Fare alert auto-generate from live data.",
           "- The flight-research knowledge base organizes itself nightly.", "",
           f"Everything for this week is in: `{wk}`"]
    _write(wk, "00-CHECKLIST.md", "\n".join(chk))

    print(f"Weekly batch ready -> {wk}")
    for f in ("00-CHECKLIST.md", "1-scripts.md", "2-newsletter.html", "3-schedule.md"):
        print(f"  - {f}")


def _write(folder, name, text):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
