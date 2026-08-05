"""Rolling walk-forward VaR backtest.

    Historical information available at time t
                    |
    VaR forecast at time t (using ONLY data from [t-lookback, t-1])
                    |
    Realised return at t
                    |
    Exception / no exception (realised loss > VaR forecast)
                    |
    Exception series
                    |
    Kupiec / Christoffersen / conditional-coverage (validation/kupiec.py, validation/christoffersen.py)

`var_fn` is any callable `(lookback_returns: np.ndarray) -> float` -- historical_var, or
`partial(parametric_var, ...)` composed with a mean/sigma estimator, or a Monte Carlo callable.
Deliberately decoupled from any specific risk_models function so the same harness backtests all
three methodologies identically.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from risk_engine.validation.data_access import get_returns_before


@dataclass(frozen=True)
class ExceptionRecord:
    as_of_date: dt.date
    var_forecast: float
    realised_return: float
    is_exception: bool


def run_rolling_backtest(
    returns: pd.Series,
    var_fn: Callable[..., float],
    lookback_window_days: int,
    window_start: dt.date,
    window_end: dt.date,
) -> list[ExceptionRecord]:
    """Walk `window_start..window_end` day by day. Dates with fewer than `lookback_window_days`
    of prior history are skipped (not computed from a short window) -- this is the "improper
    train/test boundary" failure mode called out in CLAUDE.md; skipping is the safe default.
    """
    dates = returns.index[
        (returns.index >= pd.Timestamp(window_start)) & (returns.index <= pd.Timestamp(window_end))
    ]

    records: list[ExceptionRecord] = []
    for ts in dates:
        as_of = ts.date()
        window = get_returns_before(returns, as_of, lookback_window_days)
        if len(window) < lookback_window_days:
            continue

        var_forecast = float(var_fn(window))
        realised = float(returns.loc[ts])
        is_exception = realised < -var_forecast  # realised loss exceeds the VaR threshold

        records.append(ExceptionRecord(as_of, var_forecast, realised, is_exception))

    return records


def exception_summary(records: list[ExceptionRecord]) -> tuple[int, int]:
    """(n_observations, n_exceptions)."""
    n = len(records)
    x = sum(1 for r in records if r.is_exception)
    return n, x
