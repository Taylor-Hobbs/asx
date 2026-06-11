# ASX Announcement Intelligence Engine — Project Context

> Drop this file in the repo root as CLAUDE.md so Claude Code sessions inherit full context.

## What this project is

A Python research pipeline over ASX company announcements: ingestion → PDF parsing → LLM structured extraction → point-in-time event store → backtested event studies. Built as a 12-month skills project (June 2026 – June 2027) to demonstrate production-grade LLM engineering: evaluation harnesses, regression tracking, leakage-free backtesting, and (later) fine-tuning a small open model against a frontier baseline.

**This is a research and engineering project, NOT a trading system and NOT a product.**
- It never places trades, never connects to a brokerage, and outputs never constitute financial advice.
- Commercial ASX summarizers exist (Ask Anna, Stockify). This project's differentiation is the public rigor they don't show: published extraction accuracy, golden datasets, regression tracking, point-in-time backtests, leakage audits.
- The deliverables are: the repo, the eval methodology doc, the leakage audit, benchmark numbers, and public write-ups.

## Owner context (one paragraph)

Taylor, 22, Deloitte analyst in Melbourne, building toward FDE/SE roles (Databricks/Anthropic/Salesforce-tier) in 18–24 months. Strong product velocity (React/Node/Postgres history across several startups); deliberately closing gaps in Python, data engineering at scale, and LLM evaluation. This project IS the gap-closing. Bias every decision toward learning depth and production discipline over shipping speed. Explain non-obvious Python/data-engineering idioms when introducing them — the owner is experienced but Python is a newer stack for him.

## The four-quarter ladder (scope discipline is critical)

- **Q1 (Jun–Aug 2026) — CURRENT:** ingestion + parsing + extraction for 2–3 announcement types + eval harness v1 + golden dataset (100+ hand-labeled filings)
- **Q2 (Sep–Nov 2026):** point-in-time event store, price data join, leakage audit, first event studies
- **Q3 (Dec 2026–Feb 2027):** fine-tune small open model (7–8B, HuggingFace) on extraction; benchmark vs frontier; cost analysis
- **Q4 (Mar–May 2027):** significance testing (multiple-hypothesis correction), batch inference cost optimization, 12-month retro

**Do not build ahead of the current rung.** If asked to add features from a later quarter, flag it and suggest deferring. Scope creep disguised as ambition is the owner's known failure mode — push back on it.

## Q1 scope (what we are building right now)

First vertical slice: ~20 hand-picked earnings announcements → one extraction prompt → one accuracy number. Then widen.

1. **Ingestion:** scheduled job polls ASX announcements (scoped to ASX 300, price-sensitive flag only ≈ 10–15k filings/yr at full scale). Raw PDFs → Cloud Storage. Metadata (ticker, timestamp, type, sensitivity flag) → BigQuery. Poll politely: rate-limited, cache everything, never re-fetch.
2. **Parsing:** PDF → text. Native-text extraction first, OCR fallback for scanned filings. Expect tables to be painful; that's part of the point.
3. **Extraction:** per announcement type, versioned prompt → typed JSON (Pydantic schemas). Start with: earnings results (revenue, NPAT, EPS, dividend, vs prior period) and guidance statements (upgrade/downgrade/affirmed, ranges). Each extraction carries confidence + source span for auditability.
4. **Eval harness v1:** golden dataset of hand-labeled filings; per-field accuracy per prompt/model version; results logged to BigQuery; no prompt version ships without beating or matching the incumbent on the golden set.

## Stack decisions (made — don't relitigate)

- Python end-to-end. pandas/polars for data. Pydantic for schemas. pytest for tests.
- GCP: Cloud Run jobs (ingestion/extraction), Cloud Storage (raw PDFs), BigQuery (metadata, extractions, eval runs, later prices/events).
- Anthropic API for extraction (frontier baseline); HuggingFace ecosystem arrives in Q3.
- GitHub Actions for CI. Structured logging from day one.
- EOD price data: cheap provider (EODHD-tier) — Q2 concern, don't build now.
- No web frontend. This is a pipeline. If a surface is ever needed, FastAPI — but default to "no."

## Engineering standards (non-negotiable)

- Tests on all parsing and extraction-schema logic. CI must be green.
- Prompts are versioned artifacts in the repo, never inline strings.
- Every eval run is logged and reproducible (model, prompt version, dataset version, timestamp).
- Repo must survive a hiring manager's 30-minute inspection: clear README, architecture doc, eval methodology doc.
- Public repo from day one — write code and commit messages accordingly. No secrets, no user data; golden datasets built from public filings only.

## Working style for Claude Code sessions

- Prefer teaching-quality implementations over clever ones; this project exists to build the owner's depth.
- When a design decision arises, present the tradeoff briefly and recommend — don't silently pick.
- Keep a BUILD_LOG.md: append a short entry each session (what was built, what broke, what the evals showed). This feeds the owner's weekly public build-log posts — it's load-bearing, not bureaucracy.
- Flag anything that smells like lookahead bias, survivorship bias, or data leakage immediately, even in Q1 code — the Q2 leakage audit starts with good Q1 hygiene.
- If the owner proposes connecting anything to live trading or signals-as-advice: refuse and cite the no-trading rule above.

## Strategic context (why each piece matters — for prioritization calls)

- Eval harness rigor > feature count. The word "evaluation" is the differentiator in every target job spec.
- The leakage audit (Q2) and the fine-tune benchmark (Q3) are the two highest-value artifacts of the year.
- Honest null results get published. Rigor is the product; signal is a bonus.
- One vertical slice working end-to-end always beats three layers half-built.
