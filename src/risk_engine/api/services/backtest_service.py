"""Orchestration for a rolling backtest: fetch portfolio returns -> run_rolling_backtest with the
requested VaR method -> Kupiec/Christoffersen/conditional-coverage -> persist.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.db.models import BacktestException, BacktestResult, ModelConfig, Portfolio
from risk_engine.db.queries import get_latest_positions, get_latest_prices, get_returns_matrix
from risk_engine.portfolio.calculations import (
    compute_portfolio_returns,
    compute_position_values,
    compute_weights,
)
from risk_engine.risk_models.historical import historical_var
from risk_engine.risk_models.monte_carlo import monte_carlo_var_cvar
from risk_engine.risk_models.parametric import parametric_var
from risk_engine.validation.backtest import exception_summary, run_rolling_backtest
from risk_engine.validation.christoffersen import (
    christoffersen_independence_test,
    conditional_coverage_test,
)
from risk_engine.validation.kupiec import kupiec_pof_test
from risk_engine.validation.traffic_light import traffic_light_zone


class BacktestError(ValueError):
    pass


def _var_fn_for_method(method: str, confidence: float, seed: int, n_simulations: int):
    if method == "historical":
        return lambda window: historical_var(window, confidence)
    if method == "parametric":
        return lambda window: parametric_var(float(np.mean(window)), float(np.std(window, ddof=1)), confidence)
    if method == "monte_carlo":
        def _mc(window: np.ndarray) -> float:
            mu = np.array([float(np.mean(window))])
            cov = np.array([[float(np.var(window, ddof=1))]])
            result = monte_carlo_var_cvar(np.array([1.0]), mu, cov, confidence, n_simulations, seed)
            return result.var
        return _mc
    raise BacktestError(f"unknown method: {method}")


def execute_backtest(
    db: Session,
    portfolio_id: int,
    config_id: int,
    method: str,
    confidence: float,
    window_start: dt.date,
    window_end: dt.date,
) -> BacktestResult:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise BacktestError(f"portfolio {portfolio_id} not found")
    config = db.get(ModelConfig, config_id)
    if config is None:
        raise BacktestError(f"model config {config_id} not found")

    existing = db.execute(
        select(BacktestResult).where(
            BacktestResult.portfolio_id == portfolio_id,
            BacktestResult.config_id == config_id,
            BacktestResult.method == method,
            BacktestResult.confidence_level == confidence,
            BacktestResult.window_start == window_start,
            BacktestResult.window_end == window_end,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    positions = get_latest_positions(db, portfolio_id, window_end)
    if not positions:
        raise BacktestError(f"no positions found for portfolio {portfolio_id} as of {window_end}")
    tickers = sorted(positions.keys())

    # Full history through window_end, generously sized: lookback + backtest window.
    history_days = config.lookback_window_days + (window_end - window_start).days + 30
    returns_matrix = get_returns_matrix(db, tickers, window_end, history_days)
    if returns_matrix.empty:
        raise BacktestError("no return history available")

    aligned_tickers = list(returns_matrix.columns)
    prices = get_latest_prices(db, aligned_tickers, window_end)
    market_values = compute_position_values({t: positions[t] for t in aligned_tickers if t in positions}, prices)
    portfolio_value = sum(market_values.values())
    weights = compute_weights(market_values, portfolio_value)

    portfolio_returns = compute_portfolio_returns(weights, returns_matrix)
    portfolio_returns.index = pd.to_datetime(returns_matrix.index)

    var_fn = _var_fn_for_method(method, confidence, config.mc_random_seed, config.mc_num_simulations)
    records = run_rolling_backtest(portfolio_returns, var_fn, config.lookback_window_days, window_start, window_end)
    if not records:
        raise BacktestError(
            f"no backtest observations produced -- insufficient history before {window_start} for "
            f"a {config.lookback_window_days}-day lookback"
        )

    n_obs, n_exc = exception_summary(records)
    kupiec = kupiec_pof_test(n_obs, n_exc, confidence)
    exceptions_binary = [r.is_exception for r in records]
    christoffersen = christoffersen_independence_test(exceptions_binary) if len(exceptions_binary) >= 2 else None
    zone = traffic_light_zone(n_obs, n_exc, confidence)

    result = BacktestResult(
        portfolio_id=portfolio_id,
        config_id=config_id,
        method=method,
        confidence_level=confidence,
        window_start=window_start,
        window_end=window_end,
        num_observations=n_obs,
        num_exceptions=n_exc,
        kupiec_stat=kupiec.lr_statistic,
        kupiec_pvalue=kupiec.p_value,
        kupiec_pass=not kupiec.reject_h0,
        christoffersen_stat=christoffersen.lr_statistic if christoffersen else None,
        christoffersen_pvalue=christoffersen.p_value if christoffersen else None,
        christoffersen_pass=(not christoffersen.reject_h0) if christoffersen else None,
        traffic_light_zone=zone,
    )
    if christoffersen is not None:
        cc = conditional_coverage_test(kupiec, christoffersen)
        result.conditional_coverage_stat = cc.lr_statistic
        result.conditional_coverage_pvalue = cc.p_value
        result.conditional_coverage_pass = not cc.reject_h0

    db.add(result)
    db.flush()

    for r in records:
        db.add(
            BacktestException(
                backtest_id=result.backtest_id,
                as_of_date=r.as_of_date,
                var_forecast=r.var_forecast,
                realised_return=r.realised_return,
                realised_pnl=r.realised_return * portfolio_value,
                is_exception=r.is_exception,
            )
        )
    db.flush()
    return result
