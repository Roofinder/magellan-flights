# Magellan — Build To-Do (loop state)

The state file for the PRD → to-do → loop. Work **one unchecked item per session**, make a plan,
implement, verify (`node --check` any changed `<script>`), then **check it off here** and note what was
done. Clear context between items. Full spec + conventions in `MAGELLAN-PRD.md` + `CLAUDE.md`.

Loop prompt to reuse each session:
> Read `MAGELLAN-PRD.md`, `CLAUDE.md`, and `MAGELLAN-TODO.md`. Plan and implement the FIRST unchecked
> item. Respect the conventions. Verify changed scripts with `node --check`. Then check the item off in
> `MAGELLAN-TODO.md` with a one-line note of what you did. Stop.

---

## Epic A — Email + airport segmentation (priority 1)
- [x] A1. Add a home-airport picker to the newsletter signup form (prefill from `localStorage.fs_home`; reuse `city_options`). Regenerate + `node --check`. ✅ 2026-07-01
- [~] A2. Update `nlSub()` + the `data-subscribe` search forms to pass the chosen airport to Beehiiv as a `home_airport` param. **nlSub() DONE** (appends `&home_airport=` + persists to localStorage). **Still to do:** the `data-subscribe` search forms (`homeSearch`, buildsite.py ~2894/2964).
- [x] A3 (verify). **TESTED LIVE 2026-07-01 — URL param does NOT work.** Created the `home_airport` TEXT custom field in Beehiiv ✅. Drove a real signup through the deployed picker → Beehiiv landing URL correctly carried `&home_airport=RDU` (front-end proven). BUT: the `?email=` param didn't even prefill Beehiiv's hosted form (field was empty), and after "Subscribed!" the active count stayed 4/4 (double opt-in → pending). Conclusion: **Beehiiv's hosted subscribe page ignores URL query params**, so home_airport isn't captured this way.
- [x] A3b. **Built `api/subscribe.js`** (Beehiiv API) + rewired `nlSub()` to POST to it (inline confirm; falls back to hosted redirect on error). Shipped `bd62593`. **VERIFIED the API directly** with the real key: create-subscription returns `custom_fields:[{name:"home_airport",value:"RDU"}]` — the field IS captured. node --check OK on both.
- [x] A3c. Vercel env vars `BEEHIIV_API_KEY` + `BEEHIIV_PUBLICATION_ID` added to Production + redeployed. **LIVE TEST PASSED 2026-07-01:** POST to https://www.magellanflights.com/api/subscribe → `{"ok":true}`; Beehiiv API confirms the subscriber (daltonnicely+livetest) is `active` with `custom_fields:[{home_airport:RDU}]`. **Epic A core is DONE — home_airport now captured on every newsletter signup.**
- [ ] A_seg (OWNER, content side). In Beehiiv: Audience → Segments → new segment filtering `home_airport` = <code> (per airport), then send per-airport deal alerts. This is what turns the captured data into targeted MAU.
- [x] A2b. **DONE 2026-09-01.** `homeSearch` now POSTs to `/api/subscribe` with `home_airport` instead of window.open-ing the hosted Beehiiv URL with `?email=`, which A3 had already proved does nothing: the hosted page ignores query params, so the email did not prefill and the user had to retype it. The departure airport is richer data than the newsletter form gets, because that form has to ask and this one already knows. Also persists `fs_home` like `nlSub()`. `keepalive:true` is load bearing: the Aviasales redirect fires immediately after and a normal fetch is cancelled on navigation, losing the subscribe exactly when the search succeeded. Falls back to the hosted page on error.
- [ ] A4. Test: signup with an airport → confirm it lands on the Beehiiv subscriber record + a segment can filter by it. Verify no regression to existing localStorage personalization.

## Epic B — Search cache / traffic readiness (priority 2, mostly done)
- [ ] B1. Read through `api/search.js` fallback branches; confirm memory cache + `stale-if-error` return last-good on a simulated upstream 429/5xx. Write a 1-paragraph confirmation.
- [ ] B2. Document the **Vercel Pro** trigger (invocation/traffic threshold to upgrade) in `MAGELLAN-ACTION-PLAN.md`. Do not enable prematurely.

## Epic C — AI flight/deal assistant (priority 3, the differentiator)
- [x] C1. Data contract decided: assistant grounds on **winners.json** (curated best below-normal one-ways) + **oneway_index.json** (regional avg fares, latest day). Both tiny (~500 tokens) → bundle into the system prompt. (`/api/search` left as a future live-lookup extension.)
- [x] C2. Built **`api/ask.js`** (serverless, native fetch, no SDK). **Model: `claude-haiku-4-5`** ($1/$5 per 1M — cheapest capable). Grounds ONLY in DATA, one-way-led, cites Aviasales links (741311), never invents prices. Server-side key. `node --check` OK; grounding verified against real data.
- [x] C3. Freemium/cost-control: hard `max_tokens: 500` (output cost ceiling) + per-warm-instance IP rate limit (8/day). **NOTE:** durable per-user monthly cap needs edge KV/Upstash — soft cap for MVP; the real cost lever is Haiku + max_tokens + tiny payload (~$0.003/question).
- [~] C4. Research-cache: N/A for MVP — grounding data is tiny (no LLM round-trip to cache) and answers vary by question. Add an answer cache later only if volume warrants.
- [x] C5. Ask-box UI: `body_ask()` → **ask.html** ("Ask Magellan"), input + suggestion chips → POSTs `{question}` to `/api/ask`, renders answer (linkifies Aviasales URLs), loading + error states. **Registered but NOT nav-linked yet** (waiting on the key, so we don't expose a broken feature). Shipped `eb8a63b`; py_compile + rebuild + node --check OK.
- [x] C6. **LIVE + VERIFIED 2026-07-01.** `ANTHROPIC_API_KEY` added to Vercel + redeployed. Two deploy fixes along the way: (1) Vercel wasn't bundling the grounding JSONs into the function — added `functions.api/ask.js.includeFiles` to vercel.json; (2) model answered in markdown, which the page renders literally — system prompt now demands plain text + bare URLs (page linkifies them into booking buttons). Nav link "Ask Magellan" flipped on (`8a16f4f`, `4c71095`). **Live tests passed:** grounded answer citing exact winners.json fares + Aviasales link w/ marker 741311; out-of-data question (RDU→Tokyo) correctly declined, no invented price; plain-text render verified in a real browser session on /ask.html. **Epic C DONE.**

## Epic D — weekly video (path chosen 2026-07-01: Dalton records, Claude edits)
- [x] D0. Decision: **weekly self-recorded newsletter walkthrough** (not daily, not AI-avatar — Dalton's call after evaluating the Fable/HeyGen/ElevenLabs route). Script auto-generated each week (`4-newsletter-video.md`, added to the weekly batch this week).
- [x] D1. Built the global **`weekly-video-edit`** skill: silence-cut → stitch → loudnorm → faster-whisper captions → Pillow+ffmpeg-overlay burn-in → 9:16 export → frame-verify. Toolchain verified on-machine (Shotcut ffmpeg + Pillow + faster-whisper), zero paid tools. Raw footage convention: `weekly-batch/week-X/raw/`.
- [ ] D2 (OWNER). Record the first walkthrough (~40s, phone upright, quiet room, read `4-newsletter-video.md`), drop it in `weekly-batch/week-20260701/raw/`, say "edit my weekly video". First run = calibration (silence threshold, caption sizing).
- [ ] D3. (later) Fold the video-script generation into weekly.py output permanently + save tuned edit parameters back into the skill.

---

## Done log
- **2026-07-01 — A1 (+ part of A2):** Threaded `home` into `body_newsletter(market, oneway, home=None)` and its call site. Added a `#nl-airport` home-airport `<select>` (populated by `city_options`, 46 airports) to the newsletter signup form; prefills from `localStorage.fs_home`. Updated `nlSub()` to persist the pick to localStorage and append `&home_airport=<code>` to the Beehiiv signup URL alongside `email`. `py_compile` OK; full rebuild OK (19 pages + …); extracted the generated `nlSub` script and `node --check` OK. **DEPLOYED 2026-07-01** — committed buildsite.py only (`a03d63d`), rebased over 8 cron data-commits, pushed to main; publish.yml rebuilds root. Next: **A3 verify** (does Beehiiv capture the `home_airport` URL param into a custom field? test a real signup) — that answer decides whether A2's remaining work is a URL param or a `api/subscribe.js` Beehiiv-API call.
