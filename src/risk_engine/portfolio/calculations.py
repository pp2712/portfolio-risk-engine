"""Portfolio aggregation: positions -> market values -> weights -> portfolio returns.

Pure functions only (CLAUDE.md architecture principle #1) -- plain dicts/DataFrames in and out,
no DB/ORM objects. The orchestration layer (api/scheduler) is responsible for pulling ORM data,
converting to these plain structures, calling these functions, and persisting results.

Scope (see docs/KNOWN_LIMITATIONS.md): long-only, no leverage, no derivatives, cash treated as
zero-volatility. Short positions would need sign-consistent handling of weights/VaR conventions
that is explicitly out of scope here.
"""

from __future__ import annotations

import pandas as pd


def compute_position_values(quantities: dict[str, float], prices: dict[str, float]) -> dict[str, float]:
    """market_value_i = quantity_i * price_i. Raises if a quantity has no matching price."""
    missing = set(quantities) - set(prices)
    if missing:
        raise KeyError(f"no price available for: {sorted(missing)}")
    return {ticker: quantities[ticker] * prices[ticker] for ticker in quantities}


def compute_portfolio_value(market_values: dict[str, float], cash: float = 0.0) -> float:
    """portfolio_value = sum(position market values) + cash."""
    return sum(market_values.values()) + cash


def compute_weights(market_values: dict[str, float], portfolio_value: float) -> dict[str, float]:
    """weight_i = market_value_i / portfolio_value. Zero-value portfolio -> all weights 0.0."""
    if portfolio_value == 0:
        return dict.fromkeys(market_values, 0.0)
    return {ticker: mv / portfolio_value for ticker, mv in market_values.items()}


def compute_portfolio_returns(weights: dict[str, float], returns_matrix: pd.DataFrame) -> pd.Series:
    """R_p,t = sum_i(weight_i * r_i,t), i.e. w^T r_t applied per row.

    `returns_matrix` columns must be a superset of `weights` keys (extra columns are ignored, so
    callers can pass a full universe return matrix and a subset-weighted portfolio). Uses TODAY's
    weights held constant across the whole return history ("rebalanced-weight approximation" per
    the spec -- an approximation because it doesn't model weight drift between rebalances, but
    standard for daily VaR horizons).
    """
    missing = set(weights) - set(returns_matrix.columns)
    if missing:
        raise KeyError(f"returns_matrix missing columns for: {sorted(missing)}")
    tickers = list(weights.keys())
    w = pd.Series(weights, index=tickers)
    return returns_matrix[tickers].mul(w, axis=1).sum(axis=1)


def herfindahl_hirschman_index(weights: dict[str, float]) -> float:
    """HHI = sum(w_i^2). Ranges (1/n) for equal-weight to 1.0 for fully concentrated."""
    return sum(w**2 for w in weights.values())


def diversification_benefit(standalone_vars: dict[str, float], portfolio_var: float) -> float:
    """sum(standalone position VaRs) - portfolio VaR.

    Positive whenever assets are imperfectly correlated (the covariance matrix is doing real
    work); ~0 would indicate something is wrong with the correlation modelling (see
    docs/QUANTITATIVE_METHODOLOGY.md and notebooks/01_var_model_comparison.ipynb Experiment 5).
    """
    return sum(standalone_vars.values()) - portfolio_var
