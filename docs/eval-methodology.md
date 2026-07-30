# Evaluation Methodology

> v1 — harness landed. Scoring semantics below are implemented in
> `asx_engine.eval` and pinned by tests in `tests/test_eval_harness.py`. This
> document is a primary deliverable: it should let a reader reproduce every
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

## Scoring (harness v1)

One eval run scores a single `(model, prompt_version, dataset_version)` against
every `labeled` golden, joined to its extraction by `content_hash`. Each scored
field resolves to exactly one of four outcomes:

| outcome        | golden        | prediction    | meaning                                  |
| -------------- | ------------- | ------------- | ---------------------------------------- |
| `correct`      | value / null  | same / null   | values equal, **or** both assert absence |
| `wrong`        | value         | different value | reading error                          |
| `missed`       | value         | null          | false negative (recall gap)              |
| `hallucinated` | null          | value         | false positive — invented a figure       |

A correct `null` is a scored success, not a skipped field: the prompt requires
the model to assert "the document does not state this." Banks are the clearest
case — the locked convention labels bank "revenue" as `null` (no conventional
revenue line; deriving one is judgment, and null beats deriving), so a model
that correctly declines to invent a bank revenue figure scores `correct` there,
and one that conjures a number scores `hallucinated`. The four outcomes are kept
separate per field — a hallucinated dividend and a missed dividend are different
failures and a prompt revision needs to see which it is.

**Match semantics.** Values are normalized at extraction time (absolute amount
in the reporting currency, cents per share), so both sides are already in the
same units:

- **Numeric fields** (revenue, NPAT, EPS, dividend): exact `Decimal` value
  equality — no tolerance. `Decimal("141.4") == Decimal("141.40")` and
  `24212000000 == 2.4212E10`, so trailing zeros and exponent form don't matter,
  but a genuinely different quantity is `wrong`. A tolerance would hide reading
  errors rather than absorb formatting, and the $M-vs-$K problem is solved
  upstream by normalization, not here.
- **`reporting_currency`** (e.g. "AUD", "USD"): case-normalized string equality.
  Multi-currency reporters (BHP, RIO, CSL report in USD) make currency a value
  the model has to get right; scoring it as its own field means a figure read
  correctly under the *wrong* currency is caught here, not waved through because
  the number happened to match.
- **`period`** (free text): whitespace- and case-normalized string equality.
  Period has no canonical form ("1H FY2026" vs "Half-year ended 31 December
  2025"), so it is reported on its own line and expected to surface real
  disagreement rather than hide inside a blended average.

**Missing vs null.** Distinguished by construction: the golden schema and the
extraction schema both make `null` a *required, explicit* assertion of absence,
so "the model didn't emit this field" cannot occur — a payload that omits a
field fails Pydantic validation before it is ever scored.

**Coverage.** `n_skipped` counts labeled goldens with no extraction for the
scored `(model, prompt_version)`. The denominator is the goldens actually
scored; the skip count stays in the row and the console table so coverage gaps
never masquerade as accuracy.

**Reproducibility.** Each run appends one row to `eval_runs` (schema in
`infra/bq/eval_runs.schema.json`): the keys, `evaluated_at`, `n_documents`,
`n_skipped`, `overall_accuracy`, and a repeated `field_scores` record so any
field can be tracked across prompt versions in SQL.

## Open questions — status

- **Confidence calibration — ANSWERED (2026-07-14).** Do confidence scores
  predict accuracy? Yes, but the miscalibration is *structured*, not smooth:
  scores ≥ 0.95 are well-calibrated (95–97% accurate), while the 0.90–0.95
  bin is only ~21% accurate. Use confidence as a **binary review flag**
  (< 0.95 → human review), never as a probability. Cross-document
  disagreement turned out to be the stronger error detector: where sibling
  documents disagree on a value, it is ~7.7× more likely to be wrong, and
  ~87% of errors have the correct value present in a sibling document —
  consensus voting is near-free QA. Details: BUILD_LOG.md (Family-2 entries).
- **Label provenance — answered in practice, formal study still open.** The
  first director-trades eval run exposed that 30/36 `director_role` labels
  had been written from outside knowledge rather than document text — the
  harness audits the labels as much as the model (see eval-history.md, the
  v2 corrected-goldens row). Systematic double-labeling to estimate residual
  label error has not been done.
- **Period scoring — resolved via the prompt, not the scorer.** `earnings_v6`
  requires the long-form date and forbids short forms, lifting period from
  43.5% to 91.3% under unchanged exact-match scoring. One residual hyphen
  variant ("Half-year" vs "Half year") remains at v7.
