"""The leakage-safe data-access boundary for backtesting.

CLAUDE.md: "No look-ahead, structurally enforced. The backtest/data-access layer takes an explicit
as_of_date and the query layer must be physically incapable of returning rows with
return_date >= as_of_date." This module is that boundary for in-memory (already-fetched) return
series; the equivalent boundary for direct DB queries lives in db/queries.py and uses the same
strict `<` comparison.

Every function here uses a strict `<` on the date index -- there is no parameter or code path that
can widen this to `<=`. tests/anti_leakage/ asserts this holds even under adversarial mutation of
"future" data.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd


def get_returns_before(returns: pd.Series, as_of_date: dt.date, lookback_window_days: int) -> np.ndarray:
    """The most recent `lookback_window_days` observations strictly before `as_of_date`.

    `returns` must be indexed by date (any type `pandas.Timestamp` can compare against). Returns
    fewer than `lookback_window_days` observations if insufficient history exists -- callers that
    require a full window must check `len(result)` themselves (see backtest.py, which skips dates
    with insufficient history rather than silently computing VaR from a short window).
    """
    if lookback_window_days <= 0:
        raise ValueError("lookback_window_days must be positive")
    cutoff = pd.Timestamp(as_of_date)
    eligible = returns[returns.index < cutoff]  # strict '<' -- the entire leakage guarantee lives here
    window = eligible.iloc[-lookback_window_days:]
    return window.to_numpy(dtype=float)
