// Magellan Flights — live fare proxy (Vercel serverless, Node 18+)
// Proxies Travelpayouts "prices_for_dates" so the API token stays server-side.
// Powers: live prices, the trip builder, and the one-way hopper.

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
    if (!r.ok) { res.status(502).json({ success: false, error: "upstream " + r.status }); return; }
    const j = await r.json();
    if (j && Array.isArray(j.data)) {
      for (const d of j.data) {
        if (d.link && d.link.startsWith("/")) {
          d.link = "https://www.aviasales.com" + d.link + (d.link.includes("marker=") ? "" : "&marker=" + MARKER);
        }
      }
    }
    res.setHeader("Cache-Control", "public, s-maxage=300, stale-while-revalidate=1800");
    res.status(200).json(j);
  } catch (e) {
    res.status(502).json({ success: false, error: "fetch failed", detail: String(e) });
  }
}
