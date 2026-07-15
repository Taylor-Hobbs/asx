# Pre-registered hypotheses

Predictions written down BEFORE the data that will test them exists. The
point: results discovered by scanning historical data (as PR-001 was) carry
an unquantifiable multiple-testing discount; a prediction registered today
and tested on future filings cannot be contaminated by that fishing. Rules:
the specification below is frozen — any deviation in the eventual test must
be reported as such, and a failed prediction is published as loudly as a
confirmed one.

---

## PR-001 — Off-season director purchases outperform (registered 2026-07-08)

**Origin.** The 2026-07-08 research day dissected the apparent director-sales
signal into three artifacts (window double-counting, alpha extrapolation,
reporting-season momentum — see BUILD_LOG). One residual survived with the
*structure* of genuine signal but a fishing-discounted t-stat: freely-timed
director purchases showed +2.5% market-adjusted drift (t=2.49, n=321,
in-sample 2024-07→2026-07), while trading-window-constrained purchases showed
none. Free-choice trades being the informative ones is what real insider
signal should look like; discovering it in cell ~40 of a scan is what noise
looks like. This registration settles it out of sample.

**Hypothesis.** On-market director purchases announced OUTSIDE ASX reporting
season will show positive market-adjusted drift over the following quarter;
reporting-season purchases will not.

**Frozen specification.**
- Universe: ASX 200 constituents at time of filing (or the project universe
  file then current).
- Event: Appendix 3Y with trade_type = acquisition and nature containing
  "on-market" (case-insensitive), extracted by the then-current benchmarked
  prompt. Dedup: one event per (ticker, director) per 30 calendar days.
- Cohort split: OFF-SEASON = announcement day-0 month ∉ {Feb, Mar, Aug, Sep};
  SEASON = month ∈ {Feb, Mar, Aug, Sep}. (Upgrade to exact per-company
  earnings dates if available by test time; report both splits.)
- Day 0: first trading day on which the notice was tradeable (before 16:00
  Sydney on a trading day → that day; else next trading day).
- Measurement: cumulative (stock log return − ASX 200 log return) over
  trading days +1..+63 after day 0. Adjusted closes.
- **Test data: filings announced on or after 2026-07-09 only.** Nothing
  announced before this date may enter the test cohort.
- Evaluation date: on or after 2027-07-09 (≥12 months of events, each with
  its full 63-day window; expected n ≈ 150–200 off-season events).

**Success criteria (stated now).**
- CONFIRMED: off-season mean market-adjusted CAR > +1.0% with t ≥ 2.0, AND
  off-season mean exceeds season mean.
- REFUTED: off-season mean ≤ 0, or t < 1.0.
- INCONCLUSIVE: anything between — reported as such, no re-slicing to rescue it.

**Commitments.** No parameter of this spec will be tuned after seeing test
data. The result — confirmed, refuted, or inconclusive — goes in the public
write-up with equal prominence.

---

## PR-002 — Forward paper test of the director-sales strategy (registered 2026-07-14)

**Origin.** The one surviving in-sample lead: large ($1M+), freely-timed
(>30d post-results) on-market director sales precede ~−5–6%/quarter of
market/sector-adjusted underperformance (t ≈ −2.2 to −2.7 across
specifications; survived dedup, alpha-extrapolation correction, exact-date
confound control, sector adjustment, retirement purge, and an earnings-
mechanism test that found no mechanism). All in-sample, n=31, scan debt
acknowledged. This registration deploys it forward on an IBKR paper account.
**Paper only. No live capital, ever.**

**Frozen strategy specification.**
- Universe: the combined ASX 300 universe file current at signal time
  (data/universe/asx300_combined_2026-07-14.csv until superseded by a
  documented refresh).
- SIGNAL: Appendix 3Y filing, on-market disposal, total_consideration
  ≥ A$1,000,000, extracted by the then-current benchmarked prompt
  (director_trades_v3 at registration). CLEAN gate: >30 calendar days since
  the ticker's most recent price-sensitive results filing (results-headline
  regex). The gate's known forward-blindness (it does not exclude sales just
  BEFORE the next results; found 2026-07-14) is retained as-is. Dedup: one
  entry per (ticker, director) per 30 calendar days.
- ENTRY: short A$10,000 notional at the next market open after signal
  detection (pessimistic vs the backtest's day-0 close entry; the daily
  detector runs after each ASX close). Simultaneously add A$10,000 to a
  single long STW (ASX 200 ETF) hedge position so hedge notional ≈ total
  short notional at each day's rebalance.
- EXIT: buy to cover at the market open after the 63rd trading day of the
  position; hedge reduced correspondingly.
- LIMITS: max 12 concurrent shorts; a signal arriving at the cap is logged
  SKIPPED-CAP and not taken later. Borrow unavailable in paper → logged
  SKIPPED-BORROW (itself a capacity finding).
- MISSED DAYS: if the daily job does not run, signals detected late are
  taken at the next open if still within 5 calendar days of filing;
  otherwise logged SKIPPED-STALE.
- No discretionary overrides. Any manual intervention is logged and the
  affected positions excluded from the primary endpoint.

**Measurement & endpoints (stated now).**
- Primary (position-level, evaluation ≥ 2027-07-14 or ≥30 completed round
  trips, whichever is later): mean market-adjusted (vs XJO) return over each
  position's 63-trading-day window, computed from closes. SUPPORTIVE if
  mean ≤ −2.0% with one-sided t ≤ −1.0; UNSUPPORTIVE if mean ≥ 0;
  INCONCLUSIVE otherwise.
- Secondary (account-level, descriptive): paper P&L of the hedged book after
  IBKR paper commissions; sector-adjusted per-position returns computed
  analytically; skip/borrow/capacity logs.
- Paper fills are optimistic; this validates TIMING, not execution realism —
  reported with that caveat verbatim.

**Commitments.** Spec frozen at registration; deviations logged and reported.
Result published with equal prominence, supportive or not. If anything in
this document tempts live capital: the answer is no.

---

## PR-003 — Scale-invariant, domain-gated director-sales signal (registered 2026-07-15)

**Origin — full disclosure: every parameter below is in-sample-tuned.** The
2026-07-15 cap-gradient and relative-size analyses (BUILD_LOG same date)
showed: (a) the post-sale trailing effect is monotone in market cap
(−5.8pp per 10× of cap, excess vs own baseline), positive below ~$2B and
strongest above ~$7B; (b) sale size AS A FRACTION OF CAP carries nothing
pooled but shows a dose-response within large caps (above-median relative
size −9.7% vs −0.4%); (c) the fixed A$1M threshold of the original lead is
what created its cap-dependence. This spec is the scale-invariant
restatement those findings suggest. Because its thresholds were read off
the same 41–71 in-sample events the lead was found on, **it deserves zero
credibility until it survives forward data** — which is the only reason
this registration exists. REP-1's out-of-band failure (2026-07-15) is
already one strike against the family; this is the family's best remaining
formulation, stated before any forward data exists.

**Frozen specification.**
- Universe / domain gate: the **top 100 ASX-listed companies by market
  capitalization at the time of filing** (scale-invariant proxy for "sales
  are frictionless free choices"; ~cap ≥ A$7B at registration).
- Signal: Appendix 3Y on-market disposal with stated total consideration
  **≥ 0.5 basis points of the issuer's market cap** at filing (the
  in-sample large-cap median; at A$7B ≈ A$350k, at A$150B ≈ A$7.5M).
  Extraction by the then-current benchmarked prompt.
- Clean gate: >30 calendar days since the ticker's most recent
  price-sensitive results filing. The gate remains backward-only BY
  NECESSITY: the next results date is not knowable at signal time without
  a results calendar, so forward-blindness is inherent to any real-time
  implementation, not a defect to patch.
- Dedup: one event per (ticker, director) per 30 calendar days.
- Measurement: analytical, not traded (PR-002 owns the traded book):
  cumulative (stock log return − XJO log return) over trading days
  +1..+63 from the first tradeable day, adjusted closes.
- **Test data: filings announced on or after 2026-07-15 only.**

**Endpoints (stated now).** Evaluate at ≥ 2027-07-15 AND ≥ 20 qualifying
events (if fewer than 20 by then, extend and report the delay).
- SUPPORTIVE: mean ≤ −2.0% with one-sided t ≤ −1.28.
- REFUTED: mean ≥ 0, or t > −0.5.
- INCONCLUSIVE: otherwise. No re-slicing; the relative-size dose-response
  (above/below-median split) is reported as a pre-named secondary, not an
  escape hatch.
- Overlap with PR-002's book (events qualifying under both specs) is
  reported so the two tests are not presented as independent.

**Commitments.** No parameter changes after this commit. Result published
with equal prominence either way. Paper measurement only; no live capital,
ever.

---

## PR-004 — The strength-raise kicker (registered 2026-07-16)

**Origin — every parameter in-sample-tuned; full audit trail in BUILD_LOG
2026-07-15/16.** Exploration of the headline_index found: raises are
strength-seeking (top-decile 6-month run-ins raise at 1.63× base); those
"strength raises" (~15/yr, 17% of raises) showed a shallow 2-day dilution
dip followed by back-loaded drift (+22.8% mean over 63td, two-thirds
accruing after day +21); matched momentum-only windows drifted +8.1%, so
the raise-specific increment was **+14.6pp at Welch t=+1.62** — the
largest unpromoted effect size the project has produced, at
sub-significance, on n=32, in a momentum regime, on a survivorship-lifted
universe. An in-sample backtest (fixed 1/8 sizing) showed ~+29%/yr,
maxDD −19%, Sharpe 1.3 — numbers this project's own history says to
distrust until forward data speaks. Hence this registration.

**The claim being tested.** After a capital raise announced by a stock in
a strong uptrend, the stock's subsequent quarter beats what momentum alone
would deliver — i.e., the raise itself carries positive information
(institutional validation + funded growth) beyond the trend it rides.

**Frozen specification.**
- Universe: the combined ASX 300 file current at signal time.
- Raise event: headline in `headline_index` matching the frozen regex
  (placement | capital rais | entitlement offer | rights issue | share
  purchase plan | SPP | equity raising | institutional offer | retail
  offer | renounceable), clustered one event per ticker per 30 days.
- Momentum gate: trailing 126-trading-day cumulative (stock log return −
  XJO log return) through day −1 **≥ +49%**.
- Measurement: analytical (no traded book): cumulative market-adjusted
  log return over trading days **+1..+63** from the announcement's first
  tradeable day. Adjusted closes. Day 0 excluded (halt-realism).
- CONTROL, measured contemporaneously on forward data: all windows in the
  same universe/period passing the same +49% gate with NO raise event
  within 91 calendar days, non-overlapping per ticker.
- Descriptive portfolio metric (secondary): fixed 1/8-capital sizing,
  next-day entry, 20 bps per side.
- **Test data: raise announcements on or after 2026-07-16.**

**Endpoints (stated now).** Evaluate at ≥ 2027-07-16 AND ≥ 12 qualifying
events (expected ~15/yr; if fewer, extend and report the delay).
- SUPPORTIVE: event mean CAR ≥ +5.0% AND event mean exceeds the
  contemporaneous momentum-control mean (the kicker exists forward).
- REFUTED: event mean ≤ 0, OR event mean ≤ control mean (momentum
  explains everything).
- INCONCLUSIVE: otherwise. Pre-named secondaries (no escape hatches):
  back-loaded accrual (≤ 35% of the total move by day +21) and dilution-
  dip recovery (median ≤ 10 trading days).

**Commitments.** Frozen at this commit. Published either way. The forward
universe is fixed today, so the survivorship/backfill bias that inflates
the in-sample numbers cannot recur forward — a deliberately harder test.
Analytical measurement only; no live capital, ever.
