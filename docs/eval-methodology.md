# Evaluation Methodology

> v0 stub — fills in as eval harness v1 lands (Q1). This document is a primary
> deliverable of the project: it should eventually let a reader reproduce every
> reported accuracy number.

## Principles

1. **Golden dataset:** 100+ hand-labeled filings (Q1 target). Labels are public;
   filings are referenced by ticker + date + announcement ID, never republished.
2. **Per-field accuracy** per prompt version per model — not a single blended score.
   A prompt that nails revenue but hallucinates dividends should look exactly that way.
3. **Reproducibility:** every eval run logs (model, prompt version, dataset version,
   timestamp) to BigQuery. No number is reported that can't be regenerated.
4. **Regression gate:** no prompt version ships without matching or beating the
   incumbent on the golden set.
5. **Honest nulls:** results get published whatever they show.

## Open questions (to resolve while building harness v1)

- Field-level match semantics: exact match for enums/dates; numeric tolerance for
  currency fields (reported in $M vs $K)? How are missing-vs-null distinguished?
- Confidence calibration: do extraction confidence scores predict actual accuracy?
- Label provenance: single-labeler for v1; double-labeling a sample to estimate
  label error rate?
