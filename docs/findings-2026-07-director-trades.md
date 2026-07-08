# Do ASX Director Trades Predict Returns? — Findings Report

**Study window:** July 2024 – July 2026 · **Universe:** 199 ASX 200 constituents
**Author:** Taylor Hobbs · **Report date:** 2026-07-09
**Status:** In-sample research complete. One pre-registered hypothesis (PR-001) pending out-of-sample evaluation ≥ 2027-07-09.

---

## 1. Executive summary

We built an end-to-end pipeline that collected every Appendix 3Y director-interest filing for 199 large-cap ASX tickers over 24 months, extracted the trades with an LLM benchmarked at **93.1% field accuracy**, and tested whether director trading predicts returns.

**Conclusion: no identifiable edge.** Director purchases are uninformative at every horizon. Director sales appear — under naive analysis — to precede a **−7.1%** abnormal fall with z = −7.48; under adversarial testing that result decomposes entirely into three artifacts: (1) double-counted overlapping event windows from serial sellers, (2) alpha-extrapolation bias in the market-model benchmark, and (3) reporting-season momentum (directors mechanically sell when trading windows open after results; the drift belongs to the results). A built-in placebo — directors' zero-information custodial transfer filings — behaves exactly like random dates, confirming the method distinguishes real from fake effects.

Two sub-significant leads survive for future work: sales by executives/founders (n = 12, −6.4%/quarter), and freely-timed purchases (+2.5%/quarter, t = 2.49, discovered by scanning and therefore **pre-registered** rather than claimed).

---

## 2. The dataset

| item | value |
|---|---|
| Filings crawled (Appendix 3Y family, 24 months) | 3,234 (from ~45,000 announcements inspected) |
| Parsed to text | 3,200/3,200, 100% good quality |
| Extracted (Haiku batch, director_trades_v3 prompt) | 3,232/3,233 · cost ≈ $12 (14.0M in / 2.0M out tokens) |
| Individual trades | **4,743** — 3,396 acquisitions · 1,057 disposals · 250 transfers |
| Distinct directors | 1,040 |
| Extraction accuracy (28-filing golden set, 36 trades) | **93.1%** overall; trade_type/date/quantity/class ≥ 96.9% |
| Event store | 4,743 events · 2,811 documents · 176 tickers, anchored on ASX release timestamp (never trade date — 5-business-day disclosure lag would be lookahead) |
| Prices (yfinance, prototype-grade) | 147,721 daily rows · 763 trading days · 190 tickers clean, 7 short-history, 3 missing (IFL, NSR, XYX) |

**On-market sales inventory:** 412 filings (106 tickers); 191 state consideration; **110 ≥ $1M**, 40 ≥ $5M. Largest: DRO $49.5M, ALK $42.0M, NWL (Heine family) 5 filings $22.5–32.0M, GMG $43.0M in one day, NWH $19.8M. Deduplicated to one episode per ticker/30 days: **~206 selling episodes (~49–57 at $1M+ depending on filter)**.

**Conviction asymmetry (descriptive finding):** ~110 sales over $1M vs **~5 purchases** that size. Median on-market buy: **$50k**; median $1M-filter sale: **$1.15M**. ASX directors sell with real money and buy with gestures.

---

## 3. Headline event-study results (market model, BMP + Corrado tests)

Estimation window [−120, −21] trading days; event window [−5, +20]; day 0 = first tradeable day (pre-16:00 Sydney → same day).

| cohort | n | CAAR | BMP z | p | verdict |
|---|---|---|---|---|---|
| On-market purchases | 1,254 | +0.45% | +0.12 | 0.91 | **null** |
| On-market sales | 397 | **−7.10%** | **−7.48** | <0.0001 | *artifact — see §4* |

---

## 4. The decomposition of the sales "signal"

### 4.1 Artifact 1 — double-counted windows
Only **201 of 397** sale events are distinct episodes (WTC filed 26 sale notices, HVN 21, DRO 18). Deduplicated: CAAR −7.1% → **−3.07%**, z −7.48 → **−2.57**. The naive z was inflated ~2.3×.

### 4.2 Artifact 2 — alpha extrapolation
Under simple market-adjusted returns (stock − index), the deduped $1M+ 63-day effect is **−1.23% (t = −0.54, ns)**; bootstrap 95% CI **[−6.30%, +2.81%]**. Diagnosis: directors sell after run-ups → estimation windows fit high alphas → extrapolating those alphas manufactures large negative "abnormal" returns when a winner merely stops winning. The earlier −11.7% (3mo, z = −4.28) and −16.1% (6mo, z = −3.06) figures were dominated by this bias.

### 4.3 What a placebo shows
The same tickers on 1,000 random dates drift **+3.90%** per 63 trading days (5th percentile −0.64%). Sale-timed windows: −1.23% → conditional effect ≈ **−5.1 points**, real observation at **percentile 2.6**. So the sale filings do mark *something* — the end of the outperformance the director had been enjoying — but see 4.5.

### 4.4 The transfer control (methodological contribution)
143 zero-information director filings (custodial/entity transfers, no change in beneficial interest — a category our schema captures deliberately): **+3.53% (t = +2.02)**, indistinguishable from the placebo baseline. Non-informative filings do not bend the curve; the method is not haunted.

### 4.5 Artifact 3 — reporting-season momentum (the decisive split)
Peak sale months are September 2025 (46 episodes) and September 2024 (42): trading windows open after August results. Seasonal proxy split (Feb/Mar/Aug/Sep = post-results):

| sales cohort | n | fwd 63d (mkt-adj) | t |
|---|---|---|---|
| Reporting season | 132 | **−2.2%** | −1.55 |
| **Off-season (freely timed)** | 95 | **+3.5%** | +2.10 |

The entire negative drift lives in post-results windows. Freely-timed sales — which should be the *most* informative if directors carry signal — show **none**. Post-earnings drift wearing a director-sale costume.

### 4.6 Run-up-matched control (the final falsification test)
Each $1M+ sale matched to a no-sale stock with near-identical prior 6-month run-up (+16.8% vs +16.3%): event fwd 63d **−1.68%** vs matched control **+2.78%** → sale-specific difference **−4.46%, paired t = −1.72 (p ≈ 0.09, n = 43)**. Not mere mean reversion — but not significant, and per §4.5 substantially earnings-entangled.

---

## 5. Cross-sectional structure (what carries the residual)

OLS: fwd63 ~ pre-drift + log(size) + repeat-seller + disclosure-lag (n = 81):

| predictor | coefficient | t |
|---|---|---|
| pre-event drift | +0.115 | +1.90 |
| log sale size | −0.022 | **−0.89 (size carries nothing)** |
| **repeat seller** | **−0.084** | **−2.07** |
| disclosure lag | +0.0003 | +0.47 |

Sale *size* is not informative once you control for *who* is selling — the "$1M+" effect was partly proxying serial sellers. But "repeat seller" splits into opposite populations:

- **Deteriorating-situation sellers:** Richard White/WTC −13.6% (n=4), Eric Rose −12.6%, Ian Narev/SEK −8.5%, Owen Wilson/REA −8.5%. Worst tickers: COH −11.1% (n=7), WTC −9.9%, SEK −9.2%, REA −8.5%.
- **Programmatic sellers (no signal):** Heine family/NWL +7.3–9.4% (n=7), NWH +10.1% (n=7).

**Role slice:** only 12/227 episodes have identifiable roles (bare 3Y forms carry none — verified during labeling). Those 12 executive sales: **−6.4% (median −8.6%, t = −1.80)** vs +0.6% for the unknown pool. Three independent lenses point at *executive/founder repeat-sellers at high-multiple stocks* as the surviving lead — all at anecdote-grade n.

**Failed sharpeners:** multiple sellers within 30d no better than lone (−0.5% vs +0.3%); selling ≥50% of stake is *positive* (+4.5% — retirements); filing speed irrelevant (fast −1.1% vs slow +0.4%); no hold-period plateau (42d −0.8%, 63d −1.2%, 84d +0.9%); volume at filing only 1.15× normal (the market barely notices).

---

## 6. Tradeability (in-sample prototypes — upper bounds on nothing)

57 deduped $1M+ signals; short at day-0 close, 63-day hold, 20bps/side:

| implementation | ann. | Sharpe | maxDD | by year |
|---|---|---|---|---|
| Short vs index | +3.7% | 0.23 | −33.7% | −0.3% / −11.4% / +22.9% |
| Short vs sector basket | +8.2% | **0.67** | −15.5% | +1.7% / +3.7% / +19.3% |
| Short sales + long buys | +2.6% | 0.33 | −12.8% | ~flat |

Hit rates ($1M+, deduped): raw price fell in only **53–58%** of cases (market rose over the sample); **underperformed the market in 77%** (33/43) at 3 months, 75% (27/36) at 6 months. The signal, such as it was, is relative — and per §4, mostly seasonal. The Sharpe 0.67 inherits every artifact above plus selection bias (best of three variants) and is not believed.

---

## 7. Purchases in full

- Event study: null (z = +0.12). Directors buy after dips (−0.8% pre-event drift) — contrarian, uninformative.
- Horizon grid (489 deduped): ns at 1wk–3mo; +11.8% at 1yr (z = +3.20) — but placebo shows these tickers drift +5.3%/yr anyway → real at percentile 91 (**p ≈ 0.09, not significant**), plus long-horizon method weaknesses (bad-model compounding, survivorship, overlap). Hypothesis dead.
- Seasonal split: reporting-season buys +0.2% (n = 521, ns); **off-season buys +2.5% (n = 321, t = +2.49)** — the mirror-image structure of sells, in the direction *supporting* signal (free-choice trades informative). Found as ~cell 40 of a scan → **pre-registered as PR-001** (commit `f4ad668`): off-season buys > +1.0% with t ≥ 2.0 on filings dated ≥ 2026-07-09 only, evaluation ≥ 2027-07-09, criteria frozen.

---

## 8. Limitations

Universe = today's ASX 200 (survivorship; 3 tickers already unpriceable — exactly the stocks that crash); yfinance prototype prices (EODHD gates anything published); seasonal proxy not exact earnings dates (broad crawl pending); role data absent for 95% of sellers; consideration stated on only 191/412 sales; entire analysis in-sample of its own discovery window; dozens of cells scanned (all p-values face a multiple-testing discount, applied qualitatively throughout).

## 9. Conclusions

1. **No identifiable edge in ASX 200 director trades, 2024–26.** Purchases: null. Sales: three stacked artifacts and no signal in freely-timed trades.
2. **The signal class manufactures false edges with unusual ease** — every correction moved the result toward zero; the naive analysis (z = −7.5) would survive most retail backtests and some academic referees.
3. **Methodological contributions:** the transfer-filing placebo; announcement-time (not trade-time) anchoring with disclosure-lag tracking; extraction with per-field audit trails at 93.1% benchmarked accuracy.
4. **Descriptive findings:** 20× conviction asymmetry (sell big, buy small); disclosure makes insider information stale by up to 5 business days; the market barely reacts to these filings (1.15× volume).
5. **Open, honestly-labeled leads:** executive/founder repeat-sellers (needs role enrichment); PR-001 (off-season buys, out-of-sample verdict 2027).

*Every number reproducible from the repo: eval runs in BigQuery, prompts versioned, session log in BUILD_LOG.md.*
