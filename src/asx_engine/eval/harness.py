"""Scoring core: golden labels vs an extracted payload, one outcome per field.

This module is deliberately pure — no I/O, no BigQuery, no Anthropic. It takes
a `GoldenEarningsLabels` (ground truth) and an `EarningsResult` (prediction)
and returns outcomes. The job module wraps it with storage; tests exercise it
directly with synthetic values, which is where the real logic risk lives.

Match semantics are strict on purpose. Units are normalized at extraction time
(absolute amount in the reporting currency, cents per share — see EarningsResult),
so both sides are already in the same units and a numeric tolerance would hide
reading errors rather than absorb formatting noise. Currency itself is a scored
field (`reporting_currency`), so a figure read correctly under the wrong currency
is caught there rather than silently passing as a matching number:

- numeric fields: exact Decimal value equality. Decimal compares by value, so
  Decimal("141.4") == Decimal("141.40") and 24212000000 == 2.4212E10 — trailing
  zeros and exponent form don't matter, the quantity does.
- period (free text): whitespace- and case-normalized equality. Period has no
  canonical form ("1H FY2026" vs "Half-year ended 31 December 2025"), so this
  field is expected to surface genuine disagreement; it is reported on its own
  line so a systematic format mismatch never hides inside a blended average.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from asx_engine.schemas import (
    EarningsResult,
    GoldenEarningsLabels,
    GoldenMetric,
    ReportedMetric,
)
from asx_engine.schemas.eval import FieldOutcome, FieldScore

# A comparable value: a money/share figure, a period string, a trade date
# (director trades), or "not stated". Strings compare whitespace/case
# normalized; everything else compares by value equality.
ScoredValue = Decimal | str | date | None


@dataclass(frozen=True)
class ScoredField:
    """A field to score, paired with how to read it from each side.

    Explicit accessor lambdas rather than getattr: they keep the value types
    (Decimal | str | None) flowing through mypy --strict instead of decaying to
    Any, so a renamed schema field fails type-checking here, not silently at
    runtime in an eval.
    """

    name: str
    golden: Callable[[GoldenEarningsLabels], ScoredValue]
    pred: Callable[[EarningsResult], ScoredValue]


def _metric_fields(
    name: str,
    golden: Callable[[GoldenEarningsLabels], GoldenMetric],
    pred: Callable[[EarningsResult], ReportedMetric],
) -> tuple[ScoredField, ScoredField]:
    """The current/prior pair for one metric, typed end to end.

    The metric accessors return GoldenMetric / ReportedMetric, so the leaf
    accessors below stay concretely typed — no getattr, no Any.
    """
    return (
        ScoredField(
            f"{name}.current", lambda g: golden(g).current, lambda p: pred(p).current.value
        ),
        ScoredField(f"{name}.prior", lambda g: golden(g).prior, lambda p: pred(p).prior.value),
    )


# The ten scored fields in report order: period and reporting_currency, then
# current+prior for each of the four metrics. This tuple is the single source of
# truth for what the harness scores; the aggregate iterates it, so adding a
# metric is local. reporting_currency is plain text on the golden side (always
# present, default "AUD") and a SourcedField on the prediction side.
SCORED_FIELDS: tuple[ScoredField, ...] = (
    ScoredField("period", lambda g: g.period, lambda p: p.period.value),
    ScoredField(
        "reporting_currency",
        lambda g: g.reporting_currency,
        lambda p: p.reporting_currency.value,
    ),
    *_metric_fields("revenue", lambda g: g.revenue, lambda p: p.revenue),
    *_metric_fields("npat", lambda g: g.npat, lambda p: p.npat),
    *_metric_fields("eps_cents", lambda g: g.eps_cents, lambda p: p.eps_cents),
    *_metric_fields("dividend_cents", lambda g: g.dividend_cents, lambda p: p.dividend_cents),
)


def _normalize_text(s: str) -> str:
    """Collapse whitespace runs to one space, strip ends, casefold."""
    return re.sub(r"\s+", " ", s).strip().casefold()


def _values_match(golden: ScoredValue, pred: ScoredValue) -> bool:
    """Compare two stated (non-null) values under this field's semantics."""
    if isinstance(golden, str) and isinstance(pred, str):
        return _normalize_text(golden) == _normalize_text(pred)
    return golden == pred  # Decimal value equality


def score_field(golden: ScoredValue, pred: ScoredValue) -> FieldOutcome:
    """Classify one (golden, prediction) pair into a FieldOutcome.

    The null cases come first and carry the most meaning: a correct null is a
    success (the model rightly asserted absence), a hallucination is the model
    inventing a figure, a miss is the model failing to read one that was there.
    """
    if golden is None and pred is None:
        return FieldOutcome.CORRECT
    if golden is None:
        return FieldOutcome.HALLUCINATED
    if pred is None:
        return FieldOutcome.MISSED
    return FieldOutcome.CORRECT if _values_match(golden, pred) else FieldOutcome.WRONG


def score_document(golden: GoldenEarningsLabels, pred: EarningsResult) -> dict[str, FieldOutcome]:
    """Every scored field's outcome for one document."""
    return {f.name: score_field(f.golden(golden), f.pred(pred)) for f in SCORED_FIELDS}


def aggregate(per_document: list[dict[str, FieldOutcome]]) -> list[FieldScore]:
    """Tally per-field outcomes across all scored documents, in report order."""
    scores: list[FieldScore] = []
    for field in SCORED_FIELDS:
        outcomes = [doc[field.name] for doc in per_document]
        scores.append(
            FieldScore(
                field=field.name,
                correct=sum(o is FieldOutcome.CORRECT for o in outcomes),
                wrong=sum(o is FieldOutcome.WRONG for o in outcomes),
                missed=sum(o is FieldOutcome.MISSED for o in outcomes),
                hallucinated=sum(o is FieldOutcome.HALLUCINATED for o in outcomes),
            )
        )
    return scores
