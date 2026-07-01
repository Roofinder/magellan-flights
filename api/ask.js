// Magellan Flights — AI deal assistant (Vercel serverless, Node 18+)
// Answers natural-language flight-deal questions grounded ONLY in Magellan's own
// daily-tracked data (winners.json = best below-normal one-ways; oneway_index.json
// = regional average fares). Cheap by design: Claude Haiku 4.5, a hard max_tokens
// output cap, a tiny grounding payload, and a per-instance IP rate limit. Keeps the
// API key server-side; never invents prices (mirrors the site's hedged framing).
//
// Env (Vercel project settings): ANTHROPIC_API_KEY
import { readFileSync } from "node:fs";
import path from "node:path";

const MODEL = "claude-haiku-4-5"; // cheapest capable: $1/1M in, $5/1M out
const MAX_TOKENS = 500;           // hard output cap = hard per-request cost ceiling
const MARKER = "741311";          // Aviasales affiliate marker (brand rule)

// Load committed data once per cold start. The cron redeploys with fresh data,
// so each deploy picks up the latest winners/index.
function loadJSON(name, fallback) {
  try {
    return JSON.parse(readFileSync(path.join(process.cwd(), name), "utf8"));
  } catch {
    return fallback;
  }
}
const WINNERS = loadJSON("winners.json", []);
const INDEX = loadJSON("oneway_index.json", {});

// Per-warm-instance soft rate limit — blunts single-source abuse. NOT a durable
// per-user monthly cap (that needs edge KV / Upstash; see note below).
const RL = new Map(); // ip -> { count, day }
const RL_MAX = 8;     // questions per IP per day per warm instance
function rateLimited(ip) {
  const day = new Date().toISOString().slice(0, 10);
  const e = RL.get(ip);
  if (!e || e.day !== day) {
    RL.set(ip, { count: 1, day });
    if (RL.size > 5000) RL.delete(RL.keys().next().value); // bound memory
    return false;
  }
  e.count += 1;
  return e.count > RL_MAX;
}

function groundingText() {
  const deals = WINNERS.map(
    (w) =>
      `- ${w.origin}->${w.code} (${w.name}): $${w.price} one-way, avg $${w.avg}, ${w.disc}% below normal. Book: ${w.link}`
  ).join("\n");
  const dates = Object.keys(INDEX).sort();
  const latest = dates.length ? INDEX[dates[dates.length - 1]] : {};
  const idx = Object.entries(latest)
    .map(([r, v]) => `${r} ~$${Math.round(v)}`)
    .join(", ");
  return `CURRENT BEST DEALS (each below its own price history):\n${deals}\n\nREGIONAL AVERAGE ONE-WAY FARES (latest tracked): ${idx}`;
}

const SYSTEM = `You are the Magellan Flights deal assistant. You ONLY know the flight data provided in DATA below — Magellan's own daily-tracked cheapest one-way US fares. Rules:
- Answer ONLY from DATA. If it doesn't cover the question, say so plainly and point them to browse magellanflights.com. NEVER invent prices, routes, discounts, or deals.
- Magellan is one-way-led: quote fares as one-way.
- When you cite a specific deal, include its booking link exactly as given (Aviasales, marker ${MARKER}) and note the real price is confirmed on Aviasales.
- Prices are the "freshest tracked" fares, not guaranteed. Be concise, friendly, and specific.
- Write in PLAIN TEXT only: no markdown — no # headings, no ** bold, no [text](url) links. Put each booking URL bare on its own line (the site turns bare URLs into booking buttons).

DATA:
${groundingText()}`;

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
  const question = (body.question || "").toString().trim().slice(0, 500);
  if (!question) return res.status(400).json({ ok: false, error: "question required" });

  const ip = (req.headers["x-forwarded-for"] || "").split(",")[0].trim() || "unknown";
  if (rateLimited(ip)) {
    return res.status(429).json({ ok: false, error: "You've hit today's question limit — try again tomorrow." });
  }

  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) return res.status(500).json({ ok: false, error: "ANTHROPIC_API_KEY not set in Vercel" });

  try {
    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: MAX_TOKENS,
        system: SYSTEM,
        messages: [{ role: "user", content: question }],
      }),
    });
    if (!r.ok) {
      const detail = await r.text().catch(() => "");
      return res.status(502).json({ ok: false, error: "assistant unavailable", detail: detail.slice(0, 200) });
    }
    const data = await r.json();
    const answer = (data.content || [])
      .filter((b) => b.type === "text")
      .map((b) => b.text)
      .join("")
      .trim();
    res.setHeader("Cache-Control", "no-store");
    return res.status(200).json({ ok: true, answer });
  } catch (e) {
    return res.status(502).json({ ok: false, error: "assistant unavailable" });
  }
}
