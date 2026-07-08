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
