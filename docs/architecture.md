# Architecture

> Living document. Updated as components land; sections marked *(planned)* describe
> the agreed design, not built code.

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
| `asx_engine.schemas` | Announcement metadata + extraction models | *(planned — next)* |
| `asx_engine.ingestion` | Poller, rate limiter, GCS/BQ writers | *(planned)* |
| `asx_engine.parsing` | PDF → text, quality flags | *(planned)* |
| `asx_engine.extraction` | Prompt loading, Anthropic client, typed outputs | *(planned)* |
| `evals/` | Golden-set accuracy runs, logged to BQ | *(planned)* |

## Key invariants

- **Announcements are immutable** once stored, keyed by content hash. Amended filings are
  new records; originals are never overwritten (revision-leakage hygiene for the Q2 audit).
- **`ingested_at` and `announced_at` are always separate columns.** Point-in-time
  correctness starts at row one.
- **Raw filings never leave the private bucket.** The public golden dataset references
  filings by ticker + date + announcement ID; labels are public, documents are not.
- **Prompts are versioned files in `prompts/`,** never inline strings. An eval run records
  (model, prompt version, dataset version, timestamp) and is reproducible from those.
