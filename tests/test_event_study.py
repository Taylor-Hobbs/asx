"""Tests for the event study core: known-by-construction synthetic returns.

The discipline mirrors the eval harness tests: every assertion is against an
answer the test itself constructs — a stock built as α + β·market + noise must
give back that α and β; an injected +2% event-day jump must surface in AR,
CAAR and both test statistics; a null cohort must NOT reject.
"""

from math import sqrt

import numpy as np
import pytest

from asx_engine.events.event_study import (
    aggregate_cohort,
    fit_market_model,
    forecast_error_factor,
    study_event,
    z_to_p,
)

RNG = np.random.default_rng(seed=42)  # determinism: same draws every run

EST, WINDOW = 100, 11  # estimation days; event days (e.g. -5..+5)


def market(n: int = EST) -> np.ndarray:
    return RNG.normal(0.0003, 0.01, n)


def stock_from(mkt: np.ndarray, alpha: float, beta: float, noise_std: float) -> np.ndarray:
    return alpha + beta * mkt + RNG.normal(0.0, noise_std, len(mkt))


class TestMarketModel:
    def test_recovers_constructed_alpha_and_beta(self) -> None:
        mkt = market(2000)  # long window shrinks estimation error
        stock = stock_from(mkt, alpha=0.0005, beta=1.4, noise_std=0.01)
        model = fit_market_model(stock, mkt)
        assert model.beta == pytest.approx(1.4, abs=0.1)
        assert model.alpha == pytest.approx(0.0005, abs=0.001)
        assert model.residual_std == pytest.approx(0.01, rel=0.1)

    def test_perfect_fit_has_zero_residual_std(self) -> None:
        mkt = market()
        model = fit_market_model(0.001 + 2.0 * mkt, mkt)
        assert model.residual_std == pytest.approx(0.0, abs=1e-12)

    def test_rejects_mismatched_lengths_and_constant_market(self) -> None:
        with pytest.raises(ValueError, match="length mismatch"):
            fit_market_model(np.zeros(10), np.zeros(9))
        with pytest.raises(ValueError, match="constant"):
            fit_market_model(market(10), np.full(10, 0.01))


class TestForecastErrorFactor:
    def test_always_inflates_never_deflates(self) -> None:
        mkt = market()
        model = fit_market_model(stock_from(mkt, 0.0, 1.0, 0.01), mkt)
        factor = forecast_error_factor(model, market(WINDOW))
        assert (factor > 1.0).all()

    def test_larger_for_unusual_market_days(self) -> None:
        mkt = market()
        model = fit_market_model(stock_from(mkt, 0.0, 1.0, 0.01), mkt)
        calm, wild = forecast_error_factor(model, np.array([model.market_mean, 0.08]))
        assert wild > calm


class TestStudyEvent:
    def test_injected_jump_appears_in_event_ar(self) -> None:
        mkt_est, mkt_evt = market(), market(WINDOW)
        stock_est = stock_from(mkt_est, 0.0, 1.0, 0.01)
        stock_evt = stock_from(mkt_evt, 0.0, 1.0, 0.01)
        stock_evt[5] += 0.05  # +5% abnormal jump on day index 5
        result = study_event(stock_est, mkt_est, stock_evt, mkt_evt)
        assert result.event_ar[5] == pytest.approx(0.05, abs=0.03)
        assert abs(result.event_sar[5]) > 2.0  # clearly standout after standardization

    def test_null_event_ars_are_small(self) -> None:
        mkt_est, mkt_evt = market(), market(WINDOW)
        result = study_event(
            stock_from(mkt_est, 0.0, 1.0, 0.01),
            mkt_est,
            stock_from(mkt_evt, 0.0, 1.0, 0.01),
            mkt_evt,
        )
        assert np.abs(result.event_ar).max() < 0.04  # ~4σ bound on 1% noise


def cohort(n_events: int, jump: float, day: int = 5) -> list:
    events = []
    for _ in range(n_events):
        mkt_est, mkt_evt = market(), market(WINDOW)
        stock_est = stock_from(mkt_est, 0.0, 1.0, 0.01)
        stock_evt = stock_from(mkt_evt, 0.0, 1.0, 0.01)
        stock_evt[day] += jump
        events.append(study_event(stock_est, mkt_est, stock_evt, mkt_evt))
    return events


class TestAggregateCohort:
    def test_positive_effect_detected_by_both_statistics(self) -> None:
        stats = aggregate_cohort(cohort(40, jump=0.02))
        assert stats.n_events == 40
        # CAAR ends near the injected +2%.
        assert stats.caar[-1] == pytest.approx(0.02, abs=0.01)
        # BMP rejects the null in the right direction. (A +2% jump against 1%
        # daily noise across an 11-day window gives E[z] ≈ 3.6 at n=40, but
        # the seed's draw sits ~1σ under — 2.0/0.05 is the honest line.)
        assert stats.bmp_z > 2.0
        assert stats.bmp_p < 0.05
        # Corrado's day-5 z is the cohort's largest and significant.
        assert int(np.argmax(stats.corrado_z)) == 5
        assert stats.corrado_p[5] < 0.01

    def test_null_cohort_does_not_reject(self) -> None:
        stats = aggregate_cohort(cohort(40, jump=0.0))
        assert abs(stats.bmp_z) < 2.5
        assert abs(stats.caar[-1]) < 0.01

    def test_negative_effect_gives_negative_statistics(self) -> None:
        stats = aggregate_cohort(cohort(40, jump=-0.02))
        assert stats.bmp_z < -3.0
        assert stats.corrado_z[5] < -2.0

    def test_empty_and_ragged_cohorts_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            aggregate_cohort([])
        ragged = cohort(2, jump=0.0)
        ragged[0] = study_event(
            stock_from(market(), 0.0, 1.0, 0.01),
            market(),
            stock_from(market(5), 0.0, 1.0, 0.01),
            market(5),
        )
        with pytest.raises(ValueError, match="differ in length"):
            aggregate_cohort(ragged)


class TestZToP:
    def test_reference_values(self) -> None:
        assert z_to_p(0.0) == pytest.approx(1.0)
        assert z_to_p(1.96) == pytest.approx(0.05, abs=0.001)
        assert z_to_p(-1.96) == pytest.approx(0.05, abs=0.001)  # two-sided, symmetric

    def test_scar_scaling_uses_window_length(self) -> None:
        # Guard the sqrt(L) convention: a cohort of identical unit SARs over
        # an 11-day window has SCAR = 11/sqrt(11) = sqrt(11) each.
        events = cohort(3, jump=0.0)
        scar = float(np.sum(events[0].event_sar)) / sqrt(WINDOW)
        assert scar == pytest.approx(np.sum(events[0].event_sar) / np.sqrt(11))
