---
name: magellan-deploy
description: Build and publish magellanflights.com to production. Bundles the working deploy flow — rebuild the static site, copy changed files into the non-OneDrive git clone, commit, push to main (Vercel auto-deploys), and verify live. Invoke whenever changes need to go live.
---

# Deploy Magellan Flights to production

The OneDrive working folder can't `git push` (file-locking), so we publish through a
clone OUTSIDE OneDrive. Credentials are cached in Git Credential Manager.

## Steps

1. **Build** from `C:\Users\dalto\OneDrive\Desktop\FlightExchange`:
   ```
   python buildsite.py
   cp site/*.html .
   cp site/sitemap.xml site/robots.txt site/llms.txt .
   ```
   (Run `python make_og.py` only if the share image changed.)

2. **Sync the deploy clone** at `C:\Users\dalto\mf-deploy` (create it once with
   `git clone https://github.com/Roofinder/magellan-flights.git`):
   ```
   cd /c/Users/dalto/mf-deploy && git pull origin main
   ```

3. **Copy changed files** from the working folder into the clone — the built
   `*.html`, `sitemap.xml`, `robots.txt`, `llms.txt`, `og-image.png`, and any changed
   source (`buildsite.py`, etc.). **Never copy `config.json`** (gitignored; holds the
   API token).

4. **Commit & push:**
   ```
   git add -A
   git commit -m "<what changed>

   Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
   GIT_TERMINAL_PROMPT=0 git push origin main
   ```
   If the first push of a session prompts for auth, a Git Credential Manager window
   opens — the owner signs in once, then it's cached.

5. **Verify live** (site serves on www; apex 308s to www — follow redirects):
   ```
   curl -s -m 15 -L https://www.magellanflights.com/<changed-page> -o /dev/null -w "%{http_code}\n"
   ```
   Confirm HTTP 200 and grep for the specific change you shipped. Vercel redeploys
   ~1-2 min after the push.

## Notes
- `BASE_URL` in buildsite.py is the www canonical form.
- The GitHub Action refreshes data + reprices 4×/day and pushes on its own; this
  skill is for shipping code/content changes immediately.
</content>
