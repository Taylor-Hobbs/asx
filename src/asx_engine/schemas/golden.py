"""Golden labels: hand-labeled ground truth, one file per filing document.

Design decisions:

- Labels are PER DOCUMENT, not per filing event. When a media release and a
  statutory 4D disagree (CBA's 5,367 vs 5,412), the label records what THAT
  document states under the labeling conventions — extraction is scored on
  reading the document in front of it, not on divining the "true" number.
- Same field names and units as EarningsResult, minus confidence and source
  quotes (those are the model's audit trail, not ground truth). `null` means
  "this document does not state this figure in the required form" — the same
  assertion the prompt demands of the model.
- A `status` lifecycle (`unlabeled` → `labeled`, or `excluded`) lets stub
  files exist in the repo without poisoning the eval: the harness consumes
  `labeled` rows only, and the validator refuses a `labeled` file with no
  labeler attribution or an `excluded` file with no reason.
- Reference keys (ticker + Sydney date + announcement_id) follow the
  redistribution rule: anyone can reconstruct the dataset from public
  sources; we never republish the documents.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, Field, model_validator

GOLDEN_DATASET_VERSION = "golden_v1"


class LabelStatus(StrEnum):
    UNLABELED = "unlabeled"  # stub generated, awaiting human eyes
    LABELED = "labeled"  # ground truth — the harness consumes these
    EXCLUDED = "excluded"  # not an earnings doc (e.g. production report)


class GoldenMetric(BaseModel):
    """Hand-labeled current + prior-corresponding-period values."""

    current: Decimal | None
    prior: Decimal | None


class GoldenEarningsLabels(BaseModel):
    """Ground truth in the exact shape and units of EarningsResult."""

    period: str | None
    reporting_currency: str = "AUD"  # ISO 4217 — "AUD", "USD", etc.
    revenue: GoldenMetric
    npat: GoldenMetric
    eps_cents: GoldenMetric
    dividend_cents: GoldenMetric


class GoldenLabel(BaseModel):
    # Citation keys — reconstructable from public ASX sources.
    ticker: str = Field(min_length=1)
    announcement_id: str = Field(min_length=1)
    announced_at: AwareDatetime
    headline: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    announcement_type: str = "earnings"
    status: LabelStatus = LabelStatus.UNLABELED
    exclusion_reason: str | None = None
    labels: GoldenEarningsLabels

    # Labeling metadata — who asserted this and when.
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
