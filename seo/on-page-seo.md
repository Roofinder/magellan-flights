# On-page SEO checklist — read before generating ANY page

The master on-page spec for Magellan Flights. The `magellan-blog` skill (and any
page generator) reads this before building a page. Goal: hit every signal **while
keeping the voice** in `seo/writing_style.md` — never trade readability for boxes
ticked. Technical SEO (sitemap, robots, Core Web Vitals) is in `seo/ai_seo.md`.

Legend: ✅ built into buildsite.py · ✍️ author must do per page

## 1. Head & metadata  ✅
- ✅ Title 50–60 chars, primary keyword near the front, ends "| Magellan Flights"
- ✅ Meta description 150–160 chars, keyword + benefit + soft CTA
- ✅ Canonical URL (www), Open Graph (title/desc/image 1200×630/url/type), Twitter card
- ✅ `<html lang="en">`, viewport, charset, favicon, theme-color

## 2. URL structure  ✅
- ✅ Short slug (<60 chars), primary keyword in slug, hyphens, lowercase, no stop words

## 3. Headings  ✅ / ✍️
- ✅ Exactly one H1 (contains primary keyword)
- ✍️ Logical H2→H3, no skipped levels; H2s use secondary keywords + cluster questions

## 4. Opening  ✍️
- ✍️ Primary keyword in the first ~100 words
- ✅ Answer-first "Quick answer" box (extractable for AI Overviews) — `quick_answer`
- ✍️ Hook in sentence one, no throat-clearing

## 5. FAQ  ✅ / ✍️
- ✍️ 4–8 questions (from the cluster's secondary keywords + "People Also Ask")
- ✅ FAQPage schema applied automatically

## 6. Links  ✍️  ← easy to forget
- ✍️ **2–3 external links** to authoritative, non-competitor sources (e.g. .gov, data,
  research). Open in new tab, `rel="noopener"`.
- ✍️ 3–5 internal links to relevant pages (always link the money page for the cluster)

## 7. Images  ✅
- ✅ Alt text (decorative flags = empty alt, by design), width/height (no CLS), lazy-load
- ✍️ If adding a hero/inline image: descriptive keyword filename, WebP, <200 KB

## 8. Content quality  ✍️
- ✍️ Genuinely useful, original, matches search intent; tables/lists for extractability
- ✍️ Voice per writing_style.md (no AI slop); one earned laugh per few sections
- ✍️ HowTo schema (`howto`) if it's a how-to topic

## 9. Structured data  ✅
- ✅ Article + BreadcrumbList + WebPage + (FAQ/HowTo) JSON-LD generated per post

## Pre-publish gate
Before deploy, confirm: 1 H1 · keyword in first 100 words · 4–8 FAQs · 2–3 external
links · 3–5 internal links (incl. money page) · unique title/desc · quick_answer set.
</content>
