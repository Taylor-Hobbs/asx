"""Run event studies: events × prices -> CAAR tables with test statistics.

    uv run python -m asx_engine.events.study_runner

The assembly layer around the pure core in event_study.py. Decisions made
here, once, for every study:

- **Day 0** is the first trading day on which the announcement was tradeable:
  released before 16:00 Sydney on a trading day -> that day; after the close
  or on a non-trading day -> the next trading day. Coarse (intraday precision
  needs tick data we don't have) but honest — never a day the market couldn't
  have reacted on.
- **Alignment is pairwise on real observations.** A stock's returns are
  joined to the index's by date; days where either side is missing drop out.
  No forward-filling, no imputation — a thin stock just contributes fewer
  observations, and the minimum-coverage guard drops it if too few.
- **Windows** in trading days relative to day 0: estimation [-120, -21],
  event [-5, +20]. The gap (-20..-6) belongs to neither — run-up
  contamination stays out of the estimation sample.
- Events whose windows don't fit (too near the price history's edges, ticker
  missing from prices) are counted and reported, never silently dropped.

First hypotheses on the board: on-market purchases vs on-market sales — the
classic insider-signal pair, filtered on nature so plan-driven grants,
vestings and DRP allotments don't dilute deliberate trades.
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import structlog
from dotenv import load_dotenv
from google.cloud import bigquery

from asx_engine.config import Settings, load_settings
from asx_engine.events.director_trades import EVENTS_TABLE
from asx_engine.events.event_study import CohortStats, EventResult, aggregate_cohort, study_event
from asx_engine.prices.loader import INDEX_TICKER, PRICES_TABLE

log = structlog.get_logger()

SYDNEY = ZoneInfo("Australia/Sydney")
MARKET_CLOSE_HOUR = 16

ESTIMATION = (-120, -21)  # trading-day offsets, inclusive
EVENT = (-5, 20)
MIN_ESTIMATION_OBS = 60

COHORTS: dict[str, str] = {
    "on-market purchases": ("trade_type = 'acquisition' AND LOWER(nature) LIKE '%on-market%'"),
    "on-market sales": ("trade_type = 'disposal' AND LOWER(nature) LIKE '%on-market%'"),
}


@dataclass
class CohortReport:
    name: str
    stats: CohortStats | None
    studied: int
    skipped_no_prices: int
    skipped_window: int


def day_zero(announced_at: datetime, trading_days: pd.DatetimeIndex) -> pd.Timestamp | None:
    """First trading day the announcement was tradeable, or None past the data."""
    local = announced_at.astimezone(SYDNEY)
    date = pd.Timestamp(local.date())
    if local.hour >= MARKET_CLOSE_HOUR:
        date += pd.Timedelta(days=1)
    idx = int(trading_days.searchsorted(date))  # first trading day >= date
    if idx >= len(trading_days):
        return None
    return pd.Timestamp(trading_days[idx])


def slice_windows(
    aligned: pd.DataFrame, day0: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """(estimation rows, event rows) around day0, or None if they don't fit.

    `aligned` is one ticker's (stock, market) return pairs indexed by date —
    only days where BOTH traded, so offsets count real observations.
    """
    pos = int(aligned.index.searchsorted(day0))
    if pos >= len(aligned.index) or aligned.index[pos] != day0:
        return None  # day0 isn't an observation for this stock (halt, gap)
    est_lo, est_hi = pos + ESTIMATION[0], pos + ESTIMATION[1]
    evt_lo, evt_hi = pos + EVENT[0], pos + EVENT[1]
    if est_lo < 0 or evt_hi >= len(aligned):
        return None  # window runs off the data's edge
    estimation = aligned.iloc[est_lo : est_hi + 1]
    if len(estimation) < MIN_ESTIMATION_OBS:
        return None
    return estimation, aligned.iloc[evt_lo : evt_hi + 1]


def load_returns(
    bq: bigquery.Client, dataset: str
) -> tuple[dict[str, pd.DataFrame], pd.DatetimeIndex]:
    """(ticker -> (stock, market) return pairs on shared dates, market calendar)."""
    prices = bq.query_and_wait(
        f"SELECT ticker, date, adj_close FROM `{dataset}.{PRICES_TABLE}` "  # noqa: S608
        "ORDER BY ticker, date"
    ).to_dataframe()
    prices["date"] = pd.to_datetime(prices["date"])
    wide = prices.pivot(index="date", columns="ticker", values="adj_close")
    returns = cast(pd.DataFrame, np.log(wide)).diff().iloc[1:]
    market = returns[INDEX_TICKER].dropna().rename("market")
    out: dict[str, pd.DataFrame] = {}
    for ticker in returns.columns:
        if ticker == INDEX_TICKER:
            continue
        stock = returns[ticker].dropna().rename("stock")
        out[ticker] = pd.concat([stock, market], axis=1, join="inner")
    return out, pd.DatetimeIndex(market.index)


def run_cohort(
    name: str,
    events: pd.DataFrame,
    returns: dict[str, pd.DataFrame],
    trading_days: pd.DatetimeIndex,
) -> CohortReport:
    results: list[EventResult] = []
    skipped_no_prices = skipped_window = 0
    for row in events.itertuples():
        ticker = cast(str, row.ticker)
        announced_at = cast(datetime, row.announced_at)
        aligned = returns.get(ticker)
        if aligned is None or aligned.empty:
            skipped_no_prices += 1
            continue
        day0 = day_zero(announced_at, trading_days)
        windows = slice_windows(aligned, day0) if day0 is not None else None
        if windows is None:
            skipped_window += 1
            continue
        estimation, event = windows
        results.append(
            study_event(
                estimation["stock"].to_numpy(),
                estimation["market"].to_numpy(),
                event["stock"].to_numpy(),
                event["market"].to_numpy(),
            )
        )
    stats = aggregate_cohort(results) if results else None
    return CohortReport(
        name=name,
        stats=stats,
        studied=len(results),
        skipped_no_prices=skipped_no_prices,
        skipped_window=skipped_window,
    )


def print_report(report: CohortReport) -> None:
    print(f"\n=== {report.name} ===")
    print(
        f"  events studied: {report.studied}   "
        f"skipped: {report.skipped_no_prices} no prices, {report.skipped_window} window"
    )
    if report.stats is None:
        print("  (nothing to aggregate)")
        return
    stats = report.stats
    print(
        f"  BMP z = {stats.bmp_z:+.2f}  (p = {stats.bmp_p:.4f})  over days {EVENT[0]}..{EVENT[1]}"
    )
    print(f"  {'day':>4} {'meanAR':>8} {'CAAR':>8} {'Corrado z':>10}")
    for i, day in enumerate(range(EVENT[0], EVENT[1] + 1)):
        marker = " <- day 0" if day == 0 else ""
        print(
            f"  {day:>4} {stats.mean_ar[i] * 100:>7.2f}% {stats.caar[i] * 100:>7.2f}% "
            f"{stats.corrado_z[i]:>10.2f}{marker}"
        )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    load_dotenv()
    settings: Settings = load_settings()
    bq = bigquery.Client(project=settings.gcp_project)
    dataset = f"{settings.gcp_project}.{settings.bq_dataset}"

    returns, market_days = load_returns(bq, dataset)
    log.info("study.prices_loaded", tickers=len(returns), trading_days=len(market_days))

    for name, predicate in COHORTS.items():
        events = bq.query_and_wait(
            f"SELECT ticker, announced_at FROM `{dataset}.{EVENTS_TABLE}` "  # noqa: S608
            f"WHERE {predicate}"
        ).to_dataframe()
        log.info("study.cohort", name=name, events=len(events))
        print_report(run_cohort(name, events, returns, market_days))


if __name__ == "__main__":
    main()
