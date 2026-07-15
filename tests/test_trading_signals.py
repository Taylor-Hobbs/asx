"""The frozen PR-002 gates, pinned. Every gate has a test that would fail if
someone 'improved' the spec after registration."""

from datetime import date, timedelta
from decimal import Decimal

from asx_engine.trading.signals import (
    MAX_CONCURRENT,
    Entry,
    OpenPosition,
    SaleFiling,
    Skip,
    SkipReason,
    clean_gap,
    exits_due,
    select_entries,
)

TODAY = date(2026, 7, 14)
RESULTS = {"AAA": [date(2026, 2, 20)]}


def filing(
    ticker: str = "AAA",
    director: str = "Jane Doe",
    filed: date = TODAY,
    consideration: float | None = 2_000_000,
) -> SaleFiling:
    c = Decimal(consideration) if consideration is not None else None
    return SaleFiling(ticker, director, filed, c)


def run(filings, *, results=None, open_pos=None, recent=None, today=TODAY):
    return select_entries(
        filings,
        results if results is not None else RESULTS,
        open_pos or [],
        recent or {},
        today,
    )


class TestGates:
    def test_qualifying_sale_enters(self):
        entries, skips = run([filing()])
        assert entries == [Entry("AAA", "Jane Doe", TODAY, (TODAY - RESULTS["AAA"][0]).days)]
        assert skips == []

    def test_below_1m_skipped(self):
        _, skips = run([filing(consideration=999_999)])
        assert skips[0].reason is SkipReason.SIZE

    def test_null_consideration_skipped_not_passed(self):
        _, skips = run([filing(consideration=None)])
        assert skips[0].reason is SkipReason.SIZE

    def test_within_30d_of_results_skipped(self):
        _, skips = run([filing()], results={"AAA": [TODAY - timedelta(days=30)]})
        assert skips[0].reason is SkipReason.NOT_CLEAN

    def test_31d_after_results_enters(self):
        entries, _ = run([filing()], results={"AAA": [TODAY - timedelta(days=31)]})
        assert len(entries) == 1

    def test_no_results_date_skips_never_passes(self):
        _, skips = run([filing()], results={})
        assert skips[0].reason is SkipReason.NO_RESULTS_DATE

    def test_stale_filing_skipped(self):
        _, skips = run([filing(filed=TODAY - timedelta(days=6))])
        assert skips[0].reason is SkipReason.STALE

    def test_dedup_30d_same_director(self):
        recent = {("AAA", "jane doe"): TODAY - timedelta(days=10)}
        _, skips = run([filing()], recent=recent)
        assert skips[0].reason is SkipReason.DUPLICATE

    def test_dedup_expired_after_30d(self):
        recent = {("AAA", "jane doe"): TODAY - timedelta(days=31)}
        entries, _ = run([filing()], recent=recent)
        assert len(entries) == 1

    def test_already_open_skipped(self):
        pos = [OpenPosition("AAA", "Jane Doe", TODAY - timedelta(days=3))]
        _, skips = run([filing()], open_pos=pos)
        assert skips[0].reason is SkipReason.ALREADY_OPEN

    def test_cap_skips_when_full(self):
        pos = [OpenPosition(f"T{i:02d}", "X", TODAY) for i in range(MAX_CONCURRENT)]
        results = {"AAA": RESULTS["AAA"], **{f"T{i:02d}": [] for i in range(MAX_CONCURRENT)}}
        _, skips = run([filing()], results=results, open_pos=pos)
        assert Skip("AAA", "Jane Doe", TODAY, SkipReason.CAP) in skips

    def test_same_batch_dedup(self):
        entries, skips = run([filing(), filing(filed=TODAY - timedelta(days=1))])
        assert len(entries) == 1 and skips[0].reason is SkipReason.DUPLICATE


class TestCleanGap:
    def test_gap_counts_from_most_recent_prior_results(self):
        assert clean_gap(date(2026, 7, 14), [date(2026, 2, 1), date(2026, 6, 1)]) == 43

    def test_future_results_ignored(self):
        assert clean_gap(date(2026, 7, 14), [date(2026, 8, 1)]) is None


class TestExits:
    def test_exit_due_after_63_trading_days(self):
        days = [date(2026, 1, 1) + timedelta(days=i) for i in range(200)]
        p = OpenPosition("AAA", "Jane", days[10])
        assert exits_due([p], days, days[10 + 63]) == [p]
        assert exits_due([p], days, days[10 + 62]) == []

    def test_entry_on_halt_day_counts_from_next_trading_day(self):
        days = [date(2026, 1, 1) + timedelta(days=2 * i) for i in range(120)]
        p = OpenPosition("AAA", "Jane", days[5] + timedelta(days=1))  # not a trading day
        assert exits_due([p], days, days[6 + 63]) == [p]
        assert exits_due([p], days, days[6 + 62]) == []
