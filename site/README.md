# site/ — the hosted research hub

Deployed on Railway from this repo. Two pages:

- `/` — the Frosted Terminal hub: forward paper-test dashboard (equity chart,
  signal book, gate log) + the research library panels.
- `/research/` — the interactive study write-up, served from this repo's
  `docs/index.html` (single source of truth — the Docker build copies it in).

## How it builds

Railway builds `site/Dockerfile` with the repo root as context:

1. `python site/src/build.py` assembles `public/index.html` from
   `terminal-src.html` + `loader.js` + `frames-manifest.json` (the scroll-video
   frames, gzip+base64 — committed once, never edited).
2. `docs/index.html` is copied to `/research/index.html`.
3. Caddy serves `public/` on `$PORT` (gzip, no-cache on HTML).

The 10.6MB bundle is a BUILD artifact — never commit it. Only sources live here.

## Updating

- Terminal content/data (the `DATA` object): edit `src/terminal-src.html`, push.
- Research page: rebuild `docs/index.html` (see docs/design-handoff.md), push.
- Live paper equity (Q4): a daily job writes the equity series into the
  `DATA.live` block of `terminal-src.html` (or a future `/data/live.json`)
  and pushes — Railway redeploys on push.

## Railway setup (one-time, dashboard)

New project → Deploy from GitHub repo → `Taylor-Hobbs/asx` →
Settings: **Dockerfile path = `site/Dockerfile`** (root directory stays `/`).
Optional: watch paths `site/**` and `docs/index.html` to skip rebuilds on
research-code-only pushes. Add a custom domain under Settings → Networking.
