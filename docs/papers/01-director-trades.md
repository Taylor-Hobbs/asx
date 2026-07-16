# Paper 01 — Do ASX Director Trades Predict Returns?

**Status:** DRAFT v1 (2026-07-16) · **Study window:** Jul 2024 – Jul 2026 ·
**Universe:** ASX 200 (199 tickers), replication band ASX 201–300 (107 tickers)
**Author:** Taylor Hobbs · Full audit trail: BUILD_LOG.md; pre-registrations: docs/preregistrations.md

## Abstract

We collected every Appendix 3Y director-interest filing for the ASX 200 over 24
months (3,232 documents, 4,743 trades, 1,040 directors), extracted them with an
LLM benchmarked at 93.1% field accuracy against hand-labeled goldens, and tested
whether director trading predicts returns. **Headline conclusion: no confirmed
edge.** Director purchases are placebo-confirmed noise at every horizon. Director
sales appeared — naively — to precede a −7.1% abnormal fall (z = −7.48); under
adversarial testing that result decomposed into three self-inflicted artifacts.
One residual survived seven attacks: large ($1M+), freely-timed sales precede
~−5–6%/quarter of idiosyncratic underperformance in large caps — then **failed
out-of-band replication** on the ASX 201–300, where the same filter selects
*momentum*, not information. The lead survives only as a domain-bounded,
in-sample hypothesis, now deployed to three pre-registered forward tests that
will settle it by mid-2027. The study's strongest products are its nulls, its
self-caught artifacts, and a mechanism finding: below ~$2B of market cap, a
large on-market sale is only *executable into strength* — the same filter means
opposite things at opposite ends of the exchange.

## 1. Pipeline and data

- 24 months × 199 tickers → 3,234 filings crawled (of ~45,000 announcements
  inspected), 3,232/3,233 extracted (Haiku batch, ~$12), prompt
  `director_trades_v3` at **93.1%** on a 28-filing / 36-trade golden set
  (detection 94.6%, dates/quantities/types ≥97%).
- 4,743 trades: 3,396 acquisitions, 1,057 disposals, **250 transfers** — the
  TRANSFER class exists because forcing custodial reorganizations into
  buy/sell would fabricate directional events (5% of all trades).
- Event store anchored on the ASX release timestamp, never the trade date
  (up to 5 business days of disclosure lag = lookahead otherwise).
- Prices: yfinance daily (prototype-grade, disclosed), market = XJO.

## 2. First results

| cohort | n | CAAR(−5..+20) | BMP z | verdict |
|---|---|---|---|---|
| on-market purchases | 1,254 | +0.45% | +0.12 | null |
| on-market sales | 397 | −7.10% | −7.48 | artifact — see §3 |

Purchases stayed null at every horizon and against a 1,000-draw placebo.
A descriptive fact frames everything: the median on-market buy is **~$48k**
(identical in the 201–300 band: $49k) while the median $1M-filter sale is
$1.15M; $1M+ buys vs sells run 18:110. *Sells are financial decisions; buys
are communications.*

## 3. The decomposition of the sales "signal"

1. **Window double-counting.** Only 201 of 397 sale events were distinct
   episodes (one director at WTC filed 26 times). Dedup: −7.1% → −3.07%,
   z −7.48 → −2.57. The first z was inflated ~2.3×.
2. **Alpha extrapolation.** Directors sell after run-ups; market-model
   estimation fits a high alpha which, extrapolated 63 days, manufactures
   negative "abnormal" returns. Simple market-adjusted returns: −1.23% (ns).
   But the same tickers drift +3.90%/63td on random dates — the conditional
   effect vs own drift is ≈ −5 points at placebo percentile 2.6. A built-in
   control corroborates: 143 zero-information custodial transfer filings
   behave exactly like random dates (+3.5%).
3. **Reporting-season momentum.** A seasonal proxy suggested all drift was
   post-results momentum. Buying exact results dates (1,500 filings) showed
   the proxy was too coarse — and inverted it: post-results sales carry
   nothing; the drift concentrates in **large, freely-timed sales**
   (−5.7%/qtr, t = −2.15, n = 28), the theoretically-predicted cell.

## 4. Seven attacks the residual survived

Run-up-matched controls (−4.46%, p≈0.09); cross-sectional regression (only
repeat-seller significant); bootstrap CI spanning zero noted; **sector
adjustment strengthened it** (−6.2%, t = −2.73, 21/31 negative — not a gold
artifact, despite the standout event decomposing into a gold-sector drawdown);
an earnings-mechanism test **failed to find a mechanism** (post-sale results
were *better* than the corpus: 5/26 NPAT declines vs 36% expected, zero
dividend cuts); a retirement purge removed only 2/31 events (−5.7%, t=−2.24);
role of the seller adds nothing (and the LLM-knowledge role labels behind the
exec hypothesis were only 72% correct against primary documents — see Paper 03).

## 5. The replication that failed — and what it taught

**REP-1** (spec frozen and committed before any new-ticker data): the identical
cell on the ASX 201–300 band returned **+14.9% (t = +3.10, 8/10 positive) —
UNSUPPORTIVE.** Not merely absent: inverted. The cap gradient makes it
coherent: the trailing effect is monotone in market cap (−9.4pp per 10× of
cap raw; −5.8pp vs each stock's own baseline), crossing zero near **~$2B**.
Mechanism: below ~$2B, a $1M+ on-market sale is only *executable into
strength* — someone must be buying — so the filter selects momentum
situations; above it, the sale is a frictionless free choice. **The same
screen measures opposite things at opposite ends of the exchange.** (The
band's survivorship updraft — today's-constituents universe — inflates its
positive numbers; the *absence* of negative drift is the substantive result.)

## 6. Disclosure hygiene (descriptive)

- Directors respect blackout windows almost perfectly: 2.9% of trades within
  30d *before* results vs 50.9% within 30d after.
- Late filing (LR 3.19B, 5 business days): 4.0% in the ASX 200 — but
  disposals are late ~3× as often as acquisitions (7.8% vs 2.8%) and $1M+
  trades 10.2% — the deadline leaks precisely where information lives. Below
  the ASX 200, late filing doubles (9.8%). Extreme lags (up to 523 business
  days) require PDF verification before naming individuals.

## 7. Strategy reality check

In-sample calendar-time backtests of the naive short: Sharpe 0.23, maxDD
−33.7%. Sector-hedged variant: Sharpe 0.67, maxDD −15.5% — best of three
tried, in-sample, selection-biased; honest prior well below. A unified
cross-sectional model (Paper 04, §8) shows announcement features add +0.003
rank IC over price features — the lead is an event-time claim, not a factor.

## 8. What settles it

Three frozen pre-registrations (docs/preregistrations.md, all timestamped in
git before their test data existed):

- **PR-001** — off-season director purchases (evaluates ≥ 2027-07-09).
- **PR-002** — the sales strategy on an IBKR paper account (A$10k/position,
  63td hold, STW hedge, skip-logs as deliverables).
- **PR-003** — the scale-invariant restatement (top-100 by cap, sale ≥ 0.5bps
  of cap), evaluates ≥ 2027-07-15.

## Caveats (the point, not the fine print)

In-sample discovery window with accumulated scan debt; today's-constituents
universe (survivorship measured, not assumed: it is worth ~+3.5%/qtr in the
band); yfinance prices; n = 31 in the surviving cell; mechanism unknown after
five candidate mechanisms were tested and eliminated. Paper trading only; no
live capital, ever.
