"""Tests for extraction output schemas (SourcedField, earnings, guidance)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from asx_engine.schemas import (
    EarningsResult,
    ExtractionRecord,
    GuidanceDirection,
    GuidanceStatement,
    ReportedMetric,
    SourcedField,
)


def money(value: str | None, confidence: float = 0.9) -> dict[str, object]:
    """Build a SourcedField[Decimal] payload the way the LLM will: from JSON."""
    return {
        "value": value,
        "confidence": confidence,
        "source_quote": None if value is None else f"reported {value}",
        "page": None if value is None else 1,
    }


class TestSourcedField:
    def test_decimal_parsed_from_json_string(self) -> None:
        # The LLM emits JSON; "1234500000.50" must arrive as an exact Decimal,
        # not a float that's already lost precision.
        field = SourcedField[Decimal].model_validate(money("1234500000.50"))
        assert field.value == Decimal("1234500000.50")

    def test_value_is_required_even_when_absent(self) -> None:
        # Omitting `value` is a schema violation; asserting absence requires
        # an explicit null. "Skipped" and "not in document" must never blur.
        with pytest.raises(ValidationError):
            SourcedField[Decimal].model_validate({"confidence": 0.5})

    def test_explicit_absence_is_valid(self) -> None:
        field = SourcedField[Decimal].model_validate(money(None))
        assert field.value is None

    @pytest.mark.parametrize("confidence", [-0.1, 1.1])
    def test_confidence_bounds(self, confidence: float) -> None:
        with pytest.raises(ValidationError):
            SourcedField[Decimal].model_validate(money("1", confidence=confidence))

    def test_type_parameter_is_enforced(self) -> None:
        with pytest.raises(ValidationError):
            SourcedField[Decimal].model_validate(money("not a number"))


class TestEarningsResult:
    def test_full_result_parses(self) -> None:
        result = EarningsResult.model_validate(
            {
                "period": {"value": "1H FY2026", "confidence": 0.95},
                "reporting_currency": {"value": "AUD", "confidence": 0.99},
                "revenue": {"current": money("27200000000"), "prior": money("25900000000")},
                "npat": {"current": money("5100000000"), "prior": money("4800000000")},
                "eps_cents": {"current": money("100.6"), "prior": money("94.7")},
                "dividend_cents": {"current": money("110"), "prior": money("102")},
            }
        )
        assert result.revenue.current.value == Decimal("27200000000")
        assert result.eps_cents.prior.value == Decimal("94.7")

    def test_missing_dividend_is_explicit_not_omitted(self) -> None:
        metric = ReportedMetric.model_validate({"current": money(None), "prior": money(None)})
        assert metric.current.value is None


class TestGuidanceStatement:
    def valid_payload(self) -> dict[str, object]:
        return {
            "direction": {"value": "downgrade", "confidence": 0.9},
            "metric": {"value": "EBITDA", "confidence": 0.9},
            "basis": {"value": "underlying", "confidence": 0.8},
            "period": {"value": "FY2027", "confidence": 0.95},
            "range_low_aud": money("400000000"),
            "range_high_aud": money("450000000"),
        }

    def test_direction_enum_from_string(self) -> None:
        guidance = GuidanceStatement.model_validate(self.valid_payload())
        assert guidance.direction.value is GuidanceDirection.DOWNGRADE

    def test_unknown_direction_rejected(self) -> None:
        payload = self.valid_payload()
        payload["direction"] = {"value": "sideways", "confidence": 0.9}
        with pytest.raises(ValidationError):
            GuidanceStatement.model_validate(payload)

    def test_inverted_range_rejected(self) -> None:
        payload = self.valid_payload()
        payload["range_low_aud"] = money("450000000")
        payload["range_high_aud"] = money("400000000")
        with pytest.raises(ValidationError, match="range inverted"):
            GuidanceStatement.model_validate(payload)

    def test_open_ended_range_allowed(self) -> None:
        # "at least $400m" guidance has no upper bound — explicit null is fine.
        payload = self.valid_payload()
        payload["range_high_aud"] = money(None)
        guidance = GuidanceStatement.model_validate(payload)
        assert guidance.range_high_aud.value is None


class TestExtractionRecord:
    def test_envelope_binds_payload_to_provenance(self) -> None:
        record = ExtractionRecord[GuidanceStatement](
            content_hash="b" * 64,
            model="claude-opus-4-8",
            prompt_version="guidance_v1",
            extracted_at=datetime(2026, 6, 11, 12, 0, tzinfo=UTC),
            payload=GuidanceStatement.model_validate(TestGuidanceStatement().valid_payload()),
        )
        assert record.payload.metric.value == "EBITDA"
        assert record.extracted_at.tzinfo == UTC

    def test_payload_must_be_a_model(self) -> None:
        # The bound `[PayloadT: BaseModel]` is enforced statically by mypy;
        # at runtime pydantic still validates the declared payload type.
        class NotGuidance(BaseModel):
            x: int

        with pytest.raises(ValidationError):
            ExtractionRecord[GuidanceStatement](
                content_hash="b" * 64,
                model="claude-opus-4-8",
                prompt_version="guidance_v1",
                extracted_at=datetime(2026, 6, 11, 12, 0, tzinfo=UTC),
                payload=NotGuidance(x=1),  # type: ignore[arg-type]
            )


class TestGuidanceResult:
    def test_empty_statements_is_valid(self):
        from asx_engine.schemas.extraction import GuidanceResult

        assert GuidanceResult(statements=[]).statements == []

    def test_withdrawn_and_initiated_directions_exist(self):
        from asx_engine.schemas.extraction import GuidanceDirection

        assert GuidanceDirection("withdrawn") is GuidanceDirection.WITHDRAWN
        assert GuidanceDirection("initiated") is GuidanceDirection.INITIATED
