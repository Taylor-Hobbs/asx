"""Tests for the price loader's pure logic: symbol mapping, coverage, reshaping.

The yfinance call and the BQ load are the integration's problem; what these
pin down is the logic that decides which tickers a study may trust.
"""

from datetime import date

import pandas as pd

from asx_engine.prices.loader import (
    INDEX_TICKER,
    classify_coverage,
    frame_to_rows,
    to_yahoo,
)


class TestSymbolMapping:
    def test_asx_codes_get_the_ax_suffix(self) -> None:
        assert to_yahoo("BHP") == "BHP.AX"

    def test_the_index_maps_to_yahoos_axjo(self) -> None:
        # Yahoo's ASX 200 symbol is ^AXJO, not ^XJO — the first run failed on
        # exactly this, caught by the fail-loud index check.
        assert to_yahoo(INDEX_TICKER) == "^AXJO"


class TestCoverage:
    def test_buckets_ok_short_and_empty(self) -> None:
        rows = {"BHP": 500, "THIN": 100, INDEX_TICKER: 500}
        coverage = classify_coverage(rows, index_days=500, tickers=["BHP", "THIN", "GONE"])
        assert coverage.ok == ["BHP"]
        assert coverage.short_history == {"THIN": 100}
        assert coverage.empty == ["GONE"]

    def test_ninety_percent_of_index_days_is_the_line(self) -> None:
        rows = {"JUST": 450, "UNDER": 449}
        coverage = classify_coverage(rows, index_days=500, tickers=["JUST", "UNDER"])
        assert coverage.ok == ["JUST"]
        assert "UNDER" in coverage.short_history


class TestFrameToRows:
    def _wide(self) -> pd.DataFrame:
        idx = pd.to_datetime(["2026-01-05", "2026-01-06"])
        cols = pd.MultiIndex.from_product([["BHP.AX", "^AXJO"], ["Close", "Adj Close", "Volume"]])
        frame = pd.DataFrame(
            [[40.0, 39.5, 1000.0, 8500.0, 8500.0, 0.0], [41.0, 40.5, 1100.0, 8550.0, 8550.0, 0.0]],
            index=idx,
            columns=cols,
        )
        return frame

    def test_wide_multiindex_becomes_long_rows(self) -> None:
        rows = frame_to_rows(self._wide(), ["BHP", INDEX_TICKER])
        assert set(rows["ticker"]) == {"BHP", INDEX_TICKER}
        assert len(rows) == 4
        bhp = rows[rows["ticker"] == "BHP"].iloc[0]
        assert bhp["close"] == 40.0
        assert bhp["adj_close"] == 39.5
        assert bhp["date"] == date(2026, 1, 5)

    def test_nan_close_rows_drop_out(self) -> None:
        wide = self._wide()
        wide.loc[wide.index[0], ("BHP.AX", "Close")] = float("nan")
        rows = frame_to_rows(wide, ["BHP", INDEX_TICKER])
        assert len(rows[rows["ticker"] == "BHP"]) == 1

    def test_missing_ticker_is_skipped_not_fatal(self) -> None:
        rows = frame_to_rows(self._wide(), ["BHP", "GONE", INDEX_TICKER])
        assert "GONE" not in set(rows["ticker"])
