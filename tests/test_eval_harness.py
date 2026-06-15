"""Tests for the eval harness: scoring core and the run/aggregate wiring.

The scoring logic in `asx_engine.eval.harness` is the real risk and is tested
directly with synthetic goldens and predictions. The job is tested against a
structural FakeBackend exactly like the parse and extraction jobs — BigQuery
and the filesystem are the integration's problem, not a unit test's.
"""

from datetime import UTC, datetime
from decimal import Decimal

from asx_engine.eval.harness import SCORED_FIELDS, aggregate, score_document, score_field
from asx_engine.eval.job import EvalReport, run
from asx_engine.schemas import (
    EarningsResult,
    EvalRun,
    GoldenEarningsLabels,
    GoldenLabel,
    GoldenMetric,
    LabelStatus,
    ReportedMetric,
    SourcedField,
)
from asx_engine.schemas.eval import FieldOutcome

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64

EVALUATED_AT = datetime(2026, 6, 15, tzinfo=UTC)


# --- builders -------------------------------------------------------------


def sourced(value: object, quote: str | None = "quoted") -> SourcedField:  # type: ignore[type-arg]
    return SourcedField(value=value, confidence=0.9, source_quote=quote, page=1)


def pred_metric(current: str | None, prior: str | None) -> ReportedMetric:
    cur = Decimal(current) if current is not None else None
    pri = Decimal(prior) if prior is not None else None
    return ReportedMetric(current=sourced(cur, None), prior=sourced(pri, None))


def prediction(
    period: str | None = "1H FY2026",
    currency: str | None = "AUD",
    revenue: tuple[str | None, str | None] = ("24212000000", "23490000000"),
    npat: tuple[str | None, str | None] = ("1603000000", "1510000000"),
    eps: tuple[str | None, str | None] = ("207", "195"),
    dividend: tuple[str | None, str | None] = ("145", "140"),
) -> EarningsResult:
    return EarningsResult(
        period=sourced(period, None),
        reporting_currency=sourced(currency, None),
        revenue=pred_metric(*revenue),
        npat=pred_metric(*npat),
        eps_cents=pred_metric(*eps),
        dividend_cents=pred_metric(*dividend),
    )


def gold_metric(current: str | None, prior: str | None) -> GoldenMetric:
    return GoldenMetric(
        current=Decimal(current) if current is not None else None,
        prior=Decimal(prior) if prior is not None else None,
    )


def golden_labels(
    period: str | None = "1H FY2026",
    currency: str = "AUD",
    revenue: tuple[str | None, str | None] = ("24212000000", "23490000000"),
    npat: tuple[str | None, str | None] = ("1603000000", "1510000000"),
    eps: tuple[str | None, str | None] = ("207", "195"),
    dividend: tuple[str | None, str | None] = ("145", "140"),
) -> GoldenEarningsLabels:
    return GoldenEarningsLabels(
        period=period,
        reporting_currency=currency,
        revenue=gold_metric(*revenue),
        npat=gold_metric(*npat),
        eps_cents=gold_metric(*eps),
        dividend_cents=gold_metric(*dividend),
    )


def golden_label(content_hash: str, labels: GoldenEarningsLabels, **kw: object) -> GoldenLabel:
    return GoldenLabel(
        ticker="WES",
        announcement_id="03061906",
        announced_at=datetime(2026, 2, 18, 21, 6, tzinfo=UTC),
        headline="2026 Half-year results",
        content_hash=content_hash,
        status=LabelStatus.LABELED,
        labels=labels,
        labeled_by="Taylor Hobbs",
        labeled_at=datetime(2026, 6, 14, tzinfo=UTC).date(),
        **kw,  # type: ignore[arg-type]
    )


# --- score_field: the four outcomes ---------------------------------------


class TestScoreField:
    def test_equal_values_are_correct(self) -> None:
        assert score_field(Decimal("100"), Decimal("100")) is FieldOutcome.CORRECT

    def test_both_null_is_correct_not_skipped(self) -> None:
        # A correct "not stated" assertion is a scored success (USD reporters).
        assert score_field(None, None) is FieldOutcome.CORRECT

    def test_golden_null_pred_value_is_hallucinated(self) -> None:
        assert score_field(None, Decimal("100")) is FieldOutcome.HALLUCINATED

    def test_golden_value_pred_null_is_missed(self) -> None:
        assert score_field(Decimal("100"), None) is FieldOutcome.MISSED

    def test_different_values_are_wrong(self) -> None:
        assert score_field(Decimal("100"), Decimal("101")) is FieldOutcome.WRONG

    def test_decimal_equality_ignores_trailing_zeros_and_exponent(self) -> None:
        assert score_field(Decimal("141.4"), Decimal("141.40")) is FieldOutcome.CORRECT
        assert score_field(Decimal("24212000000"), Decimal("2.4212E10")) is FieldOutcome.CORRECT

    def test_period_match_is_whitespace_and_case_normalized(self) -> None:
        assert score_field("1H FY2026", "1h   fy2026") is FieldOutcome.CORRECT

    def test_period_genuine_disagreement_is_wrong(self) -> None:
        assert score_field("1H FY2026", "FY2026") is FieldOutcome.WRONG


# --- score_document / aggregate -------------------------------------------


class TestScoreDocument:
    def test_perfect_prediction_is_all_correct(self) -> None:
        outcomes = score_document(golden_labels(), prediction())
        assert set(outcomes) == {f.name for f in SCORED_FIELDS}
        assert all(o is FieldOutcome.CORRECT for o in outcomes.values())

    def test_each_failure_mode_lands_on_the_right_field(self) -> None:
        golden = golden_labels(
            revenue=("24212000000", "23490000000"),  # both stated
            npat=("1603000000", "1510000000"),
            dividend=(None, None),  # document states no dividend
        )
        pred = prediction(
            revenue=("99999999999", "23490000000"),  # current wrong, prior right
            npat=("1603000000", None),  # prior missed
            dividend=("145", None),  # current hallucinated
        )
        outcomes = score_document(golden, pred)
        assert outcomes["revenue.current"] is FieldOutcome.WRONG
        assert outcomes["revenue.prior"] is FieldOutcome.CORRECT
        assert outcomes["npat.prior"] is FieldOutcome.MISSED
        assert outcomes["dividend_cents.current"] is FieldOutcome.HALLUCINATED

    def test_reporting_currency_is_scored(self) -> None:
        # A USD reporter read as USD is correct; reading it as AUD is wrong even
        # if the figure matches — the currency field is what catches that.
        usd = score_document(golden_labels(currency="USD"), prediction(currency="USD"))
        assert usd["reporting_currency"] is FieldOutcome.CORRECT
        mismatch = score_document(golden_labels(currency="USD"), prediction(currency="AUD"))
        assert mismatch["reporting_currency"] is FieldOutcome.WRONG


class TestAggregate:
    def test_tallies_outcomes_per_field_across_documents(self) -> None:
        # Three real scored documents: period 2 correct / 1 wrong;
        # revenue.current 2 correct / 1 missed.
        docs = [
            score_document(golden_labels(), prediction()),  # all correct
            score_document(golden_labels(), prediction(period="FY2026")),  # period wrong
            score_document(  # revenue.current missed, period still correct
                golden_labels(revenue=("100", "200")),
                prediction(revenue=(None, "200")),
            ),
        ]
        scores = {s.field: s for s in aggregate(docs)}
        period = scores["period"]
        assert (period.correct, period.wrong, period.total) == (2, 1, 3)
        assert period.accuracy is not None and abs(period.accuracy - 2 / 3) < 1e-9
        revenue = scores["revenue.current"]
        assert (revenue.correct, revenue.missed, revenue.total) == (2, 1, 3)

    def test_empty_input_gives_zeroed_fields_with_null_accuracy(self) -> None:
        scores = aggregate([])
        assert len(scores) == len(SCORED_FIELDS)
        assert all(s.total == 0 and s.accuracy is None for s in scores)


# --- the run() wiring against a structural fake ---------------------------


class FakeBackend:
    """Satisfies the EvalBackend Protocol structurally; records what was saved."""

    def __init__(
        self,
        goldens: list[GoldenLabel],
        extractions: dict[str, EarningsResult],
    ) -> None:
        self._goldens = goldens
        self._extractions = extractions
        self.saved: list[EvalRun] = []

    def labeled_goldens(self, dataset_version: str) -> list[GoldenLabel]:
        return [g for g in self._goldens if g.dataset_version == dataset_version]

    def extractions(self, model: str, prompt_version: str) -> dict[str, EarningsResult]:
        return self._extractions

    def save(self, run: EvalRun) -> None:
        self.saved.append(run)


def _run(backend: FakeBackend) -> EvalReport:
    return run(
        backend,
        model="claude-opus-4-8",
        prompt_version="earnings_v1",
        evaluated_at=EVALUATED_AT,
    )


class TestRun:
    def test_scores_matched_goldens_and_persists_one_run(self) -> None:
        backend = FakeBackend(
            goldens=[golden_label(HASH_A, golden_labels())],
            extractions={HASH_A: prediction()},
        )
        report = _run(backend)
        assert report.run.n_documents == 1
        assert report.run.n_skipped == 0
        assert report.run.overall_accuracy == 1.0
        assert len(backend.saved) == 1
        assert backend.saved[0].evaluated_at == EVALUATED_AT

    def test_golden_without_extraction_is_skipped_not_scored(self) -> None:
        backend = FakeBackend(
            goldens=[golden_label(HASH_A, golden_labels()), golden_label(HASH_B, golden_labels())],
            extractions={HASH_A: prediction()},
        )
        report = _run(backend)
        assert report.run.n_documents == 1
        assert report.run.n_skipped == 1
        assert [g.content_hash for g in report.skipped] == [HASH_B]

    def test_empty_golden_set_runs_but_persists_nothing(self) -> None:
        backend = FakeBackend(goldens=[], extractions={})
        report = _run(backend)
        assert report.run.n_documents == 0
        assert report.run.overall_accuracy is None
        assert backend.saved == []  # the eval_runs history starts with real labels

    def test_wrong_field_shows_up_in_the_persisted_field_scores(self) -> None:
        backend = FakeBackend(
            goldens=[golden_label(HASH_A, golden_labels(revenue=("100", "200")))],
            extractions={HASH_A: prediction(revenue=("999", "200"))},
        )
        report = _run(backend)
        by_field = {s.field: s for s in report.run.field_scores}
        assert by_field["revenue.current"].wrong == 1
        assert by_field["revenue.prior"].correct == 1


class TestEvalRunSerialization:
    def test_model_dump_includes_computed_totals_for_bigquery(self) -> None:
        # The BQ load relies on model_dump(mode="json") carrying total/accuracy.
        run_obj = EvalRun(
            model="m",
            prompt_version="earnings_v1",
            dataset_version="golden_v1",
            evaluated_at=EVALUATED_AT,
            n_documents=1,
            n_skipped=0,
            field_scores=aggregate([score_document(golden_labels(), prediction())]),
        )
        dumped = run_obj.model_dump(mode="json")
        assert "overall_accuracy" in dumped
        first = dumped["field_scores"][0]
        assert {"field", "correct", "wrong", "missed", "hallucinated", "total", "accuracy"} <= set(
            first
        )
