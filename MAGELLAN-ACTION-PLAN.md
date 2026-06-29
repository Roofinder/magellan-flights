# Magellan Flights — Master Action Plan

_Everything the STORM research recommended (defensibility · newsletter content & growth · deliverability), in one checklist. Compiled 2026-06-29. ✅ = already shipped this session. Internal doc; not served on the site._

**The one-line strategy:** You can't out-tool Google, so win on **trust + per-airport relevance + staying free**. Lead every issue with one bookable deal and its savings number, grow with compounding loops (not the daily grind), protect deliverability like the asset it is, and monetize *around* a free core (cards + optional premium), never by paywalling the deals.

---

## ✅ DONE — shipped & deployed this session
- [x] **Forward/referral mechanic** in every weekly issue ("Know a fellow deal-hunter? Forward this")
- [x] **"How we judge below normal" transparency** (email footer + newsletter FAQ) — protects the trust asset
- [x] **Per-airport relevance**: "Cheap one-ways from your home airport" module on the homepage + "Closest to you" (East/Middle/West) section in the newsletter
- [x] **Honest travel-cards page** (`travel-cards.html`) — scaffolded, ready for your affiliate links
- [x] **Hero deal anchored with the struck-through normal price** ("$100, normally ~$495, 80% below")
- [x] **"Fare Watch" market-mood signature line** (the honest home for the research identity)
- [x] **Curiosity-gap auto-send subject** ("How is Tijuana $100 right now?")
- [x] Research repositioned as the *voice/credibility*, with the bookable deal leading ("Book this week" hero)
- [x] Content playbooks written: `SOCIAL-POSTS.md`, `NEWSLETTER-GROWTH.md`, and the STORM briefings
- [x] **Homepage remembers your saved home airport** (pre-selects + "Welcome back, see your deals" line)

---

## 🙋 YOUR ACTIONS — only you can do these (accounts / Beehiiv / off-site)

### A. Protect deliverability FIRST (before any growth push)
- [ ] Authenticate on a **dedicated sending subdomain** (`mail.magellanflights.com`) — SPF + DKIM + DMARC via Beehiiv's wizard; paste records into Namecheap DNS
- [ ] Set **DMARC to `p=none`** first; tighten to quarantine → reject after ~2–4 weeks of clean reports
- [ ] Turn on **double opt-in** (confirmed opt-in) for signups
- [ ] Verify the domain in **Google Postmaster Tools** (free) — your survival dashboard
- [ ] Confirm **one-click unsubscribe** is on and visible
- **Hold forever:** spam-complaint rate **under 0.1%**

### B. Warm up + keep the list clean (first ~month)
- [ ] **Warm the domain ~4 weeks** — ramp volume (10–20/day → 50 → 100 → full), start with most-engaged contacts
- [ ] Set up a **sunset / re-engagement automation** — flag inactive after 60–90 days, then remove
- [ ] **Accept the Promotions tab** (don't fake personal mail — it backfires)

### C. Newsletter operations
- [ ] **Wire Beehiiv's RSS-to-send** to `magellanflights.com/newsletter.xml` (Automations → RSS, weekly) — auto-sends the issue, no copy-paste
- [ ] **Lock one fixed send slot** (test Tue/Wed ~10–11 AM recipient time) and never move it
- [ ] **A/B test the subject line every send** (Beehiiv automates it) — price-led vs. curiosity-led
- [ ] **Judge by clicks/forwards, not opens** (Apple inflates opens ~15–30 pts)

### D. Growth loops (ranked — do in order, only after A & B)
- [ ] **Beehiiv Boosts / Recommendations** — pays you ~$1.63/sub; cross-recommend with adjacent travel newsletters
- [ ] **Milestone referral program** — turn on once you pass ~1–2K subs; make the savings number the share unit; double opt-in; **no prize/contest mechanics**
- [ ] **Lead-magnet swaps** with adjacent creators ("Cheapest months to fly from your city")
- [ ] **Pinterest** (evergreen travel pins → signup) + **short-form video** ("$X from your city" clips)
- [ ] **Reddit / niche communities** — value-first, post the deal not the signup (first ~500 subs, ongoing trickle)

### E. Monetization — ⏸️ PARKED until the list grows (~1–2K subs)
_Dalton's call 2026-06-29: grow the following first. Correct — a small list earns almost nothing from cards, and monetization is meant to wrap around an audience, not precede it. Revisit when the list is bigger._
- [ ] (later) **Apply to credit-card affiliate programs** (the biggest lever — up to ~$200/approval vs ~1% on a flight)
- [ ] (later) Once approved, send me the card names + your affiliate links → I'll populate `travel-cards.html`
- [x] Aviasales links live (marker 741311) — the bonus revenue while you grow ✅

### F. Distribution content (ready to use)
- [ ] Post the **brand-story / transparency posts** (Format H–K in `SOCIAL-POSTS.md`) + weekly movers
- [ ] Run the **repeatable weekly motion** (grab top movers → A/D/G posts → one heatmap video → 2–3 channels, link in bio)

---

## 🔧 BUILD OPPORTUNITIES — things I (Claude) can implement
- [x] **Per-airport relevance, deeper** — the homepage now remembers your saved airport (pre-selects + "Welcome back" line). ✅ shipped
- [x] **Class + Non-stop in the search URL — RESOLVED (intentionally left as on-results filters).** Verified 2026-06-29: Non-stop has no Aviasales deep-link parameter, and the only URL format that supports cabin class (`search.aviasales.com/flights/?...trip_class=`) **redirects to the Russian homepage and drops the route + the affiliate marker** when tested — i.e. switching would break the working, revenue-tracking search. The compact `aviasales.com/search/...?marker=741311` format works and is kept. Both filters are one tap on the Aviasales results page. _Correct call, not a gap._
- [ ] Add an optional **feature-premium** scaffold (more home airports / instant alerts) — _gated on your decision to add a paid tier_
- [ ] Any tweak to the cards page, newsletter layout, or a new signature section — on request

---

## 🧭 STRATEGIC DECISIONS — your call (then I can act)
- [ ] **Pick a beachhead niche** — "US-to-anywhere" is the hardest surface. Own a tighter segment first (specific hubs? a region? one-way deal-hunters?) then widen
- [ ] **Decide on a paid tier** — keep the core deals free forever (free is a trust moat); only charge for *features*, never the deals
- [ ] **Commit to the cadence** — one honest, relevant weekly issue you can sustain (the auto-generation keeps output light)

---

## The non-negotiables (guardrails from the research)
- Keep the **core deals free** — billing resentment is competitors' #1 complaint; free is your moat
- Keep **"below normal" honest and visible** — the whole research wedge dies if it reads as marketing (Hopper's unverifiable 95% is the cautionary tale)
- **Loops before grind** — don't burn hours on daily TikTok/Reddit before Boosts + referral are live
- **Deliverability before growth** — a growth push into an unprotected list is how the newsletter dies silently
