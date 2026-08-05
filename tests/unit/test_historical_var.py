from __future__ import annotations

import numpy as np
import pytest

from risk_engine.risk_models.common import empirical_var_cvar, tail_size
from risk_engine.risk_models.historical import historical_cvar, historical_var


def test_tail_size_rounds_up_and_floors_at_one():
    assert tail_size(100, 0.95) == 5  # ceil(0.05*100) = 5
    assert tail_size(100, 0.99) == 1  # ceil(0.01*100) = 1
    assert tail_size(10, 0.999) == 1  # ceil(0.001*10) = 1 -> floored at 1 anyway


def test_historical_var_hand_computed_10_observations():
    # 10 returns, worst is -0.10; at 90% confidence k=ceil(0.10*10)=1 -> VaR = -(-0.10) = 0.10
    returns = np.array([0.01, 0.02, -0.01, 0.03, -0.10, 0.00, 0.015, -0.02, 0.005, -0.03])
    var = historical_var(returns, confidence=0.90)
    assert var == pytest.approx(0.10)


def test_historical_cvar_averages_k_worst():
    # k = ceil(0.20*10) = 2 -> two worst returns are -0.10 and -0.03 -> CVaR = -mean(-0.10,-0.03) = 0.065
    returns = np.array([0.01, 0.02, -0.01, 0.03, -0.10, 0.00, 0.015, -0.02, 0.005, -0.03])
    cvar = historical_cvar(returns, confidence=0.80)
    assert cvar == pytest.approx(0.065)


def test_historical_cvar_always_greater_equal_var():
    rng = np.random.default_rng(7)
    returns = rng.normal(0.0005, 0.02, size=500)
    for confidence in (0.90, 0.95, 0.99):
        var, cvar = empirical_var_cvar(returns, confidence)
        assert cvar >= var


def test_historical_var_empty_raises():
    with pytest.raises(ValueError):
        historical_var(np.array([]), 0.95)


def test_historical_var_all_positive_returns_gives_negative_or_small_var():
    # If every historical return is a gain, the "worst" observation is still the smallest gain --
    # VaR can legitimately come out negative (no historical loss occurred in-sample). This is a
    # known, documented limitation of historical VaR with too-short/benign lookback windows.
    returns = np.array([0.01, 0.02, 0.005, 0.03, 0.015])
    var = historical_var(returns, confidence=0.80)
    assert var == pytest.approx(-0.005)  # k=1 -> worst (smallest) return is 0.005 -> VaR = -0.005


def test_historical_var_matches_manual_sort_for_larger_sample():
    rng = np.random.default_rng(42)
    returns = rng.standard_t(df=5, size=1000) * 0.02
    confidence = 0.95
    k = tail_size(len(returns), confidence)
    manual_var = -np.sort(returns)[k - 1]
    assert historical_var(returns, confidence) == pytest.approx(manual_var)
