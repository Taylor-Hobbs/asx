"""Signal selection for PR-002 — pure functions, no I/O.

The spec is FROZEN (docs/preregistrations.md PR-002). These functions encode
it and nothing else: on-market disposals >= A$1M, >30 calendar days since the
ticker's last results filing, one entry per (ticker, director) per 30 days,
entries taken at the next open within 5 calendar days of filing, exits after
63 trading days. Every rejection carries its reason so the skip log — itself
a deliverable of the forward test — is honest by construction.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum

NOTIONAL_AUD = 10_000
MIN_CONSIDERATION = Decimal(1_000_000)
CLEAN_GAP_DAYS = 30
DEDUP_DAYS = 30
MAX_STALE_DAYS = 5
HOLD_TRADING_DAYS = 63
MAX_CONCURRENT = 12


class SkipReason(StrEnum):
    SIZE = "below_1m"
    NO_RESULTS_DATE = "no_results_date"
    NOT_CLEAN = "within_30d_of_results"
    DUPLICATE = "dedup_30d"
    ALREADY_OPEN = "already_open"
    STALE = "stale_gt_5d"
    CAP = "max_concurrent"


@dataclass(frozen=True)
class SaleFiling:
    """One on-market disposal as it appears in the event store."""

    ticker: str
    director: str
    filed: date  # Sydney date the market learned of it (announced_at)
    consideration: Decimal | None


@dataclass(frozen=True)
class OpenPosition:
    ticker: str
    director: str
    entry_date: date


@dataclass(frozen=True)
class Entry:
    ticker: str
    director: str
    filed: date
    gap_days: int
    size_aud: int = NOTIONAL_AUD


@dataclass(frozen=True)
class Skip:
    ticker: str
    director: str
    filed: date
    reason: SkipReason


def _key(ticker: str, director: str) -> tuple[str, str]:
    return ticker.upper(), (director or "").strip().casefold()


def clean_gap(filed: date, results_dates: list[date]) -> int | None:
    """Calendar days since the most recent results ON OR BEFORE the filing.

    None when the ticker has no results date on record — PR-002 treats that
    as a skip (gate unresolvable), never as a pass.
    """
    prior = [d for d in results_dates if d <= filed]
    return (filed - max(prior)).days if prior else None


def select_entries(
    filings: list[SaleFiling],
    results_dates: dict[str, list[date]],
    open_positions: list[OpenPosition],
    recent_entry_dates: dict[tuple[str, str], date],
    today: date,
) -> tuple[list[Entry], list[Skip]]:
    """Apply the frozen gates to candidate filings, oldest first.

    `recent_entry_dates` is the last entry date per (ticker, director) across
    the ledger's history — the dedup gate looks at entries ever taken, not
    just currently-open ones, so a re-filing five days after an exit still
    dedups against the original.
    """
    entries: list[Entry] = []
    skips: list[Skip] = []
    open_keys = {_key(p.ticker, p.director) for p in open_positions}
    last_entry = dict(recent_entry_dates)
    slots = MAX_CONCURRENT - len(open_positions)

    for f in sorted(filings, key=lambda f: f.filed):
        key = _key(f.ticker, f.director)
        if f.consideration is None or f.consideration < MIN_CONSIDERATION:
            skips.append(Skip(f.ticker, f.director, f.filed, SkipReason.SIZE))
            continue
        if (today - f.filed).days > MAX_STALE_DAYS:
            skips.append(Skip(f.ticker, f.director, f.filed, SkipReason.STALE))
            continue
        gap = clean_gap(f.filed, results_dates.get(f.ticker.upper(), []))
        if gap is None:
            skips.append(Skip(f.ticker, f.director, f.filed, SkipReason.NO_RESULTS_DATE))
            continue
        if gap <= CLEAN_GAP_DAYS:
            skips.append(Skip(f.ticker, f.director, f.filed, SkipReason.NOT_CLEAN))
            continue
        prior = last_entry.get(key)
        if prior is not None and (f.filed - prior).days <= DEDUP_DAYS:
            skips.append(Skip(f.ticker, f.director, f.filed, SkipReason.DUPLICATE))
            continue
        if key in open_keys:
            skips.append(Skip(f.ticker, f.director, f.filed, SkipReason.ALREADY_OPEN))
            continue
        if slots <= 0:
            skips.append(Skip(f.ticker, f.director, f.filed, SkipReason.CAP))
            continue
        entries.append(Entry(f.ticker.upper(), f.director, f.filed, gap))
        last_entry[key] = f.filed
        open_keys.add(key)
        slots -= 1
    return entries, skips


def exits_due(
    open_positions: list[OpenPosition], trading_days: list[date], today: date
) -> list[OpenPosition]:
    """Positions whose 63rd trading day has passed as of `today`.

    `trading_days` is the ascending market calendar (from daily_prices). A
    position entered on a date not in the calendar (halt day) counts from the
    next trading day, which is when its entry actually filled.
    """
    idx = {d: i for i, d in enumerate(trading_days)}
    if today not in idx:
        later = [d for d in trading_days if d >= today]
        if not later:
            return []
        today = later[0]
    t_now = idx[today]
    due = []
    for p in open_positions:
        entry_days = [d for d in trading_days if d >= p.entry_date]
        if not entry_days:
            continue
        if t_now - idx[entry_days[0]] >= HOLD_TRADING_DAYS:
            due.append(p)
    return due


def hedge_target_aud(n_open: int) -> int:
    """STW hedge notional: match total short notional (PR-002)."""
    return n_open * NOTIONAL_AUD


def stale_cutoff(today: date) -> date:
    return today - timedelta(days=MAX_STALE_DAYS)
