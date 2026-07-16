# Paper 04 — Capital Raises on the ASX: Anatomy of a Mirage

**Status:** DRAFT v1 (2026-07-16) · **Data:** 305,636 headlines / 1,828
tickers (the full exchange, 2024–26); 3,486 clustered raise events across
1,168 tickers; full-market daily prices (1.35M rows)
**Author:** Taylor Hobbs · Specs: docs/analysis-plan-2026-07-earnings.md (REP-2), docs/preregistrations.md (PR-004)

## Abstract

Roughly **two-thirds of all ASX-listed companies raised equity at least once
in 24 months** (~150 raises/month) — the exchange's small end is a
fundraising machine with tickers attached. We model who raises, when, what
happens after, and whether any of it is tradeable. Findings: raising is an
**identity**, not a price event (a hazard model reaches out-of-time AUC 0.75
with momentum contributing *zero*); raises are strength-seeking and convex
in prior performance; a spectacular "buy the momentum raise" backtest
(+90%/yr, Sharpe 1.5) is dismantled in full — **survivorship contributed
~+26pp per event**, and on the honest full-market universe the same trade
*loses* 3%/quarter; the durable information is a single quality axis
(distance from the 52-week high at the raise) which separates disaster from
survival by ~30pp per quarter, ranks raises robustly across a regime change,
and lives almost entirely beyond the reach of borrow, options, or any
tradeable instrument — a textbook limits-to-arbitrage exhibit. Qualitatively,
winners finance *named projects*; losers finance *narratives and survival* —
and the market prices adjectives at zero.

## 1. Who raises: identity, not momentum

A hazard model over 33,119 ticker-weeks — P(raise within 63td) — reaches
**AUC 0.754 out-of-time** (top decile: 26.8% raise rate, 3.8× base). Its
drivers, in order: **past raises (+0.32), sub-index size (+0.26), volatility
(+0.24)**; six-month momentum contributes +0.09 — and removing momentum
entirely leaves AUC unchanged (0.756). Explorers and biotechs raise on
~9–12-month funding cycles regardless of price. An earlier "momentum
predicts raises" gradient (top-decile run-ins raise at 1.63× base;
worst-decile at 0.42×) is real but *confounded*: momentum and raising are
both symptoms of the same company type. Rescue raises barely exist in the
top 300 — crashed companies mostly cannot raise.

## 2. The anatomy of a mirage

The seductive result, and its autopsy — each step frozen or firewalled:

1. **Discovery (survivor band):** raises by top-decile-momentum stocks in
   today's top-300 returned **+22.8%/event**; a backtest annualized at
   +89%/yr, Sharpe 1.54. The drawdown (−44.6%) was itself a construction
   artifact — equal-weighting 1–3 concurrent legs; fixed 1/8 sizing gives
   +29%/yr at −18.6%.
2. **Momentum control:** identical momentum without a raise: **+8.1%/qtr**
   in the same band. The raise "kicker": +14.6pp at Welch t=+1.62.
3. **Decomposition:** 94.7% of the move came from sub-$1B stocks; Materials
   86.4%; the top 3 events were 54% of all profits; one serial raiser (at a
   $60–70M event-time cap) was 44% alone. These names are in the universe
   *because they subsequently grew into it.*
4. **REP-2 (spec frozen before the full-market crawl):** on all 1,828
   listed tickers — where nothing must "grow into" the sample — gated raise
   events returned **−3.1%** vs **−6.1%** for momentum-only controls.
   Verdict: UNSUPPORTIVE. Whole-market top-decile momentum *mean-reverts*;
   the band's +8.1% drift was the survivor filter. **Survivorship's price
   tag: ~+26pp per event — enough to turn a losing trade into a Sharpe-1.5
   backtest.**

A weak residual (+3.0pp vs momentum peers, t=1.1 — a placement-price
floor?) is registered as **PR-004** (fixed forward universe, contemporaneous
momentum control) and expected to be refuted.

## 3. The quality axis: the one thing that replicates

Of 18 features screened with a train(≤2025)/test(2026) firewall, four held —
and they are one axis: **distance from the 52-week high** (IC +0.18/+0.17),
volatility (−), price level (+), with momentum's entire value being
disaster-avoidance. Distress raises (announced >30% below the high — **62%
of all raises**) run −7.3% (t = −7.06); the worst tercile of the test period
averaged **−40.5%**. A composite of all eight variables equals the single
axis out-of-sample (IC 0.158 vs 0.162): *one honest variable beats eight
fitted ones.* Horizon: the quarter is where quality expresses (21td: 2.3pp;
63td: **+20.7pp Q5−Q1, out-of-regime**); longer horizons are untestable in
this span. Critically, the axis ranks **relatively** in both regimes while
every *absolute* long cell flipped sign in 2026 — the regime owns direction;
the axis owns order.

## 4. Limits to arbitrage: why the anomaly persists in plain sight

Only **35 of 1,939 distress raises (1.8%)** occur in the borrowable ASX 300 —
and there the effect *inverts* (mean +4.5%, median −7.2%): majority-down,
occasionally-rips, i.e. negative short expectancy with squeeze-shaped tails,
on ~16 events/yr. Listed options reach only the top ~70 names; every
derivative inherits the borrow wall through its hedger. The −40% cohort
lives exclusively where no instrument reaches — and delisting censorship
means the true number is *worse*. The result survives precisely because it
cannot be traded. Its value is informational: **a raise announced deep below
the 52-week high is among the most reliable disaster flags on the exchange.**

## 5. Behavior around the raise

- **The drumroll:** healthy raisers ramp news flow +30% (accelerating) and
  promotional tone (t = +2.60) over the six months into a placement;
  distress raisers show no ramp — they raise when they must. Disclosure
  management, visible in metadata alone.
- **The pipeline:** 33.9% of feasibility/FID/offtake milestones are followed
  by a raise within 91 days (~5–7× base; median lag 33 days). Project
  financing telegraphs itself a month ahead — a dilution early-warning for
  holders; not a profitable front-run (both entry points tested flip
  negative out-of-time).
- **Director participation:** 51% of raises see director buying within 45
  days (vs 32% expected, z = +5.48) — whole boards, median $30k, zero
  forward information. Governance custom, not signal.
- **The portrait (blinded LLM on headlines):** best-quartile raises are
  *developers advancing a named project* (83% specific use of proceeds,
  cornerstone partners); worst-quartile are *narrative and survival raisers*
  (23% survival-purpose, problems visible pre-raise 15% vs 0%). Post-raise
  headline tone is uniformly positive across ±100pp of outcomes — the
  market funds projects and punishes stories, and tells you which is which
  in the filing, never in the adjectives.

## 6. What survives

Three tools: a dilution-risk model (who raises, AUC 0.75), a disaster flag
(distress raises), and a relative quality ranking (~20pp/quarter of
separation among raises, both regimes). Zero absolute trades. One frozen
forward test (PR-004). And a methods exhibit we believe is rare in public
work: the same strategy run on survivor and honest universes 24 hours
apart, pricing survivorship bias at ~26pp per event.

## Caveats

Two years, one regime change (2026 inverted every raise-adjacent long);
delisting censorship in the full-market sample (strengthens the distress
finding, weakens any long claim); regex-defined events (raise sizes and
discounts not extracted — the natural next data layer); yfinance microcap
price quality bounded by explicit guardrails. Nothing here is investment
advice; the study trades nothing but a paper account.
