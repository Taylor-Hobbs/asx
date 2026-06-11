"""Tests for manual ingestion: filtering, record building, orchestration.

The run() orchestration is tested with plain fake classes — they satisfy the
AnnouncementSource/Store Protocols structurally, no mocking framework needed.
GCS/BigQuery never appear here; AnnouncementStore itself is a thin wrapper
exercised against the real services during the first live run.
"""

import hashlib
from datetime import UTC, datetime
from typing import Any

from asx_engine.ingestion.asx_client import HtmlAnnouncement
from asx_engine.ingestion.manual import IngestSummary, is_earnings_candidate, run
from asx_engine.ingestion.store import build_announcement
from asx_engine.schemas import Announcement


def listed(
    headline: str = "Appendix 4E and Full Year Results",
    *,
    price_sensitive: bool = True,
    ids_id: str = "03084954",
) -> HtmlAnnouncement:
    return HtmlAnnouncement(
        ids_id=ids_id,
        announced_at=datetime(2026, 2, 16, 22, 30, tzinfo=UTC),
        price_sensitive=price_sensitive,
        headline=headline,
        pages=58,
        file_size="2.1MB",
    )


class TestEarningsFilter:
    def test_accepts_statutory_earnings_headlines(self) -> None:
        for headline in [
            "Appendix 4E and Full Year Results",
            "Appendix 4D - Half Year Report",
            "Half-Year Results Presentation",
            "FY26 Full Year Results",
            "Annual Report 2026",
        ]:
            assert is_earnings_candidate(listed(headline)), headline

    def test_rejects_non_earnings_headlines(self) -> None:
        for headline in [
            "Initial Director's Interest Notice",
            "Notification of cessation of securities",
            "Trading Halt",
            "Change of Registered Office",
        ]:
            assert not is_earnings_candidate(listed(headline)), headline

    def test_rejects_non_price_sensitive(self) -> None:
        # Earnings-shaped headline but not flagged sensitive -> outside the
        # Q1 universe (price-sensitive only, per CLAUDE.md).
        assert not is_earnings_candidate(listed(price_sensitive=False))


class TestBuildAnnouncement:
    def test_builds_canonical_record(self) -> None:
        pdf_bytes = b"%PDF-1.7 contents"
        ingested_at = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)
        announcement = build_announcement(
            listed(),
            ticker="BHP",
            pdf_url="https://announcements.asx.com.au/asxpdf/x.pdf",
            pdf_bytes=pdf_bytes,
            ingested_at=ingested_at,
        )
        assert announcement.content_hash == hashlib.sha256(pdf_bytes).hexdigest()
        assert announcement.announcement_id == "03084954"
        assert announcement.ticker == "BHP"
        assert announcement.document_type is None  # HTML listing has no taxonomy
        assert announcement.announced_at == datetime(2026, 2, 16, 22, 30, tzinfo=UTC)
        assert announcement.ingested_at == ingested_at

    def test_different_bytes_different_identity(self) -> None:
        kwargs: dict[str, Any] = {
            "ticker": "BHP",
            "pdf_url": "https://example.test/x.pdf",
            "ingested_at": datetime(2026, 6, 11, tzinfo=UTC),
        }
        a = build_announcement(listed(), pdf_bytes=b"original", **kwargs)
        b = build_announcement(listed(), pdf_bytes=b"amended", **kwargs)
        assert a.content_hash != b.content_hash


class FakeSource:
    """Satisfies AnnouncementSource structurally (see Protocol note in manual.py)."""

    def __init__(self, announcements: dict[str, list[HtmlAnnouncement]]) -> None:
        self._announcements = announcements
        self.pdf_fetches: list[str] = []

    def get_announcements_html(self, ticker: str, *, year: int) -> list[HtmlAnnouncement]:
        return self._announcements[ticker]

    def fetch_pdf(self, ids_id: str) -> tuple[str, bytes]:
        self.pdf_fetches.append(ids_id)
        return ("https://example.test/doc.pdf", b"%PDF " + ids_id.encode())


class FakeStore:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = existing or set()
        self.saved: list[tuple[Announcement, bytes]] = []

    def existing_announcement_ids(self) -> set[str]:
        return self.existing

    def save(self, announcement: Announcement, pdf_bytes: bytes) -> None:
        self.saved.append((announcement, pdf_bytes))


class TestRun:
    def test_ingests_earnings_candidates_only(self) -> None:
        source = FakeSource(
            {
                "BHP": [
                    listed("Appendix 4D - Half Year Report", ids_id="03000001"),
                    listed("Trading Halt", ids_id="03000002"),
                ]
            }
        )
        store = FakeStore()
        summary = run(source, store, ["BHP"], year=2026, per_ticker_limit=5, dry_run=False)
        assert [a.announcement_id for a, _ in store.saved] == ["03000001"]
        assert len(summary.ingested) == 1

    def test_excluded_ids_skipped_and_free_their_limit_slot(self) -> None:
        source = FakeSource(
            {
                "BHP": [
                    listed("Full Year Results", ids_id="03000001"),
                    listed("Half Year Results", ids_id="03000002"),
                ]
            }
        )
        store = FakeStore()
        run(
            source,
            store,
            ["BHP"],
            year=2026,
            per_ticker_limit=1,
            dry_run=False,
            exclude={"03000001"},
        )
        # The exclusion happens before the limit: slot goes to the next candidate.
        assert [a.announcement_id for a, _ in store.saved] == ["03000002"]

    def test_respects_per_ticker_limit(self) -> None:
        source = FakeSource(
            {"BHP": [listed("Full Year Results", ids_id=f"0300000{i}") for i in range(5)]}
        )
        store = FakeStore()
        run(source, store, ["BHP"], year=2026, per_ticker_limit=2, dry_run=False)
        assert len(store.saved) == 2

    def test_skips_existing_before_any_pdf_fetch(self) -> None:
        source = FakeSource({"BHP": [listed("Full Year Results", ids_id="03000001")]})
        store = FakeStore(existing={"03000001"})
        summary = run(source, store, ["BHP"], year=2026, per_ticker_limit=5, dry_run=False)
        # The etiquette invariant: a stored announcement costs ASX zero requests.
        assert source.pdf_fetches == []
        assert summary.skipped_existing == ["03000001"]
        assert store.saved == []

    def test_dry_run_fetches_and_stores_nothing(self) -> None:
        source = FakeSource({"BHP": [listed("Full Year Results")]})
        store = FakeStore()
        summary = run(source, store, ["BHP"], year=2026, per_ticker_limit=5, dry_run=True)
        assert source.pdf_fetches == []
        assert store.saved == []
        assert len(summary.candidates) == 1

    def test_multiple_tickers_all_processed(self) -> None:
        source = FakeSource(
            {
                "BHP": [listed("Full Year Results", ids_id="03000001")],
                "CBA": [listed("Half Year Results", ids_id="03000002")],
            }
        )
        store = FakeStore()
        summary = run(source, store, ["BHP", "CBA"], year=2026, per_ticker_limit=5, dry_run=False)
        assert {a.ticker for a, _ in store.saved} == {"BHP", "CBA"}
        assert isinstance(summary, IngestSummary)
