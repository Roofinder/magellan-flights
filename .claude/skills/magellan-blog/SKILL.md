---
name: magellan-blog
description: Research, write, and publish a new SEO blog post for Magellan Flights (magellanflights.com). Bundles the full pipeline — keyword cluster → top-3 SERP research → article written in the brand voice with answer box + FAQ/HowTo schema → build → deploy → verify. Invoke when the user wants a new blog post / guide. Optional arg = the topic or cluster name.
---

# Write & publish a Magellan Flights blog post

The site is a static generator at `C:\Users\dalto\OneDrive\Desktop\FlightExchange`
(repo `Roofinder/magellan-flights`, Vercel). Posts are Python dicts in the
`ARTICLES` list inside `buildsite.py`; adding one auto-generates the page, schema,
sitemap entry, nav, and guides-index card. **All booking links stay Aviasales
(marker 741311).**

## Steps

1. **Pick the cluster.** If the user named a topic, match it to a cluster in
   `seo/keyword_clusters.md`. Otherwise pick the highest-priority cluster that isn't
   already published (check existing slugs in `ARTICLES`).

2. **Study what ranks (the video's "copy the winning formula").** WebSearch the
   primary keyword; WebFetch the top 2-3 results. Note their structure, depth,
   subtopics, and what question they answer first. Match/beat that shape — don't copy text.

3. **Write the article** as a new dict appended to `ARTICLES` in `buildsite.py`:
   - `slug` (keyword-in-url), `title` (≤60 chars, ends "| Magellan Flights"),
     `h1`, `description` (~155 chars), `primary`, `secondary` (the 4 cluster kws),
     `kicker`, `published`/`updated` (today's date from the session context),
     `read_min`, `money_href`/`money_label` (the cluster's internal-link target).
   - `lede` — answer-first hook (NO throat-clearing).
   - `quick_answer` — 2-3 sentence extractable answer (AI Overviews).
   - `sections` — list of (h2, html) with `<p>`/`<ul class='blog-list'>`; use `{LIVE_ROUTES}`,
     `{LIVE_TOPCITY}`, `{LIVE_TOPPCT}` tokens to inject live data.
   - `faqs` — the secondary keywords as natural questions (plain-text answers).
   - `howto` (optional) — `{name, steps:[{name,text}]}` if it's a "how to" topic.
   - Follow **`seo/writing_style.md`** (voice, zero AI slop), **`seo/ai_seo.md`**
     (answer-first, extractable tables/lists, FAQ/HowTo), **`seo/cro.md`** (clear CTAs).
   - **Read `seo/on-page-seo.md` and satisfy its pre-publish gate** — especially the
     two easy-to-miss items: 2-3 external authoritative (non-competitor) links and
     3-5 internal links including the cluster's money page.

4. **Build & verify locally:** `python buildsite.py`, then confirm the new
   `<slug>.html` has a unique title, the answer box, valid JSON-LD, live data
   injected, and an internal link to the money page.

5. **Deploy** with the `magellan-deploy` skill (or inline: copy changed files into
   the `C:\Users\dalto\mf-deploy` clone, commit, `git push origin main`, then curl
   the live URL to confirm HTTP 200 and the new title).

6. **Close the loop:** mark the matching task complete, and tell the user the live URL.

## Guardrails
- Never copy `config.json` into the deploy clone (it holds the API token).
- One genuine, useful post — not thin filler. If the data tokens would be empty, omit them.
- Keep titles/descriptions unique vs existing posts.
</content>
