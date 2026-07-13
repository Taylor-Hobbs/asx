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
