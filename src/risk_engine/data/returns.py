"""Return-series construction.

Log returns are the primary series for risk models (time-additive, approximately normal for daily
equity data -- see docs/QUANTITATIVE_METHODOLOGY.md). Simple returns are stored alongside and used
for P&L / portfolio-value reporting, where they are the economically correct quantity (values
compound multiplicatively). Never conflate the two -- see CLAUDE.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_returns_for_asset(prices: pd.DataFrame) -> pd.DataFrame:
    """`prices` must have columns [price_date, adj_close], sorted or not, one row per date.

    Returns a frame [return_date, log_return, simple_return] with one row per date after the
    first (a return needs a previous price). Log return: r_t = ln(P_t / P_{t-1}).
    """
    work = prices[["price_date", "adj_close"]].drop_duplicates("price_date").sort_values("price_date")
    adj_close = work["adj_close"].to_numpy(dtype=float)
    if len(adj_close) < 2:
        return pd.DataFrame(columns=["return_date", "log_return", "simple_return"])

    log_returns = np.diff(np.log(adj_close))
    simple_returns = adj_close[1:] / adj_close[:-1] - 1.0

    return pd.DataFrame(
        {
            "return_date": work["price_date"].to_numpy()[1:],
            "log_return": log_returns,
            "simple_return": simple_returns,
        }
    )


def build_aligned_return_matrix(
    returns_by_ticker: dict[str, pd.DataFrame], column: str = "log_return"
) -> pd.DataFrame:
    """Align multiple assets' return series to the INTERSECTION of valid trading days.

    `returns_by_ticker[ticker]` must have columns [return_date, log_return, simple_return].
    Deliberately an inner join, not a forward-fill -- forward-filling manufactures a zero-return
    day that never happened, which corrupts both VaR and the backtest (see CLAUDE.md).

    This is called at query time on data already scoped to a portfolio's holdings and to an
    as_of_date cutoff, not at ingestion time -- aligning the whole universe to intersection would
    truncate history to the youngest asset's IPO date for everyone, which is wrong for the assets
    the caller doesn't actually hold.
    """
    if not returns_by_ticker:
        return pd.DataFrame()

    series = {}
    for ticker, df in returns_by_ticker.items():
        s = df.set_index("return_date")[column]
        s.index = pd.to_datetime(s.index)
        series[ticker] = s

    matrix = pd.DataFrame(series).dropna(how="any")
    matrix.index.name = "return_date"
    return matrix.sort_index()
