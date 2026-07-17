"""Tests for the bulk backfill: cutoff, filters, isolation, resumability.

Same structural-fake pattern as test_manual_ingestion — the crawl logic is
what these pin down; the client and store are the integration's problem.
"""

from datetime import UTC, datetime

import pytest

from asx_engine.ingestion.asx_client import HtmlAnnouncement
from asx_engine.ingestion.backfill import (
    is_broad_candidate,
    load_universe,
    run,
    years_covering,
)
from asx_engine.ingestion.director_trades_ingest import is_3y_candidate
from asx_engine.schemas import Announcement

NOW = datetime(2026, 7, 6, tzinfo=UTC)


def listed(
    ids_id: str = "03000001",
    headline: str = "Appendix 3Y - Change of Director's Interest Notice",
    announced_at: datetime = datetime(2026, 5, 1, tzinfo=UTC),
) -> HtmlAnnouncement:
    return HtmlAnnouncement(
        ids_id=ids_id,
        announced_at=announced_at,
        price_sensitive=False,
        headline=headline,
        pages=2,
        file_size="200KB",
    )


class FakeSource:
    """AnnouncementSource fake: listings per (ticker, year), scripted failures."""

    def __init__(
        self,
        listings: dict[tuple[str, int], list[HtmlAnnouncement]],
        fail_tickers: set[str] | None = None,
    ) -> None:
        self._listings = listings
        self._fail = fail_tickers or set()
        self.pdf_fetches: list[str] = []

    def get_announcements_html(self, ticker: str, *, year: int) -> list[HtmlAnnouncement]:
        if ticker in self._fail:
            raise RuntimeError(f"scripted failure for {ticker}")
        return self._listings.get((ticker, year), [])

    def fetch_pdf(self, ids_id: str) -> tuple[str, bytes]:
        self.pdf_fetches.append(ids_id)
        return (f"https://example.com/{ids_id}.pdf", b"%PDF-" + ids_id.encode())


class FakeStore:
    def __init__(self, existing: set[str] | None = None) -> None:
        self._existing = existing or set()
        self.pdfs: list[Announcement] = []
        self.flushes: list[list[Announcement]] = []

    def existing_announcement_ids(self) -> set[str]:
        return set(self._existing)

    def save_pdf(self, announcement: Announcement, pdf_bytes: bytes) -> None:
        self.pdfs.append(announcement)

    def append_rows(self, announcements: list[Announcement]) -> None:
        self.flushes.append(list(announcements))

    @property
    def saved(self) -> list[Announcement]:
        """All rows that reached BigQuery, across every flush."""
        return [a for flush in self.flushes for a in flush]


def _run(source: FakeSource, store: FakeStore, tickers: list[str], **kw: object):
    defaults: dict = {"months": 24, "candidate_fn": is_3y_candidate, "dry_run": False, "now": NOW}
    defaults.update(kw)
    return run(source, store, tickers, **defaults)


class TestCutoffAndYears:
    def test_years_covering_spans_cutoff_to_now(self) -> None:
        cutoff = datetime(2024, 7, 10, tzinfo=UTC)
        assert years_covering(cutoff, NOW) == [2024, 2025, 2026]

    def test_announcements_before_cutoff_are_dropped(self) -> None:
        old = listed(ids_id="03000001", announced_at=datetime(2024, 1, 1, tzinfo=UTC))
        new = listed(ids_id="03000002", announced_at=datetime(2026, 5, 1, tzinfo=UTC))
        source = FakeSource({("BHP", 2024): [old], ("BHP", 2026): [new]})
        store = FakeStore()
        summary = _run(source, store, ["BHP"])
        assert [a.announcement_id for a in store.saved] == ["03000002"]
        assert summary.before_cutoff == 1
        assert summary.ingested == 1


class TestFilters:
    def test_3y_filter_keeps_only_director_notices(self) -> None:
        source = FakeSource(
            {
                ("BHP", 2026): [
                    listed(ids_id="03000001", headline="Appendix 3Y - Jane Smith"),
                    listed(ids_id="03000002", headline="Quarterly Activities Report"),
                ]
            }
        )
        store = FakeStore()
        summary = _run(source, store, ["BHP"])
        assert [a.announcement_id for a in store.saved] == ["03000001"]
        assert summary.filtered_out == 1

    @pytest.mark.parametrize(
        "noise",
        [
            "Change of Registered Office",
            "Notice of Annual General Meeting",
            "Results of Meeting",
            "Cleansing Notice (Section 708A)",
            "Proxy Form",
            "Constitution",
            "Change of Company Secretary",
        ],
    )
    def test_broad_filter_excludes_admin_noise(self, noise: str) -> None:
        assert not is_broad_candidate(listed(headline=noise))

    @pytest.mark.parametrize(
        "signal",
        [
            "Appendix 4D - Half Year Report",
            "Appendix 3Y - Change of Director's Interest Notice",
            "Completed Placement and SPP",
            "Becoming a substantial holder",
            "Trading Halt",
            "FY26 Guidance Update",
        ],
    )
    def test_broad_filter_keeps_signal_categories(self, signal: str) -> None:
        assert is_broad_candidate(listed(headline=signal))


class TestP0Filter:
    def _ps(self, headline: str, sensitive: bool = True) -> HtmlAnnouncement:
        a = listed(headline=headline)
        return HtmlAnnouncement(**{**a.model_dump(), "price_sensitive": sensitive})

    @pytest.mark.parametrize(
        "headline",
        [
            "Appendix 4D and Half Year Report",
            "Appendix 4E - Preliminary Final Report",
            "Quarterly Activities Report and Appendix 4C",
            "FY26 Results Presentation",
        ],
    )
    def test_price_sensitive_results_pass(self, headline: str) -> None:
        from asx_engine.ingestion.backfill import is_p0_candidate

        assert is_p0_candidate(self._ps(headline))

    def test_unflagged_results_do_not_pass(self) -> None:
        from asx_engine.ingestion.backfill import is_p0_candidate

        assert not is_p0_candidate(self._ps("Appendix 4D Half Year Report", sensitive=False))

    @pytest.mark.parametrize(
        "headline",
        [
            "Appointment of Managing Director",
            "Appendix 3X - Initial Director's Interest Notice",
            "Resignation of Director",
            "CEO Succession Announcement",
        ],
    )
    def test_appointments_pass_without_flag(self, headline: str) -> None:
        from asx_engine.ingestion.backfill import is_p0_candidate

        assert is_p0_candidate(self._ps(headline, sensitive=False))

    def test_results_of_meeting_is_rejected(self) -> None:
        from asx_engine.ingestion.backfill import is_p0_candidate

        assert not is_p0_candidate(self._ps("Results of Annual General Meeting"))


class TestResumability:
    def test_existing_records_are_never_refetched(self) -> None:
        source = FakeSource({("BHP", 2026): [listed(ids_id="03000001")]})
        store = FakeStore(existing={"03000001"})
        summary = _run(source, store, ["BHP"])
        assert source.pdf_fetches == []
        assert summary.skipped_existing == 1
        assert summary.ingested == 0

    def test_duplicate_listing_within_one_run_is_fetched_once(self) -> None:
        # Same idsId appearing under two years (year-boundary duplicates).
        dup = listed(ids_id="03000001")
        source = FakeSource({("BHP", 2025): [dup], ("BHP", 2026): [dup]})
        store = FakeStore()
        summary = _run(source, store, ["BHP"], months=18)
        assert source.pdf_fetches == ["03000001"]
        assert summary.ingested == 1


class TestErrorIsolation:
    def test_one_failing_ticker_does_not_stop_the_crawl(self) -> None:
        source = FakeSource(
            {("WES", 2026): [listed(ids_id="03000009")]},
            fail_tickers={"BHP"},
        )
        store = FakeStore()
        summary = _run(source, store, ["BHP", "WES"])
        assert "BHP" in summary.failed_tickers
        assert "scripted failure" in summary.failed_tickers["BHP"]
        assert [a.announcement_id for a in store.saved] == ["03000009"]


class TestRowBatching:
    """One load job per FLUSH_EVERY rows — the 1,500 jobs/day quota lesson."""

    def _many(self, n: int) -> list[HtmlAnnouncement]:
        return [listed(ids_id=f"0300{i:04d}") for i in range(n)]

    def test_rows_flush_in_batches_not_per_row(self) -> None:
        source = FakeSource({("BHP", 2026): self._many(5)})
        store = FakeStore()
        summary = _run(source, store, ["BHP"], flush_every=2)
        # 5 rows at flush_every=2 -> 2+2 threshold flushes + 1 final flush.
        assert [len(f) for f in store.flushes] == [2, 2, 1]
        assert summary.ingested == 5

    def test_final_flush_catches_the_remainder(self) -> None:
        source = FakeSource({("BHP", 2026): self._many(3)})
        store = FakeStore()
        _run(source, store, ["BHP"], flush_every=100)
        assert [len(f) for f in store.flushes] == [3]

    def test_pdf_uploads_before_its_row_is_flushed(self) -> None:
        # Write order: PDF first, row later — a crash between the two leaves a
        # hash-addressed blob without a row, which the next run re-writes.
        source = FakeSource({("BHP", 2026): self._many(3)})
        store = FakeStore()
        _run(source, store, ["BHP"], flush_every=100)
        assert len(store.pdfs) == 3
        assert len(store.saved) == 3

    def test_buffer_survives_a_failing_ticker(self) -> None:
        source = FakeSource(
            {
                ("AAA", 2026): [listed(ids_id="03000001")],
                ("WES", 2026): [listed(ids_id="03000002")],
            },
            fail_tickers={"BHP"},
        )
        store = FakeStore()
        summary = _run(source, store, ["AAA", "BHP", "WES"], flush_every=100)
        assert [a.announcement_id for a in store.saved] == ["03000001", "03000002"]
        assert "BHP" in summary.failed_tickers


class TestDryRun:
    def test_dry_run_fetches_no_pdfs_and_saves_nothing(self) -> None:
        source = FakeSource({("BHP", 2026): [listed()]})
        store = FakeStore()
        summary = _run(source, store, ["BHP"], dry_run=True)
        assert source.pdf_fetches == []
        assert store.saved == []
        assert summary.would_ingest == 1


class TestUniverse:
    def test_load_universe_reads_and_uppercases_tickers(self, tmp_path) -> None:
        p = tmp_path / "u.csv"
        p.write_text("ticker,company,sector\nbhp,BHP Group,Materials\nCBA,CommBank,Financials\n")
        assert load_universe(p) == ["BHP", "CBA"]

    def test_empty_universe_raises(self, tmp_path) -> None:
        p = tmp_path / "u.csv"
        p.write_text("ticker,company,sector\n")
        with pytest.raises(ValueError, match="no tickers"):
            load_universe(p)


class TestGuidanceFilter:
    def test_guidance_headlines_match(self):
        from asx_engine.ingestion.backfill import is_guidance_candidate

        for headline, want in [
            ("FY26 Guidance Update", True),
            ("Trading Update and Outlook Statement", True),
            ("Profit Warning", True),
            ("Quarterly Operational Update", True),
            ("Notice of Annual General Meeting", False),
            ("Change of Director's Interest Notice", False),
        ]:
            assert is_guidance_candidate(listed(headline=headline)) is want, headline
