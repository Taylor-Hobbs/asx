# Build Log

Short entry per session: what was built, what broke, what the evals showed.
Feeds the weekly public build-log posts. Newest entries first.

---

## 2026-06-11 — Repo setup + scaffold

**Built:**
- Repo created and published to github.com/Taylor-Hobbs/asx (CLAUDE.md v2, README, .gitignore).
- Python scaffold: uv-managed `pyproject.toml` (src/ layout, hatchling), `asx_engine` package
  with `ingestion` / `parsing` / `extraction` / `schemas` subpackages.
- `config.py` — typed settings via pydantic-settings (`ASX_`-prefixed env vars); required GCP
  fields fail loudly when missing; ingestion-etiquette defaults (3s request interval,
  identifiable User-Agent) live here.
- Tests for config (env loading, defaults, fail-loud validation).
- CI: GitHub Actions running ruff (lint + format), mypy --strict, pytest on every push/PR.
- Docs stubs: architecture.md, eval-methodology.md. Conventions READMEs in prompts/ and golden/.
- **Schemas:** `Announcement` (frozen, content-hash keyed, tz-aware UTC-normalized
  `announced_at`/`ingested_at` — naive datetimes rejected at construction).
  `SourcedField[T]` (PEP 695 generic; per-field confidence + verbatim source quote),
  `ReportedMetric` (current + prior comparative), `EarningsResult`, `GuidanceStatement`
  (direction enum, ordered-range validation, open-ended ranges allowed),
  `ExtractionRecord[PayloadT]` envelope binding payloads to (model, prompt version,
  timestamp) for eval reproducibility. Decimal for money, units in field names.
- 26 tests passing; mypy --strict clean.

**Broke:** nothing yet — machine had no Python; installed uv + managed Python 3.12.13.

**Evals:** n/a (harness not built yet).

**Decisions made:** confidence/source-span at field grain (matches per-field eval grain);
source spans as quoted text not char offsets (parser-version proof); units encoded in
field names (`revenue_aud`, `eps_cents`) with normalization at extraction time.

**ASX data source de-risked (the big Q1 unknown).** Probed live, politely (~8 requests,
3s spacing, identifying UA):
- The pyasx-era endpoint (`asx.com.au/asx/1/...`) is **dead** — 404. pyasx is stale.
- Live chain verified end-to-end: (1) metadata JSON from
  `asx.api.markitdigital.com/asx-research/1.0/companies/{ticker}/announcements`;
  (2) PDF resolution via legacy `displayAnnouncement.do?display=pdf&idsId={middle
  segment of documentKey}` → terms interstitial with hidden `pdfURL` input;
  (3) direct PDF download from `announcements.asx.com.au` → 200 application/pdf.
- Quirks: `itemsPerPage` is a suggestion (asked 3, got 5); metadata `url` field is
  empty; markitdigital cdn-api file-gateway patterns from older scrapers also 404.
- ⚠️ To verify during manual ingestion: the resolved pdfURL for idsId 03081111 had a
  date-path (20260409) that didn't match the announcement date (2026-04-21) — confirm
  the documentKey→idsId→PDF mapping lands on the right document before trusting it
  at scale.

**Built (continued):** `AsxClient` — rate-limited (injectable clock/sleep), fail-loud
(`AsxApiChangedError` with payload snippets on any drift), exponential backoff on
429/5xx/transport errors only (hard 4xx never retried), interstitial pdfURL extraction
with direct-PDF short-circuit. Tests (15) run against verbatim captured payloads via
httpx.MockTransport — zero network in CI. 41 tests total.

**GCP stood up** (project `asx-scanner-499110`, billing linked, budget alert set):
- Private bucket `asx-scanner-499110-raw-pdfs` in australia-southeast2 — uniform
  bucket-level access + public-access prevention *enforced* (public ACLs impossible,
  enforcing the redistribution rule at the infrastructure level).
- BQ dataset `asx_engine` + `announcements` table; schema versioned in
  `infra/bq/announcements.schema.json`, field descriptions carry the invariants
  (immutability, announced_at vs ingested_at separation).
- Auth via ADC only — no service-account key files anywhere.
- Verified end-to-end from Python: settings → storage.Client → bigquery.Client all
  resolve against live resources.

**⚠️ RESOLVED — and it was a real bug.** The JSON documentKey's middle segment is NOT an
idsId: for BHP's 2026-04-21 quarterly it gave 03081111, which resolves to a *different
document* (2026-04-09); the correct idsId is 03084954. Worse, the JSON endpoint returns
only the 5 most recent items — pagination and fromDate/toDate are silently ignored.
**Pivot:** the legacy announcements.do HTML listing is the source of truth (full calendar
year per request, correct idsIds, price-sensitive marker, Sydney-local times). The JSON
endpoint is demoted to forward-polling metadata only. Client rewritten accordingly:
bs4-parsed listing with verbatim-capture fixtures, AEST/AEDT→UTC conversion pinned by
tests on both sides of the daylight-saving boundary.

**First real ingestion (26 filings).** `python -m asx_engine.ingestion.manual` with
dry-run curation + `--exclude` hand-picking. 10 tickers (BHP CBA NAB ANZ WBC CSL WES TLS
WOW RIO), Feb–May 2026 results season: statutory 4Ds, media releases, investor decks.
26 PDFs → GCS (hash-addressed), 26 metadata rows → BQ, ~4.5 min at polite pacing, zero
errors. Spot-checked BHP/ANZ/WES PDFs against stored metadata: contents match headlines;
WES's first page shows Revenue/NPAT/EPS in clean native text — extraction targets
confirmed reachable. Lesson: exclusions free limit slots that refill with the next
candidate (by design) — re-run dry-run after excluding to see the final list; one RIO
production report slipped in this way (harmless: label-set curation happens later).

**Next:** parsing — PDF → text + parse-quality flags across the 26, find out how bad
the tables really are.
