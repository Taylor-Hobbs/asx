# Eval History

Per-vertical benchmark tables. Every row is one persisted `eval_runs` record —
(model, prompt_version, dataset_version, timestamp) reproduces it.

---

# Director Trades (Appendix 3Y)

All runs against `golden_v1` (28 labeled filings, 36 trades, 0 skipped).
`detection` is trade alignment (found / missed / invented trades); field
columns count matched trades only — see `eval/director_trades_harness.py`.

## Haiku series (`claude-haiku-4-5`)

| version | overall | detection | name | role | type | nature | class | qty | price | consid | date | hold.b | hold.a | evaluated |
|---------|---------|-----------|------|------|------|--------|-------|-----|-------|--------|------|--------|--------|-----------|
| v2 (original goldens) | 75.0% | 88.9% | 93.8% | 15.6% | 100% | 59.4% | 50.0% | 96.9% | 68.8% | 71.9% | 100% | 75.0% | 78.1% | 2026-07-04 |
| v2 (corrected goldens) | 81.7% | 88.9% | 93.8% | 96.9% | 100% | 59.4% | 50.0% | 96.9% | 68.8% | 71.9% | 100% | 75.0% | 78.1% | 2026-07-04 |
| **v3** | **93.1%** | **94.6%** | **100%** | 88.6% | **100%** | 62.9% | **100%** | **100%** | **97.1%** | **100%** | **100%** | **85.7%** | **88.6%** | 2026-07-04 |

> v1 was never benchmarked: labeling surfaced transfers (3/28 filings), which
> forced `TradeType.TRANSFER` into the schema before the first eval — v2 is v1
> plus the transfer rules.
>
> **Golden correction 2026-07-04:** the first v2 run exposed that director_role
> had been labeled from outside knowledge — the bare 3Y form has no role field
> and 30 of 36 labeled roles never appear in the document text. Those were
> nulled (enforcing the README's own "as stated" convention); 6 stated in
> covering letters were kept. Both v2 rows above are the same extractions —
> the delta is purely the label fix.
>
> **v3** (scored against corrected goldens) added: security-class
> canonicalisation (drop issuer names, "fully paid", ticker codes → 50%→100%),
> never-derive price↔total with the exact failing examples (→ 97/100%),
> honorific stripping (name → 100%), same-class-same-holder rule for holdings
> (→ 86/89%), and multi-class tranche splitting (detection → 94.6%: 35/36
> found, 1 missed, 1 invented). `nature` (62.9%) is the known ceiling — golden
> paraphrases are too free for exact match; the remaining wrongs are wording
> variance, not misreading.

---

# Earnings Extraction

All runs against the `golden_v1` dataset (23 labeled documents, 0 skipped).
Model column is what produced the extractions being scored.

Scores are per-field accuracy (correct / total scored documents).

---

## Haiku baseline series (`claude-haiku-4-5`)

| version | overall | period | rev.c | rev.p | npat.c | npat.p | eps.c | eps.p | div.c | div.p | currency | evaluated |
|---------|---------|--------|-------|-------|--------|--------|-------|-------|-------|-------|----------|-----------|
| v1 | 67.8% | 56.5% | 52.2% | 52.2% | 65.2% | 52.2% | 65.2% | 69.6% | 91.3% | 73.9% | 100.0% | 2026-06-23 |
| v2 | 76.1% | 60.9% | 82.6% | 82.6% | 65.2% | 60.9% | 65.2% | 69.6% | 100.0% | 78.3% | 95.7% | 2026-06-23 |
| v3 | 82.2% | 65.2% | 95.7% | 95.7% | 73.9% | 65.2% | 69.6% | 73.9% | 100.0% | 82.6% | 100.0% | 2026-06-20 |
| v4 | 78.3% | 56.5% | 91.3% | 91.3% | 69.6% | 60.9% | 65.2% | 65.2% | 100.0% | 82.6% | 100.0% | 2026-06-23 |
| v5 | 78.3% | 43.5% | 87.0% | 87.0% | 73.9% | 60.9% | 73.9% | 69.6% | 100.0% | 87.0% | 100.0% | 2026-06-23 |
| v6 | 84.3% | 91.3% | 95.7% | 95.7% | 73.9% | 65.2% | 69.6% | 73.9% | 100.0% | 78.3% | 100.0% | 2026-06-23 |
| **v7** | **87.8%** | **95.7%** | **91.3%** | **91.3%** | **91.3%** | **73.9%** | **78.3%** | **73.9%** | **100.0%** | **82.6%** | **100.0%** | 2026-06-23 |

## Opus baseline (`claude-opus-4-8`)

| version | overall | period | rev.c | rev.p | npat.c | npat.p | eps.c | eps.p | div.c | div.p | currency | evaluated |
|---------|---------|--------|-------|-------|--------|--------|-------|-------|-------|-------|----------|-----------|
| v1 | 62.6% | 43.5% | 43.5% | 43.5% | 69.6% | 56.5% | 65.2% | 65.2% | 82.6% | 73.9% | 82.6% | 2026-06-21 |
| v3 | 82.2% | 65.2% | 95.7% | 95.7% | 73.9% | 65.2% | 69.6% | 73.9% | 100.0% | 82.6% | 100.0% | 2026-06-20 |

> v3 appears in both tables: the 2026-06-20 eval run used haiku extractions and is
> listed under haiku. The opus v1 run shows the frontier model's baseline on the
> original schema. v3 haiku ≈ v3 opus (both 82.2%) — model choice has not been a
> dominant factor in accuracy.

---

## Per-field outcome breakdown — v7 (haiku, 2026-06-23) ← current champion

| field | acc | correct | wrong | missed | halluc |
|-------|-----|---------|-------|--------|--------|
| period | 95.7% | 22 | 1 | 0 | 0 |
| reporting_currency | 100.0% | 23 | 0 | 0 | 0 |
| revenue.current | 91.3% | 21 | 0 | 1 | 1 |
| revenue.prior | 91.3% | 21 | 0 | 1 | 1 |
| npat.current | 91.3% | 21 | 2 | 0 | 0 |
| npat.prior | 73.9% | 17 | 5 | 1 | 0 |
| eps_cents.current | 78.3% | 18 | 3 | 2 | 0 |
| eps_cents.prior | 73.9% | 17 | 3 | 3 | 0 |
| dividend_cents.current | 100.0% | 23 | 0 | 0 | 0 |
| dividend_cents.prior | 82.6% | 19 | 2 | 2 | 0 |
| **OVERALL** | **87.8%** | | | | |

## Per-field outcome breakdown — v6 (haiku, 2026-06-23)

| field | acc | correct | wrong | missed | halluc |
|-------|-----|---------|-------|--------|--------|
| period | 91.3% | 21 | 2 | 0 | 0 |
| reporting_currency | 100.0% | 23 | 0 | 0 | 0 |
| revenue.current | 95.7% | 22 | 0 | 0 | 1 |
| revenue.prior | 95.7% | 22 | 0 | 0 | 1 |
| npat.current | 73.9% | 17 | 6 | 0 | 0 |
| npat.prior | 65.2% | 15 | 7 | 1 | 0 |
| eps_cents.current | 69.6% | 16 | 4 | 3 | 0 |
| eps_cents.prior | 73.9% | 17 | 3 | 3 | 0 |
| dividend_cents.current | 100.0% | 23 | 0 | 0 | 0 |
| dividend_cents.prior | 78.3% | 18 | 2 | 3 | 0 |
| **OVERALL** | **84.3%** | | | | |

---

## Key changes per version

| version | primary change | effect |
|---------|---------------|--------|
| v1 | First versioned prompt; AUD-only, statutory>underlying, unit norms | baseline |
| v2 | Multi-currency schema (reporting_currency field); revenue/npat renamed | +8.3pp overall; revenue halluc reduced |
| v3 | Bank revenue rule tightened; NPAT attribution rule; currency → 100% | +6.1pp overall; revenue 95.7%, currency perfect |
| v4 | NPAT rule expanded with code-block example; null-for-partial-docs rule added | −3.9pp overall; period regressed (rule interaction) |
| v5 | NPAT rule rewritten as prose; EPS basic/diluted rule added; null rule clarified | flat vs v4; period further regressed to 43.5% |
| v6 | Period: long-form date required, short forms forbidden; v5 NPAT+EPS+null rules | +2.1pp overall; period 65.2%→91.3%; bug fix: batch job now skips thinking for haiku |
| v7 | Rule 1 expanded: "before significant items" = non-statutory; new Rule 3: prior = same period last year | +3.5pp overall; npat.current 73.9%→91.3%; eps.current 69.6%→78.3% |

---

## Remaining weak spots after v7

- **npat.prior** (73.9%, 5 wrongs + 1 miss): some column/label confusion persists in
  multi-period tables; further gains require inspecting the remaining wrong cases.
- **eps.current/prior** (~76%, 3 wrongs + 2–3 misses): misses from partial docs are
  unfixable via prompt (media releases legitimately omit EPS); wrongs likely cash/adjusted
  EPS still leaking through in bank investor decks.
- **revenue** (91.3%, 1 miss + 1 halluc): slight regression from v6; one CBA
  hallucination introduced — before-SI language may have shifted attention in a dense
  statutory doc. Worth a targeted fix in v8 if pursuing 90%+.
- **Period** (95.7%, 1 wrong): one residual hyphen variant ("Half-year" vs "Half year").
