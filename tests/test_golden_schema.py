"""Tests for the golden-label schema: the contract hand labels are typed against."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from asx_engine.schemas import GoldenEarningsLabels, GoldenLabel, GoldenMetric, LabelStatus

ANNOUNCED_AT = datetime(2026, 2, 18, 8, 15, tzinfo=UTC)
HASH = "1" * 64


def empty_labels() -> GoldenEarningsLabels:
    metric = GoldenMetric(current=None, prior=None)
    return GoldenEarningsLabels(
        period=None,
        revenue=metric,
        npat=metric,
        eps_cents=metric,
        dividend_cents=metric,
    )


def stub(**overrides: object) -> GoldenLabel:
    fields: dict[str, object] = {
        "ticker": "WES",
        "announcement_id": "03091234",
        "announced_at": ANNOUNCED_AT,
        "headline": "2026 Half-year results",
        "content_hash": HASH,
        "labels": empty_labels(),
    }
    fields.update(overrides)
    return GoldenLabel.model_validate(fields)


class TestGoldenLabel:
    def test_fresh_stub_is_valid_and_unlabeled(self) -> None:
        label = stub()
        assert label.status is LabelStatus.UNLABELED
        assert label.dataset_version == "golden_v1"

    def test_labeled_requires_attribution(self) -> None:
        with pytest.raises(ValidationError, match="who labeled it and when"):
            stub(status="labeled")

    def test_labeled_with_attribution_is_valid(self) -> None:
        label = stub(status="labeled", labeled_by="Taylor", labeled_at=date(2026, 6, 14))
        assert label.status is LabelStatus.LABELED

    def test_excluded_requires_a_reason(self) -> None:
        with pytest.raises(ValidationError, match="must say why"):
            stub(status="excluded")

    def test_monetary_strings_parse_to_exact_decimals(self) -> None:
        json_metric = '{"current": "24212000000", "prior": "141.4"}'
        metric = GoldenMetric.model_validate_json(json_metric)
        assert metric.current == Decimal("24212000000")
        assert metric.prior == Decimal("141.4")

    def test_naive_announced_at_rejected(self) -> None:
        with pytest.raises(ValidationError):
            stub(announced_at=datetime(2026, 2, 18))  # no tzinfo
