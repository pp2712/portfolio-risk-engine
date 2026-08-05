"""Dedicated look-ahead-bias / data-leakage tests.

CLAUDE.md: "Treat look-ahead prevention as a first-class engineering requirement... The test suite
should fail if future information becomes available to a forecast. Do not rely merely on developer
discipline." These tests exist independently of test_backtest.py's functional tests -- they exist
specifically to catch a regression that reintroduces leakage, even if every functional test still
passes (a leaky implementation can easily still produce plausible-looking VaR numbers).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_engine.validation.backtest import run_rolling_backtest
from risk_engine.validation.data_access import get_returns_before


def test_get_returns_before_never_includes_the_as_of_date_itself():
    dates = pd.bdate_range("2020-01-01", periods=10)
    returns = pd.Series(np.arange(10, dtype=float), index=dates)

    as_of = dates[5].date()
    window = get_returns_before(returns, as_of, lookback_window_days=10)

    # The value AT as_of (index 5, value 5.0) must never appear in the window.
    assert 5.0 not in window
    # Only the 5 strictly-prior values (0..4) should appear.
    np.testing.assert_array_equal(np.sort(window), np.array([0.0, 1.0, 2.0, 3.0, 4.0]))


def test_get_returns_before_never_includes_dates_after_as_of_date():
    dates = pd.bdate_range("2020-01-01", periods=10)
    returns = pd.Series(np.arange(10, dtype=float), index=dates)

    as_of = dates[3].date()
    window = get_returns_before(returns, as_of, lookback_window_days=100)  # ask for more than exists

    assert len(window) == 3  # only 3 days exist strictly before index 3
    assert window.max() < 3.0  # values 0,1,2 only -- nothing from index >= 3


def test_mutating_future_data_does_not_change_a_past_forecast():
    """The core anti-leakage assertion from CLAUDE.md: changing a return value AFTER as_of_date
    must never change the VaR forecast FOR as_of_date."""
    dates = pd.bdate_range("2020-01-01", periods=20)
    rng = np.random.default_rng(1)
    original = pd.Series(rng.normal(0, 0.01, 20), index=dates)

    as_of = dates[15].date()

    def var_fn(window: np.ndarray) -> float:
        return float(-np.percentile(window, 5))

    forecast_before = var_fn(get_returns_before(original, as_of, lookback_window_days=15))

    # Mutate every value from as_of onward (the "future" relative to the forecast) to something
    # extreme -- a leaky implementation would change the forecast; a correct one cannot.
    mutated = original.copy()
    mutated.loc[mutated.index >= pd.Timestamp(as_of)] = 999.0

    forecast_after = var_fn(get_returns_before(mutated, as_of, lookback_window_days=15))

    assert forecast_before == forecast_after


def test_full_backtest_forecast_series_unaffected_by_mutating_future_tail():
    """Same guarantee, exercised through the full run_rolling_backtest orchestration rather than
    the data_access primitive directly -- catches a regression introduced in the loop itself."""
    dates = pd.bdate_range("2020-01-01", periods=30)
    rng = np.random.default_rng(2)
    original = pd.Series(rng.normal(0, 0.01, 30), index=dates)

    def var_fn(window: np.ndarray) -> float:
        return float(-np.percentile(window, 5))

    window_start = dates[20].date()
    window_end = dates[24].date()  # a 5-day backtest window, well before the series end

    records_before = run_rolling_backtest(original, var_fn, lookback_window_days=15, window_start=window_start, window_end=window_end)

    mutated = original.copy()
    # Corrupt everything strictly after the backtest window under test.
    mutated.loc[mutated.index > pd.Timestamp(window_end)] = 12345.0

    records_after = run_rolling_backtest(mutated, var_fn, lookback_window_days=15, window_start=window_start, window_end=window_end)

    forecasts_before = [r.var_forecast for r in records_before]
    forecasts_after = [r.var_forecast for r in records_after]
    assert forecasts_before == forecasts_after


def test_widening_lookback_window_never_reaches_beyond_as_of_date_even_with_huge_window():
    """A caller requesting an absurdly large lookback window must still never receive data at or
    after as_of_date -- there is no window size that can widen the leakage boundary."""
    dates = pd.bdate_range("2020-01-01", periods=10)
    returns = pd.Series(np.arange(10, dtype=float), index=dates)

    as_of = dates[4].date()
    window = get_returns_before(returns, as_of, lookback_window_days=1_000_000)

    assert len(window) == 4  # capped by actual available history, not the requested window
    assert window.max() < 4.0


def test_off_by_one_regression_guard_boundary_date_excluded():
    """A classic off-by-one leakage bug: using `<=` instead of `<` would let the as_of_date's own
    return leak into its own forecast. Explicit boundary-value test."""
    dates = pd.bdate_range("2020-01-01", periods=5)
    returns = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=dates)

    as_of = dates[2].date()  # value 3.0 lives here
    window = get_returns_before(returns, as_of, lookback_window_days=5)

    assert 3.0 not in window
    np.testing.assert_array_equal(window, np.array([1.0, 2.0]))
