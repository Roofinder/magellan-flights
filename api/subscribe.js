// Magellan Flights — newsletter subscribe proxy (Vercel serverless, Node 18+)
// Creates a beehiiv subscription WITH the `home_airport` custom field, so the list
// can be segmented by home airport for targeted deal alerts. Keeps the API key
// server-side. The hosted beehiiv page drops URL params, so we call the API directly.
//
// Env (set in Vercel project settings):
//   BEEHIIV_API_KEY         beehiiv API key
//   BEEHIIV_PUBLICATION_ID  beehiiv publication id (pub_...)

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ ok: false, error: "Method not allowed" });
  }

  let body = req.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch { body = {}; }
  }
  body = body || {};

  const email = (body.email || "").toString().trim();
  const airport = (body.home_airport || "").toString().trim().toUpperCase().slice(0, 8);
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return res.status(400).json({ ok: false, error: "valid email required" });
  }

  const key = process.env.BEEHIIV_API_KEY;
  const pub = process.env.BEEHIIV_PUBLICATION_ID;
  if (!key || !pub) {
    return res.status(500).json({ ok: false, error: "beehiiv env vars not set" });
  }

  const payload = {
    email,
    reactivate_existing: true,
    send_welcome_email: true,
    utm_source: "magellanflights.com",
    referring_site: "magellanflights.com",
  };
  if (/^[A-Z]{3}$/.test(airport)) {
    payload.custom_fields = [{ name: "home_airport", value: airport }];
  }

  try {
    const r = await fetch(
      `https://api.beehiiv.com/v2/publications/${pub}/subscriptions`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${key}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      }
    );
    if (!r.ok) {
      const detail = await r.text().catch(() => "");
      return res.status(502).json({ ok: false, error: "subscribe failed", detail: detail.slice(0, 300) });
    }
    return res.status(200).json({ ok: true });
  } catch (e) {
    return res.status(502).json({ ok: false, error: "subscribe failed" });
  }
}
