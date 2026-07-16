# Paper 02 — The Graveyard: Five ASX Anomalies That Aren't There

**Status:** DRAFT v1 (2026-07-16) · **Data:** 1,440 LLM-extracted earnings
records + 4,743 director trades + 890 role notices, ASX 200/300, 2024–26
**Author:** Taylor Hobbs · Specs frozen before execution: docs/analysis-plan-2026-07-earnings.md

## Abstract

Five popular announcement anomalies, each tested with a specification —
cohort, endpoint, success threshold — frozen *before* the test ran, under a
shared Bonferroni family (significance required t ≥ 2.41). **Zero survived.**
Post-earnings-announcement drift is inconclusive-at-best and absent exactly
where folklore puts it; dividend cuts are fully priced by lunchtime; insider
dip-buying after crashes is near-reflexive and carries no recovery
information; CEO transitions are noise; and the executive-seller theory died
twice — once on returns, once on its own labels. These nulls are the study's
credibility: they are what make the one surviving lead (Paper 01) something
other than a cherry-picked cell. A unifying reading emerges: **ASX 200
announcement news is priced the day it lands — down instantly and completely,
up with a mild, unconfirmed one-month echo.**

## 1. Method: nulls by design, not by accident

Every test below pre-specified its universe, event definition, endpoint, and
verdict thresholds in a committed document before execution. Three primary
endpoints shared one Bonferroni correction (p < 0.05/3 → t ≥ 2.41). Machinery
identical to Paper 01: day-0 = first tradeable day (pre-16:00 Sydney rule),
market-adjusted returns vs XJO, full +1..+63 windows required, exclusions
counted. Multi-document results days collapsed to the best-extracted document.

## 2. ES-1 — Post-earnings-announcement drift: INCONCLUSIVE

712 results-day events, quintiled by the market's own day-0 reaction (no
consensus data exists for the ASX at retail — the reaction *is* the surprise):

| quintile | day-0 | CAR +1..+63 | t |
|---|---|---|---|
| Q1 worst | −9.5% | −0.6% | −0.39 |
| Q2 | −2.1% | +4.2% | +2.56 |
| Q3 | +0.4% | +0.6% | +0.40 |
| Q4 | +2.9% | +3.4% | +2.12 |
| Q5 best | +9.2% | +3.1% | +1.65 |

Primary endpoint Q5−Q1: **+3.7%, Welch t = +1.51** — under even a nominal
bar; the per-season spread flips sign in 2026Q1 (+9.2/+2.7/+2.8/−3.5%). The
informative negative: **stocks that crash ~9.5% on results day show zero
further drift and zero reversal.** Bad news is a one-candle repricing. The
only pulse is exploratory and un-prespecified: winners drift +3.6% in days
+1..+21, then stop — underreaction to good news, not bad.

Secondary: extracted YoY changes barely predict the reaction (Spearman
+0.12) — the market trades against expectations that are not in the filing.
A +250% YoY result falls as often as it rises.

## 3. ES-2 — Dividend-cut drift: REFUTED

509 events with stated dividend pairs (101 cuts, 4 omissions, 82 holds,
322 raises). Cuts are noticed on day 0 (−1.6%) and then: CUT−HOLD spread
over the next quarter **+0.1%, t = +0.04** — as null as arithmetic allows.
The one echo: raises drifted +1.6% (within-group t = +2.22; vs holds t =
1.07, ns) — rhyming with ES-1's upside underreaction, at the same
not-significant tier.

## 4. ES-3 — Insider dip-buying: REFUTED (and the best descriptive fact)

Of 112 results-day crashes (day-0 ≤ −5%), directors bought within 30 days
after **45%** of them — dip-buying is close to a reflex. And precisely
because it is a reflex, it carries nothing: bought crashes recovered
**−0.1%** vs **+1.7%** for ignored crashes (Welch t = −0.48). Directors
bought into XRO (−49.7% afterwards) and COH (−66.5%). Buying the dip is what
a director does to signal confidence, not what a director does when they
know something.

## 5. EX-4 — CEO/MD transitions: nothing

63 appointment/cessation events from primary-document role extraction:
appointments +4.2% (t = +1.38), cessations +5.6% (t = +1.57) — both
indistinguishable from the corpus's survivorship-positive base drift. One
anecdote (WTC −40.8% post-cessation), no pattern.

## 6. The exec-seller theory: dead twice

Enriching 179 selling directors with LLM world-knowledge role labels
suggested executives' sales carried extra signal. Two deaths: (1) role adds
nothing — the exec × clean × large cell is *weaker* than unconditioned; the
"three converging lenses" were the same few events counted three times;
(2) the labels themselves were only **72% correct** against primary
appointment documents, with systematic failure modes (Paper 03, §3).

## 7. What the graveyard means

A market that prices results, dividends, insider gestures and board changes
same-day is the *hostile environment* any surviving claim must be read
against. Two footnotes for future work, both shelved as hypotheses, neither
claimed: small-cap post-results sells at −6.0% (t = −2.78, one cell of an
exploratory grid) hint that PEAD may live below the attention line; and
every quintile in every table sits above zero — the visible signature of a
today's-constituents universe, and the standing argument for delisting-aware
data before anything here is called final.

## Caveats

One results cycle of seasons; overlapping event windows make pooled t-stats
optimistic; no consensus estimates (surprise proxied by reaction); prototype
prices; universe survivorship lifts all levels (spreads partially immune).
Pre-specification limits, but does not eliminate, the garden of forking
paths — which is why the thresholds were set before the data was touched.
