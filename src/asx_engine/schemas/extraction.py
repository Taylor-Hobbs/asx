"""Typed extraction outputs: what the LLM must produce per announcement type.

Design decisions (made here, relied on everywhere downstream):

- Confidence and source span are PER FIELD, not per document. The eval
  harness reports per-field accuracy, so auditability has to live at the
  same grain: when `npat` is wrong we want the exact quote the model relied
  on, not a document-level shrug.
- Source spans are quoted text, not character offsets. Offsets break every
  time the PDF parser changes; a verbatim quote stays checkable against any
  rendering of the document.
- Monetary values are `Decimal`, never float — 0.1 + 0.2 != 0.3 in binary
  floating point, and silently-wrong cents in a finance repo is a credibility
  bug even when no money moves. Pydantic parses Decimal from JSON strings.
- Units are encoded in field NAMES (`eps_cents`) and the reporting currency in
  `reporting_currency`. A reported "$1,234.5m" must be normalized to
  1_234_500_000 in the reporting currency at extraction time; unit mismatches
  then fail loudly in evals instead of hiding in a separate column nobody joins on.
- `value=None` means "the document does not state this" — an explicit,
  required assertion (no default), distinct from a field the model skipped.
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator


class SourcedField[T](BaseModel):
    """One extracted value with its audit trail.

    PEP 695 generic syntax (`class SourcedField[T]`) — Python 3.12's native
    spelling of what previously required `Generic[T]` and a separate
    `TypeVar`. `SourcedField[Decimal]` and `SourcedField[str]` are distinct
    validated types.
    """

    # Required-but-nullable: callers must explicitly assert absence.
    value: T | None
    confidence: float = Field(ge=0.0, le=1.0)
    # Verbatim quote from the document supporting `value` (None only when
    # value is None — nothing to support).
    source_quote: str | None = None
    page: int | None = Field(default=None, ge=1)


class ReportedMetric(BaseModel):
    """A financial line item: current period plus prior-period comparative.

    Earnings announcements report both ("revenue of $X, up from $Y"), and the
    extraction prompt is required to capture both — comparatives are what the
    Q2 event studies key on.
    """

    current: SourcedField[Decimal]
    prior: SourcedField[Decimal]


class EarningsResult(BaseModel):
    """Extraction target for earnings/results announcements.

    Unit conventions (normalize at extraction time):
    - `reporting_currency`: ISO 4217 code as stated in the document ("AUD", "USD", etc.)
    - `revenue` / `npat`: absolute value in reporting currency — "$1,234.5m" becomes 1234500000
    - `*_cents`: cents per share in reporting currency (ASX convention for EPS/DPS)
    """

    # Reporting period as the company states it, e.g. "FY2026" or "1H FY2026".
    period: SourcedField[str]
    reporting_currency: SourcedField[str]
    revenue: ReportedMetric
    npat: ReportedMetric
    eps_cents: ReportedMetric
    dividend_cents: ReportedMetric


class GuidanceDirection(StrEnum):
    """StrEnum members serialize as plain strings — BigQuery- and JSON-friendly."""

    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    AFFIRMED = "affirmed"


class GuidanceStatement(BaseModel):
    """Extraction target for guidance announcements."""

    direction: SourcedField[GuidanceDirection]
    # What is being guided and on what basis, as stated — e.g. metric
    # "EBITDA" on basis "underlying". Statutory vs underlying is exactly the
    # distinction sell-side numbers get wrong; we keep the company's words.
    metric: SourcedField[str]
    basis: SourcedField[str]
    # Period the guidance covers, e.g. "FY2027".
    period: SourcedField[str]
    range_low_aud: SourcedField[Decimal]
    range_high_aud: SourcedField[Decimal]

    @model_validator(mode="after")
    def _range_is_ordered(self) -> "GuidanceStatement":
        low, high = self.range_low_aud.value, self.range_high_aud.value
        if low is not None and high is not None and low > high:
            raise ValueError(f"guidance range inverted: low {low} > high {high}")
        return self


class ExtractionRecord[PayloadT: BaseModel](BaseModel):
    """Envelope tying a payload to everything needed to reproduce it.

    `[PayloadT: BaseModel]` is a PEP 695 *bounded* type parameter: any
    payload is accepted as long as it is itself a Pydantic model. One eval
    run = filter records by (model, prompt_version) and score payloads
    against golden labels; reproducibility is impossible without this
    metadata, so it is part of the schema, not a logging afterthought.
    """

    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    extracted_at: AwareDatetime
    payload: PayloadT

    @field_validator("extracted_at")
    @classmethod
    def _normalize_to_utc(cls, v: datetime) -> datetime:
        return v.astimezone(UTC)


def utc_now() -> datetime:
    """Timezone-aware now — `datetime.utcnow()` is deprecated AND naive."""
    return datetime.now(UTC)
