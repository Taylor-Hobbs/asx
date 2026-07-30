# ASX Announcement Research

[![CI](https://github.com/Taylor-Hobbs/asx/actions/workflows/ci.yml/badge.svg)](https://github.com/Taylor-Hobbs/asx/actions/workflows/ci.yml)

An end-to-end research study testing whether ASX company announcements contain
exploitable, tradeable signal — **paper-simulated only, no live capital, ever**:

**crawl → PDF parsing → benchmarked LLM extraction → point-in-time event store →
event studies → pre-registered forward tests (paper).**

The deliverable is the documented study itself, including honest negative results.
A rigorously-reached "no edge after costs" counts as success.

## Purpose

Commercial ASX announcement summarizers and director-trade trackers exist, but
none publish extraction accuracy against hand-labeled ground truth, and none
publish leakage-audited, costed event studies of the signals they imply. This
study exists to produce that missing evidence, in public:

1. **Can LLM extraction over raw filings be trusted?** Benchmarked per-field
   against golden datasets, with every prompt version and regression on the
   record.
2. **Does the extracted data predict returns?** Tested with point-in-time
   discipline, adversarial robustness checks, multiple-testing awareness, and
   pre-registered forward hypotheses — where negative and null results are
   reported with the same prominence as positive ones.

Everything needed to audit the answers — prompts, labels, methodology, and
every benchmark number — is in this repo.

## Results so far

### Extraction accuracy (per-field, hand-labeled golden sets)

| Vertical | Model | Prompt | Accuracy | Golden set |
|---|---|---|---|---|
| Director trades (Appendix 3Y) | claude-haiku-4-5 | v3 | **93.1%** | 28 filings / 36 trades |
| Company results (Appendix 4D/4E) | claude-haiku-4-5 | v7 | **87.8%** | 23 documents |
| Company results — frontier head-to-head | claude-opus-4-8 | v7 | **88.7%** | same 23 documents |

Seven measured prompt versions took the bulk model from 67.8% to 87.8%; the
frontier model ends 0.9pp ahead at ~20× the working cost. Full per-version,
per-field history (including the regressions): [docs/eval-history.md](docs/eval-history.md).
Every number is reproducible from a persisted `eval_runs` row —
methodology in [docs/eval-methodology.md](docs/eval-methodology.md).

### Research findings

- **[Do ASX director trades predict returns?](docs/findings-2026-07-director-trades.md)** —
  4,743 trades across 24 months / ~200 tickers. **Conclusion: no identifiable
  edge.** The apparent −7.1% signal after director sales decomposed under
  adversarial testing into three artifacts (window double-counting,
  alpha-extrapolation, reporting-season timing). The write-up shows the
  dismantling step by step.
- **Three clean nulls on the earnings corpus** (1,440 extracted reports):
  results news is priced same-day; no exploitable drift from dividend cuts or
  insider dip-buying ([analysis plan](docs/analysis-plan-2026-07-earnings.md)).
- **[Pre-registered hypotheses](docs/preregistrations.md)** — four frozen
  specifications with success/refutation criteria stated in advance, evaluated
  on post-registration filings only, results published either way (first
  verdicts due July 2027).

## What's in the repo

| Path | What it is |
|---|---|
| [`docs/`](docs/) | Eval history + methodology, findings reports, pre-registrations, architecture |
| [`prompts/`](prompts/) | Every prompt version as an immutable artifact (v1…v7 — the iteration story) |
| [`golden/`](golden/) | Hand-labeled golden datasets + labeling conventions (labels only — see redistribution rule) |
| [`src/asx_engine/`](src/asx_engine/) | Pipeline: ingestion, parsing, extraction, eval harness, event store, event studies, paper-trading |
| [`tests/`](tests/) | Unit tests for parsing, schemas, eval scoring, event-study math (synthetic-truth) |
| [`BUILD_LOG.md`](BUILD_LOG.md) | Session-by-session build log — highlights index at the top |

## Reproducibility & boundaries

- **You can't run the pipeline without your own GCP project** (BigQuery +
  private PDF bucket) and Anthropic API key — see [`.env.example`](.env.example).
  What you *can* inspect without running anything: the prompts, the golden
  labels, the eval methodology, every benchmark number, and the findings.
- **Raw ASX filings are never redistributed here.** Golden labels reference
  filings by ticker + date + announcement ID so the dataset can be
  reconstructed from public sources ([`golden/README.md`](golden/README.md)).
- **Paper trading only.** The forward tests run against an IBKR *paper*
  account. Nothing here is financial advice, and no live capital is ever
  involved.

## Stack

Python 3.12 (Pydantic, polars/pandas, numpy, pytest) · GCP (BigQuery, Cloud
Storage) · Anthropic API (Haiku for bulk extraction via the Batch API; Opus as
the benchmarked frontier baseline) · GitHub Actions CI.

## Status (July 2026)

Data collection and extraction are complete for two verticals (director
trades, company results); the in-sample research phase is closed with the
findings above; a guidance-extraction vertical and the forward paper-trading
phase are in flight. Day-to-day detail lives in [BUILD_LOG.md](BUILD_LOG.md).
