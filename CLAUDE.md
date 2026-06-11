# ASX Announcement Intelligence Engine — Project Context (v2)

> Drop this file in the repo root as CLAUDE.md so Claude Code sessions inherit full context.

## What this project is

A Python research pipeline over ASX company announcements: ingestion → PDF parsing → LLM structured extraction → point-in-time event store → backtested event studies → fine-tuned model benchmark. Built as a 12-month skills project (June 2026 – June 2027) to demonstrate production-grade LLM engineering: evaluation harnesses, regression tracking, leakage-free backtesting, and fine-tuning a small open model against a frontier baseline.

**This is a research and engineering project, NOT a trading system and NOT a product.**
- It never places trades, never connects to a brokerage, and outputs never constitute financial advice. If the owner proposes either: refuse and cite this rule.
- Commercial ASX summarizers exist (Ask Anna, Stockify). This project's differentiation is the public rigor they don't show: published extraction accuracy, golden datasets, regression tracking, point-in-time backtests, leakage audits, honest null results.
- Deliverables: the repo, the eval methodology doc, the leakage audit, benchmark numbers, public write-ups.

## Owner context

Taylor, 22, Deloitte analyst in Melbourne, building toward FDE/SE roles (Databricks/Anthropic/Salesforce-tier) in 18–24 months. Strong product velocity (React/Node/Postgres history); deliberately closing gaps in Python, data engineering at scale, and LLM evaluation. This project IS the gap-closing. Bias decisions toward learning depth and production discipline over shipping speed. Explain non-obvious Python/data-engineering idioms when introducing them.

## Data sources (decided — and the rules around them)

### Announcements
- **Primary: ASX.com.au undocumented JSON endpoints** (the same APIs the website uses; see pyasx on GitHub as a *reference implementation to read, not a dependency to install* — write our own thin client). Per-ticker announcements endpoint returns metadata: headline, release timestamp, price-sensitive flag, document type, PDF link.
- **Universe:** ASX 300 constituents, filtered to price-sensitive announcements (≈10–15k filings/yr at full scale). Backfill last 12–24 months per ticker; collect forward from there. Deep historical backfill is explicitly out of scope unless a commercial source (WebLink, Twelve Data) is added later.
- **Etiquette (non-negotiable engineering discipline):** rate-limit to ~1 request per few seconds, set a descriptive User-Agent, cache every response, NEVER re-fetch a PDF already stored, exponential backoff on errors. The undocumented API can change without notice — the client must fail loudly and the ingestion job must be idempotent and resumable.
- **Redistribution rule (legal):** ASX announcements are public disclosures and reading them is fine; ASX site terms restrict redistribution. Therefore: raw PDFs live ONLY in the private Cloud Storage bucket — never committed to the repo, never re-hosted, never in public datasets. The public golden dataset references filings by ticker + date + announcement ID + our labels, so others can reconstruct it without us republishing documents. Code, schemas, metrics, labels = public. Raw corpus = private. Enforce this in .gitignore and code review.

### Prices (Q2 onward)
- Prototyping: yfinance with `.AX` suffixes (free, scrappy, fine for curiosity only).
- Real backtests: paid EOD source, decision deferred to Q2 start. Candidates: EODHD (~$30/mo, broad coverage), iTick (free tier exists). 
- **Known trap to design around: survivorship bias.** Cheap EOD APIs typically cover currently-listed companies only. The Q2 leakage audit MUST address delisted-stock handling; the likely fix is a delisting-aware dataset (Norgate Data is the Australian standard, ~$50/mo tier). Until then, every backtest result carries an explicit survivorship caveat. Corporate-action adjustment (splits, consolidations) must also be verified, not assumed.

## The four-quarter ladder (scope discipline is critical)

**Do not build ahead of the current rung.** If asked to add features from a later quarter, flag it and suggest deferring. Scope creep disguised as ambition is the owner's known failure mode — push back on it. Difficulty comes from depth and rigor, never from more features.

### Q1 (Jun–Aug 2026) — CURRENT: Ingestion, extraction, eval harness v1
First milestone is a vertical slice: ~20 hand-picked earnings announcements → one extraction prompt → one accuracy number. Then widen.

1. **Ingestion:** scheduled Cloud Run job polls per-ticker announcement endpoints for the ASX 300 universe. Raw PDFs → Cloud Storage (private). Metadata (ticker, release timestamp, type, sensitivity flag, doc URL, content hash) → BigQuery.
2. **Parsing:** PDF → text. Native-text extraction first, OCR fallback for scanned filings. Tables will be painful; that's part of the point. Store parsed text + parse-quality flags alongside raw.
3. **Extraction:** per announcement type, versioned prompt → typed JSON (Pydantic schemas). Launch types: earnings results (revenue, NPAT, EPS, dividend, vs prior period) and guidance statements (upgrade/downgrade/affirmed, ranges, basis). Every extraction carries confidence + source span for auditability.
4. **Eval harness v1:** golden dataset of 100+ hand-labeled filings (labels public, per redistribution rule); per-field accuracy per prompt/model version; results logged to BigQuery; no prompt version ships without matching or beating the incumbent on the golden set.

**Q1 done means:** pipeline runs end-to-end unattended for the universe; two announcement types extracting; golden set ≥100; eval methodology doc v1 in repo; CI green.

### Q2 (Sep–Nov 2026): Point-in-time event store + first event studies
1. **Price layer:** chosen EOD provider integrated; prices + corporate actions in BigQuery; adjustment logic tested.
2. **Point-in-time event store:** every extracted event keyed to exact announcement release timestamp. Forward returns (t+1d, t+5d, t+20d) computed strictly from post-announcement data. Abnormal returns vs market (and sector where feasible).
3. **The leakage audit (flagship artifact):** a written document covering — lookahead bias (no price known before it printed), survivorship bias (delisted handling), revision leakage (amended filings must not contaminate originals; announcements are immutable records keyed by content hash), and timestamp integrity (release time vs trading hours; events after close map to next session).
4. **First event studies:** do guidance downgrades drift after day 1? Do large director buys predict 20-day returns? Is there post-earnings drift in our sample? Publish results whatever they are — a rigorous null beats a suspicious positive.
5. Expand extraction types: capital raises (amount, price, discount to last close), director trades (Appendix 3Y).

**Q2 done means:** event store live, leakage audit published, ≥2 event studies written up, four announcement types extracting.

### Q3 (Dec 2026–Feb 2027): Fine-tuning track
1. **Corpus:** assemble labeled training set from golden data + human-verified pipeline outputs. Train/validation/test splits by TIME, not random — no temporal leakage into evaluation.
2. **Fine-tune** a small open model (7–8B class, HuggingFace ecosystem; LoRA/QLoRA acceptable) on the extraction task.
3. **Benchmark honestly** vs the frontier-model baseline on held-out filings: per-field accuracy, failure analysis by announcement type and document quality.
4. **Cost analysis:** $/1,000 filings, fine-tuned (inference hosting) vs frontier API — the exact analysis FDEs run for clients.
5. Publish win or lose.

**Q3 done means:** benchmark published with methodology; cost model in repo; fine-tuning code reproducible.

### Q4 (Mar–May 2027): Scale, statistics, retro
1. **Statistics done properly:** significance testing on event-study results with multiple-hypothesis correction (e.g. Benjamini–Hochberg). If it doesn't survive correction, it isn't reported as a finding.
2. **Batch inference optimization:** prompt caching, batching, model routing (small model for easy filings, frontier for hard ones based on parse-quality flags); measured cost reduction.
3. **Hardening:** pipeline runs end-to-end unattended; alerting on ingestion gaps; documentation pass.
4. **The 12-month retro:** what the evals taught, what the market graded, what we'd rebuild — the capstone artifact of the year.

**Q4 done means:** 12 months of commit history, retro published, repo survives a hiring manager's 30-minute inspection.

## Stack decisions (made — don't relitigate)

- Python end-to-end. pandas/polars for data. Pydantic for schemas. pytest for tests.
- GCP: Cloud Run jobs (ingestion/extraction), Cloud Storage (raw PDFs, private), BigQuery (metadata, extractions, eval runs, prices, events).
- Anthropic API for extraction (frontier baseline); HuggingFace ecosystem arrives in Q3.
- GitHub Actions for CI. Structured logging from day one.
- No web frontend. This is a pipeline. If a surface is ever truly needed, FastAPI — but default to "no."

## Engineering standards (non-negotiable)

- Tests on all parsing, schema, and (Q2+) return-computation logic. CI must be green.
- Prompts are versioned artifacts in the repo, never inline strings.
- Every eval run is logged and reproducible (model, prompt version, dataset version, timestamp).
- Ingestion is idempotent and resumable; announcements are immutable once stored (content-hash keyed).
- Repo must survive a hiring manager's 30-minute inspection: clear README, architecture doc, eval methodology doc, leakage audit (Q2+).
- Public repo from day one — write code and commit messages accordingly. No secrets, no raw PDFs, no redistributed ASX content (see redistribution rule).

## Working style for Claude Code sessions

- Prefer teaching-quality implementations over clever ones; this project exists to build the owner's depth.
- When a design decision arises, present the tradeoff briefly and recommend — don't silently pick.
- Maintain BUILD_LOG.md: append a short entry each session (what was built, what broke, what the evals showed). This feeds the owner's weekly public posts — load-bearing, not bureaucracy.
- Flag anything that smells like lookahead bias, survivorship bias, revision leakage, or temporal leakage immediately, in any quarter.
- Flag any commit that would include raw filing content or violate the redistribution rule.
- If the owner proposes live trading, brokerage connections, or signal-as-advice content: refuse, cite the no-trading rule.

## Strategic context (for prioritization calls)

- Eval harness rigor > feature count. "Evaluation" is the differentiator in every target job spec.
- The two highest-value artifacts of the year: the Q2 leakage audit and the Q3 fine-tune benchmark.
- Honest null results get published. Rigor is the product; signal is a bonus.
- One vertical slice working end-to-end always beats three layers half-built.
