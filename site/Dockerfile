# Build context is the REPO ROOT (Railway: set Dockerfile path to site/Dockerfile).
# Stage 1 assembles the terminal bundle from committed sources; the research page
# is taken straight from docs/index.html — no duplicated copies in the repo.
FROM python:3.12-alpine AS build
COPY site /site
RUN python /site/src/build.py
COPY docs/index.html /site/public/research/index.html

FROM caddy:2-alpine
COPY site/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /site/public /srv
