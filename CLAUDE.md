# ASX Announcement Alpha Research — Project Context (v3)

> Drop this file in the repo root as CLAUDE.md so Claude Code sessions inherit full context.
> **v3 supersedes v1/v2.** The project identity changed: the old "intelligence engine"
> was descriptive and explicitly *forbade* trading; this version makes a **paper-trading
> endpoint the goal**. Where v2 and v3 conflict, v3 wins.

## What this project is

An end-to-end quant **research study** that rigorously tests whether ASX announcement
data contains *exploitable, tradeable signal*, validated in a **paper (simulated)
environment**. The arc: idea generation → data collection → LLM extraction → hypothesis
generation → safe testing.

**The deliverable is the documented study itself**, including honest negative results.
A rigorously-reached "no edge after costs" is a successful outcome. Target quality bar:
**done, honest, and public** — not journal-grade, not perfect.

## The boundary (this REPLACES the old no-trading rule)

- Research + **simulated/paper trading only**. The endpoint is an **IBKR paper account**. **No live capital, ever.**
- If the owner proposes deploying **real money / live trading**: flag the line. Paper is the goal; real capital is a separate, much higher bar.
- **Rigor is the defense against self-deception.** Once the goal is "beat the market," sloppiness stops producing harmless wrong numbers and starts producing a *fake edge you believe in*. If a signal looks real, remind: backtest ≠ live, and paper fills are optimistic.

## Owner context

Taylor, 22, Deloitte analyst (MDT) in Melbourne. Highest-EV path assessed as
**founder-operator**; no business idea yet and not forcing a half-baked one.

This project's job is to **sharpen skills, build a public image, and bank credibility
while between ventures.** It is **not** an academic stepping stone — the UK postgrad
route was explored and deprioritised.

It is a **whetstone / side-quest. Time-box it.** It must not balloon into an
academic-grade opus, must not become a comfortable substitute for the founder leap, and
must not eat the focus the eventual business will need. Strong product velocity
(React/Node/Postgres); still closing gaps in Python, data engineering, LLM evaluation,
and quant methods — teach non-obvious idioms when introducing them.

## Scope decisions (settled this cycle)

**Universe:** ASX 300, ~12–24mo backfill, collect forward. Small-caps are a known
frontier (stronger signals, messier, harder to trade) — *not* in first scope.

**Announcement set (the hypothesis menu):**
- **Tier 1 (core):** periodic results (Appendix 4E/4D/4C) · guidance/trading updates/profit warnings · director trades (Appendix 3Y) · capital raisings (placements/rights/SPP) · M&A (Ch.6) · material contracts.
- **Tier 2 (subsets):** substantial holder notices (Forms 603/604/605) · index changes (S&P/ASX rebalances) · buy-backs (Appendix 3C) · sector binaries (drilling/JORC, clinical/TGA-FDA) → **phase two**.
- **Context (collect for correctness, not signal):** trading halts & suspensions · security issuance (Appendix 3B/2A).
- **Exclude (admin noise):** registry/address changes, constitution amendments, proxy/meeting procedurals, cleansing notices.

Use the issuer **price-sensitive flag as a first filter but don't trust it** — collect
known-signal categories even when unflagged (3Y often isn't). Flag-vs-content divergence
is itself a finding.

**Build order by extractability (clean → hard):** 3Y → substantial holders → capital
raises → M&A → results/guidance → sector binaries. **Director trades is the flagship
first vertical slice — build it end-to-end before going wide.**

## Data sources & tooling (decided)

- **Announcements:** own thin Python client against the ASX JSON endpoints (pyasx as a *reference to read, not a dependency*). Metadata → BigQuery; PDFs → Cloud Storage (cached, rate-limited, idempotent, resumable).
- **Redistribution rule (preserved):** raw PDFs in a private bucket only, never in the repo; golden set published as ticker + date + announcement ID + our labels.
- **Extraction:** parse PDF text **locally** and send text, not raw PDFs (far cheaper). Claude API via **Batch API (50% off) + prompt caching**; Haiku for bulk, Opus/Sonnet for the golden-set baseline.
- **Price data:** yfinance for prototyping → **EODHD (~€20/mo, adjusted + delisting-aware + bulk)** before ANY published backtest. Corporate-actions adjustment and survivorship are *correctness* issues — capital raises are an event type, so mis-adjustment fabricates abnormal returns.
- **Paper broker:** **Interactive Brokers** (TWS API via `ib_insync`). **NOT Alpaca** — Alpaca is US-only and cannot trade ASX.
- **Cost envelope:** ~$120 one-off extraction backfill (Haiku batch) + ~$10/mo real-time + ~€20/mo EODHD from Q2 (+ optional ~$50–300 fine-tune). IBKR paper is free. The expensive input is time, not infra.

## The four quarters

- **Q1 — Data collection & extraction:** Tier-1 announcements → structured, signal-oriented features; finalise taxonomy; golden set + extraction-accuracy eval vs a frontier baseline.
- **Q2 — Point-in-time store & hypothesis generation:** leakage-free event store; event studies (market model + BMP + Corrado rank + multiple-testing correction) → a **ranked hypothesis shortlist**; leakage audit v1.
- **Q3 — Signal construction & costed historical backtest (the core):** formal signal definitions; self-built simulator with realistic frictions (transaction costs, spreads, liquidity limits, execution lag); strategy metrics (return, Sharpe/Sortino, max drawdown, hit rate, turnover, capacity) vs ASX 200; walk-forward; robustness + decay. *Optional:* fine-tuned cheap extraction model.
- **Q4 — Forward paper validation & the written study:** deploy surviving signals to the IBKR paper account; forward out-of-sample run; backtest-vs-forward comparison; capacity/decay; the documented study. **Calendar-bound — can't be rushed; let it tick over while focus goes to the business.**

## Rigor checklist (non-negotiable — credibility depends on these)

- [ ] Point-in-time; anchor to precise release timestamps; no lookahead.
- [ ] No survivorship; include delisted tickers / historical constituents.
- [ ] Realistic costs, modelled **more pessimistically** than paper fills.
- [ ] Walk-forward / out-of-sample; never random splits.
- [ ] One held-out test set, touched once; FDR/Bonferroni or deflated Sharpe.
- [ ] Report nulls as loudly as positives.
- [ ] Backtest ≠ live; paper fills are optimistic. Forward paper validates *timing*, not execution realism.
- [ ] No live capital. Paper only.

## Engineering standards (preserved)

Tests on all parsing, schema, and return-computation logic; CI green. Prompts are
versioned artifacts, never inline strings. Every eval run logged and reproducible
(model, prompt version, dataset version, timestamp). Ingestion idempotent and resumable;
announcements immutable once stored (content-hash keyed). Public repo from day one —
no secrets, no raw PDFs, no redistributed ASX content. Repo must survive a 30-minute
inspection: clear README, architecture doc, eval methodology doc, leakage audit (Q2+).

## Working style for Claude Code sessions

- Teaching-quality implementations over clever ones. Present a tradeoff and recommend — don't silently pick.
- Maintain **BUILD_LOG.md** each session (what was built, what broke, what evals showed) — it feeds public posts, which are load-bearing for the credibility/public-image goal.
- Flag anything that smells like lookahead, survivorship, revision, or temporal leakage immediately, in any quarter.
- Keep it **finished-and-honest, not academic-infinite.** If scope is ballooning past "credible flex," say so.
- If the owner proposes **live capital / real-money trading**: flag the line (paper only). If a passing backtest tempts real money: remind that backtest ≠ live.

## Differentiation / context

Commercial summarisers exist (Ask Anna, Stockify) and director-trade trackers exist
(e.g. ASX Insider Tracker / asxdirectortrades, asxinsider.com.au). **None publish
rigorous, leakage-audited, costed backtests** — that gap is the entire differentiation.

Publishing aspiration (a cherry, not the goal): GitHub repo + write-up → Quantocracy
feature → SSRN / arXiv q-fin preprint. Academic conferences (FIRN, AFBC alt-data prize)
noted but the academic route is deprioritised.
