# Money pages — the origin × destination matrix (service-page equivalent)

The video builds a *service × city* matrix of money pages. Magellan isn't local,
so our matrix is **departure airport × destination/region**, and every page must be
**backed by live fares** (not a thin doorway template) or Google penalizes it.

## Keyword shape (transactional, high-CPC — the money terms)
- `cheap flights from {city}` — e.g. "cheap flights from Chicago" (primary money kw)
- `cheapest flights from {city}`
- `flights from {city} to {region}` — e.g. "flights from JFK to Europe"
- `cheap flights from {city} to {destination}`
- Pattern intent = **transactional**; these carry real CPC (airlines/OTAs bid on them).

## Banned (the "near me" equivalent)
- Thin pages with no real fare data (= doorway pages → penalty).
- Auto-generated combos for airports we don't actually have data for.
- Duplicated body text across pages (each page's fare table must be its own data).

## Matrix — Axis 1: departure airports (start here)
We already track ~46 US home airports (homebase.py). Begin with the ~20-25 biggest
by passenger volume so each page has rich data:

JFK, EWR, LGA, BOS, PHL, IAD, DCA, BWI, ATL, MIA, FLL, MCO, TPA, ORD, MDW, DTW,
MSP, DFW, IAH, DEN, PHX, LAS, LAX, SFO, SEA, SAN, BOS, AUS, CLT.

Each page = **"Cheap flights from {City} ({CODE})"**:
- H1 + intro with the city, live "cheapest right now" number from our data
- Live table: cheapest destinations from that airport (price, dates, book link)
- Internal links to world / last-minute / relevant guides
- Schema: WebPage + ItemList of offers + BreadcrumbList
- URL: `/cheap-flights-from-{city}.html` (keyword in slug)

## Matrix — Axis 2 (phase 2, only if Axis 1 performs): destination / region
Layer on `{origin} → {region}` pages (e.g. "Cheap flights from Boston to Europe")
ONLY for origin/region pairs where we have enough routes to fill a real table.

## Scope guardrails (straight from the video — be conservative)
- Google dislikes mass thin pages. **Do NOT** generate hundreds of combos.
- Start with ~20-25 origin pages (Axis 1). Measure in Search Console for 3-4 weeks.
- Expand to origin×region only where data is genuinely rich. Cap well under ~400 total.
- Every page lives or dies on having real, current fares. No data → no page.

## Why this is safe for us (and not for a generic site)
Sites get penalized for *programmatic* pages when they're empty templates. Ours
render the actual cheapest live fares for that airport, refreshed daily by the
pipeline — the same reason Kayak/Skyscanner route pages rank. Unique data per URL
is the whole defense.

## Relationship to existing pages
`airports.html` already shows per-airport deals, but it's ONE JS-driven URL Google
can't index per city. These matrix pages are the **static, indexable** version —
one crawlable URL per origin, server-rendered with that origin's fares at build time.
</content>
