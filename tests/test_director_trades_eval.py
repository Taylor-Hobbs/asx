"""Tests for the director-trades eval harness: alignment and list scoring.

The genuinely new logic over the earnings harness is trade alignment — matching
a variable-length predicted list against a variable-length golden list before
any field is compared. That is where the risk lives, so these tests drive
``match_trades`` directly with synthetic trades, then check ``score_document``
emits detection outcomes (missed / hallucinated trades) alongside field
outcomes, and that ``aggregate`` keeps them on their own report line.
"""

from datetime import date
from decimal import Decimal

from asx_engine.eval.director_trades_harness import (
    DETECTION_FIELD,
    MIN_IDENTITY_AGREEMENT,
    REPORT_FIELDS,
    TRADE_FIELDS,
    aggregate,
    match_trades,
    score_document,
)
from asx_engine.schemas.director_trades import (
    DirectorTrade,
    DirectorTradesResult,
    GoldenDirectorTrade,
    GoldenDirectorTradesLabels,
    TradeType,
)
from asx_engine.schemas.eval import FieldOutcome
from asx_engine.schemas.extraction import SourcedField

# --- builders -------------------------------------------------------------


def sourced(value: object) -> SourcedField:  # type: ignore[type-arg]
    return SourcedField(value=value, confidence=0.9, source_quote="quoted", page=1)


def _dec(v: str | None) -> Decimal | None:
    return Decimal(v) if v is not None else None


def golden_trade(
    director_name: str = "Rob Scott",
    director_role: str | None = "Managing Director & CEO",
    trade_type: TradeType = TradeType.ACQUISITION,
    nature: str | None = "on-market purchase",
    security_class: str | None = "ordinary shares",
    quantity: str = "5000",
    price_per_security: str | None = "71.44",
    total_consideration: str | None = "357200",
    trade_date: date = date(2026, 3, 11),
    holdings_before: str | None = "1241300",
    holdings_after: str | None = "1246300",
) -> GoldenDirectorTrade:
    return GoldenDirectorTrade(
        director_name=director_name,
        director_role=director_role,
        trade_type=trade_type,
        nature=nature,
        security_class=security_class,
        quantity=Decimal(quantity),
        price_per_security=_dec(price_per_security),
        total_consideration=_dec(total_consideration),
        trade_date=trade_date,
        holdings_before=_dec(holdings_before),
        holdings_after=_dec(holdings_after),
    )


def pred_trade(
    director_name: str = "Rob Scott",
    director_role: str | None = "Managing Director & CEO",
    trade_type: TradeType = TradeType.ACQUISITION,
    nature: str | None = "on-market purchase",
    security_class: str | None = "ordinary shares",
    quantity: str = "5000",
    price_per_security: str | None = "71.44",
    total_consideration: str | None = "357200",
    trade_date: date = date(2026, 3, 11),
    holdings_before: str | None = "1241300",
    holdings_after: str | None = "1246300",
) -> DirectorTrade:
    return DirectorTrade(
        director_name=sourced(director_name),
        director_role=sourced(director_role),
        trade_type=sourced(trade_type),
        nature=sourced(nature),
        security_class=sourced(security_class),
        quantity=sourced(Decimal(quantity)),
        price_per_security=sourced(_dec(price_per_security)),
        total_consideration=sourced(_dec(total_consideration)),
        trade_date=sourced(trade_date),
        holdings_before=sourced(_dec(holdings_before)),
        holdings_after=sourced(_dec(holdings_after)),
    )


def goldens(*trades: GoldenDirectorTrade) -> GoldenDirectorTradesLabels:
    return GoldenDirectorTradesLabels(trades=list(trades))


def preds(*trades: DirectorTrade) -> DirectorTradesResult:
    return DirectorTradesResult(trades=list(trades))


def outcomes_for(scored: list[tuple[str, FieldOutcome]], name: str) -> list[FieldOutcome]:
    return [o for n, o in scored if n == name]


# --- match_trades: alignment ------------------------------------------------


class TestMatchTrades:
    def test_identical_single_trade_matches(self) -> None:
        matches, missed, hallucinated = match_trades([golden_trade()], [pred_trade()])
        assert [(m.golden_index, m.pred_index) for m in matches] == [(0, 0)]
        assert missed == [] and hallucinated == []

    def test_empty_prediction_leaves_all_goldens_missed(self) -> None:
        matches, missed, hallucinated = match_trades([golden_trade(), golden_trade()], [])
        assert matches == []
        assert missed == [0, 1] and hallucinated == []

    def test_empty_golden_leaves_all_predictions_hallucinated(self) -> None:
        matches, missed, hallucinated = match_trades([], [pred_trade()])
        assert matches == [] and missed == [] and hallucinated == [0]

    def test_two_tranches_same_day_align_by_agreement_not_order(self) -> None:
        # A form with direct + indirect rows on the same date: the model returns
        # them in the opposite order. Greedy-by-agreement recovers the pairing.
        g_direct = golden_trade(quantity="1905", holdings_after="1905")
        g_indirect = golden_trade(
            quantity="2920",
            nature="on-market purchase — indirect interest",
            holdings_after="2920",
        )
        p_indirect = pred_trade(
            quantity="2920",
            nature="on-market purchase — indirect interest",
            holdings_after="2920",
        )
        p_direct = pred_trade(quantity="1905", holdings_after="1905")
        matches, missed, hallucinated = match_trades([g_direct, g_indirect], [p_indirect, p_direct])
        assert {(m.golden_index, m.pred_index) for m in matches} == {(0, 1), (1, 0)}
        assert missed == [] and hallucinated == []

    def test_identity_floor_rejects_unrelated_trades(self) -> None:
        # A disposal of options vs an acquisition of shares by someone else on
        # another day: nothing identifying agrees, so no pairing.
        g = golden_trade()
        p = pred_trade(
            director_name="Someone Else",
            trade_date=date(2025, 1, 1),
            trade_type=TradeType.DISPOSAL,
            security_class="unlisted options",
            quantity="42",
        )
        matches, missed, hallucinated = match_trades([g], [p])
        assert matches == []
        assert missed == [0] and hallucinated == [0]

    def test_type_and_class_overlap_alone_is_not_identity(self) -> None:
        # The dangerous coincidence: an invented trade and a missed trade that
        # are both "acquisition of ordinary shares" (most 3Y rows are). They
        # clear the numeric floor of 2, but neither strong identifier (director,
        # date) agrees — pairing them would mask two detection errors as a pile
        # of field errors, so they must stay unmatched.
        g = golden_trade()
        p = pred_trade(director_name="Someone Else", trade_date=date(2025, 1, 1))
        matches, missed, hallucinated = match_trades([g], [p])
        assert matches == []
        assert missed == [0] and hallucinated == [0]

    def test_one_wrong_identity_field_still_matches(self) -> None:
        # The model misread the trade date but got director, class and type
        # right: 3 of 4 identity fields agree, clearing the floor, so the pair
        # is scored (and the date lands as WRONG) rather than counted as one
        # missed plus one hallucinated trade.
        assert MIN_IDENTITY_AGREEMENT == 2
        matches, missed, hallucinated = match_trades(
            [golden_trade()], [pred_trade(trade_date=date(2026, 3, 12))]
        )
        assert len(matches) == 1
        assert missed == [] and hallucinated == []

    def test_both_null_identity_fields_do_not_count_toward_floor(self) -> None:
        # security_class null on both sides is a shared absence, not evidence of
        # identity. With director+date also disagreeing, only trade_type truly
        # agrees — below the floor, so no match.
        g = golden_trade(security_class=None)
        p = pred_trade(
            director_name="Someone Else",
            trade_date=date(2025, 1, 1),
            security_class=None,
        )
        matches, _missed, _hallucinated = match_trades([g], [p])
        assert matches == []

    def test_extra_predicted_tranche_is_hallucinated_not_stealing_the_match(self) -> None:
        g = golden_trade()
        exact = pred_trade()
        near = pred_trade(quantity="9999")  # same identity, wrong quantity
        matches, missed, hallucinated = match_trades([g], [near, exact])
        assert [(m.golden_index, m.pred_index) for m in matches] == [(0, 1)]
        assert missed == [] and hallucinated == [0]


# --- score_document ---------------------------------------------------------


class TestScoreDocument:
    def test_perfect_single_trade_is_all_correct_including_detection(self) -> None:
        scored = score_document(goldens(golden_trade()), preds(pred_trade()))
        assert outcomes_for(scored, DETECTION_FIELD) == [FieldOutcome.CORRECT]
        for field in TRADE_FIELDS:
            assert outcomes_for(scored, field.name) == [FieldOutcome.CORRECT]

    def test_field_errors_on_a_matched_pair_land_on_the_right_fields(self) -> None:
        golden = golden_trade(price_per_security=None, holdings_before="100")
        pred = pred_trade(
            quantity="4000",  # wrong
            price_per_security="71.44",  # hallucinated (golden: nil consideration)
            holdings_before=None,  # missed
        )
        scored = score_document(goldens(golden), preds(pred))
        assert outcomes_for(scored, "quantity") == [FieldOutcome.WRONG]
        assert outcomes_for(scored, "price_per_security") == [FieldOutcome.HALLUCINATED]
        assert outcomes_for(scored, "holdings_before") == [FieldOutcome.MISSED]
        assert outcomes_for(scored, "director_name") == [FieldOutcome.CORRECT]

    def test_missed_trade_scores_detection_only_no_phantom_fields(self) -> None:
        # The model returned one of two trades: the found one is scored on all
        # fields, the missed one is a single MISSED detection — its fields are
        # not scored against nothing.
        g_found = golden_trade()
        g_missed = golden_trade(quantity="777", trade_date=date(2026, 4, 1))
        scored = score_document(goldens(g_found, g_missed), preds(pred_trade()))
        assert sorted(outcomes_for(scored, DETECTION_FIELD)) == sorted(
            [FieldOutcome.CORRECT, FieldOutcome.MISSED]
        )
        assert len(outcomes_for(scored, "quantity")) == 1  # only the matched pair

    def test_invented_trade_is_a_hallucinated_detection(self) -> None:
        scored = score_document(
            goldens(golden_trade()),
            preds(
                pred_trade(),
                pred_trade(
                    director_name="Nobody",
                    trade_date=date(2025, 1, 1),
                    trade_type=TradeType.DISPOSAL,
                    security_class="performance rights",
                ),
            ),
        )
        assert sorted(outcomes_for(scored, DETECTION_FIELD)) == sorted(
            [FieldOutcome.CORRECT, FieldOutcome.HALLUCINATED]
        )

    def test_trade_type_is_scored_as_text(self) -> None:
        scored = score_document(
            goldens(golden_trade(trade_type=TradeType.DISPOSAL)),
            preds(pred_trade(trade_type=TradeType.ACQUISITION)),
        )
        assert outcomes_for(scored, "trade_type") == [FieldOutcome.WRONG]

    def test_nature_match_is_whitespace_and_case_normalized(self) -> None:
        scored = score_document(
            goldens(golden_trade(nature="On-market purchase")),
            preds(pred_trade(nature="on-market   purchase")),
        )
        assert outcomes_for(scored, "nature") == [FieldOutcome.CORRECT]


# --- aggregate ----------------------------------------------------------------


class TestAggregate:
    def test_tallies_across_documents_with_detection_on_its_own_line(self) -> None:
        docs = [
            score_document(goldens(golden_trade()), preds(pred_trade())),  # found + all correct
            score_document(goldens(golden_trade()), preds()),  # missed entirely
        ]
        scores = {s.field: s for s in aggregate(docs)}
        detection = scores[DETECTION_FIELD]
        assert (detection.correct, detection.missed, detection.total) == (1, 1, 2)
        # Field lines only count the matched pair — denominator 1, not 2.
        assert scores["quantity"].total == 1
        assert scores["quantity"].correct == 1

    def test_empty_input_gives_zeroed_rows_for_every_report_field(self) -> None:
        scores = aggregate([])
        assert [s.field for s in scores] == list(REPORT_FIELDS)
        assert all(s.total == 0 and s.accuracy is None for s in scores)

    def test_multi_trade_document_counts_each_matched_trade(self) -> None:
        two = score_document(
            goldens(
                golden_trade(),
                golden_trade(quantity="42500", nature="vesting of performance rights"),
            ),
            preds(
                pred_trade(),
                pred_trade(quantity="42500", nature="vesting of performance rights"),
            ),
        )
        scores = {s.field: s for s in aggregate([two])}
        assert scores[DETECTION_FIELD].correct == 2
        assert scores["quantity"].total == 2
