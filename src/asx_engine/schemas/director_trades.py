"""Director trades schemas: extraction target and golden labels for Appendix 3Y.

Appendix 3Y is the ASX form directors and officers must lodge within five
business days of a change in their relevant interests. The form is highly
structured, mapping almost 1:1 to these fields — the extraction task is closer
to form-filling than to reading a narrative report.

Design decisions:

- A single 3Y can cover multiple transactions (different tranches, direct and
  indirect holdings on the same date, or multiple exercise events). The
  extraction result is therefore a list of DirectorTrade, not a single record.
  Each trade in the list is an independent scoreable unit.
- `TradeType` is a clean enum (acquisition | disposal) — it is always stated
  and has no ambiguous cases.
- `nature` stays free text: the variety of forms (on-market purchase, off-market
  transfer, exercise of options, vesting of performance rights, DRP allotment,
  off-market buy-back, scrip consideration...) does not compress cleanly into an
  enum without losing signal that matters for the event study.
- Prices and consideration are nullable — options exercises at nil cost,
  off-market transfers for no consideration, and performance-right vestings all
  legitimately have no price.
- `trade_date` uses `date`, not `datetime` — the form records a date only.
- Holdings before/after are nullable on the golden side: some lodgements
  (particularly for indirect interests) omit the prior holding level.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from asx_engine.schemas.extraction import SourcedField
from asx_engine.schemas.golden import GOLDEN_DATASET_VERSION, LabelStatus


class TradeType(StrEnum):
    ACQUISITION = "acquisition"
    DISPOSAL = "disposal"


class DirectorTrade(BaseModel):
    """One transaction line from an Appendix 3Y.

    All fields carry a source quote and page number so every figure can be
    traced back to the exact cell in the form that produced it.
    """

    director_name: SourcedField[str]
    director_role: SourcedField[str]
    trade_type: SourcedField[TradeType]
    # Free text: "on-market purchase", "exercise of options", "vesting of
    # performance rights", "off-market transfer", etc.
    nature: SourcedField[str]
    # "ordinary shares", "unlisted options", "performance rights", etc.
    security_class: SourcedField[str]
    quantity: SourcedField[Decimal]
    # Null for nil-consideration transactions (options exercise, vesting).
    price_per_security: SourcedField[Decimal]
    # Null when no cash changed hands.
    total_consideration: SourcedField[Decimal]
    trade_date: SourcedField[date]
    holdings_before: SourcedField[Decimal]
    holdings_after: SourcedField[Decimal]


class DirectorTradesResult(BaseModel):
    """Extraction target for Appendix 3Y director interest notices."""

    trades: list[DirectorTrade]


# ---------------------------------------------------------------------------
# Golden labels
# ---------------------------------------------------------------------------


class GoldenDirectorTrade(BaseModel):
    """Hand-labeled ground truth for one transaction line."""

    director_name: str
    director_role: str | None = None
    trade_type: TradeType
    nature: str | None = None
    security_class: str | None = None
    quantity: Decimal
    price_per_security: Decimal | None = None
    total_consideration: Decimal | None = None
    trade_date: date
    holdings_before: Decimal | None = None
    holdings_after: Decimal | None = None


class GoldenDirectorTradesLabels(BaseModel):
    """Ground truth in the exact shape of DirectorTradesResult."""

    trades: list[GoldenDirectorTrade]


class DirectorTradeGoldenLabel(BaseModel):
    """One labeled Appendix 3Y filing — mirrors GoldenLabel for earnings."""

    ticker: str = Field(min_length=1)
    announcement_id: str = Field(min_length=1)
    announced_at: AwareDatetime
    headline: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    announcement_type: str = "director_trade"
    status: LabelStatus = LabelStatus.UNLABELED
    exclusion_reason: str | None = None
    labels: GoldenDirectorTradesLabels

    labeled_by: str | None = None
    labeled_at: date | None = None
    dataset_version: str = GOLDEN_DATASET_VERSION
    notes: str | None = None

    @model_validator(mode="after")
    def _status_requires_metadata(self) -> Self:
        if self.status is LabelStatus.LABELED and (
            self.labeled_by is None or self.labeled_at is None
        ):
            raise ValueError("a labeled file must say who labeled it and when")
        if self.status is LabelStatus.EXCLUDED and not self.exclusion_reason:
            raise ValueError("an excluded file must say why")
        return self
