# Magellan Newsletter — Growth & Deliverability Checklist

_Owner playbook from the STORM newsletter research (2026-06-29). These are the **Beehiiv-side / off-site actions only Dalton can do** — the content side is already built into the site. Do them roughly in this order. Internal doc; not served on the site._

> The golden rule from the research: **grow with quality-gated compounding loops, protect deliverability like the asset it is, and judge yourself by clicks — not the (inflated) open rate.**

---

## PHASE 0 — Protect deliverability FIRST (do before any growth push)
A "deal" email is the hardest type to land in the inbox, and junk subscribers from a growth push can silently route the whole list to spam. Set the pipes up before you pour water in.

- [ ] **Authenticate on a dedicated sending subdomain** — in Beehiiv, add a custom domain and choose a **subdomain** like `mail.magellanflights.com` (NOT the root), so a deliverability hit never poisons your normal mail on magellanflights.com. Beehiiv's wizard generates the SPF/DKIM (CNAME) records — paste them into your DNS host (Namecheap).
- [ ] **Add a DMARC record**, starting at **`p=none`** (monitor only). After ~2–4 weeks of reports showing SPF/DKIM passing, tighten to `p=quarantine`, then eventually `p=reject`. Beehiiv has a DMARC wizard.
- [ ] **Turn on double opt-in** (confirmed opt-in) for signups — keeps typos and spam-traps off the list from day one. This is your single best defense against junk.
- [ ] **Verify the domain in Google Postmaster Tools** (free) — add the DNS TXT record. This is your survival dashboard; **spam complaint rate is the #1 signal**. (Data is sparse until you send ~100+/day to Gmail, so set it up now to accrue history.)
- [ ] **Confirm one-click unsubscribe** is on (Beehiiv handles this) and the unsubscribe link is visible in every issue.

**Targets to hold forever:** spam-complaint rate **under 0.1%** (hard fail at 0.3% on Gmail/Yahoo since Feb 2024).

---

## PHASE 1 — Warm up + clean (first ~month)
- [ ] **Warm the domain over ~4 weeks** — don't blast a big cold batch day one. Ramp roughly 10–20 sends/day (wk1) → 50/day (wk2) → 100/day (wk3) → full. Start with your **most engaged** contacts (friends, early subs) and ask a few to reply — replies signal "real human wants this."
- [ ] **Set up a sunset / re-engagement automation** in Beehiiv — flag subscribers **inactive after 60–90 days** of no opens/clicks, run a 1–2 email "still want this?" sequence, then move non-responders to Inactive. (Beehiiv's "Unengaged" trigger does this; re-engagement has lifted open rates ~14%→45%.)
- [ ] **Accept the Promotions tab.** Don't try to disguise a deal email as personal mail — Gmail detects and penalizes that. Promotions is NOT spam; deal-hunters browse it. The real fight is **inbox vs. spam**, not tab vs. tab.

---

## PHASE 2 — Turn on the compounding growth loops (ranked by leverage)
Do these in order. Each compounds; the manual channels (Phase 3) don't.

1. [ ] **Beehiiv Recommendations / Boosts** — the #1 zero-budget channel: it **pays you** per confirmed subscriber (Beehiiv's own avg ≈ $1.63/sub) and recommended subs open ~42%. Turn on recommendations and cross-recommend with adjacent **travel/deal** newsletters. _(Vendor-reported numbers — verify on your own dashboard.)_
2. [ ] **Milestone referral program** (turn on once you pass ~**1,000–2,000 subs** — loops need a base to refer from). Forward-to-earn, Morning-Brew style (theirs built ~1.5M subs). Simple reward tiers (e.g. 3 / 10 / 25 referrals). **Make the savings number the share unit** ("I'm flying to Lisbon for $231"). Use double opt-in; **avoid prize/sweepstakes mechanics** — organic referrals convert ~32%, contest signups bring junk that wrecks deliverability.
3. [ ] **Lead-magnet swaps with adjacent creators** — trade a genuinely useful freebie ("Cheapest months to fly from your city") with a complementary travel newsletter/creator, not a bare shout-out. Highest-leverage no-budget loop after Boosts.

---

## PHASE 3 — Evergreen top-of-funnel (flywheel, not a quick win)
- [ ] **Pinterest** — an evergreen visual search engine for travel (skews female = the deal-booker demographic). One pin per standout deal/destination → links to a landing page with the signup. Low time-per-asset, long tail.
- [ ] **Short-form video** (Reels / Shorts / TikTok) — one "$X from [your city] right now" clip repurposes across all three free. Scroll-stopping by nature. Treat as a slow flywheel.
- [ ] **Reddit / niche communities** — value-first only: post the actual deal in mid-sized engaged subs (r/Shoestring, r/awardtravel, city subs), link in profile/comment, never spam. Good for the first ~500 subs and an ongoing trickle, not scale.

> ⚠️ **Don't** pour hours into daily TikTok/Reddit *before* the Boosts + referral loops are live — high time-cost, unpredictable, and it doesn't compound. (See SOCIAL-POSTS.md for ready-to-post content.)

---

## CONTENT & CADENCE (already built into the site — just operate it)
- One **hero deal + single CTA + anchored "normal price"** leads every issue ✅ (shipped)
- **Curiosity-gap subject line** auto-generated in the feed ✅ ("How is Tijuana $100 right now?")
- **"Fare Watch"** market-mood line + **"Closest to you"** per-airport block ✅ (shipped)
- [ ] **Lock one fixed send slot** and never move it — test **Tue/Wed ~10–11 AM (recipient local time)**. Consistency beats the "perfect" hour.
- [ ] **A/B test the subject every send** (Beehiiv automates it) — usually price-led vs. curiosity-led. Judge by **clicks**.
- [ ] Keep a healthy **text-to-image ratio** (never an all-image email), plain subject lines, avoid trigger words (ALL CAPS, "!!!", "FREE/CHEAP/$$$"), and link to your own domain + Aviasales.

---

## THE DASHBOARD — what to actually watch (weekly)
Open rate lies (Apple inflates it ~15–30 points). Track these instead:
- [ ] **Spam-complaint rate** (Postmaster) — keep < 0.1%. This is the survival metric.
- [ ] **Unique click rate** — your real engagement signal.
- [ ] **Forwards / referrals** — is the savings number traveling?
- [ ] **Bounces + unsubscribes** — clean as you go.

**The silent death to avoid:** a vanity open rate stays high (propped up by Apple) while real engagement rots and dead addresses drag your Gmail reputation into spam. By the time opens visibly drop, the list is half-buried. Watch complaints + clicks, not opens.
