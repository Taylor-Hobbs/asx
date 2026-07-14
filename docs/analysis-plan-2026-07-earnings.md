# Analysis plan — earnings-corpus studies (specified 2026-07-13)

Pre-specified analysis plans for the three studies chosen from the earnings
corpus extracted 2026-07-13 (earnings_v7, 1,440 records; 751 ticker-results-
days, 684 with usable NPAT/EPS pairs). These are NOT pre-registrations in the
PR-001 sense — the data already exists and is in-sample — but the hypotheses,
cohort definitions, endpoints, and success criteria below are frozen BEFORE
any of the three analyses is run. Deviations must be reported as deviations.
Anything not specified here that we compute anyway is exploratory and will be
labeled as such.

**Multiple-testing accounting:** three primary endpoints, one per study
(ES-1, ES-2, ES-3). Within the family, a primary result is called
significant at Bonferroni-corrected p < 0.05/3 ≈ 0.017; nominal p in
[0.017, 0.05] is reported as "suggestive". Secondary endpoints are
descriptive only.

Shared machinery (identical to the director-trades study): day 0 = first
trading day on which the announcement was tradeable (before 16:00 Sydney on
a trading day → that day, else next trading day); returns = daily log
returns from `daily_prices` (yfinance, prototype-grade); market = XJO
(^AXJO); abnormal return = stock − market (simple market-adjusted — the
alpha-extrapolation lesson rules out market-model CARs for multi-month
windows). Full +1..+63 forward window required; events without one are
excluded and counted.

---

## ES-1 — ASX post-earnings-announcement drift (PEAD)

**Hypothesis.** The market underreacts to results-day news: the drift over
the 63 trading days after a results announcement continues in the direction
of the day-0 abnormal return.

**Events.** All price-sensitive announcements matching the results-headline
regex (the P0 filter, same as used for exact earnings dates), collapsed to
one event per (ticker, Sydney calendar day) keyed on the earliest
announced_at, then deduped to one event per ticker per 30 calendar days
(keeps interim vs final separate; collapses multi-document days).

**Sort.** Day-0 abnormal return (the market's own surprise measure — no
consensus data exists, and this choice avoids proxying expectations).
Quintiles Q1 (worst reaction) … Q5 (best), computed over the full event set.

**Primary endpoint.** Q5 − Q1 spread in mean market-adjusted CAR over
+1..+63. PEAD is CONFIRMED if spread > 0 with two-sample t ≥ 2.41
(Bonferroni p < 0.017), and the quintile means are directionally consistent
(Q1 < Q3 < Q5). REFUTED if spread ≤ 0 or |t| < 1. Otherwise inconclusive.

**Robustness (specified now, reported alongside).** (a) Per-season Q5−Q1
spread (results cluster in seasons; event windows overlap heavily in
calendar time, inflating naive t-stats — sign consistency across the ≥4
seasons is required color on any positive result); (b) median as well as
mean; (c) drift over +1..+21 vs +22..+63 (front-loaded or slow).

**Secondary (descriptive).** Same quintile table sorted by fundamental
surprise proxy — YoY NPAT change (and EPS where NPAT null) from the
extracted payloads, on the 684-event usable subset. Correlation between
day-0 reaction and YoY change (how much of "surprise" the YoY proxy
captures). No success criterion — no consensus baseline means YoY is
expectation-contaminated (a +40% YoY result can be a miss).

**Known limitations stated upfront:** overlapping event windows in results
seasons (cross-sectional dependence; t-stats optimistic); yfinance prices;
survivorship-lite universe (today's ASX 200); 4C quarterlies included as
events (they are price-sensitive results-shaped news even though the
earnings prompt extracts little from them).

## ES-2 — Dividend actions (NOT YET RUN)

**Hypothesis.** Dividend cuts carry post-announcement drift beyond the
day-0 reaction (dividend momentum / sticky-information channel).

**Events.** The usable-extraction subset with both dividend_cents.current
and .prior stated. CUT = current < prior (OMISSION subset: current = 0 <
prior); RAISE = current > prior; HOLD = equal. One event per ticker per 30d.

**Primary endpoint.** Mean market-adjusted CAR +1..+63 of CUT vs HOLD
events; confirmed if CUT − HOLD < 0 with t ≤ −2.41 and CUT day-0 abnormal
return is also negative (sanity: the market noticed). Secondary: RAISE vs
HOLD asymmetry; omissions vs ordinary cuts.

## ES-3 — Director purchases after results-day crashes (NOT YET RUN)

**Hypothesis.** An on-market director purchase filed within 30 calendar
days after a results day whose day-0 abnormal return ≤ −5% predicts
recovery (positive market-adjusted CAR +1..+63 from the purchase's day 0)
relative to post-crash episodes with no insider purchase.

**Cohorts.** TREAT: purchase events (events_director_trades, on-market
acquisitions, deduped 1/ticker/30d) whose day 0 falls 1–30 calendar days
after a qualifying crash results-day for the same ticker. CONTROL: crash
results-days with no on-market purchase filed within 30 days; CAR measured
from the median TREAT lag after the crash.

**Primary endpoint.** TREAT mean CAR − CONTROL mean CAR > 0, t ≥ 2.41.
If TREAT n < 15 the study is reported as underpowered, no test claimed.
Overlap with PR-001 noted: any confirmed cell here still requires its own
forward pre-registration before being called a signal.

---

## Exploratory extensions (added 2026-07-13, after ES-1..3 ran)

Four further angles, all EXPLORATORY — no frozen endpoints, no membership
in the Bonferroni family, no significance claims. EX-3 in particular is a
further cut on the same 31 in-sample sale events and is reported as
characterization only.

- **EX-1 flag-vs-content divergence:** price-sensitive flag vs market
  reaction and extracted content. Known limitation stated upfront: the P0
  crawl gated results filings ON the PS flag, so unflagged results are
  under-collected; the full test needs the P1-P3 broad sweep.
- **EX-2 cross-document consistency:** among multi-document results days,
  per-field agreement rates across independently-extracted documents, and
  whether per-field confidence is calibrated (lower on disagreeing values).
  Methodology study — no goldens consumed.
- **EX-3 retirement purge:** tag clean-31 sales where the seller has a
  CEASED role event (director_roles_v1, same ticker, name-matched) within
  −30..+180 days of the sale; re-score the cohort without them.
- **EX-4 board-change events:** CEO/MD appointment and cessation notices
  as events; day-0 AR and +1..+63 CAR by action. Descriptive.

---

## REP-1 — Cross-sectional replication of the director-sales lead on the ASX 201–300 band (frozen 2026-07-14, BEFORE any new-ticker data was analyzed)

**Purpose.** The surviving lead (large freely-timed director sales, ~−5–6%/qtr,
in-sample on ASX 200, 2024–26) gets its first test on data that played no part
in finding it: the next ~107 tickers by market cap. This is replication in the
cross-section, NOT out-of-sample in time — a regime-specific artifact would
replicate too. The forward test (Q4→2027) remains the verdict; this can only
raise or lower confidence.

**Universe.** `data/universe/asx300_delta_2026-07-14_directory.csv` — today's
top-300-by-market-cap band from the ASX company directory, minus the existing
ASX 200 file. Known impurities accepted and reported: not the official S&P
index; today's constituents (survivorship, as elsewhere); ~7 band-drift names.
Crawled 2026-07-14 (3Y + P0 results filters, 24 months).

**Event definition (copied verbatim from the ASX 200 cell — no tuning).**
On-market disposals, total_consideration ≥ $1,000,000, extracted by
director_trades_v3; day 0 = first tradeable day; dedup one event per
(ticker, director) per 30 days; CLEAN gate = >30 calendar days since the
ticker's most recent price-sensitive results filing (results-headline regex,
as in the original). The gate's known asymmetry (it never looks FORWARD to
the next results — found 2026-07-14 by the hygiene study) is kept AS-IS for
comparability and reported alongside.

**Measurement.** Cumulative (stock log return − XJO log return), trading days
+1..+63, full window required. XJO retained (not a small-cap index) for
comparability with the original cell; noted as a limitation. Secondary:
sector-adjusted CAR where a GICS sector basket of ≥3 members exists within
the COMBINED (ASX 200 + delta) price universe, event ticker self-excluded.

**Endpoints (stated now).**
- SUPPORTIVE: new-ticker clean $1M+ cohort mean CAR ≤ −2.0% AND one-sided
  t ≤ −1.0. (Expected n is small — ~10–25; this is a direction-and-magnitude
  check, not a significance claim.)
- UNSUPPORTIVE: mean CAR ≥ 0.
- INCONCLUSIVE: anything between; reported as such, no re-slicing.
- Also reported, labeled descriptive: pooled ASX300 estimate (original 31 +
  new events), the non-clean and sub-$1M cells for contrast, and per-event
  table. No new cells may be promoted to "lead" status from this data.

**Commitments.** No parameter above changes after seeing new-ticker data.
Result goes in BUILD_LOG and the write-up with equal prominence either way.
Known risks stated now: thin cell (small caps have fewer $1M+ sales),
yfinance quality degrades below the ASX 200, delistings within the window
are invisible (survivorship inflates CARs upward — which biases AGAINST
finding the negative drift, so a supportive result survives it; an
unsupportive one is partially confounded).
