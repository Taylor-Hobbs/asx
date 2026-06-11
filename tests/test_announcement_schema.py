"""Tests for the Announcement metadata model.

These pin the two schema-level invariants (immutability, timezone
discipline) so a future refactor can't silently drop them.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from asx_engine.schemas import Announcement

# Australia/Sydney winter offset (AEST). A fixed offset keeps the test
# independent of the host's tz database; real code uses zoneinfo.
AEST = timezone(timedelta(hours=10))

VALID = {
    "content_hash": "a" * 64,
    "announcement_id": "02-95-3344",
    "ticker": "BHP",
    "headline": "Half Year Results",
    "document_type": "Half Yearly Report",
    "price_sensitive": True,
    "document_url": "https://announcements.asx.com.au/asxpdf/example.pdf",
    "announced_at": datetime(2026, 2, 17, 9, 30, tzinfo=AEST),
    "ingested_at": datetime(2026, 6, 11, 12, 0, tzinfo=UTC),
}


def make(**overrides: object) -> Announcement:
    return Announcement(**{**VALID, **overrides})  # type: ignore[arg-type]


def test_valid_announcement_roundtrips() -> None:
    ann = make()
    assert ann.ticker == "BHP"
    assert ann.price_sensitive is True


def test_frozen_rejects_mutation() -> None:
    ann = make()
    with pytest.raises(ValidationError):
        ann.headline = "Amended Half Year Results"  # type: ignore[misc]


def test_ticker_is_normalized_to_uppercase() -> None:
    assert make(ticker="bhp").ticker == "BHP"


def test_bad_ticker_rejected() -> None:
    with pytest.raises(ValidationError):
        make(ticker="TOOLONGTICKER")


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValidationError):
        make(announced_at=datetime(2026, 2, 17, 9, 30))  # no tzinfo


def test_timestamps_normalized_to_utc() -> None:
    ann = make()
    assert ann.announced_at.tzinfo == UTC
    # 09:30 AEST == 23:30 UTC the previous day — the exact off-by-one that
    # corrupts event studies if timestamps are stored naive.
    assert ann.announced_at == datetime(2026, 2, 16, 23, 30, tzinfo=UTC)


def test_content_hash_must_be_sha256_hex() -> None:
    with pytest.raises(ValidationError):
        make(content_hash="not-a-hash")
    with pytest.raises(ValidationError):
        make(content_hash="A" * 64)  # uppercase hex also rejected: one canonical form


def test_announcements_with_same_hash_are_equal() -> None:
    # frozen=True gives value equality + hashability — lets ingestion dedupe
    # with a plain set.
    assert make() == make()
    assert len({make(), make()}) == 1
