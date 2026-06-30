// Magellan Flights — live fare proxy (Vercel serverless, Node 18+)
// Proxies Travelpayouts "prices_for_dates" so the API token stays server-side.
// Powers: live prices, the trip builder, and the one-way hopper.
//
// Surge hardening (the upstream caps prices_for_dates at ~300 req/min / ~5 req/s and
// 429-blocks on a burst, so under a traffic spike the job is to call it as little as
// possible and never hand the client a hard error):
//   1. Long edge cache + stale-while-revalidate + stale-if-error, so the CDN absorbs
//      the flood and serves last-good fares if the function ever errors.
//   2. A small in-memory cache per warm instance, so a repeated query during a burst
//      is answered without touching the upstream at all.
//   3. Graceful degradation: on an upstream 429/5xx or a fetch failure, serve the
//      last-known-good result if we have one, else a soft empty 200 — never a 502.
//
// Query params (all optional except origin):
//   origin, destination        IATA codes (e.g. JFK, MAD)
//   departure_at, return_at    YYYY-MM or YYYY-MM-DD
//   one_way                    "true" | "false"  (default false)
//   sorting                    "price" | "route"  (default price)
//   limit                      1..1000  (default 30)
//   direct                     "true" | "false"  (default false)

const MARKER = "741311";

// Cache headers. s-maxage: how long the edge serves a cached response as fresh.
// stale-while-revalidate: keep serving it (revalidating in the background) past that.
// stale-if-error: if a later revalidation errors, keep serving the stale copy up to a day.
const CACHE_OK = "public, s-maxage=300, stale-while-revalidate=600, stale-if-error=86400";
const CACHE_STALE = "public, s-maxage=60, stale-while-revalidate=600, stale-if-error=86400";
const CACHE_EMPTY = "public, s-maxage=20, stale-if-error=86400";

// Warm-instance memory cache (module scope persists across invocations on a warm lambda).
const MEM_TTL_MS = 90 * 1000; // serve an identical query without re-calling upstream for 90s
const MEM_MAX = 600;          // cap entries so memory stays bounded
const memCache = new Map();   // key -> { ts, json }

function memSet(key, json) {
  memCache.set(key, { ts: Date.now(), json });
  if (memCache.size > MEM_MAX) memCache.delete(memCache.keys().next().value); // evict oldest
}

function dropPhantomLows(j, dest) {
  // For a specific route, prefer fares cached today and drop a lone phantom-low
  // singleton (a cheapest sitting far below the next-cheapest), matching the
  // build-time reprice logic so "check live price" stays trustworthy.
  if (j && Array.isArray(j.data) && /^[A-Z]{3}$/.test(dest) && j.data.length > 1) {
    const t = new Date();
    const sd = String(t.getDate()).padStart(2, "0") +
      String(t.getMonth() + 1).padStart(2, "0") + t.getFullYear();
    const fresh = j.data.filter((x) => (x.link || "").includes("search_date=" + sd));
    const pool = (fresh.length ? fresh : j.data).slice().sort((a, b) => a.price - b.price);
    while (pool.length > 1 && pool[0].price < 0.70 * pool[1].price) pool.shift();
    j.data = pool;
  }
  return j;
}

export default async function handler(req, res) {
  const q = req.query || {};
  const origin = (q.origin || "").toString().trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(origin)) {
    res.status(400).json({ success: false, error: "valid 3-letter 'origin' required" });
    return;
  }
  const token = process.env.TP_TOKEN;
  if (!token) {
    res.status(500).json({ success: false, error: "TP_TOKEN env var not set in Vercel" });
    return;
  }

  const p = new URLSearchParams({
    origin,
    currency: "usd",
    token,
    one_way: q.one_way === "true" ? "true" : "false",
    sorting: q.sorting === "route" ? "route" : "price",
    direct: q.direct === "true" ? "true" : "false",
    limit: String(Math.min(parseInt(q.limit, 10) || 30, 1000)),
  });
  const dest = (q.destination || "").toString().trim().toUpperCase();
  if (/^[A-Z]{3}$/.test(dest)) p.set("destination", dest);
  if (q.departure_at) p.set("departure_at", String(q.departure_at).slice(0, 10));
  if (q.return_at) p.set("return_at", String(q.return_at).slice(0, 10));

  // Cache key excludes the token (constant) so identical user queries collapse together.
  const cacheKey = [origin, dest, p.get("one_way"), p.get("sorting"), p.get("direct"),
    p.get("limit"), q.departure_at || "", q.return_at || ""].join("|");
  const hit = memCache.get(cacheKey);

  // 1) Warm-instance hit: answer a recent identical query without touching the upstream.
  if (hit && (Date.now() - hit.ts) < MEM_TTL_MS) {
    res.setHeader("Cache-Control", CACHE_OK);
    res.setHeader("X-Magellan-Cache", "mem");
    res.status(200).json(hit.json);
    return;
  }

  const url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates?" + p.toString();

  try {
    const r = await fetch(url, { headers: { "Accept-Encoding": "identity" } });

    if (!r.ok) {
      // 2) Upstream rate-limited / erroring. Never propagate a hard 502.
      if (hit) {
        res.setHeader("Cache-Control", CACHE_STALE);
        res.setHeader("X-Magellan-Cache", "stale");
        res.status(200).json(hit.json);            // last-known-good fares
        return;
      }
      res.setHeader("Cache-Control", CACHE_EMPTY);  // soft, cacheable empty so a burst can't hammer upstream
      res.setHeader("X-Magellan-Cache", "miss");
      res.status(200).json({ success: true, data: [], stale: true, note: "upstream " + r.status });
      return;
    }

    const j = await r.json();
    if (j && Array.isArray(j.data)) {
      for (const d of j.data) {
        if (d.link && d.link.startsWith("/")) {
          d.link = "https://www.aviasales.com" + d.link +
            (d.link.includes("marker=") ? "" : "&marker=" + MARKER);
        }
      }
      dropPhantomLows(j, dest);
      memSet(cacheKey, j); // remember the good result for the warm cache + error fallback
    }
    res.setHeader("Cache-Control", CACHE_OK);
    res.setHeader("X-Magellan-Cache", hit ? "revalidated" : "fresh");
    res.status(200).json(j);
  } catch (e) {
    // 3) Network/fetch failure — same graceful path: stale if we have it, else soft empty.
    if (hit) {
      res.setHeader("Cache-Control", CACHE_STALE);
      res.setHeader("X-Magellan-Cache", "stale");
      res.status(200).json(hit.json);
      return;
    }
    res.setHeader("Cache-Control", CACHE_EMPTY);
    res.setHeader("X-Magellan-Cache", "error");
    res.status(200).json({ success: true, data: [], stale: true, note: "fetch failed" });
  }
}
