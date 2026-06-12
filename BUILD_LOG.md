# Build Log

Short entry per session: what was built, what broke, what the evals showed.
Feeds the weekly public build-log posts. Newest entries first.

---

## 2026-06-12 — Extraction v1 built (live run still gated on the API key)

**Built (step 7, everything except the live call):**
- `prompts/earnings_v1.md` — first versioned prompt. It pins the two conventions
  the golden labels MUST share, or accuracy numbers will measure label
  disagreement instead of model quality:
  1. **Statutory beats underlying** (and group beats segment) when both appear.
  2. **AUD only, never convert** — USD reporters (BHP, RIO) get `value: null`
     for non-AUD figures. Honest gap for v1; revisit at schema level if it
     costs too much corpus.
  Plus unit normalization ($1,234.5m → 1234500000; EPS/DPS in cents), losses
  as negatives, no derived figures (null beats computing EPS from NPAT), and
  per-field verbatim quote + `[page N]` + calibrated confidence.
- `extraction/earnings.py` — parsed text → Claude (claude-opus-4-8, adaptive
  thinking) → validated `EarningsResult` via the SDK's `messages.parse()`:
  the Pydantic schema is the structured-output constraint AND the validator;
  constraints the API can't enforce (confidence 0–1 bounds) are checked
  client-side by the SDK. prompt_version = prompt file stem.
- `extraction/job.py` — idempotent like parsing: pending = good-quality parses
  minus extraction_records rows for the current (model, prompt_version);
  `--limit N` for eyeball-first runs (extraction costs real tokens). Records
  land in BQ only — payload is a JSON string column; no GCS artifact needed
  at ~2KB/record.
- `infra/bq/extraction_records.schema.json` + live table created. Backend
  smoke-tested against real GCS/BQ: 26 good parses pending, 0 extracted,
  text loads with page markers intact.
- `.env.example` documenting required env vars. Gotcha found: pydantic-settings
  reads `.env` privately — the anthropic client reads the PROCESS environment,
  so the job calls `load_dotenv()` explicitly (python-dotenv now a declared dep).
- 79 tests (extractor wiring faked at the client boundary, job against a
  structural FakeBackend), mypy --strict clean, CI green.

**First live extractions (key landed same day).** `--limit 3` →
CBA profit announcement + both WES half-year docs, ~60s, ~20s/filing.
Results strong: every numeric value correct against the parsed text, the two
WES documents (media release vs statutory 4D) agree with each other on all
four metrics — a free cross-document consistency check — and confidence
looks calibrated (0.99 on WES's clean tables, 0.92–0.97 on CBA's denser
statutory pages).

**Audit-trail verification (now `scripts/verify_quotes.py`) found the real
lesson:** strict byte-matching flagged 6/27 quotes "missing", but diagnosis
showed ZERO hallucinations — 5 were quotes spanning a line break (model joins
"label:\nvalue row" with a space; a faithful quote the parser's line breaks
can't byte-match) and 1 was a wrong page number (right quote, page 1 not 7).
Whitespace-normalized matching: 26/27 pass. The eval harness must compare
quotes whitespace-normalized or it will measure the parser, not the model.

**Two conventions the first 3 filings surfaced that earnings_v1 does NOT pin
(golden labels must decide; candidates for v2):**
1. **EPS basis:** CBA reports basic EPS "from continuing operations" (323.7c)
   AND "including discontinued operations" (321.0c). Model chose including-
   discontinued. Pick one and label consistently.
2. **Bank "revenue":** banks report no conventional revenue line; the model
   chose "total net operating income before operating expenses and
   impairment" ($15,000m) at conf 0.96. Decide what revenue means for
   financials — or whether it's null for banks.

**Batch mode built and the remaining 23 run through it (corpus now 26/26).**
Owner wants full scale and $5k/yr was out of scope — so the Batches API
(50% off, the natural shape for headless runs) got pulled forward. Same
idempotent pending-set; `--resume BATCH_ID` collects a crashed run without
resubmitting; per-document token usage now logged. The 23-doc batch went
submit → ended in ~2.5 minutes, 23/23 succeeded.

**Measured economics (no more bill archaeology):** 1,144,717 input +
27,847 output tokens for 23 docs = **$3.21 batched (~$0.14/doc avg)**;
input is ~98% of tokens and ~90% of dollars; doc sizes vary 6K–129K tokens. Whole 26-doc corpus:
~$4.40. Full-scale projection at ~2,000 earnings docs/yr: **~$280/yr on
batched Opus** — the scary $5k figure was Opus over all 10–15k filings,
which extraction never does. Decision: pipeline stays on the API key
(structured outputs + batches + clean provenance); the Max-plan Agent SDK
credit ($100/mo included, no rollover, June 15 policy) gets evaluated later
as a second runner — same prompt, same model, API vs agent harness, scored
by the eval harness once it exists. If accuracy holds, production moves to
the credit and marginal cost is $0.

**Full-corpus quote audit: 176 quotes, 35 failures (~20%) — all soft, and
they sort into a taxonomy the harness should count separately:**
1. **Stitched quotes** (most common): model joins non-contiguous fragments
   with "..." or appends annotations like "(US$m)" — informative but not
   verbatim. Prompt v2 candidate: "one contiguous span, no ellipses, no
   annotations".
2. **Wrong page numbers** (8): right quote, wrong `[page N]`.
3. **One real rule violation** (NAB): prior revenue COMPUTED as NII + other
   operating income, with the arithmetic admitted in the pseudo-quote —
   rule 5 says never derive. Bank "revenue" ambiguity again.
4. USD reporters (RIO, CSL!) correctly nulled values but quoted the USD
   figures as evidence — good auditability, fine.
5. **Cross-doc disagreement to resolve in goldens:** CBA NPAT extracted as
   5,367 from the profit announcement but 5,412 ("Statutory NPAT" per the
   investor deck) from two other docs; ANZ 3,414 vs 3,400. Same filing
   events, different documents, different numbers — statutory vs cash vs
   rounding. The golden labels arbitrate.

Per prompts/README.md discipline, no earnings_v2 until the harness can show
it beats v1 on the golden set.

**Evals:** none yet — first accuracy number needs golden labels.

### ⏸ PARKED HERE (2026-06-12) — state of play for next session

All 26 extracted; extraction is no longer the critical path. In order:

1. Owner: golden labels (step 8) per `golden/README.md` — THE long pole.
   Conventions to decide while labeling: EPS basis (continuing vs incl.
   discontinued), bank "revenue" definition, and the CBA 5,367-vs-5,412 /
   ANZ 3,414-vs-3,400 cross-doc calls. Exclude the RIO Q4 production report.
2. Eval harness v1 (step 9): per-field accuracy vs goldens + the quote-audit
   taxonomy above as named metrics; results to a BQ eval_runs table.
3. Then earnings_v2 (contiguous-quote rule, page-number fix, bank-revenue
   convention) — shipped only if it beats v1 on the golden set.
4. After the harness: the Agent SDK runner experiment (Max credit, $0
   marginal) — same prompt/model through `claude -p`, scored side by side.
   Design pre-registered (metrics + decision rule fixed before running) in
   `docs/experiments/2026-06-12-extraction-v1-first-live-run.md`, which is
   also the source-of-record for the public write-up of this session.

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

**Parsing built and run over all 26.** `parse_pdf` (pdfplumber, native text only) +
versioned `ParsedDocument` with computed quality flags (page_count, empty_page_count,
total_chars, quality good/partial/empty). Storage: full text →
GCS `parsed/{parser_version}/{content_hash}.json`, flags row → BQ `parsed_documents`.
Job is idempotent via set-difference against BQ — crash-safe, resumable, and bumping
PARSER_VERSION re-parses naturally. Tests build minimal-but-valid PDFs byte-by-byte
(correct xref offsets) so the real pdfplumber path is exercised without fixture files;
an "empty page" in tests is genuinely a page with no text operators.

**Parse results:** 26/26 `good`, zero empty pages across 1,630 pages / ~3.2M chars —
all born-digital, OCR correctly deferred. Tables linearize better than feared:
`Revenue 24,212 23,490 3.1` keeps label/current/prior/variance on one line. Stored
text is clean Unicode (console mojibake during inspection was display-only). The real
extraction risk is now ambiguity (statutory vs underlying rows, segment vs group
tables), not parse quality. 71 tests.

---

### State of play at end of 2026-06-11 (superseded by the entry above)

**Where we are:** Q1 vertical slice, steps 1–6 of 9 done in one day. The pipeline is
live end-to-end up to parsed text: ASX → private GCS bucket → BigQuery → parsed pages
with quality flags. 71 tests, mypy --strict, CI green, everything pushed.

**What exists and works:**
- 26 real earnings filings (10 tickers, Feb–May 2026 results season) in
  `gs://asx-scanner-499110-raw-pdfs/raw/{hash}.pdf` + `asx_engine.announcements`
- All 26 parsed `good` → `parsed/pdfplumber_v1/{hash}.json` + `asx_engine.parsed_documents`
- CLI entry points: `python -m asx_engine.ingestion.manual` (dry-run + --exclude
  curation) and `python -m asx_engine.parsing.job` (idempotent)

**Next step (7 — extraction v1), blocked on ONE thing:** owner's `ANTHROPIC_API_KEY`
in the local `.env` (console.anthropic.com → API Keys). Then, in order:
1. `prompts/earnings_v1.md` — versioned prompt with unit-normalization rules
   ($1,234.5m → 1234500000; EPS/DPS in cents; statutory vs underlying: capture as stated)
2. Extraction module: parsed text → Claude → validated `EarningsResult`
   (per-field confidence + source quotes) → `extraction_records` BQ table
3. Run a handful of the 26 live; eyeball before building the harness

**Also unblocked, owner's hands (step 8):** golden labels for the 26 — read each filing,
record true revenue/NPAT/EPS/DPS per `golden/README.md` format. The long pole to the
first accuracy number; parallelizes with step 7.

**Watch out for:**
- Extraction's real difficulty is ambiguity (statutory vs underlying, group vs segment
  tables), not parse quality — the prompt must pin which number wins and the golden
  labels must record the same convention, or accuracy numbers will measure label
  disagreement instead of model quality.
- Big statutory docs run ~100K+ tokens; fine for v1, batch/caching optimizations are
  Q4 scope — don't build them now.
- RIO Q4-production filing in the corpus is not an earnings doc — exclude from the
  earnings golden set at labeling time.
