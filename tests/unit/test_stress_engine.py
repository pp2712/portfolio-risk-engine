from __future__ import annotations

import pandas as pd
import pytest

from risk_engine.stress.engine import run_factor_shock, run_historical_replay, run_scenario
from risk_engine.stress.scenarios import ScenarioSpec


def test_historical_replay_hand_computed():
    scenario = ScenarioSpec(name="Test Replay", scenario_type="HISTORICAL_REPLAY")
    weights = {"A": 0.6, "B": 0.4}
    # A: two days of +10% each -> cumulative (1.1*1.1 - 1) = 0.21
    # B: two days of -5% each -> cumulative (0.95*0.95 - 1) = -0.0975
    window = pd.DataFrame({"A": [0.10, 0.10], "B": [-0.05, -0.05]})
    result = run_historical_replay(scenario, weights, window, portfolio_value=1000.0)

    expected_a = 0.6 * 1000.0 * (1.1 * 1.1 - 1)
    expected_b = 0.4 * 1000.0 * (0.95 * 0.95 - 1)
    assert result.position_contributions["A"] == pytest.approx(expected_a)
    assert result.position_contributions["B"] == pytest.approx(expected_b)
    assert result.portfolio_pnl == pytest.approx(expected_a + expected_b)
    assert result.portfolio_pnl_pct == pytest.approx((expected_a + expected_b) / 1000.0)
    assert result.excluded_assets == []


def test_historical_replay_excludes_asset_with_no_data():
    scenario = ScenarioSpec(name="Test Replay", scenario_type="HISTORICAL_REPLAY")
    weights = {"A": 0.5, "META_LATE_IPO": 0.5}
    window = pd.DataFrame({"A": [0.05, 0.05]})  # no column for META_LATE_IPO at all
    result = run_historical_replay(scenario, weights, window, portfolio_value=1000.0)

    assert result.excluded_assets == ["META_LATE_IPO"]
    assert result.position_contributions["META_LATE_IPO"] == 0.0
    assert result.position_contributions["A"] == pytest.approx(0.5 * 1000.0 * (1.05 * 1.05 - 1))


def test_factor_shock_hand_computed():
    scenario = ScenarioSpec(
        name="Market Down", scenario_type="FACTOR_SHOCK", factor_shocks={"equity_market": -0.20}
    )
    weights = {"A": 0.5, "B": 0.5}
    asset_betas = {"A": {"equity_market": 1.2}, "B": {"equity_market": 0.8}}
    result = run_factor_shock(scenario, weights, asset_betas, portfolio_value=1000.0)

    expected_a = 0.5 * 1000.0 * (1.2 * -0.20)
    expected_b = 0.5 * 1000.0 * (0.8 * -0.20)
    assert result.position_contributions["A"] == pytest.approx(expected_a)
    assert result.position_contributions["B"] == pytest.approx(expected_b)
    assert result.portfolio_pnl == pytest.approx(expected_a + expected_b)


def test_factor_shock_missing_beta_contributes_zero():
    scenario = ScenarioSpec(
        name="Market Down", scenario_type="FACTOR_SHOCK", factor_shocks={"equity_market": -0.20}
    )
    weights = {"A": 1.0}
    result = run_factor_shock(scenario, weights, asset_betas={}, portfolio_value=1000.0)
    assert result.position_contributions["A"] == 0.0


def test_run_scenario_dispatches_correctly():
    replay_scenario = ScenarioSpec(name="Replay", scenario_type="HISTORICAL_REPLAY")
    window = pd.DataFrame({"A": [0.01]})
    result = run_scenario(replay_scenario, {"A": 1.0}, 1000.0, simple_returns_window=window)
    assert result.scenario_name == "Replay"

    shock_scenario = ScenarioSpec(name="Shock", scenario_type="FACTOR_SHOCK", factor_shocks={"f": -0.1})
    result2 = run_scenario(shock_scenario, {"A": 1.0}, 1000.0, asset_betas={"A": {"f": 1.0}})
    assert result2.scenario_name == "Shock"


def test_run_scenario_missing_required_arg_raises():
    replay_scenario = ScenarioSpec(name="Replay", scenario_type="HISTORICAL_REPLAY")
    with pytest.raises(ValueError, match="simple_returns_window"):
        run_scenario(replay_scenario, {"A": 1.0}, 1000.0)

    shock_scenario = ScenarioSpec(name="Shock", scenario_type="FACTOR_SHOCK", factor_shocks={"f": -0.1})
    with pytest.raises(ValueError, match="asset_betas"):
        run_scenario(shock_scenario, {"A": 1.0}, 1000.0)
