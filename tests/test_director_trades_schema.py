"""Tests for the DirectorTradesResult schema."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from asx_engine.schemas.director_trades import (
    DirectorTrade,
    DirectorTradesResult,
    GoldenDirectorTrade,
    GoldenDirectorTradesLabels,
    TradeType,
)


def sf(value: object, quote: str = "form field") -> dict:
    return {"value": value, "confidence": 0.95, "source_quote": quote, "page": 1}


def trade_payload(**overrides: object) -> dict:
    base = {
        "director_name": sf("Jane Smith"),
        "director_role": sf("Non-Executive Director"),
        "trade_type": sf("acquisition"),
        "nature": sf("on-market purchase"),
        "security_class": sf("ordinary shares"),
        "quantity": sf("10000"),
        "price_per_security": sf("45.20"),
        "total_consideration": sf("452000"),
        "trade_date": sf("2026-05-15"),
        "holdings_before": sf("50000"),
        "holdings_after": sf("60000"),
    }
    base.update(overrides)
    return base


class TestDirectorTrade:
    def test_full_trade_parses(self) -> None:
        result = DirectorTradesResult.model_validate({"trades": [trade_payload()]})
        t = result.trades[0]
        assert t.trade_type.value is TradeType.ACQUISITION
        assert t.quantity.value == Decimal("10000")
        assert t.price_per_security.value == Decimal("45.20")
        assert t.trade_date.value == date(2026, 5, 15)
        assert t.holdings_after.value == Decimal("60000")

    def test_nil_consideration_trade(self) -> None:
        payload = trade_payload(
            trade_type=sf("acquisition"),
            nature=sf("vesting of performance rights"),
            price_per_security={"value": None, "confidence": 1.0, "source_quote": None, "page": None},
            total_consideration={"value": None, "confidence": 1.0, "source_quote": None, "page": None},
        )
        result = DirectorTradesResult.model_validate({"trades": [payload]})
        t = result.trades[0]
        assert t.price_per_security.value is None
        assert t.total_consideration.value is None

    def test_disposal(self) -> None:
        payload = trade_payload(trade_type=sf("disposal"))
        result = DirectorTradesResult.model_validate({"trades": [payload]})
        assert result.trades[0].trade_type.value is TradeType.DISPOSAL

    def test_unknown_trade_type_rejected(self) -> None:
        payload = trade_payload(trade_type=sf("transfer"))
        with pytest.raises(ValidationError):
            DirectorTradesResult.model_validate({"trades": [payload]})

    def test_multiple_trades_in_one_result(self) -> None:
        result = DirectorTradesResult.model_validate(
            {"trades": [trade_payload(), trade_payload(trade_type=sf("disposal"))]}
        )
        assert len(result.trades) == 2
        assert result.trades[1].trade_type.value is TradeType.DISPOSAL

    def test_empty_trades_list_is_valid(self) -> None:
        result = DirectorTradesResult.model_validate({"trades": []})
        assert result.trades == []

    def test_json_round_trip(self) -> None:
        result = DirectorTradesResult.model_validate({"trades": [trade_payload()]})
        result2 = DirectorTradesResult.model_validate_json(result.model_dump_json())
        assert result2.trades[0].quantity.value == Decimal("10000")
        assert result2.trades[0].trade_date.value == date(2026, 5, 15)


class TestGoldenDirectorTrade:
    def test_full_golden_trade(self) -> None:
        t = GoldenDirectorTrade(
            director_name="Jane Smith",
            trade_type=TradeType.ACQUISITION,
            quantity=Decimal("10000"),
            price_per_security=Decimal("45.20"),
            total_consideration=Decimal("452000"),
            trade_date=date(2026, 5, 15),
            holdings_after=Decimal("60000"),
        )
        assert t.trade_type is TradeType.ACQUISITION
        assert t.price_per_security == Decimal("45.20")

    def test_optional_fields_default_null(self) -> None:
        t = GoldenDirectorTrade(
            director_name="Jane Smith",
            trade_type=TradeType.DISPOSAL,
            quantity=Decimal("5000"),
            trade_date=date(2026, 5, 15),
        )
        assert t.price_per_security is None
        assert t.holdings_before is None
