from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_engine.portfolio.calculations import (
    compute_portfolio_returns,
    compute_portfolio_value,
    compute_position_values,
    compute_weights,
    diversification_benefit,
    herfindahl_hirschman_index,
)


def test_compute_position_values():
    values = compute_position_values({"AAPL": 10, "MSFT": 5}, {"AAPL": 200.0, "MSFT": 300.0})
    assert values == {"AAPL": 2000.0, "MSFT": 1500.0}


def test_compute_position_values_missing_price_raises():
    with pytest.raises(KeyError):
        compute_position_values({"AAPL": 10}, {"MSFT": 300.0})


def test_compute_portfolio_value_with_cash():
    total = compute_portfolio_value({"AAPL": 2000.0, "MSFT": 1500.0}, cash=500.0)
    assert total == 4000.0


def test_compute_weights_known_values():
    weights = compute_weights({"AAPL": 2000.0, "MSFT": 2000.0}, portfolio_value=4000.0)
    assert weights == {"AAPL": 0.5, "MSFT": 0.5}


def test_compute_weights_zero_portfolio_value():
    weights = compute_weights({"AAPL": 0.0, "MSFT": 0.0}, portfolio_value=0.0)
    assert weights == {"AAPL": 0.0, "MSFT": 0.0}


def test_compute_portfolio_returns_matches_hand_calculation():
    weights = {"A": 0.6, "B": 0.4}
    returns_matrix = pd.DataFrame({"A": [0.01, -0.02, 0.03], "B": [0.02, 0.01, -0.01]})
    result = compute_portfolio_returns(weights, returns_matrix)

    expected = [0.6 * 0.01 + 0.4 * 0.02, 0.6 * -0.02 + 0.4 * 0.01, 0.6 * 0.03 + 0.4 * -0.01]
    np.testing.assert_allclose(result.to_numpy(), expected, atol=1e-12)


def test_compute_portfolio_returns_ignores_extra_columns():
    weights = {"A": 1.0}
    returns_matrix = pd.DataFrame({"A": [0.05], "B": [0.99]})
    result = compute_portfolio_returns(weights, returns_matrix)
    assert result.iloc[0] == pytest.approx(0.05)


def test_compute_portfolio_returns_missing_column_raises():
    with pytest.raises(KeyError):
        compute_portfolio_returns({"A": 1.0}, pd.DataFrame({"B": [0.1]}))


def test_hhi_fully_concentrated():
    assert herfindahl_hirschman_index({"A": 1.0}) == pytest.approx(1.0)


def test_hhi_equal_weight_n_assets():
    n = 5
    weights = dict.fromkeys([f"A{i}" for i in range(n)], 1.0 / n)
    assert herfindahl_hirschman_index(weights) == pytest.approx(1.0 / n)


def test_diversification_benefit_positive_when_imperfectly_correlated():
    # Standalone VaRs sum to more than a correlated portfolio VaR -- the normal case.
    benefit = diversification_benefit({"A": 100.0, "B": 100.0}, portfolio_var=150.0)
    assert benefit == pytest.approx(50.0)


def test_diversification_benefit_zero_for_perfectly_correlated():
    # If portfolio VaR equals the sum of standalone VaRs, there's no diversification benefit
    # (the perfectly-correlated edge case).
    benefit = diversification_benefit({"A": 100.0, "B": 100.0}, portfolio_var=200.0)
    assert benefit == pytest.approx(0.0)
