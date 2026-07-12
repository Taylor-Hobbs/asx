# Build Log

Short entry per session: what was built, what broke, what the evals showed.
Feeds the weekly public build-log posts. Newest entries first.

---

## 2026-07-10 — EXACT earnings dates overturn the seasonal proxy

P0 crawl delivered 1,500 price-sensitive results filings (185 tickers, median
4 dates each) — the confound test no longer needs a calendar guess. Result
(`scripts/_exact_confound.py`, 63d market-adjusted, deduped):

| cohort | within 30d of results | clean (>30d) |
|---|---|---|
| ALL sales | −0.4% (n=112, ns) | +0.9% (n=102, ns) |
| **$1M+ sales** | +3.1% (n=27, ns) | **−5.7% (n=28, t=−2.15)** |

**The proxy's conclusion inverts.** The Feb/Mar/Aug/Sep month-split was too
coarse (median sale is 28 days after results; 52% within 30d — the proxy
misclassified heavily). With exact dates: post-results sales show NOTHING —
and the negative drift concentrates in **large, freely-timed sales**, exactly
where insider information should live. The earnings-momentum explanation is
NOT supported for the big-sale cohort.

Status: the hypothesis is (partially) back — "large director sales NOT
adjacent to results precede ~−5.7%/quarter (p≈0.04, n=28)". Same evidentiary
tier as before (small n, many cells scanned), but now with the confound
CONTROLLED rather than suspected, and in the theoretically-predicted cell.
Also: PR-001's evaluation must use exact dates (spec already allows).
Findings report §4.5 amended by this entry. Remaining: role extraction
(parse ~60% done), exec × clean-timing interaction — the two leads may be
the same lead.

---

## 2026-07-08 (coda) — the earnings confound confirmed by a calendar

yfinance earnings dates: 0/106 ASX coverage (US-only API). Fallback: ASX
reporting seasonality as proxy (Feb/Mar + Aug/Sep = post-results trading
windows). The split is decisive: **reporting-season sales −2.2% (n=132,
t=−1.55); off-season sales +3.5% (n=95, t=+2.10)** — the entire negative
drift lives in the post-results window, and free-timed off-season sales
(which should be MOST informative if directors carry signal) show none.
Post-earnings drift wearing a director-sale costume. Combined with the
matched-control and regression results, the residual hypothesis is now
substantially dead pending the broad crawl's exact dates. Study conclusion
firms up: **no identifiable edge in ASX 200 director trades 2024–26; the
apparent signal decomposes into (1) window double-counting, (2) alpha
extrapolation, (3) reporting-season momentum.** Role-enrichment (exec
sellers, n=12 at −6.4%) is the one thread left open.

---

## 2026-07-08 (sign-off) — final battery: no confirmed edge; a suggestive residual

Five closing tests (`scripts/_signoff.py`):

1. **Run-up-matched control** (the decisive one): each $1M+ sale matched to a
   no-sale stock with near-identical prior 6mo run-up (+16.8% vs +16.3%).
   Event fwd 63d −1.68% vs control +2.78% → **sale-specific effect −4.46%,
   paired t=−1.72 (p≈0.09)**. Not mere mean reversion — matched winners kept
   climbing — but not significant either at n=43.
2. **Cross-sectional regression** (n=81): the only significant carrier is
   **repeat-seller (coef −8.4%, t=−2.07)**. Size is NOT significant once
   controlled — the "$1M+" framing was partly proxying serial sellers
   (WTC/HVN/NWL). Sale size per se carries nothing.
3. **Buys 1yr placebo:** real +10.1% vs placebo +5.3% on the same tickers →
   percentile 91, p≈0.09. **Hypothesis #2 dead** — mostly base drift.
4. **Bootstrap CI** on big-sale fwd63: −1.68% **[−6.3%, +2.8%]** — spans zero.
5. **Volume at filing:** 1.15× normal — the market barely notices these.

**SIGN-OFF STATEMENT: no confirmed identifiable edge in ASX 200 director
trades, 2024–26.** Purchases: null at all horizons (placebo-confirmed).
Sales: a directionally consistent ~4–5%/quarter sale-timing effect vs
matched controls, concentrated in repeat sellers, at p≈0.09 — suggestive,
unconfirmed, and still earnings-confounded. Resolution requires earnings
dates (broad crawl) and Q4 forward paper. The study's strongest products:
two clean nulls, two self-caught inflation artifacts (window double-count,
alpha extrapolation), and the transfer-filing control methodology.

---

## 2026-07-08 (battery) — robustness battery rewrites the story: alpha-extrapolation artifact found

Eight tests in one pass (`scripts/_flesh_out.py`, market-ADJUSTED returns,
63d, deduped). The headline: **the −12–16% market-model CAR collapses to
−1.2% (ns) under simple market-adjusted returns.** Diagnosis: directors sell
after run-ups → the estimation window fits a high α → extrapolating that α
63 days forward manufactures negative "abnormal" returns when the stock
merely stops outperforming. Most of hypothesis #1's MAGNITUDE was method
artifact.

**What survives — smaller but placebo-proof:** these same tickers randomly
drift +3.9%/63d (winners; that's why directors are selling). Sale-timed
windows: −1.2%. The conditional effect is ≈ **−5% vs the stock's own
baseline**, sitting at percentile 2.6 of 1,000 random-date placebo draws.
The transfer control corroborates perfectly: 143 zero-information filings
show +3.5% (≈ placebo), sales show deterioration — the sale filing does mark
a turning point.

**Sharpeners mostly failed:** multi-seller no better than lone; selling out
≥50% of stake is OPPOSITE (+4.5% — full exits are retirements, not
information); fast vs slow filers identical; entry-delay and hold sweeps show
no robust plateau. Only repeat-sellers (−4.0% vs first-sale +1.6%) hints at
structure. The signal is real, diffuse, and ~5% — not crisp and −16%.

**Study status: "large director sales mark ~−5% conditional underperformance
vs the stock's own drift over 3 months (placebo p≈0.03); prior magnitude
estimates were alpha-extrapolation artifacts."** The sector-hedged Sharpe
0.67 is accordingly suspect. This entry is the rigor checklist earning its
keep — again.

---

## 2026-07-08 (close) — hit rates + sector-neutral stat-arb: the shape improves

**Hit rates (the sharpest sentence in the study):** of 49 deduped $1M+
director sales, **77% underperformed the market over the next 3 months**
(75% at 6mo). Literal price drops were a coin flip (~53%) — the signal is
relative, not absolute, which is why unhedged shorts fail.

**Stat-arb variants** (all IN-SAMPLE, and now selection-biased — three tried,
best reported): short-vs-index Sharpe 0.23 (baseline); short sales + long
buys 0.33; **short vs same-sector basket: Sharpe 0.67, maxDD −15.5%,
positive every calendar year** (+1.7/+3.7/+19.3%). Sector-neutrality isolates
the idiosyncratic underperformance the hit rate measures. Honest prior on
true Sharpe: well below 0.67 (discovery + selection haircuts, earnings
confound, 57 signals, no borrow costs).

**Q3 strategy definition graduates: sector-neutral short on $1M+ on-market
director sales, 63-day hold.** Verdict still owed by: earnings-date controls
(broad crawl) and Q4 out-of-sample forward paper.

---

## 2026-07-08 (last) — in-sample prototype backtest: the CAAR doesn't survive a portfolio

Calendar-time portfolio on hypothesis #1 (57 deduped $1M+ sale signals →
short at day-0 close, 63-day hold, index-hedged, ~7 concurrent, 20bps/side):
**Sharpe 0.23, max DD −33.7%**, 2024 flat, 2025 −11.4%, all profit in
H1-2026. Even fitted to its own discovery window, the naive implementation
is near-worthless as a strategy — CAAR equal-weights events, a portfolio
lives in calendar time, and clustered signals dilute. Close to the honest
"no edge after costs" outcome for the naive version; refinements on the same
data would be curve-fitting. Path unchanged: earnings controls (broad
crawl) → out-of-sample forward paper (Q4).

---

## 2026-07-08 (addendum) — buys on the same grid: hypothesis #2, method-suspect

Same horizon×size grid for on-market purchases (deduped n=489, median buy
just $50k vs sales' $1.1M): nothing at 1wk–3mo, then +11.8% at 1yr (z=+3.2,
median +11.0%), both size halves ≈+21% mean. **Ranked below the sales
hypothesis**: the effect only appears at the horizon where the market model
is weakest — bad-model compounding over 250 days, double survivorship (must
trade a full year + today's-constituents universe), overlapping windows, and
contrarian mean reversion (directors buy dips). Sales peaks at 3–6mo where
the method is solid and is null at 1yr; buys is the reverse — that asymmetry
is itself the tell. Parked for BHAR + EODHD (delisting-aware) in Q3.

---

## 2026-07-08 (final) — horizon × size grid: the signal is BIG sales, 3–6 months

Taylor's push: "sales still feels like a signal — are we only looking at one
month?" We were. Deduped sales, post-announcement CAR by horizon × size
(`scripts/_sales_horizons.py`):

| horizon | all (n≈201) | big ≥$1.1M (n≈46) | small (n≈45) |
|---------|-------------|--------------------|---------------|
| 1wk | −1.2% ns | −2.6% ns | ns |
| 1mo | −3.1% z=−3.1 | −6.2% z=−3.4 | ns |
| 3mo | −6.9% z=−4.1 | **−11.7% z=−4.3** | ns |
| 6mo | −11.9% z=−3.7 | **−16.1% z=−3.1 (med −17.7%)** | ns |
| 1yr | ns | n=17 | median +7.4% |

Slow drift, not an announcement pop; concentrated entirely in large sales;
medians ≈ means (not outliers). The 1yr fade is horizon/time-period
confounding (1yr windows only fit the weak early half). Caveats: size split
covers only 91/206 events (consideration often unstated); long windows
contain earnings announcements (the confound the broad crawl must resolve);
15 cells scanned — the big-sale 3mo/6mo cells survive a Bonferroni haircut.

**Refined hypothesis #1: large (≥$1M) on-market director sales precede
−12–16% abnormal drift over 3–6 months.** Falsifiable, specific, and the
input Q3's costed backtest wants.

---

## 2026-07-08 (later still) — breaking the sales result: half died, the rest got interesting

Adversarial diagnostics on the −7.1% sales CAAR (`scripts/_break_sales.py`):

- **Near-duplicate windows killed the headline.** Only 201 of 397 events are
  distinct ticker-episodes (WTC 26 filings, HVN 21, DRO 18 — serial sellers
  with overlapping event windows counted repeatedly). Dedup to one event per
  ticker per 30 days: CAAR −7.1% → **−3.1%**, BMP z −7.48 → **−2.57**. The
  first-pass z was inflated ~2.3× by double-counting.
- **Time-unstable:** early half −1.95% (z −2.1), late half −12.3% (z −8.2).
- **Reporting-season confound identified:** peak months Sep 2025 (46 events)
  and Sep 2024 (42) — trading windows open after August results, so the drift
  is plausibly post-earnings drift attributed to sales.
- **What survives:** median −3.6%, 62% of events negative (not outliers);
  dose-response (big sales −12.2% vs small −5.6%) — signal-shaped.

**Verdict:** hypothesis weakened to "deduped director sales show ~−3%
post-announcement drift, possibly earnings-entangled." Disentangling needs
earnings announcement dates for the whole universe — i.e. the phase-2 broad
crawl. The model-first plan closed its own loop: it named exactly which data
to collect next.

---

## 2026-07-08 (night) — FIRST RESULT: sales drift −7%, purchases null

**The event study core** (`events/event_study.py`, pure numpy, 22 tests on
known-by-construction synthetic returns): market model (MacKinlay), BMP
standardized test with forecast-error correction, Corrado rank test. **The
runner** (`events/study_runner.py`): tradeable day-0 rule (pre-16:00 Sydney →
same day, else next trading day), pairwise alignment on real observations (no
imputation), estimation [-120,-21], run-up gap, event [-5,+20].

**First hypotheses, 24 months × ~196 tickers:**

| cohort | n | CAAR(-5..+20) | BMP z | verdict |
|--------|---|---------------|-------|---------|
| on-market purchases | 1,254 | +0.45% | +0.12 (p=0.91) | **null** — honest negative #1 |
| on-market sales | 397 | **−7.1%** | **−7.48** (p<0.0001) | hypothesis #1, not an edge |

Purchases: directors buy after price falls (−0.8% pre-event drift), then
nothing. Sales: −3.8% of the drift is POST-announcement — the theoretically
tradeable part. Both consistent with the literature, which is the right
sanity sign for a first run.

**Why sales is a hypothesis and not an edge (the Q2 to-do list it creates):**
event clustering violates BMP independence (sales bunch in downdrafts);
earnings-announcement confounds (sales cluster after results); disclosure lag
means pre-event drift contains the trade's own footprint; no costs, no
multiple-testing correction, prototype prices, survivorship-lite universe.

---

## 2026-07-08 (later) — Q2 opens: event store + price data landed

**Taylor's call: model first, find what breaks, finish Q1 data after.** Broad
crawl and earnings extraction deferred; the 3Y dataset goes straight into Q2.

**Event store** (`events/director_trades.py` → `events_director_trades`):
4,743 events, one row per trade, anchored on **announced_at** — trade_date
precedes the tradeable moment by up to five business days and would be
lookahead; the gap is kept as `disclosure_lag_days`, a feature and a tripwire.
Deduped by content_hash (latest extraction wins), whole-table rebuild.
Tripwires on first build: 421 docs with zero trades (likely initial/final
notices — verify), 3 negative lags, 66 null trade_dates, 176/199 tickers.

**Price loader** (`prices/loader.py` → `daily_prices`): yfinance daily bars,
2023-07-01 onward (a year of estimation runway before the earliest event),
universe + ^AXJO index as ticker XJO. **147,721 rows over 763 trading days:
190 tickers ok, 7 short-history (recent listings: NEM, L1G, RYM…), 3 empty
(IFL, NSR, XYX — renames/delistings).** Prototype-grade by decree; EODHD
gates anything published. First run failed loud on ^XJO — Yahoo's ASX 200 is
^AXJO — which is exactly what the no-index-no-run check is for.

**Next: the event study core** — market-model AR/CAR with BMP + Corrado rank
statistics as tested pure functions, then purchases-vs-sales, the first
hypothesis on the board.

---

## 2026-07-08 — THE DATASET: 4,743 director trades extracted from 3,232 filings

**The flagship vertical is complete end to end.** 24 months × 199 tickers of
Appendix 3Y filings → crawl → parse → Haiku batch extraction with the
benchmarked director_trades_v3 prompt (93.1%):

- **3,232 / 3,233 documents extracted** (1 batch failure), ~$12 at batch rates
  (14.0M input / 2.0M output tokens)
- **4,743 trades** — 3,396 acquisitions, 1,057 disposals, **250 transfers**
- 1,040 distinct directors

The 250 transfers (5% of all trades) vindicate the TRANSFER schema ruling:
under the old acquisition|disposal enum every one of them would have been
fabricated directional signal in the Q2 event study.

**The BQ quota saga concluded (third table, then a fourth failure mode):**
extraction_records was about to trip the 1,500 load-jobs/day quota mid-
collection — caught at record 56, stopped, both extraction jobs swept to
buffered flushes, resumed from the batch (results live 29 days; nothing
re-paid). The resumed run then hit BigQuery's SHORT-TERM table-update rate
limit (~5 ops/10s) because batched flushes fire back-to-back with no API
latency between them. Fix: `load_rows_with_backoff` — 429s retry at
10s/20s/40s/…; the daily quota stays fatal. Every bulk BQ writer is now
batched AND backoff-wrapped.

**Data note:** up to ~250 extraction_records rows may be duplicated (a flush
whose load job committed server-side while the client saw the 429). Readers
must dedupe by content_hash — the eval job's dict and the summary query's
ROW_NUMBER both already do.

**Next:** eyeball a sample of payloads against PDFs, retry the 1 failure,
then phase-2 broad crawl + earnings extraction to close Q1. Q2 event study
now has its first dataset waiting.

---

## 2026-07-07 — 3Y corpus collected AND parsed; extraction staged at the gate

**Phase-1 crawl complete: 3,234 Appendix 3Y filings**, 199 tickers × 24
months, zero failures on the resumed run. The crawler inspected ~45k
announcements to find them (35.5k non-3Y filtered, 8.5k outside the window).
Resumability proved itself for real — the rerun swept 108 already-done
tickers at listing-only speed and downloaded just the missing ~1,500.

**The BQ load-job quota bit a SECOND table.** parsed_documents tripped the
same 1,500 jobs/day limit at document 1,561 — Monday's fix had patched the
announcements store but not the parse job's own save path (the lesson: when a
pattern bites once, sweep every writer). Same remedy applied: text artifacts
per document, flag rows flushed 250/load-job. Side effect: parsing got ~4×
faster — the per-document load job, not pdfplumber, was the bottleneck.

**Corpus parsed: 3,200/3,200, 100% good quality.** Simple digital forms parse
clean.

**Built earlier in the day: bulk extraction path** (`--scope corpus --batch`)
with the submit/poll/collect/--resume shape and a --confirm cost gate. Gate
output as of tonight: **3,205 documents pending, ~$10 at Haiku batch rates.**
Not yet run — paused at the gate. Next session: submit with --confirm, then
the 3Y structured dataset (director_trades_v3, 93.1%) exists end to end.

---

## 2026-07-06 — bulk backfill script; phase-1 crawl (24mo × 3Y) launched

**Built `ingestion/backfill.py`** — the bulk sibling of manual.py. No
per-ticker cap; bounds are the universe file and a months cutoff. Properties a
multi-hour crawl needs: per-ticker error isolation (one drift can't kill hour
five; failures logged + reported + retried free on rerun), BQ-keyed
resumability decided before any PDF request, and a dry-run mode. Two filters:
`--filter 3y` (director notices) and `--filter broad` (everything minus the
taxonomy's admin-noise exclude list). 9 tests; one caught a real bug
(year-boundary duplicate idsIds double-fetched within a run).

**Universe file reality check:** no free machine-readable ASX 300 list exists
— checked asx300list.com (2021-stale), asxlistedcompanies.com (2020-stale),
Market Index (403s scripts), stockanalysis.com VAS holdings (API caps at 25),
yfiua/index-constituents (no ASX). Settled on Wikipedia's S&P/ASX 200 table
(as of 2026-04-05, 199 tickers) → `data/universe/`. The +100 small ordinaries
top-up is a plain rerun with a fuller file once EODHD (Q2) provides
constituents — idempotency makes it free. Survivorship caveat documented in
the module: this crawl is collection, not the point-in-time record.

**Phase 1 launched:** `--filter 3y --months 24` over 199 tickers. Dry-run
calibration: ~16 3Y filings per ticker per 24mo → ~3,200 PDFs, ~6h at the
3s/request rate limit. Phase 2 (broad) comes after.

---

## 2026-07-04 (evening) — CI green again; Q1 taxonomy decision written

**CI had been red on every run since June 20** and nobody noticed: the failures
were lint/format debt in committed one-off debug scripts, never in src or
tests (local checks only covered src+tests; CI checks the whole tree). Fixed
by untracking the stale scripts, linting the keepers, and formatting the
tracked tree — first green run since the streak began. New habit: run the
CI-equivalent (`ruff check .`, `ruff format --check .`, bare `mypy`, `pytest`)
before pushing.

**Taxonomy decision recorded in CLAUDE.md:** Q1 extracts exactly two verticals
— 4D/4E earnings (v7, 87.8%) and 3Y director trades (v3, 93.1%) — gated on
"golden set + accuracy number exists". Everything else (4C quarterlies,
substantial holders, capital raises, M&A, contracts, guidance) is collected in
the backfill but extraction-deferred to Q2+ in extractability order. Backfill
rule: **collect broad, extract narrow** — the rate-limited crawl is the scarce
resource, storage is ~$1/mo, extraction spend stays gated per vertical.

**Q1 remaining:** bulk backfill ingestion script → the ~$120 extraction run.

---

## 2026-07-04 (later) — director_trades_v3 at 93.1% (+11.4pp); golden role labels corrected

**The eval caught a labeling error.** v2's worst field (director_role, 15.6%,
27 "misses") turned out to be the goldens' fault, not the model's: the bare 3Y
form has no role field, and a text search proved 30 of 36 labeled roles never
appear in the documents — they were labeled from headlines and general
knowledge. The model was being punished for correctly extracting only what the
document states. Fixed with `scripts/_dt_null_unstated_roles.py` (keeps a role
only if the document text contains it — 6 kept, 30 nulled), ruling recorded in
the golden README. Re-scored v2 on corrected goldens: 75.0% → 81.7%, same
extractions.

**Built `director_trades_v3`** — every rule traces to an observed v2 failure:

| fix | field | before → after |
|-----|-------|----------------|
| canonicalise class (drop issuer, "fully paid", ticker codes) | security_class | 50.0% → **100%** |
| never derive price↔total (with the exact failing quotes as examples) | price / consid | 68.8 / 71.9% → **97.1 / 100%** |
| strip honorifics, keep post-nominals | director_name | 93.8% → **100%** |
| holdings only when same class AND same holder as the row | holdings | 75 / 78% → 85.7 / 88.6% |
| split enumerated multi-class tranches; vesting = two sides | trade_detection | 88.9% → **94.6%** |

**Results (haiku, corrected golden_v1, 28 docs / 36 trades):**
v2 81.7% → **v3 93.1%**. Detection: 35/36 trades found, 1 missed, 1 invented.
Perfect fields: name, type, class, quantity, consideration, date.

**Known ceiling:** `nature` (62.9%) — golden paraphrases are too free for
exact-match ("Dividend Investment Plan" labeled as "dividend reinvestment
plan"). The remaining wrongs are wording variance, not misreading. Options if
it ever matters: tighten the labeling convention, or fuzzy-match this field.
Not worth it now — time-box.

**Director trades now beats earnings (93.1% vs 87.8%) — the flagship vertical
is done end-to-end.** Remaining Q1: taxonomy write-up, bulk backfill script.

---

## 2026-07-04 — director trades end-to-end: first accuracy number, 75.0%

**Built:** the flagship vertical's full eval loop — golden labels (28 filings,
36 trades, hand-labeled) → parse → extract → score:

- `eval/director_trades_harness.py` — list-alignment scoring. A 3Y is a
  variable-length trade list, so before per-field comparison predicted trades
  are aligned to golden trades (greedy by field agreement, gated on an
  identity floor + one strong identifier of director/date). Unmatched trades
  are first-class outcomes on a dedicated `trade_detection` line: a golden
  trade the model never reported is a MISSED detection, an invented one is
  HALLUCINATED. Field lines only count aligned pairs; detection keeps the
  denominator honest. 18 unit tests pin the alignment edge cases.
- `extraction/director_trades_job.py` — golden-set-scoped extraction (labeled
  hashes minus already-extracted; excluded filings never touched). Sync only —
  28 small docs don't warrant the Batches machinery.
- `eval/director_trades_job.py` — earnings eval job's shape pointed at
  `golden/director_trades/`; same extraction_records + eval_runs tables,
  prompt_version keeps the verticals separate.

**Schema change forced by real data:** `TradeType` gained `TRANSFER`. Three of
28 filings were internal reorganizations (CBA custodian swap, NAB
direct→family-trust, TLS trust→SMSF) with zero change in net beneficial
interest. Forcing those into acquisition/disposal would fabricate directional
signal for the event study. `director_trades_v2` prompt teaches the type and
pins "one transfer = one trade, never a disposal+acquisition pair". Ruling
recorded in the golden README.

**Also fixed:** `TestLoadPrompt` hardcoded `earnings_v1` (stale since v3);
`messages.parse()` thinking param now uses the SDK's `omit` sentinel instead
of an untyped kwargs dict (mypy strict clean).

**Results (haiku, director_trades_v2, golden_v1, 28 docs / 36 trades):**

| field | acc | signature |
|-------|-----|-----------|
| trade_detection | 88.9% | 4 missed trades, 0 hallucinated |
| trade_type | 100% | transfers included |
| trade_date | 100% | |
| quantity | 96.9% | 1 wrong |
| director_name | 93.8% | 2 wrong |
| holdings_before/after | 75/78% | mostly hallucinated (model states, golden null) |
| price/consideration | 69/72% | all hallucinated, zero wrong/missed |
| nature | 59.4% | 13 wrong — free-text convention mismatches |
| security_class | 50.0% | 16 wrong — "fully paid ordinary shares" vs "ordinary shares"? |
| director_role | 15.6% | 27 MISSED — model nulls, goldens filled |
| **OVERALL** | **75.0%** | |

**Reading the signature:** the model reads *numbers* nearly perfectly (dates,
quantities, types at 97–100%) — the losses are convention mismatches, not
reading errors. director_role's 27 misses and the hallucinated
price/holdings suggest label conventions and prompt disagree about "as
stated"; nature/security_class need canonical-form rules like earnings
period got in v6. That's v3 prompt work + possibly convention tightening —
same playbook that took earnings 82→88%.

---

## 2026-06-23 — earnings_v7 at 87.8%; director trades golden labels next

**Built:** `prompts/earnings_v7.md` — two targeted rule additions to v6:

1. **Rule 1 expanded — "before significant items" is non-statutory.** WOW's
   NPAT line is labelled "attributable to equity holders of the parent entity
   before significant items" — it passes the NPAT attribution test but is
   still underlying. Added explicit callout: "before SI", impairments,
   restructuring are non-statutory; always use the figure AFTER significant
   items. Also named "cash earnings" / "cash NPAT" explicitly for banks (NAB).
2. **New Rule 3 — prior = same period last year, not preceding period.** ANZ's
   table had three columns (1H26, 1H25, 2H25); model took 2H25 as "prior".
   New rule pins "prior year same period" and explains the three-column trap.

**Results (haiku, golden_v1, 23 docs):**

| field | v6 | v7 | delta |
|-------|----|----|-------|
| period | 91.3% | 95.7% | +4.4pp |
| revenue.current | 95.7% | 91.3% | −4.4pp |
| npat.current | 73.9% | **91.3%** | +17.4pp |
| npat.prior | 65.2% | 73.9% | +8.7pp |
| eps_cents.current | 69.6% | 78.3% | +8.7pp |
| dividend_cents.prior | 78.3% | 82.6% | +4.3pp |
| **OVERALL** | **84.3%** | **87.8%** | **+3.5pp** |

Revenue slight regression (95.7%→91.3%): one CBA hallucination introduced —
the before-SI language may have shifted the model's attention for one dense
statutory doc. Not investigated further; 91.3% is still strong.

**Remaining weak spots:**
- npat.prior 73.9% (5 wrongs, 1 miss) — further column/label confusion
- eps.current/prior ~76% (3 wrongs, 2–3 misses) — misses from partial docs
  are unfixable via prompt; wrongs likely still cash/adjusted EPS leaking
- period: 1 wrong (hyphen variant)

**Next:** director trades golden labels (the long pole to v3Y eval harness).

---

## 2026-06-23 — First full benchmark comparison; earnings_v6 at 84.3%

**Context.** The Jun 20 session (not logged) produced v2–v5 extractions (all
haiku) and the director trades vertical (schema, prompt, extractor). This
session filled in the missing eval runs, surfaced a bug in the batch job, and
shipped a v6 prompt targeting 85–90%.

**Benchmarks: v1–v5 scored for the first time (all haiku, apples-to-apples).**

| version | overall | period | revenue | npat.c | npat.p | eps.c | eps.p | div.c | div.p | currency |
|---------|---------|--------|---------|--------|--------|-------|-------|-------|-------|----------|
| v1 | 67.8% | 56.5% | 52.2% | 65.2% | 52.2% | 65.2% | 69.6% | 91.3% | 73.9% | 100.0% |
| v2 | 76.1% | 60.9% | 82.6% | 65.2% | 60.9% | 65.2% | 69.6% | 100.0% | 78.3% | 95.7% |
| v3 | 82.2% | 65.2% | 95.7% | 73.9% | 65.2% | 69.6% | 73.9% | 100.0% | 82.6% | 100.0% |
| v4 | 78.3% | 56.5% | 91.3% | 69.6% | 60.9% | 65.2% | 65.2% | 100.0% | 82.6% | 100.0% |
| v5 | 78.3% | 43.5% | 87.0% | 73.9% | 60.9% | 73.9% | 69.6% | 100.0% | 87.0% | 100.0% |
| **v6** | **84.3%** | **91.3%** | **95.7%** | **73.9%** | **65.2%** | **69.6%** | **73.9%** | **100.0%** | **78.3%** | **100.0%** |

v3 was the incumbent at 82.2%. v4 and v5 had both been extracted but never
scored — on scoring, both regressed (78.3%). Root cause: period degraded
progressively v3→v4→v5 despite the period instruction being identical across
all three; the new rules added in v4/v5 had an indirect interaction.

**v6 prompt changes (base = v3):**
- Period: replaced short-form examples ("1H FY2026", "FY2026") with long-form
  only, added explicit "do NOT abbreviate" instruction. Golden labels use
  "Half year ended 31 December 2025" etc — the model was sometimes choosing
  the short form. Period accuracy: 65.2% → 91.3% (+26pp). Two residual wrongs
  are a hyphenation variant ("Half-year" vs "Half year") in one WES document.
- NPAT rule: adopted v5's cleaner prose version ("always use the smaller one").
- EPS rule: adopted v5's "use basic (undiluted)" rule.
- Null rule: adopted v5's "extract only what this document states" rule.
- Revenue rule unchanged from v3 (95.7% — don't fix what isn't broken).

**Bug fixed: batch extraction job always passed `thinking={"type":"adaptive"}`**
regardless of model. `extract_earnings()` (sync path) correctly checks
`supports_thinking(model)` before adding it; the batch path (`run_batch`) had
the flag hardcoded. This caused 26/26 requests to error when the model was
`claude-haiku-4-5` (haiku doesn't support extended thinking). Fixed by
importing `supports_thinking` into `job.py` and applying the same conditional.
The bug was only exposed now because previous batch runs used opus; switching
to haiku for cost consistency in v6 triggered it.

**Director trades demo built (`scripts/demo_director_trades.py`).** End-to-end
live test: fetches 3Y announcements for a ticker via the ASX HTML listing,
downloads the first matching PDF, parses in-memory, extracts with
`director_trades_v1`, prints a trade table. Tested on BHP — found Mark Vassella
initial notice (2026-06-01, 2 trades: 1,905 direct + 2,920 indirect via
Allessav Nominees). Extraction correct. One note for director_trades_v2: the
`nature` field is pulling section headers for initial notices rather than a
clean mechanism description.

**Economics (v6 batch run):** 1,025,697 input + 12,138 output tokens for 26
docs using haiku batched. Cost ≈ $0.04 (haiku is ~4× cheaper than opus).

**Remaining weak spots heading into v7:**
- NPAT (73.9%/65.2%): 6–7 wrongs per side, all wrong-value not missed —
  model is finding a number but picking the wrong row.
- EPS (69.6%/73.9%): 3–4 wrongs + 3 misses.
- Period: 2 residual wrongs (hyphen variant).
- dividend.prior: 78.3% (2 wrongs + 3 misses from partial docs).

Full per-version history in `docs/eval-history.md`.

---

## 2026-06-15 — Eval harness v1 (step 9) built on the multi-currency schema

Picked up on top of the 2026-06-13 commit (multi-currency schema + 23/26
labels). Step 8 was already done by then — both open rulings resolved (EPS
basis = incl. discontinued; bank revenue = null) and the RIO production report
excluded — so this session was step 9, plus finishing a rename the schema
commit left half-applied.

**Built (step 9 — the harness):**
- `schemas/eval.py` — `FieldOutcome` (correct / wrong / missed / hallucinated),
  `FieldScore` (per-field tallies, computed accuracy/total), `EvalRun` (one
  scoring of model × prompt × dataset, with computed `overall_accuracy`).
  The four-outcome taxonomy is the point: a *hallucinated* dividend (invented)
  and a *missed* dividend (failed to read) are different failures and a prompt
  revision has to see which. A correct `null` is a scored success — banks are
  the clean case (revenue labeled null by convention).
- `eval/harness.py` — pure scoring core (no I/O), tested directly: exact
  `Decimal` value equality for money/share fields (values normalized to the
  reporting currency upstream, so a tolerance would hide reading errors, not
  absorb formatting); case-normalized match for `reporting_currency` and
  whitespace+case-normalized for free-text `period`, each on its own line.
  Ten scored fields: period, reporting_currency, and current+prior for revenue
  / npat / eps_cents / dividend_cents.
- `eval/job.py` — runner in the same shape as the parse/extraction jobs: a
  Protocol backend, a real `GcpEvalBackend` (goldens from the repo, extractions
  + runs in BQ), a structural fake in tests. Joins golden↔extraction by
  content_hash; `n_skipped` keeps coverage gaps visible; empty runs print but
  persist nothing, so `eval_runs` history begins with the first real scoring.
- `infra/bq/eval_runs.schema.json` (+ `bq mk` documented in infra/README) —
  `field_scores` as a repeated record so a field can be tracked across prompt
  versions in SQL.
- `docs/eval-methodology.md` v0→v1: scoring table, match semantics, the
  missing-vs-null answer (both schemas make `null` a required explicit
  assertion, so an omitted field fails validation before it's ever scored).

**Completed the multi-currency rename (the schema commit left CI red).** The
06-13 commit renamed `revenue_aud`/`npat_aud` → `revenue`/`npat` and added
`reporting_currency` in the schemas and all 26 label files, but left the Python
that references those fields untouched — mypy failed on `extraction/job.py` and
three test modules failed. Fixed the job's logging, `test_extraction_schemas`,
`test_golden_schema`, `test_extraction_job`, the three `scripts/`, and a stale
schema docstring. `prompts/earnings_v1.md` deliberately NOT touched — prompts
are immutable; its stale field names are the signal that earnings_v2 is due.

- 107 tests (28 new for the harness), mypy --strict clean, ruff clean.

**Blocker for the first accuracy number — re-extraction needed.** The 23
extractions in BQ were produced 06-12 under the *old* schema, so their stored
payloads carry `revenue_aud`/`npat_aud` and no `reporting_currency`; they no
longer validate against the renamed `EarningsResult`. The harness will load
zero of them and score nothing until the corpus is re-extracted under a new
prompt version (earnings_v2, carrying the multi-currency convention) — a live
API spend (~$3 batched) and a new versioned prompt, both Taylor's call. Code is
done and green; the number is gated on that re-run, not on the harness.

---

## 2026-06-12 — Extraction v1 built (live run still gated on the API key)

**Built (step 7, everything except the live call):**
- `prompts/earnings_v1.md` — first versioned prompt. It pins the two conventions
  the golden labels MUST share, or accuracy numbers will measure label
  disagreement instead of model quality:
  1. **Statutory beats underlying** (and group beats segment) when both appear.
  2. **AUD only, never convert** — USD reporters (BHP, RIO) get `value: null`
     for non-AUD figures. Honest gap for v1; revisit at schema level if it
     costs too much corpus.
  Plus unit normalization ($1,234.5m → 1234500000; EPS/DPS in cents), losses
  as negatives, no derived figures (null beats computing EPS from NPAT), and
  per-field verbatim quote + `[page N]` + calibrated confidence.
- `extraction/earnings.py` — parsed text → Claude (claude-opus-4-8, adaptive
  thinking) → validated `EarningsResult` via the SDK's `messages.parse()`:
  the Pydantic schema is the structured-output constraint AND the validator;
  constraints the API can't enforce (confidence 0–1 bounds) are checked
  client-side by the SDK. prompt_version = prompt file stem.
- `extraction/job.py` — idempotent like parsing: pending = good-quality parses
  minus extraction_records rows for the current (model, prompt_version);
  `--limit N` for eyeball-first runs (extraction costs real tokens). Records
  land in BQ only — payload is a JSON string column; no GCS artifact needed
  at ~2KB/record.
- `infra/bq/extraction_records.schema.json` + live table created. Backend
  smoke-tested against real GCS/BQ: 26 good parses pending, 0 extracted,
  text loads with page markers intact.
- `.env.example` documenting required env vars. Gotcha found: pydantic-settings
  reads `.env` privately — the anthropic client reads the PROCESS environment,
  so the job calls `load_dotenv()` explicitly (python-dotenv now a declared dep).
- 79 tests (extractor wiring faked at the client boundary, job against a
  structural FakeBackend), mypy --strict clean, CI green.

**First live extractions (key landed same day).** `--limit 3` →
CBA profit announcement + both WES half-year docs, ~60s, ~20s/filing.
Results strong: every numeric value correct against the parsed text, the two
WES documents (media release vs statutory 4D) agree with each other on all
four metrics — a free cross-document consistency check — and confidence
looks calibrated (0.99 on WES's clean tables, 0.92–0.97 on CBA's denser
statutory pages).

**Audit-trail verification (now `scripts/verify_quotes.py`) found the real
lesson:** strict byte-matching flagged 6/27 quotes "missing", but diagnosis
showed ZERO hallucinations — 5 were quotes spanning a line break (model joins
"label:\nvalue row" with a space; a faithful quote the parser's line breaks
can't byte-match) and 1 was a wrong page number (right quote, page 1 not 7).
Whitespace-normalized matching: 26/27 pass. The eval harness must compare
quotes whitespace-normalized or it will measure the parser, not the model.

**Two conventions the first 3 filings surfaced that earnings_v1 does NOT pin
(golden labels must decide; candidates for v2):**
1. **EPS basis:** CBA reports basic EPS "from continuing operations" (323.7c)
   AND "including discontinued operations" (321.0c). Model chose including-
   discontinued. Pick one and label consistently.
2. **Bank "revenue":** banks report no conventional revenue line; the model
   chose "total net operating income before operating expenses and
   impairment" ($15,000m) at conf 0.96. Decide what revenue means for
   financials — or whether it's null for banks.

**Batch mode built and the remaining 23 run through it (corpus now 26/26).**
Owner wants full scale and $5k/yr was out of scope — so the Batches API
(50% off, the natural shape for headless runs) got pulled forward. Same
idempotent pending-set; `--resume BATCH_ID` collects a crashed run without
resubmitting; per-document token usage now logged. The 23-doc batch went
submit → ended in ~2.5 minutes, 23/23 succeeded.

**Measured economics (no more bill archaeology):** 1,144,717 input +
27,847 output tokens for 23 docs = **$3.21 batched (~$0.14/doc avg)**;
input is ~98% of tokens and ~90% of dollars; doc sizes vary 6K–129K tokens. Whole 26-doc corpus:
~$4.40. Full-scale projection at ~2,000 earnings docs/yr: **~$280/yr on
batched Opus** — the scary $5k figure was Opus over all 10–15k filings,
which extraction never does. Decision: pipeline stays on the API key
(structured outputs + batches + clean provenance); the Max-plan Agent SDK
credit ($100/mo included, no rollover, June 15 policy) gets evaluated later
as a second runner — same prompt, same model, API vs agent harness, scored
by the eval harness once it exists. If accuracy holds, production moves to
the credit and marginal cost is $0.

**Full-corpus quote audit: 176 quotes, 35 failures (~20%) — all soft, and
they sort into a taxonomy the harness should count separately:**
1. **Stitched quotes** (most common): model joins non-contiguous fragments
   with "..." or appends annotations like "(US$m)" — informative but not
   verbatim. Prompt v2 candidate: "one contiguous span, no ellipses, no
   annotations".
2. **Wrong page numbers** (8): right quote, wrong `[page N]`.
3. **One real rule violation** (NAB): prior revenue COMPUTED as NII + other
   operating income, with the arithmetic admitted in the pseudo-quote —
   rule 5 says never derive. Bank "revenue" ambiguity again.
4. USD reporters (RIO, CSL!) correctly nulled values but quoted the USD
   figures as evidence — good auditability, fine.
5. **Cross-doc disagreement to resolve in goldens:** CBA NPAT extracted as
   5,367 from the profit announcement but 5,412 ("Statutory NPAT" per the
   investor deck) from two other docs; ANZ 3,414 vs 3,400. Same filing
   events, different documents, different numbers — statutory vs cash vs
   rounding. The golden labels arbitrate.

Per prompts/README.md discipline, no earnings_v2 until the harness can show
it beats v1 on the golden set.

**Evals:** none yet — first accuracy number needs golden labels.

### ⏸ PARKED HERE (2026-06-12) — state of play for next session

All 26 extracted; extraction is no longer the critical path. In order:

1. Owner: golden labels (step 8) per `golden/README.md` — THE long pole.
   Conventions to decide while labeling: EPS basis (continuing vs incl.
   discontinued), bank "revenue" definition, and the CBA 5,367-vs-5,412 /
   ANZ 3,414-vs-3,400 cross-doc calls. Exclude the RIO Q4 production report.
2. Eval harness v1 (step 9): per-field accuracy vs goldens + the quote-audit
   taxonomy above as named metrics; results to a BQ eval_runs table.
3. Then earnings_v2 (contiguous-quote rule, page-number fix, bank-revenue
   convention) — shipped only if it beats v1 on the golden set.
4. After the harness: the Agent SDK runner experiment (Max credit, $0
   marginal) — same prompt/model through `claude -p`, scored side by side.
   Design pre-registered (metrics + decision rule fixed before running) in
   `docs/experiments/2026-06-12-extraction-v1-first-live-run.md`, which is
   also the source-of-record for the public write-up of this session.

---

## 2026-06-13 — Multi-currency schema + golden labels complete (23/26)

**Schema changes (step 8, schema sub-task):**
- `reporting_currency: str = "AUD"` added to `GoldenEarningsLabels`; `reporting_currency: SourcedField[str]` added to `EarningsResult`. Field names `revenue_aud`/`npat_aud` → `revenue`/`npat` throughout (schemas + all 26 label stubs batch-renamed).
- Rationale: BHP, RIO, CSL report in USD; labeling AUD would require FX conversion which "null beats deriving" forbids. Schema now carries the currency alongside the values.
- `golden/README.md` rule 3 updated: "Native currency only, never convert".

**Golden labeling progress: 23/26 labeled, 2 unlabeled (RIO), 1 excluded.**

Conventions locked and recorded in `golden/README.md`:
- EPS basis: **including discontinued operations** (consistent across all tickers).
- Bank revenue: **null for CBA, NAB, ANZ, WBC** — "total net operating income" requires judgment; null is the honest answer.
- Per-document rule: CBA Profit Announcement shows $5,367m NPAT (incl. discontinued), investor deck shows $5,412m (continuing only) — each file records its own document's figure.

Sources used per ticker:
- **BHP** (USD): confirmed from PDF financial summary (p20).
- **CSL** (USD, 03058873/74): confirmed from Appendix 4D — statutory NPAT $401m (not NPATA $1,946m). Investor pres (03058876) labeled as candidate pending NPATA/statutory verification.
- **TLS**: confirmed from Appendix 4D PDF — Revenue $11,641m, NPAT $1,124m, EPS 9.9c, DPS 10.5c.
- **WES**: confirmed from multiple cross-document sources (3 filings agree).
- **WOW**: confirmed from H1 FY2026 Half-Year Results Announcement PDF (p16) — Revenue $37,135m (not the ~$35.9B rounded web figure), NPAT $374m statutory, EPS 30.6c basic after significant items, DPS 45c. Prior confirmed from H1 FY2025 PDF.
- **CBA**: confirmed from Profit Announcement PDF pp15-20 — two sets of figures depending on doc type (incl. vs continuing discontinued).
- **NAB**: confirmed from downloaded NAB H1 FY2026 ASX announcement PDF (nab.com.au) — NPAT $2,750m, EPS basic 89.9c (incl. discontinued).
- **WBC**: confirmed from downloaded WBC H1 FY2026 Interim Financial Results PDF (westpac.com.au) — NPAT $3,414m, EPS basic 99.9c (diluted 99.5c per web was wrong; basic confirmed from income statement).

**RIO (2 files) remains unlabeled:** statutory basic EPS not found. SEC blocked (HTTP 403), ASX returns HTML terms page. Underlying EPS known (669.2c) but can't label a derived or non-statutory figure.

**Evals:** still none — waiting on eval harness (step 9, next session).

---

## 2026-06-11 — Repo setup + scaffold

**Built:**
- Repo created and published to github.com/Taylor-Hobbs/asx (CLAUDE.md v2, README, .gitignore).
- Python scaffold: uv-managed `pyproject.toml` (src/ layout, hatchling), `asx_engine` package
  with `ingestion` / `parsing` / `extraction` / `schemas` subpackages.
- `config.py` — typed settings via pydantic-settings (`ASX_`-prefixed env vars); required GCP
  fields fail loudly when missing; ingestion-etiquette defaults (3s request interval,
  identifiable User-Agent) live here.
- Tests for config (env loading, defaults, fail-loud validation).
- CI: GitHub Actions running ruff (lint + format), mypy --strict, pytest on every push/PR.
- Docs stubs: architecture.md, eval-methodology.md. Conventions READMEs in prompts/ and golden/.
- **Schemas:** `Announcement` (frozen, content-hash keyed, tz-aware UTC-normalized
  `announced_at`/`ingested_at` — naive datetimes rejected at construction).
  `SourcedField[T]` (PEP 695 generic; per-field confidence + verbatim source quote),
  `ReportedMetric` (current + prior comparative), `EarningsResult`, `GuidanceStatement`
  (direction enum, ordered-range validation, open-ended ranges allowed),
  `ExtractionRecord[PayloadT]` envelope binding payloads to (model, prompt version,
  timestamp) for eval reproducibility. Decimal for money, units in field names.
- 26 tests passing; mypy --strict clean.

**Broke:** nothing yet — machine had no Python; installed uv + managed Python 3.12.13.

**Evals:** n/a (harness not built yet).

**Decisions made:** confidence/source-span at field grain (matches per-field eval grain);
source spans as quoted text not char offsets (parser-version proof); units encoded in
field names (`revenue_aud`, `eps_cents`) with normalization at extraction time.

**ASX data source de-risked (the big Q1 unknown).** Probed live, politely (~8 requests,
3s spacing, identifying UA):
- The pyasx-era endpoint (`asx.com.au/asx/1/...`) is **dead** — 404. pyasx is stale.
- Live chain verified end-to-end: (1) metadata JSON from
  `asx.api.markitdigital.com/asx-research/1.0/companies/{ticker}/announcements`;
  (2) PDF resolution via legacy `displayAnnouncement.do?display=pdf&idsId={middle
  segment of documentKey}` → terms interstitial with hidden `pdfURL` input;
  (3) direct PDF download from `announcements.asx.com.au` → 200 application/pdf.
- Quirks: `itemsPerPage` is a suggestion (asked 3, got 5); metadata `url` field is
  empty; markitdigital cdn-api file-gateway patterns from older scrapers also 404.
- ⚠️ To verify during manual ingestion: the resolved pdfURL for idsId 03081111 had a
  date-path (20260409) that didn't match the announcement date (2026-04-21) — confirm
  the documentKey→idsId→PDF mapping lands on the right document before trusting it
  at scale.

**Built (continued):** `AsxClient` — rate-limited (injectable clock/sleep), fail-loud
(`AsxApiChangedError` with payload snippets on any drift), exponential backoff on
429/5xx/transport errors only (hard 4xx never retried), interstitial pdfURL extraction
with direct-PDF short-circuit. Tests (15) run against verbatim captured payloads via
httpx.MockTransport — zero network in CI. 41 tests total.

**GCP stood up** (project `asx-scanner-499110`, billing linked, budget alert set):
- Private bucket `asx-scanner-499110-raw-pdfs` in australia-southeast2 — uniform
  bucket-level access + public-access prevention *enforced* (public ACLs impossible,
  enforcing the redistribution rule at the infrastructure level).
- BQ dataset `asx_engine` + `announcements` table; schema versioned in
  `infra/bq/announcements.schema.json`, field descriptions carry the invariants
  (immutability, announced_at vs ingested_at separation).
- Auth via ADC only — no service-account key files anywhere.
- Verified end-to-end from Python: settings → storage.Client → bigquery.Client all
  resolve against live resources.

**⚠️ RESOLVED — and it was a real bug.** The JSON documentKey's middle segment is NOT an
idsId: for BHP's 2026-04-21 quarterly it gave 03081111, which resolves to a *different
document* (2026-04-09); the correct idsId is 03084954. Worse, the JSON endpoint returns
only the 5 most recent items — pagination and fromDate/toDate are silently ignored.
**Pivot:** the legacy announcements.do HTML listing is the source of truth (full calendar
year per request, correct idsIds, price-sensitive marker, Sydney-local times). The JSON
endpoint is demoted to forward-polling metadata only. Client rewritten accordingly:
bs4-parsed listing with verbatim-capture fixtures, AEST/AEDT→UTC conversion pinned by
tests on both sides of the daylight-saving boundary.

**First real ingestion (26 filings).** `python -m asx_engine.ingestion.manual` with
dry-run curation + `--exclude` hand-picking. 10 tickers (BHP CBA NAB ANZ WBC CSL WES TLS
WOW RIO), Feb–May 2026 results season: statutory 4Ds, media releases, investor decks.
26 PDFs → GCS (hash-addressed), 26 metadata rows → BQ, ~4.5 min at polite pacing, zero
errors. Spot-checked BHP/ANZ/WES PDFs against stored metadata: contents match headlines;
WES's first page shows Revenue/NPAT/EPS in clean native text — extraction targets
confirmed reachable. Lesson: exclusions free limit slots that refill with the next
candidate (by design) — re-run dry-run after excluding to see the final list; one RIO
production report slipped in this way (harmless: label-set curation happens later).

**Parsing built and run over all 26.** `parse_pdf` (pdfplumber, native text only) +
versioned `ParsedDocument` with computed quality flags (page_count, empty_page_count,
total_chars, quality good/partial/empty). Storage: full text →
GCS `parsed/{parser_version}/{content_hash}.json`, flags row → BQ `parsed_documents`.
Job is idempotent via set-difference against BQ — crash-safe, resumable, and bumping
PARSER_VERSION re-parses naturally. Tests build minimal-but-valid PDFs byte-by-byte
(correct xref offsets) so the real pdfplumber path is exercised without fixture files;
an "empty page" in tests is genuinely a page with no text operators.

**Parse results:** 26/26 `good`, zero empty pages across 1,630 pages / ~3.2M chars —
all born-digital, OCR correctly deferred. Tables linearize better than feared:
`Revenue 24,212 23,490 3.1` keeps label/current/prior/variance on one line. Stored
text is clean Unicode (console mojibake during inspection was display-only). The real
extraction risk is now ambiguity (statutory vs underlying rows, segment vs group
tables), not parse quality. 71 tests.

---

### State of play at end of 2026-06-11 (superseded by the entry above)

**Where we are:** Q1 vertical slice, steps 1–6 of 9 done in one day. The pipeline is
live end-to-end up to parsed text: ASX → private GCS bucket → BigQuery → parsed pages
with quality flags. 71 tests, mypy --strict, CI green, everything pushed.

**What exists and works:**
- 26 real earnings filings (10 tickers, Feb–May 2026 results season) in
  `gs://asx-scanner-499110-raw-pdfs/raw/{hash}.pdf` + `asx_engine.announcements`
- All 26 parsed `good` → `parsed/pdfplumber_v1/{hash}.json` + `asx_engine.parsed_documents`
- CLI entry points: `python -m asx_engine.ingestion.manual` (dry-run + --exclude
  curation) and `python -m asx_engine.parsing.job` (idempotent)

**Next step (7 — extraction v1), blocked on ONE thing:** owner's `ANTHROPIC_API_KEY`
in the local `.env` (console.anthropic.com → API Keys). Then, in order:
1. `prompts/earnings_v1.md` — versioned prompt with unit-normalization rules
   ($1,234.5m → 1234500000; EPS/DPS in cents; statutory vs underlying: capture as stated)
2. Extraction module: parsed text → Claude → validated `EarningsResult`
   (per-field confidence + source quotes) → `extraction_records` BQ table
3. Run a handful of the 26 live; eyeball before building the harness

**Also unblocked, owner's hands (step 8):** golden labels for the 26 — read each filing,
record true revenue/NPAT/EPS/DPS per `golden/README.md` format. The long pole to the
first accuracy number; parallelizes with step 7.

**Watch out for:**
- Extraction's real difficulty is ambiguity (statutory vs underlying, group vs segment
  tables), not parse quality — the prompt must pin which number wins and the golden
  labels must record the same convention, or accuracy numbers will measure label
  disagreement instead of model quality.
- Big statutory docs run ~100K+ tokens; fine for v1, batch/caching optimizations are
  Q4 scope — don't build them now.
- RIO Q4-production filing in the corpus is not an earnings doc — exclude from the
  earnings golden set at labeling time.


## 2026-07-10 (role verdict) - exec hypothesis dies; final lead characterized

LLM role enrichment: 179/181 selling directors classified (89 exec, 88 NED,
data/enrichment/director_roles_llm.json). Role carries NOTHING: exec sales
overall -0.3% ns; exec x clean -0.3% ns; adding exec to the clean+big cell
DILUTES it (n=20, -4.3%, t=-1.38 vs -5.7%, t=-2.15 without). The earlier
"three converging lenses" were the same few events counted thrice. FINAL
surviving lead: large ($1M+) freely-timed (>30d post-results) sales, -5.7%/
qtr, t=-2.15, n=28, tail-risk shaped (9/31 events preceded <=-17% quarters;
worst 3 carry half the mean; CYL pair the standout case). Role-agnostic.
Verification path: appointment-notice extraction once parse completes.

## 2026-07-13 - Q1 DATA COMPLETE: earnings corpus extracted overnight

The overnight autopilot: parse finished 605/605 good at 00:26, watcher
fired the batch at 00:28 (1,476 results-shaped docs -- the scoping fix
the night before stopped it extracting 3,200 director-trade forms by
mistake). Collection died twice on a unicode hyphen in a period string
crashing the LOG line on cp1252 consoles (not a laptop nap -- the
extraction job was the one main() missing the utf-8 reconfigure; fixed).
Final: **1,440 earnings records extracted, 36 failed** (oversized/errored,
cost $0), ~34.9M tokens ~= $19 -- half the estimate, quarter of the naive
un-scoped run. extraction_records now holds BOTH verticals: 3,232 director
-trade docs + 1,440 earnings docs, all benchmarked prompts. Remaining Q1:
P1-P3 broad sweep (optional), appointment-notice role extraction (verify
LLM labels). The dataset the study needed is banked.

## 2026-07-13 (roles) - role extraction + LLM-label verification

director_roles_v1 over 893 appointment/cessation notices: 890 extracted,
~$1, minutes. Verification vs the 2026-07-10 LLM-knowledge labels: only
51/179 sellers verifiable (long-tenured directors predate the window);
**72% agreement (18/25)**. LLM failure modes are systematic: famous-
elsewhere executives labeled exec at companies where they are NEDs
(Drummond/RHC, Formica/MFG, James/DRO), post-cutoff CEOs labeled NED
(Wells/JBH, Banks/VNT), and time-dependent roles (Kelly/SDF MD->NED).
Exec-verdict stands (noise attenuates, and the exec cell was already
weaker than unconditioned) but carries a label-noise caveat in the
write-up. Lesson worth publishing: LLM-knowledge people-enrichment has
predictable failure modes; $1 of primary-document extraction catches them.
