"""Orchestration for a full risk run: DB reads -> pure risk_models calls -> DB writes.

Route handlers stay thin (CLAUDE.md: "Do not place quantitative calculations directly inside route
handlers"). This module owns the sequencing; every quantitative step delegates to a pure function
in `portfolio/` or `risk_models/`.

Risk decomposition is computed once per risk run at the FIRST confidence level in the config's
`confidence_levels` list (not once per confidence level) -- the `risk_decomposition` table has no
confidence_level column (matching the blueprint's schema), so a single reference confidence level
is the documented choice. See docs/QUANTITATIVE_METHODOLOGY.md.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.db.models import (
    Asset,
    CvarResult,
    ModelConfig,
    Portfolio,
    RiskDecomposition,
    RiskRun,
    VarResult,
)
from risk_engine.db.queries import get_latest_positions, get_latest_prices, get_returns_matrix
from risk_engine.db.snapshot_hash import compute_data_snapshot_hash
from risk_engine.observability.metrics import timed_calculation
from risk_engine.portfolio.calculations import (
    compute_portfolio_returns,
    compute_portfolio_value,
    compute_position_values,
    compute_weights,
)
from risk_engine.portfolio.decomposition import component_var, marginal_var, pct_contribution
from risk_engine.risk_models.historical import historical_var_cvar
from risk_engine.risk_models.monte_carlo import monte_carlo_var_cvar
from risk_engine.risk_models.parametric import parametric_var_cvar, portfolio_variance


class RiskRunError(ValueError):
    """Raised for any condition that prevents a risk run from being computed (bad input, missing
    data). Callers (API routes) map this to an HTTP 422/404 as appropriate."""


def execute_risk_run(db: Session, portfolio_id: int, config_id: int, as_of_date: dt.date) -> RiskRun:
    """Idempotent: a (portfolio_id, config_id, as_of_date) triple identifies a risk run uniquely
    (see `uq_risk_runs`). Re-requesting an identical run returns the already-persisted one rather
    than recomputing/duplicating -- this is what makes "the same config against the same data
    reproduces the same result" a query, not just a property you'd have to trust."""
    existing = db.execute(
        select(RiskRun).where(
            RiskRun.portfolio_id == portfolio_id,
            RiskRun.config_id == config_id,
            RiskRun.as_of_date == as_of_date,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise RiskRunError(f"portfolio {portfolio_id} not found")
    config = db.get(ModelConfig, config_id)
    if config is None:
        raise RiskRunError(f"model config {config_id} not found")

    positions = get_latest_positions(db, portfolio_id, as_of_date)
    if not positions:
        raise RiskRunError(f"no positions found for portfolio {portfolio_id} as of {as_of_date}")
    tickers = sorted(positions.keys())

    prices = get_latest_prices(db, tickers, as_of_date)
    missing_prices = set(tickers) - set(prices)
    if missing_prices:
        raise RiskRunError(f"no price data as of {as_of_date} for: {sorted(missing_prices)}")

    market_values = compute_position_values(positions, prices)
    portfolio_value = compute_portfolio_value(market_values)
    if portfolio_value <= 0:
        raise RiskRunError("portfolio value must be positive")
    weights = compute_weights(market_values, portfolio_value)

    returns_matrix = get_returns_matrix(db, tickers, as_of_date, config.lookback_window_days)
    if returns_matrix.empty or len(returns_matrix) < config.lookback_window_days:
        available = 0 if returns_matrix.empty else len(returns_matrix)
        raise RiskRunError(
            f"insufficient return history: need {config.lookback_window_days} observations, have {available}"
        )

    aligned_tickers = list(returns_matrix.columns)
    portfolio_returns = compute_portfolio_returns(
        {t: weights[t] for t in aligned_tickers if t in weights}, returns_matrix
    )
    mu_vector = returns_matrix[aligned_tickers].mean().to_numpy()
    cov_matrix = returns_matrix[aligned_tickers].cov().to_numpy()
    w_array = np.array([weights.get(t, 0.0) for t in aligned_tickers])
    mu_p = float(w_array @ mu_vector)
    sigma_p = float(np.sqrt(portfolio_variance(w_array, cov_matrix)))

    snapshot_hash = compute_data_snapshot_hash(aligned_tickers, as_of_date, returns_matrix)

    risk_run = RiskRun(
        portfolio_id=portfolio_id,
        config_id=config_id,
        as_of_date=as_of_date,
        data_snapshot_hash=snapshot_hash,
        status="completed",
    )
    db.add(risk_run)
    db.flush()

    asset_id_by_ticker = {
        a.ticker: a.asset_id
        for a in db.execute(select(Asset).where(Asset.ticker.in_(aligned_tickers))).scalars()
    }

    confidence_levels = list(config.confidence_levels)
    for i, confidence in enumerate(confidence_levels):
        with timed_calculation("historical"):
            h_var, h_cvar = historical_var_cvar(portfolio_returns.to_numpy(), confidence)
        with timed_calculation("parametric"):
            p_var, p_cvar = parametric_var_cvar(mu_p, sigma_p, confidence)
        with timed_calculation("monte_carlo"):
            mc = monte_carlo_var_cvar(
                w_array, mu_vector, cov_matrix, confidence, config.mc_num_simulations, config.mc_random_seed
            )

        for method, var_val, cvar_val in (
            ("historical", h_var, h_cvar),
            ("parametric", p_var, p_cvar),
            ("monte_carlo", mc.var, mc.cvar),
        ):
            db.add(VarResult(risk_run_id=risk_run.risk_run_id, method=method, confidence_level=confidence, var_value=var_val, horizon_days=1))
            db.add(CvarResult(risk_run_id=risk_run.risk_run_id, method=method, confidence_level=confidence, cvar_value=cvar_val))

        if i == 0:  # decomposition computed once, at the primary (first-listed) confidence level
            mvar = marginal_var(w_array, mu_vector, cov_matrix, confidence, sigma_p)
            cvars = component_var(w_array, mvar)
            pcts = pct_contribution(cvars, p_var)
            for j, ticker in enumerate(aligned_tickers):
                db.add(
                    RiskDecomposition(
                        risk_run_id=risk_run.risk_run_id,
                        asset_id=asset_id_by_ticker[ticker],
                        component_var=float(cvars[j]),
                        marginal_var=float(mvar[j]),
                        pct_contribution=float(pcts[j]),
                    )
                )

    db.flush()
    return risk_run
