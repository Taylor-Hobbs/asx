"""Event study core: market-model abnormal returns with honest test statistics.

Pure numpy, no I/O — the runner assembles aligned return arrays from BigQuery;
this module does the statistics. Tests drive it with synthetic returns where
the right answer is known by construction, exactly like the eval harness.

The estimator is the classic market model (MacKinlay 1997): regress each
stock's daily log return on the index over an ESTIMATION window that ends
before the event window begins, then abnormal return = actual − (α + β·mkt)
through the EVENT window. Two significance tests, because each covers the
other's blind spot:

- **BMP (Boehmer–Musumeci–Poulsen 1991).** Standardize each event's abnormal
  returns by its estimation residual std, inflated by the forecast-error
  correction (a prediction outside the estimation sample is noisier than a
  fitted point), then t-test the cross-section of standardized CARs. Robust to
  event-induced variance — the classic Patell test's failure mode.
- **Corrado (1989) rank test.** Rank each event's ARs across estimation +
  event days jointly and ask whether event-day ranks are higher than the
  middle rank. Non-parametric: daily returns are fat-tailed and skewed, and
  ranks don't care. When BMP and Corrado disagree, believe Corrado.

Sign conventions: everything is "positive = good news". Disposal cohorts are
expected to show negative CAAR; the runner does not flip signs.
"""

from dataclasses import dataclass
from math import erfc, sqrt

import numpy as np

# Type alias for readability: 1-D float array of daily log returns.
Returns = np.ndarray


@dataclass(frozen=True)
class MarketModel:
    """One event's fitted market model and its estimation diagnostics."""

    alpha: float
    beta: float
    residual_std: float
    n_obs: int
    market_mean: float  # of the estimation window — feeds the BMP correction
    market_ss: float  # Σ(mkt − mean)² over estimation — same


@dataclass(frozen=True)
class EventResult:
    """One event, studied: abnormal returns and their standardization."""

    model: MarketModel
    estimation_ar: Returns  # residuals over the estimation window (Corrado needs them)
    event_ar: Returns  # abnormal returns over the event window
    event_sar: Returns  # standardized ARs (BMP forecast-error corrected)


def fit_market_model(stock: Returns, market: Returns) -> MarketModel:
    """OLS of stock on market over the estimation window.

    Closed form rather than np.polyfit: the intermediate quantities
    (market mean, Σ(mkt−mean)²) are exactly what the BMP forecast-error
    correction needs, so computing them once here keeps the two formulas
    visibly consistent.
    """
    if len(stock) != len(market):
        raise ValueError(f"length mismatch: stock {len(stock)} vs market {len(market)}")
    n = len(stock)
    if n < 3:
        raise ValueError(f"estimation window has {n} observations; cannot fit")
    market_mean = float(np.mean(market))
    market_dev = market - market_mean
    market_ss = float(np.sum(market_dev**2))
    # Not `== 0.0`: identical values still leave ~1e-35 of float dust after
    # the mean subtraction, and dividing by it would produce garbage betas.
    if market_ss < 1e-18:
        raise ValueError("market returns are constant over the estimation window")
    beta = float(np.sum(market_dev * (stock - np.mean(stock))) / market_ss)
    alpha = float(np.mean(stock) - beta * market_mean)
    residuals = stock - (alpha + beta * market)
    # ddof=2: two parameters estimated (α, β).
    residual_std = float(np.sqrt(np.sum(residuals**2) / (n - 2)))
    return MarketModel(
        alpha=alpha,
        beta=beta,
        residual_std=residual_std,
        n_obs=n,
        market_mean=market_mean,
        market_ss=market_ss,
    )


def forecast_error_factor(model: MarketModel, event_market: Returns) -> Returns:
    """Per-event-day std inflation for out-of-sample prediction.

    sqrt(1 + 1/T + (Rm_t − R̄m)² / Σ(Rm − R̄m)²): a prediction is noisier than
    a fitted point, more so on days when the market is far from its
    estimation-window mean. Dividing ARs by an UNinflated std would overstate
    significance — the whole point of BMP over a naive t.
    """
    deviation = (event_market - model.market_mean) ** 2
    return np.sqrt(1.0 + 1.0 / model.n_obs + deviation / model.market_ss)


def study_event(
    estimation_stock: Returns,
    estimation_market: Returns,
    event_stock: Returns,
    event_market: Returns,
) -> EventResult:
    """Fit on the estimation window, measure on the event window."""
    model = fit_market_model(estimation_stock, estimation_market)
    estimation_ar = estimation_stock - (model.alpha + model.beta * estimation_market)
    event_ar = event_stock - (model.alpha + model.beta * event_market)
    event_sar = event_ar / (model.residual_std * forecast_error_factor(model, event_market))
    return EventResult(
        model=model,
        estimation_ar=np.asarray(estimation_ar, dtype=float),
        event_ar=np.asarray(event_ar, dtype=float),
        event_sar=np.asarray(event_sar, dtype=float),
    )


def z_to_p(z: float) -> float:
    """Two-sided p-value for a standard-normal statistic. No scipy needed."""
    return erfc(abs(z) / sqrt(2.0))


@dataclass(frozen=True)
class CohortStats:
    """The aggregate a hypothesis is judged on."""

    n_events: int
    caar: Returns  # cumulative average abnormal return per event day
    mean_ar: Returns  # average AR per event day
    bmp_z: float  # over the whole event window (standardized CARs)
    bmp_p: float
    corrado_z: Returns  # per event day
    corrado_p: Returns


def aggregate_cohort(events: list[EventResult]) -> CohortStats:
    """Cross-sectional aggregation of same-length event windows.

    BMP over the window: each event's SCAR = ΣSAR / sqrt(L); the statistic is
    the plain t of the SCAR cross-section scaled to a z. Corrado per day:
    rank ARs within each event across estimation+event days jointly, compare
    event-day mean ranks against the expected middle rank.
    """
    if not events:
        raise ValueError("empty cohort")
    lengths = {len(e.event_ar) for e in events}
    if len(lengths) != 1:
        raise ValueError(f"event windows differ in length: {sorted(lengths)}")
    n = len(events)
    window = lengths.pop()

    ar_matrix = np.vstack([e.event_ar for e in events])  # (n_events, window)
    mean_ar = ar_matrix.mean(axis=0)
    caar = np.cumsum(mean_ar)

    # --- BMP over the full window ------------------------------------------
    scar = np.array([float(np.sum(e.event_sar)) / sqrt(window) for e in events])
    scar_std = float(np.std(scar, ddof=1)) if n > 1 else float("nan")
    bmp_z = float(np.mean(scar) / (scar_std / sqrt(n))) if n > 1 and scar_std > 0 else float("nan")

    # --- Corrado per event day ----------------------------------------------
    # Ranks are computed within each event over estimation+event days jointly;
    # ties get average ranks via double-argsort on midranked data. Expected
    # rank under the null is (T+1)/2 where T is that event's total day count.
    demeaned_rank_matrix = np.empty((n, window))
    variance_terms = np.empty(n)
    for i, event in enumerate(events):
        combined = np.concatenate([event.estimation_ar, event.event_ar])
        total_days = len(combined)
        order = combined.argsort()
        ranks = np.empty(total_days)
        ranks[order] = np.arange(1, total_days + 1)
        expected = (total_days + 1) / 2.0
        demeaned = ranks - expected
        demeaned_rank_matrix[i] = demeaned[-window:]  # the event-window days
        variance_terms[i] = float(np.mean(demeaned**2))
    # Cross-sectional mean demeaned rank per day, scaled by its null std.
    rank_std = sqrt(float(np.mean(variance_terms)) / n)
    corrado_z = demeaned_rank_matrix.mean(axis=0) / rank_std
    corrado_p = np.array([z_to_p(float(z)) for z in corrado_z])

    return CohortStats(
        n_events=n,
        caar=caar,
        mean_ar=mean_ar,
        bmp_z=bmp_z,
        bmp_p=z_to_p(bmp_z) if not np.isnan(bmp_z) else float("nan"),
        corrado_z=corrado_z,
        corrado_p=corrado_p,
    )
