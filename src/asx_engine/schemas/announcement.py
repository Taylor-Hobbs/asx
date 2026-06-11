"""Announcement metadata: the immutable record of a filing's existence.

Two project invariants are enforced *in the type* rather than by convention:

1. Immutability — `frozen=True` makes instances hashable and rejects any
   attribute assignment after construction. An amended filing is a NEW
   record with a new content hash; originals are never edited (revision-
   leakage hygiene for the Q2 audit).
2. Point-in-time correctness — `announced_at` (when the market learned the
   information) and `ingested_at` (when *we* stored it) are separate,
   timezone-aware, and normalized to UTC. Naive datetimes are rejected at
   construction: a timestamp whose meaning depends on the host machine's
   locale is a leakage bug waiting to happen.
"""

from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, Field, field_validator


class Announcement(BaseModel):
    """One ASX announcement, keyed by the SHA-256 of its PDF bytes."""

    model_config = {"frozen": True}

    # SHA-256 hex digest of the raw PDF bytes — the primary key. Two filings
    # with identical bytes are the same record; an amended version hashes
    # differently and becomes a new record.
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    # ASX's own announcement identifier, kept for cross-referencing and for
    # the public golden dataset (which cites ticker + date + this ID instead
    # of republishing documents).
    announcement_id: str = Field(min_length=1)

    ticker: str = Field(pattern=r"^[A-Z0-9]{3,6}$")
    headline: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    price_sensitive: bool
    document_url: str = Field(min_length=1)

    announced_at: AwareDatetime
    ingested_at: AwareDatetime

    @field_validator("ticker", mode="before")
    @classmethod
    def _uppercase_ticker(cls, v: str) -> str:
        # Normalize before pattern validation so "bhp" passes as "BHP".
        return v.upper() if isinstance(v, str) else v

    @field_validator("announced_at", "ingested_at")
    @classmethod
    def _normalize_to_utc(cls, v: datetime) -> datetime:
        # AwareDatetime already rejected naive values; this canonicalizes the
        # zone so AEST/AEDT inputs compare and sort correctly everywhere.
        return v.astimezone(UTC)
