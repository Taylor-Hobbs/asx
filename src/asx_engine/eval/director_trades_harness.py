"""Scoring core for director-trades (Appendix 3Y) extraction.

Where earnings has exactly one record per document, a 3Y is a *list* of trades
whose length the model must also get right. Scoring therefore has a stage the
earnings harness doesn't: before any field can be compared, predicted trades
have to be ALIGNED to golden trades. Only then does per-field scoring — the same
four-outcome classifier earnings uses — run over each matched pair.

Alignment failures are first-class outcomes, not silent denominator changes:

- a golden trade with no predicted match is a **MISSED** detection (the model
  failed to report a transaction the form recorded);
- a predicted trade with no golden match is a **HALLUCINATED** detection (the
  model invented a transaction).

Both land on a dedicated ``trade_detection`` line so "did we find the right set
of trades" is reported separately from "did we read their fields correctly" — a
prompt that emits only the trades it is sure of would score well on the fields
and badly on detection, and the report has to make that visible rather than
average it away.

Matching (see ``match_trades``) is greedy by total field agreement with an
eligibility gate. Trades carry no ID, so alignment leans on the fields that
identify a transaction within a form — director, date, security class, type.
The greedy order means the most-similar pair is committed first, which recovers
the correct assignment when a single form lists several tranches; the gate
(identity floor plus at least one strong identifier — director or date — in
agreement) stops two unrelated trades from being paired just because both are,
say, acquisitions of ordinary shares.

Everything below reuses the earnings primitives unchanged — ``score_field`` (the
CORRECT / WRONG / MISSED / HALLUCINATED classifier), ``FieldOutcome``,
``FieldScore``. Only the list-alignment and the trades field set are new.
"""

from collections.abc import Callable
from dataclasses import dataclass

from asx_engine.eval.harness import ScoredValue, score_field
from asx_engine.schemas.director_trades import (
    DirectorTrade,
    DirectorTradesResult,
    GoldenDirectorTrade,
    GoldenDirectorTradesLabels,
)
from asx_engine.schemas.eval import FieldOutcome, FieldScore


@dataclass(frozen=True)
class TradeField:
    """One scored field, paired with how to read it from each side.

    Explicit accessor lambdas rather than getattr keep the value types
    (Decimal | str | date | None) flowing through mypy --strict, so a renamed
    schema field fails type-checking here instead of silently at runtime. The
    prediction side reads ``.value`` off the SourcedField wrapper.
    """

    name: str
    golden: Callable[[GoldenDirectorTrade], ScoredValue]
    pred: Callable[[DirectorTrade], ScoredValue]


# The eleven fields of a 3Y transaction line, in report order. This tuple is the
# single source of truth for what a matched pair is scored on. trade_type is a
# StrEnum on both sides, so it compares as normalized text like any other string.
TRADE_FIELDS: tuple[TradeField, ...] = (
    TradeField("director_name", lambda g: g.director_name, lambda p: p.director_name.value),
    TradeField("director_role", lambda g: g.director_role, lambda p: p.director_role.value),
    TradeField("trade_type", lambda g: g.trade_type, lambda p: p.trade_type.value),
    TradeField("nature", lambda g: g.nature, lambda p: p.nature.value),
    TradeField("security_class", lambda g: g.security_class, lambda p: p.security_class.value),
    TradeField("quantity", lambda g: g.quantity, lambda p: p.quantity.value),
    TradeField(
        "price_per_security",
        lambda g: g.price_per_security,
        lambda p: p.price_per_security.value,
    ),
    TradeField(
        "total_consideration",
        lambda g: g.total_consideration,
        lambda p: p.total_consideration.value,
    ),
    TradeField("trade_date", lambda g: g.trade_date, lambda p: p.trade_date.value),
    TradeField("holdings_before", lambda g: g.holdings_before, lambda p: p.holdings_before.value),
    TradeField("holdings_after", lambda g: g.holdings_after, lambda p: p.holdings_after.value),
)

_FIELDS_BY_NAME = {f.name: f for f in TRADE_FIELDS}

# The detection line: one outcome per trade (found / missed / invented), scored
# alongside the fields so the headline accuracy reflects list-length errors too.
DETECTION_FIELD = "trade_detection"

# Report order: detection first, then the eleven fields.
REPORT_FIELDS: tuple[str, ...] = (DETECTION_FIELD, *(f.name for f in TRADE_FIELDS))

# Fields that identify a transaction within a form. Alignment requires at least
# MIN_IDENTITY_AGREEMENT of these to concretely agree (both sides stated, values
# equal) — enough to survive one wrong identifying field — AND at least one
# STRONG field to agree. trade_type and security_class alone cannot identify a
# transaction ("acquisition of ordinary shares" describes most 3Y rows on the
# ASX), so a coincidental type+class overlap between an invented trade and a
# missed one must not be paired: without the strong-field requirement it would
# be reported as two field errors instead of the two detection errors it is.
IDENTITY_FIELDS: tuple[str, ...] = (
    "director_name",
    "trade_date",
    "security_class",
    "trade_type",
)
STRONG_IDENTITY_FIELDS: tuple[str, ...] = ("director_name", "trade_date")
MIN_IDENTITY_AGREEMENT = 2


@dataclass(frozen=True)
class TradeMatch:
    """A committed pairing: golden trade index <-> predicted trade index."""

    golden_index: int
    pred_index: int


def _is_correct(field: TradeField, g: GoldenDirectorTrade, p: DirectorTrade) -> bool:
    return score_field(field.golden(g), field.pred(p)) is FieldOutcome.CORRECT


def _agreement(g: GoldenDirectorTrade, p: DirectorTrade) -> int:
    """How many of the eleven fields the two trades agree on (CORRECT)."""
    return sum(_is_correct(f, g, p) for f in TRADE_FIELDS)


def _stated_agreements(g: GoldenDirectorTrade, p: DirectorTrade, names: tuple[str, ...]) -> int:
    """Agreements among the named fields that carry real signal (both stated).

    A both-null match on an identity field is not identifying, so it must not
    count toward the floor — otherwise two trades that each omit a field would
    look 'identified' by a shared absence.
    """
    total = 0
    for name in names:
        field = _FIELDS_BY_NAME[name]
        gv, pv = field.golden(g), field.pred(p)
        if gv is not None and pv is not None and score_field(gv, pv) is FieldOutcome.CORRECT:
            total += 1
    return total


def _identity_agreement(g: GoldenDirectorTrade, p: DirectorTrade) -> int:
    return _stated_agreements(g, p, IDENTITY_FIELDS)


def _eligible(g: GoldenDirectorTrade, p: DirectorTrade) -> bool:
    """May these two trades be paired at all?"""
    return (
        _stated_agreements(g, p, IDENTITY_FIELDS) >= MIN_IDENTITY_AGREEMENT
        and _stated_agreements(g, p, STRONG_IDENTITY_FIELDS) >= 1
    )


def match_trades(
    goldens: list[GoldenDirectorTrade],
    preds: list[DirectorTrade],
) -> tuple[list[TradeMatch], list[int], list[int]]:
    """Align predicted trades to golden trades.

    Greedy by total field agreement (identity agreement breaks ties): the
    most-similar pair is committed first, then the next best among what remains,
    and so on. Only eligible pairs — identity floor cleared AND a strong
    identifier (director or date) in agreement — may be committed. Returns the
    committed matches plus the indices of unmatched golden trades (missed) and
    unmatched predicted trades (hallucinated).
    """
    candidates: list[tuple[int, int, int, int]] = []
    for gi, g in enumerate(goldens):
        for pj, p in enumerate(preds):
            if _eligible(g, p):
                candidates.append((_agreement(g, p), _identity_agreement(g, p), gi, pj))
    # Highest agreement first, then highest identity agreement; indices ascending
    # last so the result is deterministic regardless of input order.
    candidates.sort(key=lambda c: (-c[0], -c[1], c[2], c[3]))

    used_g: set[int] = set()
    used_p: set[int] = set()
    matches: list[TradeMatch] = []
    for _agr, _idagr, gi, pj in candidates:
        if gi in used_g or pj in used_p:
            continue
        matches.append(TradeMatch(gi, pj))
        used_g.add(gi)
        used_p.add(pj)

    missed = [gi for gi in range(len(goldens)) if gi not in used_g]
    hallucinated = [pj for pj in range(len(preds)) if pj not in used_p]
    matches.sort(key=lambda m: (m.golden_index, m.pred_index))
    return matches, missed, hallucinated


def score_document(
    golden: GoldenDirectorTradesLabels,
    pred: DirectorTradesResult,
) -> list[tuple[str, FieldOutcome]]:
    """Every (field, outcome) pair produced by one 3Y filing.

    A document emits a flat list of (field_name, outcome) pairs rather than one
    dict: a field recurs once per matched trade, and detection recurs once per
    trade on either side, so a flat list is the shape ``aggregate`` tallies.
    """
    matches, missed, hallucinated = match_trades(golden.trades, pred.trades)
    outcomes: list[tuple[str, FieldOutcome]] = []
    for match in matches:
        outcomes.append((DETECTION_FIELD, FieldOutcome.CORRECT))
        g = golden.trades[match.golden_index]
        p = pred.trades[match.pred_index]
        for field in TRADE_FIELDS:
            outcomes.append((field.name, score_field(field.golden(g), field.pred(p))))
    outcomes.extend((DETECTION_FIELD, FieldOutcome.MISSED) for _ in missed)
    outcomes.extend((DETECTION_FIELD, FieldOutcome.HALLUCINATED) for _ in hallucinated)
    return outcomes


def aggregate(per_document: list[list[tuple[str, FieldOutcome]]]) -> list[FieldScore]:
    """Tally per-field outcomes across all scored documents, in report order.

    Every REPORT_FIELDS entry is always present, so an empty input yields zeroed
    rows with null accuracy (matching the earnings harness) rather than a short
    or reordered table.
    """
    tally: dict[str, dict[FieldOutcome, int]] = {
        name: dict.fromkeys(FieldOutcome, 0) for name in REPORT_FIELDS
    }
    for document in per_document:
        for name, outcome in document:
            tally[name][outcome] += 1
    return [
        FieldScore(
            field=name,
            correct=tally[name][FieldOutcome.CORRECT],
            wrong=tally[name][FieldOutcome.WRONG],
            missed=tally[name][FieldOutcome.MISSED],
            hallucinated=tally[name][FieldOutcome.HALLUCINATED],
        )
        for name in REPORT_FIELDS
    ]
