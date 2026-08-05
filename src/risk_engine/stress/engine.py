"""Stress-testing execution engine: dispatches on scenario_type to exactly two paths.

Adding a new scenario is a new `ScenarioSpec` (stress/scenarios.py) or `scenarios` DB row -- never
a change here (CLAUDE.md architecture principle #2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from risk_engine.stress.scenarios import ScenarioSpec


@dataclass(frozen=True)
class StressResult:
    scenario_name: str
    portfolio_pnl: float
    portfolio_pnl_pct: float
    position_contributions: dict[str, float]
    excluded_assets: list[str] = field(default_factory=list)


def run_historical_replay(
    scenario: ScenarioSpec, weights: dict[str, float], simple_returns_window: pd.DataFrame, portfolio_value: float
) -> StressResult:
    """Apply realised simple returns from the scenario window to today's portfolio weights.

    Simple returns (not log returns) are used here deliberately -- this is a P&L/portfolio-value
    calculation, where simple returns are the economically correct, exactly-compounding quantity
    (CLAUDE.md: "log returns for risk models, simple returns for P&L reporting").

    Assets with no price history in the scenario window (e.g. a name that IPO'd after the window)
    are excluded from the replay and reported in `excluded_assets` rather than silently assumed
    flat or silently dropped from the weight normalisation.
    """
    available = [
        t for t in weights if t in simple_returns_window.columns and simple_returns_window[t].notna().any()
    ]
    excluded = sorted(set(weights) - set(available))

    contributions: dict[str, float] = {}
    for ticker in available:
        series = simple_returns_window[ticker].dropna()
        cumulative_return = float((1.0 + series).prod() - 1.0)
        contributions[ticker] = weights[ticker] * portfolio_value * cumulative_return
    for ticker in excluded:
        contributions[ticker] = 0.0

    portfolio_pnl = sum(contributions.values())
    portfolio_pnl_pct = portfolio_pnl / portfolio_value if portfolio_value else 0.0

    return StressResult(
        scenario_name=scenario.name,
        portfolio_pnl=portfolio_pnl,
        portfolio_pnl_pct=portfolio_pnl_pct,
        position_contributions=contributions,
        excluded_assets=excluded,
    )


def run_factor_shock(
    scenario: ScenarioSpec, weights: dict[str, float], asset_betas: dict[str, dict[str, float]], portfolio_value: float
) -> StressResult:
    """Apply factor shock magnitudes through each asset's estimated/assigned factor betas.

    asset_return_i = sum_f(beta_i,f * shock_f); position P&L = weight_i * portfolio_value * asset_return_i.
    An asset with no betas supplied for any shocked factor contributes 0.0 (conservative -- treated
    as unexposed, not silently excluded from the portfolio-value denominator).
    """
    contributions: dict[str, float] = {}
    for ticker, weight in weights.items():
        betas = asset_betas.get(ticker, {})
        asset_return = sum(betas.get(factor, 0.0) * shock for factor, shock in scenario.factor_shocks.items())
        contributions[ticker] = weight * portfolio_value * asset_return

    portfolio_pnl = sum(contributions.values())
    portfolio_pnl_pct = portfolio_pnl / portfolio_value if portfolio_value else 0.0

    return StressResult(
        scenario_name=scenario.name,
        portfolio_pnl=portfolio_pnl,
        portfolio_pnl_pct=portfolio_pnl_pct,
        position_contributions=contributions,
        excluded_assets=[],
    )


def run_scenario(
    scenario: ScenarioSpec,
    weights: dict[str, float],
    portfolio_value: float,
    simple_returns_window: pd.DataFrame | None = None,
    asset_betas: dict[str, dict[str, float]] | None = None,
) -> StressResult:
    """Single entrypoint dispatching on scenario_type -- exactly two execution paths."""
    if scenario.scenario_type == "HISTORICAL_REPLAY":
        if simple_returns_window is None:
            raise ValueError("HISTORICAL_REPLAY scenario requires simple_returns_window")
        return run_historical_replay(scenario, weights, simple_returns_window, portfolio_value)
    if scenario.scenario_type == "FACTOR_SHOCK":
        if asset_betas is None:
            raise ValueError("FACTOR_SHOCK scenario requires asset_betas")
        return run_factor_shock(scenario, weights, asset_betas, portfolio_value)
    raise ValueError(f"unknown scenario_type: {scenario.scenario_type}")
