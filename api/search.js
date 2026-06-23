// Magellan Flights — live fare proxy (Vercel serverless, Node 18+)
// Proxies Travelpayouts "prices_for_dates" so the API token stays server-side.
// Powers: live prices, the trip builder, and the one-way hopper.
//
// Query params (all optional except origin):
//   origin, destination        IATA codes (e.g. JFK, MAD)
//   departure_at, return_at    YYYY-MM or YYYY-MM-DD
//   one_way                    "true" | "false"  (default false)
//   sorting                    "price" | "route"  (default price)
//   limit                      1..1000  (default 30)
//   direct                     "true" | "false"  (default false)

const MARKER = "741311";

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

  const url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates?" + p.toString();

  try {
    const r = await fetch(url, { headers: { "Accept-Encoding": "identity" } });
    if (!r.ok) {
      res.status(502).json({ success: false, error: "upstream " + r.status });
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
      // For a specific route, prefer fares cached today and drop lone phantom-low
      // singletons (a cheapest sitting far below the next-cheapest), matching the
      // build-time reprice logic so "check live price" stays trustworthy.
      if (/^[A-Z]{3}$/.test(dest) && j.data.length > 1) {
        const t = new Date();
        const sd = String(t.getDate()).padStart(2, "0") +
          String(t.getMonth() + 1).padStart(2, "0") + t.getFullYear();
        const fresh = j.data.filter((x) => (x.link || "").includes("search_date=" + sd));
        const pool = (fresh.length ? fresh : j.data).slice().sort((a, b) => a.price - b.price);
        while (pool.length > 1 && pool[0].price < 0.70 * pool[1].price) pool.shift();
        j.data = pool;
      }
    }
    // cache at the edge for 90s, serve stale up to 10 min while revalidating —
    // a page refresh re-pulls fresher data from Travelpayouts after 90s.
    res.setHeader("Cache-Control", "public, s-maxage=90, stale-while-revalidate=600");
    res.status(200).json(j);
  } catch (e) {
    res.status(502).json({ success: false, error: "fetch failed", detail: String(e) });
  }
}
