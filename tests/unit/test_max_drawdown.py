from __future__ import annotations

import pandas as pd
import pytest

from risk_engine.portfolio.calculations import max_drawdown


def test_max_drawdown_simple_known_case():
    # Wealth: 100 -> 110 -> 88 -> 99 -> peak 110, trough 88 -> drawdown = 1 - 88/110 = 0.2
    returns = pd.Series([0.10, -0.20, 0.125])
    assert max_drawdown(returns) == pytest.approx(0.2, abs=1e-9)


def test_max_drawdown_monotonic_gains_is_zero():
    returns = pd.Series([0.01, 0.02, 0.01, 0.03])
    assert max_drawdown(returns) == pytest.approx(0.0)


def test_max_drawdown_empty_series_is_zero():
    assert max_drawdown(pd.Series([], dtype=float)) == 0.0


def test_max_drawdown_total_loss_approaches_one():
    returns = pd.Series([-0.5, -0.5, -0.5])
    dd = max_drawdown(returns)
    assert 0.85 < dd < 1.0
