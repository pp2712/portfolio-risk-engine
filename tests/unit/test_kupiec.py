from __future__ import annotations

import math

import pytest

from risk_engine.validation.kupiec import kupiec_pof_test


def test_kupiec_blueprint_worked_example_rejects_undercoverage():
    # 250 observations, 95% VaR (expected ~12.5 exceptions), 20 actual exceptions -> LR ~ 4.04,
    # exceeds the chi2(1) 5% critical value of 3.84 -> reject H0, model under-covers risk.
    result = kupiec_pof_test(n_observations=250, n_exceptions=20, confidence=0.95)
    assert result.lr_statistic == pytest.approx(4.04, abs=0.01)
    assert result.p_value < 0.05
    assert result.reject_h0 is True
    assert "UNDER-COVERS" in result.interpretation


def test_kupiec_exact_expected_rate_fails_to_reject():
    # Exactly the expected rate -- LR should be ~0, definitely not significant.
    result = kupiec_pof_test(n_observations=1000, n_exceptions=50, confidence=0.95)
    assert result.lr_statistic == pytest.approx(0.0, abs=1e-6)
    assert result.reject_h0 is False


def test_kupiec_zero_exceptions_overcoverage_edge_case():
    # x=0 hits the log(0)/0^0 edge case -- must not raise or return NaN.
    result = kupiec_pof_test(n_observations=250, n_exceptions=0, confidence=0.95)
    assert result.lr_statistic > 0
    assert not math.isnan(result.lr_statistic)
    assert result.reject_h0 is True
    assert "OVER-COVERS" in result.interpretation


def test_kupiec_all_exceptions_edge_case():
    # x=T also hits the log(0)/0^0 edge case on the other side.
    result = kupiec_pof_test(n_observations=10, n_exceptions=10, confidence=0.95)
    assert result.lr_statistic > 0
    assert not math.isnan(result.lr_statistic)
    assert result.reject_h0 is True
    assert "UNDER-COVERS" in result.interpretation


def test_kupiec_invalid_inputs_raise():
    with pytest.raises(ValueError):
        kupiec_pof_test(n_observations=0, n_exceptions=0, confidence=0.95)
    with pytest.raises(ValueError):
        kupiec_pof_test(n_observations=100, n_exceptions=101, confidence=0.95)
    with pytest.raises(ValueError):
        kupiec_pof_test(n_observations=100, n_exceptions=5, confidence=1.5)


def test_kupiec_p_value_decreases_as_deviation_from_expected_grows():
    base = kupiec_pof_test(n_observations=250, n_exceptions=13, confidence=0.95)  # ~expected 12.5
    worse = kupiec_pof_test(n_observations=250, n_exceptions=40, confidence=0.95)
    assert worse.p_value < base.p_value
