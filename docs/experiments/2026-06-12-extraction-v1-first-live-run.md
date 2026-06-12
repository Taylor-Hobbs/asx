# Extraction v1: first live run, measured cost, and the runner experiment

**Date:** 2026-06-12 · **Status:** Part 1–3 complete; Part 4 pre-registered, awaiting eval harness
**Corpus:** 26 earnings-season filings, 10 tickers (BHP CBA NAB ANZ WBC CSL WES TLS WOW RIO), Feb–May 2026
**Stack under test:** `prompts/earnings_v1.md` · `claude-opus-4-8` · adaptive thinking · structured outputs (`messages.parse()` / `output_config.format`)

This document is the source-of-record for the public write-up. Parts 1–3 are
results; Part 4 is a pre-registered experiment design — metrics and decision
rule fixed *before* the experiment runs, so the eventual result can't be
quietly reframed.

---

## 1. What ran

Two execution modes over the same idempotent pending-set
(`asx_engine/extraction/job.py`):

| Run | Mode | Docs | Wall time | Outcome |
|---|---|---|---|---|
| First live extraction | Sync (one blocking call/doc) | 3 | ~60s (~20s/doc) | 3/3 valid payloads |
| Remainder | Message Batches API | 23 | ~2.5 min submit→ended, ~4 min total | 23/23 valid payloads |

Every payload validated through the `EarningsResult` Pydantic schema —
per-field value + confidence + verbatim source quote + page number. Zero
schema-validation failures across 26 documents.

**Value-accuracy signals (pre-golden-labels, so directional only):**

- **Cross-document consistency.** Several filing events appear as 2–3
  documents (media release, statutory 4D, investor deck). Independent
  extractions agreed across documents for WES ($24,212m / $1,603m /
  141.4c / 102c), NAB ($2,750m), WBC ($3,650m), WOW ($374m on a 27-week
  period the model labeled correctly).
- **Calibrated-looking confidence.** 0.99 on clean table layouts (WES),
  0.92–0.97 on dense bank statutory pages (CBA) — lower exactly where the
  documents are genuinely harder.
- **USD reporters handled as designed.** RIO and CSL (the latter a
  surprise — labeling watch-out) returned `value: null` for non-AUD
  figures rather than converting, and quoted the USD figures as evidence
  for the null. BHP likewise.

---

## 2. Quote audit (the audit-trail experiment)

**Method:** every `source_quote` checked as a substring of the stored parsed
text (`scripts/verify_quotes.py`); page attribution checked separately.

**Finding 1 — byte-exact matching measures the parser, not the model.** On
the first 3 docs, strict matching flagged 6/27 quotes; diagnosis showed
**zero fabrications** — 5 quotes spanned a line break (model joins a table's
label line and value line with a space; a faithful quote the parser's line
breaks can't byte-match) and 1 had a wrong page number. Whitespace-normalized
matching is the correct metric and is what the script now does.

**Finding 2 — full-corpus taxonomy.** 176 quotes, 35 normalized-match
failures (~20%), all *soft* (the extracted values can still be correct;
the audit trail is what degrades):

| Class | Count | Example | Disposition |
|---|---|---|---|
| Stitched/annotated quotes | ~26 | `'Reported NPAT ... 401 ... US$m'`; appended `'(US$m)'` | Prompt v2 candidate: "one contiguous span, no ellipses, no annotations" |
| Wrong page number | 8 | right quote, said p7, lives on p1 | Prompt v2 candidate + cheap post-hoc fix (search quote, correct page) |
| Computed value (rule violation) | 1 | NAB prior revenue = NII + other operating income, arithmetic admitted in pseudo-quote | Real failure; bank-revenue convention must be pinned |

**Finding 3 — cross-document disagreements for the goldens to arbitrate:**
CBA NPAT extracted as **5,367** from the profit announcement but **5,412**
(labeled "Statutory NPAT" in the investor deck) elsewhere; ANZ **3,414** vs
**3,400**. Same filing event, different documents, different numbers —
statutory vs cash vs rounding conventions. Whatever the labels decide
becomes the convention; the harness then scores both extractions against it.

**Open labeling conventions** (decided at labeling time, recorded in the
golden set, candidates for `earnings_v2`):

1. EPS basis: continuing operations vs including discontinued (CBA reports both).
2. Bank "revenue": total net operating income, or null for financials.
3. The CBA/ANZ statutory-vs-cash calls above.

Per `prompts/README.md`, **no `earnings_v2` ships unless the harness shows
it beats v1 on the golden set.**

---

## 3. Measured economics

Token usage now logged per document (no more inferring from the bill):

| | Sync run (3 docs) | Batch run (23 docs) |
|---|---|---|
| Input tokens | (not captured — predates usage logging) | 1,144,717 (range 6,423–129,142/doc) |
| Output tokens | — | 27,847 |
| Price basis | $5/$25 per Mtok | $2.50/$12.50 per Mtok (Batches = 50% off) |
| Cost | ~$1.20 (billed) | **$3.21** ($2.86 input + $0.35 output) |
| Per document | ~$0.40 | **~$0.14** |

Observations: input is ~98% of tokens and ~90% of dollars — document length,
not output, drives cost. Document size varies 20× within one corpus.

**Projection to full scale** (ASX 300, ~600 reporting events/yr ≈ 1,500–2,000
earnings documents):

| Scenario | $/yr |
|---|---|
| Naive worst case (Opus, sync, *all* 10–15k price-sensitive filings) | ~$5,000 — the scary number; extraction never does this |
| Batched Opus, earnings docs only (today's setup) | **~$280** |
| + model routing, Q4 scope (Sonnet/Haiku for easy docs, harness-gated) | plausibly <$150 |
| + Agent SDK runner on Max-plan credit (Part 4, if accuracy holds) | **$0 marginal** |

The dominant *actual* cost this quarter is eval iteration, not production:
each prompt-version test against a 100-filing golden set ≈ $14 batched;
ten iterations ≈ $140. That spend is the project.

---

## 4. Pre-registered: API runner vs Agent SDK runner

**Background (verified 2026-06-12).** Subscription OAuth tokens may not
authenticate direct API calls (Consumer ToS, clarified Feb 2026). From
**2026-06-15**, headless Claude Code / Agent SDK usage bills to a separate
monthly credit included in paid plans (Pro $20, Max 5x $100, Max 20x $200),
at standard API rates, no rollover. A Max 5x plan therefore includes
~$1,200/yr of agent compute that currently expires unused — several times
this project's entire extraction budget.

**Question.** Does routing the identical extraction task through the Agent
SDK harness (the only surface the plan credit can pay for) change extraction
quality relative to the direct Messages API?

**Hypothesis.** No material accuracy change; quote-audit pass rate may
*drop* (no server-side structured-output enforcement; harness scaffolding
around the model).

**Method.**
- Two runners, identical inputs: same parsed text, same
  `prompts/earnings_v1.md` (or whatever version is then incumbent), same
  `claude-opus-4-8`.
  - **Runner A (incumbent):** direct API, `output_config` structured
    outputs, Batches.
  - **Runner B:** Agent SDK / `claude -p`, system prompt = the versioned
    prompt, all tools disabled, JSON requested and validated client-side
    through `EarningsResult`, one retry on validation failure.
- Provenance: `ExtractionRecord` gains a `runner` dimension (e.g. `api` vs
  `agent_sdk_<cli_version>`); records keyed `(model, prompt_version, runner)`.
- Full golden-labeled corpus through both runners.

**Metrics (decided now):**
1. Per-field value accuracy vs golden labels — the primary metric.
2. Quote-audit pass rate, by taxonomy class from §2.
3. Schema-validation failure / retry rate (Runner B's structured-output gap).
4. Wall-clock per document and measured cost per document (Runner B's
   credit draw verified against the plan dashboard, not assumed).

**Decision rule (pre-registered).** With n≈25 golden filings, treat the
runners as equivalent if Runner B's per-field accuracy is within **one
document-level error per field** of Runner A. If equivalent → production
extraction moves to the plan credit (Runner A retained as fallback and as
the eval-harness reference). If worse → result published anyway; production
stays on the API key. Either outcome is a write-up.

**Prerequisites, in order:** golden labels (step 8) → eval harness v1
(step 9) → a ~$1 probe run through `claude -p` after 2026-06-15 to confirm
the credit-billing mechanics behave as documented → this experiment.

**Threats to validity, noted now:** small n (one document-level error moves
a field ~4 points); Claude Code harness updates between runs (pin and record
CLI version); possible model-behavior differences between batch and
interactive serving paths (run Runner A both batched and sync on a 5-doc
subsample if results look odd); credit-billing mechanics are 3 days old at
pre-registration time.

---

## Reproducibility

- Extractions: BQ `asx_engine.extraction_records`, keyed
  `(content_hash, model, prompt_version)`; payloads re-validate through
  `asx_engine.schemas.EarningsResult`.
- Quote audit: `uv run python scripts/verify_quotes.py`
- Payload inspection: `uv run python scripts/eyeball_extractions.py`
- Batch in question: `msgbatch_01P1SBRH3wyxg6WnivoaxT14` (API retains
  results 29 days from 2026-06-12).
- Session narrative: `BUILD_LOG.md` entries of 2026-06-11/12.
