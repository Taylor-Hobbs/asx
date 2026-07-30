# Architecture

> Living document. Last reconciled against the code 2026-07-30.

## Pipeline overview

```
ASX announcement endpoints (undocumented JSON)
        │  polite poller: rate-limited, cached, idempotent
        ▼
Cloud Storage (raw PDFs, PRIVATE — never redistributed)
        +
BigQuery: announcement metadata (ticker, release ts, sensitivity, doc URL, content hash)
        │
        ▼
Parsing: PDF → text (native first, OCR fallback) + parse-quality flags
        │
        ▼
Extraction: versioned prompt + Anthropic API → typed JSON (Pydantic), with
confidence + source span per field
        │
        ▼
BigQuery: extractions, eval runs   ──►   Eval harness vs golden dataset
```

## Components

| Module | Responsibility | Status |
|---|---|---|
| `asx_engine.config` | Typed env-driven settings | ✅ built |
| `asx_engine.schemas` | Announcement metadata, extraction models, golden labels, eval records | ✅ built |
| `asx_engine.ingestion` | Rate-limited, fail-loud ASX client + idempotent backfill/crawl jobs (GCS/BQ writers, batched with backoff) | ✅ built |
| `asx_engine.parsing` | PDF → text (pdfplumber), quality flags, `--skip` for killer PDFs | ✅ built |
| `asx_engine.extraction` | Versioned prompts → typed outputs; earnings, director-trades, and roles jobs; Batch API + sync paths | ✅ built |
| `asx_engine.eval` | Golden-set harnesses (per-field for earnings; list-alignment for trades), runs persisted to BQ `eval_runs` | ✅ built |
| `asx_engine.events` | Point-in-time event store (announcement-anchored, content-hash deduped) | ✅ built |
| `asx_engine.prices` | Daily price loader (yfinance → BQ), ASX 300 + full-market tables | ✅ built |
| `asx_engine.events.event_study` | Market model + BMP + Corrado rank, synthetic-truth tested | ✅ built |
| `asx_engine.trading` | Paper-trading signals, ledger, IBKR wrapper (paper only, live-port guards) | ✅ built |
| `scripts/viz/` | Terminal benchmark/cost tables rendered from `eval_runs` and job logs | ✅ built |
| Guidance vertical | Schema + prompt + goldens staged; eval harness pending | 🔶 in flight |

## Key invariants

- **Announcements are immutable** once stored, keyed by content hash. Amended filings are
  new records; originals are never overwritten (revision-leakage hygiene for the Q2 audit).
- **`ingested_at` and `announced_at` are always separate columns.** Point-in-time
  correctness starts at row one.
- **Raw filings never leave the private bucket.** The public golden dataset references
  filings by ticker + date + announcement ID; labels are public, documents are not.
- **Prompts are versioned files in `prompts/`,** never inline strings. An eval run records
  (model, prompt version, dataset version, timestamp) and is reproducible from those.
