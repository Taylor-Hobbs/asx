"""Eval results: per-field scores for one (model, prompt_version) over the golden set.

Design decisions (made here, relied on by the harness and the BigQuery table):

- Per-field, never blended. CLAUDE.md is explicit: a prompt that nails revenue
  but hallucinates dividends should look exactly that way. The unit of record
  is therefore the `FieldScore`, and an `EvalRun` is just the collection of
  them plus the (model, prompt_version, dataset_version, timestamp) needed to
  reproduce it.
- Four outcomes, not one accuracy. A finance extractor fails in distinguishable
  ways and they do not weigh the same — a HALLUCINATED figure (inventing a
  number the document never printed) is the dangerous one, a MISSED figure
  (saying null when the document stated it) is a recall gap, a WRONG figure is
  a reading error. Collapsing them into a single number throws away exactly the
  signal a prompt revision needs.
- A correct `null` is a scored success. The prompt requires the model to assert
  absence ("the document does not state this figure"); a golden `null` matched
  by a predicted `null` is CORRECT, not an untested blank. USD-only reporters
  (BHP, RIO, CSL) make this the majority outcome for AUD fields, and the eval
  has to reward getting it right.
- `accuracy` and `total` are computed, never stored as independent truth — they
  are derived from the counts so a row can never disagree with itself.
"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, Field, computed_field, field_validator


class FieldOutcome(StrEnum):
    """The result of comparing one golden value to one predicted value."""

    CORRECT = "correct"  # values equal, OR both assert "not stated"
    WRONG = "wrong"  # both state a figure, the figures differ
    MISSED = "missed"  # document states it, model said null (false negative)
    HALLUCINATED = "hallucinated"  # document silent, model invented one (false positive)


class FieldScore(BaseModel):
    """Outcome tallies for one field across every scored document."""

    field: str = Field(min_length=1)
    correct: int = Field(ge=0)
    wrong: int = Field(ge=0)
    missed: int = Field(ge=0)
    hallucinated: int = Field(ge=0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        return self.correct + self.wrong + self.missed + self.hallucinated

    @computed_field  # type: ignore[prop-decorator]
    @property
    def accuracy(self) -> float | None:
        """Fraction correct, or None when the field was never scored."""
        return self.correct / self.total if self.total else None


class EvalRun(BaseModel):
    """One scoring of (model, prompt_version) against a golden dataset version.

    Everything needed to regenerate the number lives in the row (CLAUDE.md:
    every eval run is logged and reproducible). `n_documents` is what was
    actually scored; `n_skipped` is labeled goldens with no extraction for this
    (model, prompt_version) — a coverage gap that must stay visible rather than
    silently shrinking the denominator.
    """

    model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    evaluated_at: AwareDatetime
    n_documents: int = Field(ge=0)
    n_skipped: int = Field(ge=0)
    field_scores: list[FieldScore]

    @field_validator("evaluated_at")
    @classmethod
    def _normalize_to_utc(cls, v: datetime) -> datetime:
        return v.astimezone(UTC)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overall_accuracy(self) -> float | None:
        """Micro-average across every field — a headline, not the report."""
        correct = sum(s.correct for s in self.field_scores)
        total = sum(s.total for s in self.field_scores)
        return correct / total if total else None
