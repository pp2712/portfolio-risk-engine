"""Orchestration for a stress-test run: fetch scenario + portfolio -> stress/engine.py -> persist."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.data.universe import UNIVERSE
from risk_engine.db.models import Portfolio, Scenario, StressResult
from risk_engine.db.queries import (
    get_latest_positions,
    get_latest_prices,
    get_returns_matrix,
    get_simple_returns_window,
)
from risk_engine.portfolio.calculations import (
    compute_portfolio_value,
    compute_position_values,
    compute_weights,
)
from risk_engine.stress.engine import run_factor_shock, run_historical_replay
from risk_engine.stress.factor_model import estimate_factor_betas, sector_membership_betas
from risk_engine.stress.scenarios import ScenarioSpec

SECTOR_BY_TICKER = {a.ticker: a.sector for a in UNIVERSE}


class StressRunError(ValueError):
    pass


def _scenario_to_spec(scenario: Scenario) -> ScenarioSpec:
    return ScenarioSpec(
        name=scenario.name,
        scenario_type=scenario.scenario_type,  # type: ignore[arg-type]
        version=scenario.version,
        description=scenario.description or "",
        historical_start=scenario.historical_start,
        historical_end=scenario.historical_end,
        factor_shocks=scenario.factor_shocks or {},
    )


def execute_stress_run(db: Session, portfolio_id: int, scenario_id: int, as_of_date: dt.date) -> StressResult:
    existing = db.execute(
        select(StressResult).where(
            StressResult.portfolio_id == portfolio_id,
            StressResult.scenario_id == scenario_id,
            StressResult.as_of_date == as_of_date,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise StressRunError(f"portfolio {portfolio_id} not found")
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        raise StressRunError(f"scenario {scenario_id} not found")

    positions = get_latest_positions(db, portfolio_id, as_of_date)
    if not positions:
        raise StressRunError(f"no positions found for portfolio {portfolio_id} as of {as_of_date}")
    tickers = sorted(positions.keys())

    prices = get_latest_prices(db, tickers, as_of_date)
    market_values = compute_position_values(positions, prices)
    portfolio_value = compute_portfolio_value(market_values)
    weights = compute_weights(market_values, portfolio_value)

    spec = _scenario_to_spec(scenario)

    if spec.scenario_type == "HISTORICAL_REPLAY":
        if spec.historical_start is None or spec.historical_end is None:
            raise StressRunError("HISTORICAL_REPLAY scenario missing date range")
        window = get_simple_returns_window(db, tickers, spec.historical_start, spec.historical_end)
        result = run_historical_replay(spec, weights, window, portfolio_value)
    elif spec.scenario_type == "FACTOR_SHOCK":
        asset_betas = _estimate_betas_for_shock(db, tickers, spec, as_of_date)
        result = run_factor_shock(spec, weights, asset_betas, portfolio_value)
    else:
        raise StressRunError(f"unknown scenario_type: {spec.scenario_type}")

    db_result = StressResult(
        portfolio_id=portfolio_id,
        scenario_id=scenario_id,
        as_of_date=as_of_date,
        portfolio_pnl=result.portfolio_pnl,
        portfolio_pnl_pct=result.portfolio_pnl_pct,
        position_contributions=result.position_contributions,
    )
    db.add(db_result)
    db.flush()
    return db_result


def _estimate_betas_for_shock(
    db: Session, tickers: list[str], spec: ScenarioSpec, as_of_date: dt.date, lookback_days: int = 500
) -> dict[str, dict[str, float]]:
    """`equity_market` beta: OLS regression against SPY (see stress/factor_model.py). Any other
    factor named in the scenario (e.g. `rate_sensitive_financials`) is sector-membership-based,
    since there is no tradeable return series for it in scope (see docs/KNOWN_LIMITATIONS.md)."""
    betas: dict[str, dict[str, float]] = {t: {} for t in tickers}

    if "equity_market" in spec.factor_shocks:
        market_matrix = get_returns_matrix(db, ["SPY", *tickers], as_of_date, lookback_days)
        if "SPY" in market_matrix.columns:
            market_returns = market_matrix["SPY"]
            for ticker in tickers:
                if ticker not in market_matrix.columns:
                    betas[ticker]["equity_market"] = 1.0  # conservative default: full market exposure
                    continue
                try:
                    fit = estimate_factor_betas(market_matrix[ticker], market_returns.to_frame("equity_market"))
                    betas[ticker]["equity_market"] = fit.betas["equity_market"]
                except ValueError:
                    betas[ticker]["equity_market"] = 1.0
        else:
            for ticker in tickers:
                betas[ticker]["equity_market"] = 1.0

    if "rate_sensitive_financials" in spec.factor_shocks:
        sector_betas = sector_membership_betas(tickers, SECTOR_BY_TICKER, "rate_sensitive_financials", {"Financials"})
        for ticker, beta in sector_betas.items():
            betas[ticker]["rate_sensitive_financials"] = beta

    return betas
