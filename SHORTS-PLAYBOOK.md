# Magellan Shorts Playbook — format rules for deal videos that hold attention

Canonical reference for every faceless Short we make (`make_faceless.py` renders these
rules; update BOTH when the format evolves). Sources: 2025-26 Shorts retention guides
(OpusClip, Miraflow, creator frameworks) + our own production runs. Dalton's voice rules
apply everywhere: grounded, hedged claims, no hype, no emojis, no em dashes.

## The retention math (why the format looks like this)
- Viewers decide in the FIRST 2-3 SECONDS. The payoff (the fare) must be on screen and
  spoken immediately. Never open with context or a slow build.
- Sweet spot: 25-45 seconds total. Every second past 45 must earn its place; cut the
  weakest beat, usually a long overview sentence.
- Watch percentage beats watch time: a 40s video watched fully outranks a 70s video
  watched 60%. When in doubt, shorter.
- The LAST 3 seconds are the second-most important: land the deal recap or CTA cleanly,
  no trailing dead air (dead air kills replays, and replays boost distribution).

## Our fixed structure (per video type)
**Single-destination deal:**
1. HOOK (0-2s music alone, then): "Magellan Flights deal of the day is a trip to {city}
   from {origin} for only {price} dollars, direct, departing {date}. The link is in the
   description." Slide: city name, big price, route+date, "link in the description".
2. One-sentence city overview (photo bed).
3. QUICK TOUR: up to 6 stops, one line each, own photo, "STOP N OF 6" kicker.
4. Know before you go: best time + visa (one slide).
5. DEAL RECAP: price again + route + "often just a few seats".
6. CTA (~7s): brand line + newsletter ask.

**Around-the-world loop:**
0. TOUR cities need a TOURS entry (6 curated stops + Wikipedia page name) or they fall back
   to hero-photo-only. Roster so far: LON, ATH, SJU, BCN, BKK. Add new cities the same way:
   6 one-line stops, real landmarks, a clean Wikipedia page title per stop for the photo.
1. HOOK: itinerary card — total price huge, numbered stop list, "then home to {start}".
   Spoken: "Magellan Flights tracked an unforgettable trip around the world: {stops},
   and home, all for {total} dollars."
2. One beat per stop ("We would start our trip traveling to..." / "Next stop..." /
   "And finally... Then home."), each with its own photo + one-clause blurb.
3. DEAL RECAP: total + "every leg is a real, bookable one-way we track daily."
4. CTA (ATW-specific, NOT the newsletter push): "{N} stops, {N} weeks. One country a
   week is all it takes. Create your own around the world trip at magellanflights.com."
   N is computed from the actual stop count (dynamic, not hardcoded) — pitches the
   pace as doable and sends viewers to the interactive around-the-world.html builder,
   not the newsletter. Single-city Shorts keep the newsletter CTA; only ATW uses this one.

## Audio rules
- 2.0s music-alone intro before the narrator (MUSIC_LEAD). Music fades in 1.2s.
- Music bed ONLY under open + close, normalized to -28 LUFS vs voice at -16 LUFS.
  NEVER set music by raw volume multiplier — a quiet source file becomes inaudible
  (the 0.12x bug). Always loudnorm both stems to fixed targets.
- Voice: en-US-AvaMultilingualNeural, rate -3%, no pitch shift. Dalton picked Ava by
  ear from samples (Andrew = "very sharp", Christopher = "robotic"). Lessons: the
  Multilingual-generation voices are the natural-sounding ones, and do NOT force big
  rate/pitch changes - that is what makes TTS sound robotic. To trial voices, render
  the real hook line per candidate to Desktop\voice-samples and let Dalton listen.
- PLAN OF RECORD: Dalton records his own voiceovers going forward (authenticity beats
  any TTS). Build a --voice=file.mp3 mode when he starts: skip TTS, transcribe his
  recording with faster-whisper word timestamps for captions/slide sync, keep the rest.
- Location-matched tracks (all Kevin MacLeod CC BY 4.0, attribution REQUIRED in the
  description): London=Sovereign, Athens=Master of the Feast, default=Deliberate Thought.
  Add per-city tracks to MUSIC dict as the roster grows (incompetech direct mp3 URLs).

## Visual rules
- 1080x1920. Static slides + 0.5s crossfades ONLY — zoompan jitters ("shaky") and is
  banned. Motion comes from pacing, not fake camera moves.
- Text: >=90px side margins; captions overlay at H-450 (above the Shorts UI); nothing
  readable in the bottom ~330px.
- Captions: 3-word chunks, bold white on dark rounded card, timed to TTS word
  boundaries. Big fare numbers in Georgia serif; kickers in mint on photos, green on cream.
- Photos: Wikipedia REST `originalimage` (freely licensed, key-free). Fetch with 90s
  timeout. Wikimedia's image CDN (upload.wikimedia.org, separate from the lookup API)
  rate-limits with HTTP 429 if you hit it back-to-back with no delay - a plain 6-photo
  tour in a tight loop is enough to trigger it (SJU went 1/6 photos before this fix).
  `fetch()` retries with backoff (4s on 429, 1.5s otherwise, 3 attempts); ALSO sleep
  ~0.8s between consecutive photo downloads in the calling loop so you rarely trigger
  it at all. Ambiguous single-word city names (e.g. "San Juan" collides with San Juan,
  Argentina) land on a Wikipedia disambiguation page with no photo - use
  `wiki_photo_any([f"{name}, {country}", name])` for hero fetches, not a bare name.

## CTA language that converts (newsletter ask)
Formula: (1) qualify the viewer, (2) concrete benefit, (3) honest urgency, (4) free +
one action. Never "check out our website" (no reason to act).
- "If a trip like this is on your list, our free weekly newsletter is how you catch it:
  the best fares we tracked, in your inbox before they sell out. Join free at
  magellanflights.com."
- Variants to rotate: "Deals this cheap are usually a few seats. The newsletter is how
  you hear about them first." / "We send the five best fares we tracked, every week,
  free. One email, no spam, unsubscribe anytime."

## Description + upload checklist (every Short)
- Title: route + price + one intrigue element ("Orlando to London for $127? Direct, July 26").
- Description: hook line, what is in the video, WHERE THE LINK GOES (market.html?deal=
  ORIGIN-CODE flashes the exact fare row), newsletter line, honest price disclaimer,
  music attribution block (CC BY 4.0 — legally required), 4-5 hashtags incl #shorts.
- Pinned comment with the fare deep-link immediately after publishing (on Shorts the
  pinned comment is the main clickable surface).
- New channels: phone-verify at youtube.com/verify or description links are blocked
  (~24h to unlock). Bare domains pass as plain text meanwhile.
- Verify EVERY render before upload: extract frames (fps=0.25) and read them; probe
  audio with volumedetect (music audible?) and check audio/video stream durations match.
