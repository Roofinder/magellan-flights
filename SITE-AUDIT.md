# Magellan Flights — Full-Site Audit (design · SEO · marketing)

_Generated 2026-06-29 by a 101-agent workflow auditing all 22 unique pages + 1 representative per template (covers ~150 pages). Each high/critical finding was adversarially re-checked against the real markup._

> Note: the audit ran against the **live pages as of the run**, so two things already fixed in `buildsite.py` this session may still appear below — the **green ticker contrast** (now deep-green band + light text) and the **heatmap codes** (now city + country). Re-verify those after the next deploy.

---

## Executive summary

Foundations are **good-to-strong**: the Atlas parchment+green palette is consistent, structured data is present site-wide, every page has favicon/OG/canonical, and booking links correctly stay on Aviasales. But **four systemic defects repeat across the whole site** and hurt both rankings and conversion:

1. **Accessibility / contrast** — the most pervasive issue. A stale "dark text on gold buttons" rule (`color:#15130c`, ~line 417) survived the gold→green rebrand, so **primary CTA buttons render near-black on green (~2.1–2.9:1)** — failing WCAG AA on the most important conversion element across newsletter, consultant, lastminute, city-guide, region-tour, and article templates. Also: green ticker shows dark-on-dark text; the `--muted` token (`#7a715a`) and `#8a7d64` secondary text fail AA on nearly every page.
2. **One-way vs round-trip contradictions** (violates the one-way-led rule) — `market.html` meta/social/footer sells "round-trip" on a one-way page; `lastminute.html` H1 says "one-ways" but renders round-trip; footers default to "Prices are round-trip unless marked one-way."
3. **SEO H1 / heading weakness** — H1s are brand-cute labels ("Explore", "The Heatmap", "The Captain's Log") with no target keywords, often contradicting keyword-rich titles; most hub/utility pages have **zero H2s**; hubs lack ItemList/BreadcrumbList schema.
4. **Data-integrity / template bugs** that ship visibly broken content — `blog.html` shows "$101 great deal" beside a red **rising** $798 sparkline + "the local language" placeholders; the region-tour template (×9) has an unrendered "varies by season" variable in FAQ schema and **books the wrong airport** (shows Dubai, books SHJ/Sharjah); money pages bury the actual fare.

**Biggest leverage:** airport (×109), route, city-guide (×23) and region-tour (×9) pages are template-driven, so single CSS/template edits cascade across 150+ pages.

---

## Quick wins (ranked — high impact, low effort)

1. **Delete the stale dark-on-green button override** (one CSS line, ~line 417, comment "dark text on gold buttons"). Buttons revert to white `#fff` on forest-green = ~6.3:1 (passes AA). Fixes the PRIMARY CTA contrast failure site-wide (Join free, See live price on Aviasales, Book leg 1, Get free alerts). **Highest-leverage fix on the site.**
2. **Fix the green ticker contrast** — light parchment text (`#f3ecd8`) on the dark-green ticker; `--green #2e8b57` for the down-price accent. _(Largely done this session for the header band — confirm it covers blog/market/lastminute too.)_
3. **Darken `--muted`** from `#7a715a` → ~`#6a6048` and bump `#8a7d64` secondary text. One-token change that clears AA on captions/dates/ledes/descriptions across every page. Stays in palette.
4. **Align all metadata + footers to one-way-led** — rewrite `market.html` description/OG/Twitter/schema to lead with "cheapest one-way flights from the USA"; flip the sitewide footer to "Prices are one-way unless marked otherwise"; fix `lastminute.html` H1/subhead to match its (round-trip) data — or make the data one-way.
5. **Make H1s keyword-bearing + matched to titles** (keep the brand phrase as a small eyebrow): Explore → "Find Cheap One-Way Flights from the USA"; Heatmap → "Flight Fare Heatmap: every tracked fare vs its normal price"; Captain's Log → "Cheap Flights From Your Home Airport"; World Loop → "Cheapest Around-the-World Flights"; index → "The cheapest flights from the USA — tracked daily"; Market → "The Market — cheapest one-way flights from the USA".
6. **Fix the region-tour template (×9)** — booking IATA must match the displayed city (Dubai → DXB, not SHJ); inject the computed price into both the visible FAQ and the FAQPage JSON-LD (kills "about varies by season"); fix double-escaped `&amp;amp;mdash;`; add a build-time check rejecting placeholder phrases in schema.
7. **Fix `blog.html` daily-winner contradiction** — wire the sparkline + aria-label + trend color + prose to the same price/direction so a "great deal" badge never sits beside a red rising chart; populate or hide the "the local language" / "check back soon" placeholders.
8. **Fix garbled/escaped CTA + heading copy in the articles** (`what-is-a-mistake-fare.html`, `are-last-minute-flights-cheaper.html`) — un-escape entities, restore the broken CTA text.

---

## The four themes to fix first
- **Contrast** (buttons, ticker, muted token) — accessibility + conversion, all low-effort + site-wide.
- **One-way framing** consistency — trust + SEO keyword focus.
- **Keyword-bearing H1s + H2 outlines + hub schema** — on-page SEO.
- **Template data-integrity bugs** — credibility (region-tour wrong airport is a revenue/trust failure).

---

_Full per-page findings (every page, all severities + verification notes) are in the workflow output:_
`C:\Users\dalto\AppData\Local\Temp\claude\C--Users-dalto-New-folder\64ea042f-c445-4f94-b959-0c586ddecef9\tasks\wdn0ale1a.output`
