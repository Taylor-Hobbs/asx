# ASX Announcement Intelligence Engine

A Python research pipeline over ASX company announcements:
**ingestion → PDF parsing → LLM structured extraction → point-in-time event store → backtested event studies.**

Built as a 12-month skills project (June 2026 – June 2027) to demonstrate production-grade
LLM engineering: evaluation harnesses, regression tracking, leakage-free backtesting, and
(later) fine-tuning a small open model against a frontier baseline.

> **This is a research and engineering project — NOT a trading system and NOT a product.**
> It never places trades, never connects to a brokerage, and its outputs never constitute
> financial advice.

## Why this exists

Commercial ASX summarizers already exist. This project's differentiation is the public rigor
they don't show: published extraction accuracy, golden datasets, regression tracking,
point-in-time backtests, and leakage audits. The deliverables are the repo, the eval
methodology doc, the leakage audit, benchmark numbers, and public write-ups.

## Roadmap

| Quarter | Window | Focus |
|---------|--------|-------|
| **Q1** *(current)* | Jun–Aug 2026 | Ingestion + parsing + extraction for 2–3 announcement types, eval harness v1, golden dataset (100+ hand-labeled filings) |
| **Q2** | Sep–Nov 2026 | Point-in-time event store, price-data join, leakage audit, first event studies |
| **Q3** | Dec 2026–Feb 2027 | Fine-tune a small open model on extraction; benchmark vs frontier; cost analysis |
| **Q4** | Mar–May 2027 | Significance testing, batch-inference cost optimization, 12-month retro |

## Stack

- **Language:** Python end-to-end (pandas/polars, Pydantic schemas, pytest)
- **Cloud:** GCP — Cloud Run jobs, Cloud Storage (raw PDFs), BigQuery (metadata, extractions, eval runs)
- **LLM:** Anthropic API for extraction (frontier baseline); HuggingFace ecosystem arrives in Q3
- **CI:** GitHub Actions, structured logging from day one
- **Frontend:** none — this is a pipeline

## Project context

See [`CLAUDE.md`](./CLAUDE.md) for the full project context, scope discipline, and engineering
standards that govern this repo.
