"""Tests for the study runner's alignment logic: day-0 rule and window slicing.

The statistics live in event_study (tested there); what can silently corrupt a
study is the calendar work — announcing after the close, non-trading days,
windows running off the data's edge. That's what these pin down.
"""

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from asx_engine.events.study_runner import (
    ESTIMATION,
    EVENT,
    day_zero,
    slice_windows,
)

# Mon 2026-06-01 .. Fri 2026-06-12, weekdays only (a 10-day toy calendar).
DAYS = pd.DatetimeIndex(pd.bdate_range("2026-06-01", "2026-06-12"))


def sydney(y: int, m: int, d: int, hour: int) -> datetime:
    # Sydney is UTC+10 in June: build the UTC instant for that local hour.
    return datetime(y, m, d, hour - 10, tzinfo=UTC)


class TestDayZero:
    def test_before_close_on_trading_day_is_same_day(self) -> None:
        assert day_zero(sydney(2026, 6, 2, 10), DAYS) == pd.Timestamp("2026-06-02")

    def test_after_close_rolls_to_next_trading_day(self) -> None:
        assert day_zero(sydney(2026, 6, 2, 17), DAYS) == pd.Timestamp("2026-06-03")

    def test_friday_after_close_rolls_over_the_weekend(self) -> None:
        assert day_zero(sydney(2026, 6, 5, 18), DAYS) == pd.Timestamp("2026-06-08")

    def test_weekend_announcement_lands_monday(self) -> None:
        assert day_zero(sydney(2026, 6, 6, 11), DAYS) == pd.Timestamp("2026-06-08")

    def test_past_the_end_of_data_is_none(self) -> None:
        assert day_zero(sydney(2026, 6, 15, 10), DAYS) is None


class TestSliceWindows:
    def _aligned(self, n: int) -> pd.DataFrame:
        idx = pd.DatetimeIndex(pd.bdate_range("2024-01-01", periods=n))
        rng = np.random.default_rng(7)
        return pd.DataFrame(
            {"stock": rng.normal(0, 0.01, n), "market": rng.normal(0, 0.01, n)}, index=idx
        )

    def test_full_windows_slice_to_configured_lengths(self) -> None:
        aligned = self._aligned(400)
        day0 = aligned.index[200]
        windows = slice_windows(aligned, day0)
        assert windows is not None
        estimation, event = windows
        assert len(estimation) == ESTIMATION[1] - ESTIMATION[0] + 1
        assert len(event) == EVENT[1] - EVENT[0] + 1
        # Day 0 sits at the right offset inside the event window.
        assert event.index[-EVENT[0]] == day0

    def test_event_too_early_for_estimation_window_is_dropped(self) -> None:
        aligned = self._aligned(400)
        assert slice_windows(aligned, aligned.index[50]) is None  # needs 120 before

    def test_event_too_close_to_the_end_is_dropped(self) -> None:
        aligned = self._aligned(400)
        assert slice_windows(aligned, aligned.index[-5]) is None  # needs +20 after

    def test_day0_not_an_observation_for_this_stock_is_dropped(self) -> None:
        aligned = self._aligned(400)
        missing = aligned.index[200]
        gappy = aligned.drop(index=missing)  # stock halted on day0
        assert slice_windows(gappy, missing) is None
