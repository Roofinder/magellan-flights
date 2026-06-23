# On-Page, Technical & AI SEO — Magellan Flights

The video bundles on-page SEO, technical SEO, and AI SEO (getting cited in Google AI
Overviews / ChatGPT / Claude). Most of this is **already implemented and live** from
our earlier build. This file is the standard + a status check.

## On-page SEO — STATUS: ✅ live
- Unique, keyword-targeted `<title>` + meta description per page
- Keyword-in-URL slugs (e.g. /cheapest-day-to-book-flights.html)
- Clean H1 → H2 heading hierarchy in articles
- Image alt text / SVG role+title (flags decorative, map & sparklines labelled)
- Internal linking (every post → its money page; related-guides block)

## Technical SEO — STATUS: ✅ live
- sitemap.xml + robots.txt generated each build
- Canonical tags (www), Open Graph + Twitter cards
- schema.org JSON-LD: Organization, WebSite (SearchAction), WebPage, ItemList,
  Article, BreadcrumbList, FAQPage — plus HowTo for how-to posts
- Fast static pages on Vercel (good Core Web Vitals)

## AI SEO / GEO — how we get cited in AI answers
LLMs and Google AI Overviews mostly pull from page-one results and grab the most
*extractable* answer. Our rules (now baked into the blog engine):
1. **Be answer-first.** A "Quick answer" box right under the H1 that states the
   direct answer in 2-3 sentences. (Implemented: the `quick_answer` field.)
2. **Make it extractable.** Tables, bullets, numbered lists — structures an AI can
   lift cleanly. Avoid burying the answer in prose.
3. **FAQ + HowTo schema matching the exact question.** If our FAQ question equals the
   user's query, we're far more likely to be the quoted answer. (Implemented.)
4. **Earn page-one first.** AI citation almost always requires a top-10 organic
   ranking — which comes from the content depth + authority work (blogs, links),
   not a code toggle. This is the gating factor, so the blog cluster matters.

## Author checklist for every new post / page
- [ ] `quick_answer` set (extractable, direct)
- [ ] At least one table or list of concrete facts
- [ ] FAQ block whose questions match real search queries (secondary keywords)
- [ ] HowTo steps + `howto` schema if it's a "how to" topic
- [ ] Unique title/description, keyword-in-slug, internal link to a money page
- [ ] Written in the seo/writing_style.md voice (no AI slop)
</content>
