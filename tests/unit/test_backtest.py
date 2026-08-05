from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_engine.validation.backtest import exception_summary, run_rolling_backtest


def _make_returns(n_days: int, start: str = "2020-01-01") -> pd.Series:
    dates = pd.bdate_range(start, periods=n_days)
    rng = np.random.default_rng(0)
    return pd.Series(rng.normal(0, 0.01, n_days), index=dates)


def test_backtest_skips_dates_with_insufficient_lookback():
    returns = _make_returns(20)
    records = run_rolling_backtest(
        returns,
        var_fn=lambda w: 0.02,
        lookback_window_days=10,
        window_start=returns.index[0].date(),
        window_end=returns.index[-1].date(),
    )
    # Only dates with >=10 prior observations get a forecast: index positions 10..19 (10 records).
    assert len(records) == 10
    assert records[0].as_of_date == returns.index[10].date()


def test_backtest_flags_exception_when_loss_exceeds_var():
    dates = pd.bdate_range("2020-01-01", periods=5)
    returns = pd.Series([0.01, 0.01, 0.01, 0.01, -0.05], index=dates)
    records = run_rolling_backtest(
        returns,
        var_fn=lambda w: 0.02,  # constant 2% VaR forecast
        lookback_window_days=4,
        window_start=dates[4].date(),
        window_end=dates[4].date(),
    )
    assert len(records) == 1
    assert records[0].is_exception is True  # -0.05 loss exceeds 0.02 VaR
    assert records[0].realised_return == pytest.approx(-0.05)


def test_backtest_no_exception_when_loss_within_var():
    dates = pd.bdate_range("2020-01-01", periods=5)
    returns = pd.Series([0.01, 0.01, 0.01, 0.01, -0.01], index=dates)
    records = run_rolling_backtest(
        returns, var_fn=lambda w: 0.02, lookback_window_days=4,
        window_start=dates[4].date(), window_end=dates[4].date(),
    )
    assert records[0].is_exception is False


def test_backtest_var_fn_receives_correct_lookback_window():
    dates = pd.bdate_range("2020-01-01", periods=6)
    returns = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05, 0.06], index=dates)
    captured = []

    def spy_var_fn(window):
        captured.append(window.copy())
        return 0.02

    run_rolling_backtest(
        returns, var_fn=spy_var_fn, lookback_window_days=3,
        window_start=dates[3].date(), window_end=dates[3].date(),
    )
    # Forecasting for dates[3] (value 0.04) should see exactly the 3 preceding values.
    np.testing.assert_array_equal(captured[0], np.array([0.01, 0.02, 0.03]))


def test_exception_summary_counts_correctly():
    dates = pd.bdate_range("2020-01-01", periods=5)
    returns = pd.Series([0.01, -0.05, 0.01, -0.05, 0.01], index=dates)
    records = run_rolling_backtest(
        returns, var_fn=lambda w: 0.02, lookback_window_days=1,
        window_start=dates[1].date(), window_end=dates[4].date(),
    )
    n, x = exception_summary(records)
    assert n == 4
    assert x == 2
