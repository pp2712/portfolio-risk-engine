from __future__ import annotations

import numpy as np
import pytest

from risk_engine.validation.christoffersen import (
    christoffersen_independence_test,
    conditional_coverage_test,
)
from risk_engine.validation.kupiec import kupiec_pof_test


def test_evenly_spread_exceptions_do_not_reject_independence():
    # 100 obs, 10 exceptions evenly spread out (never adjacent) -- should look independent.
    exceptions = [1 if i % 10 == 0 else 0 for i in range(100)]
    result = christoffersen_independence_test(exceptions)
    assert result.applicable is True
    assert result.reject_h0 is False


def test_clustered_exceptions_reject_independence():
    # 100 obs, 10 exceptions all clustered together in one run -- classic crisis-clustering case.
    exceptions = [0] * 45 + [1] * 10 + [0] * 45
    result = christoffersen_independence_test(exceptions)
    assert result.applicable is True
    assert result.pi11 > result.pi01  # exception more likely to follow an exception
    assert result.reject_h0 is True
    assert "CLUSTERED" in result.interpretation


def test_zero_exceptions_not_applicable():
    exceptions = [0] * 50
    result = christoffersen_independence_test(exceptions)
    assert result.applicable is False
    assert result.reject_h0 is False


def test_single_exception_not_applicable():
    exceptions = [0] * 49 + [1]
    result = christoffersen_independence_test(exceptions)
    assert result.applicable is False


def test_all_exceptions_edge_case_does_not_raise_or_nan():
    exceptions = [1] * 20
    result = christoffersen_independence_test(exceptions)
    assert not np.isnan(result.lr_statistic)


def test_too_short_sequence_raises():
    with pytest.raises(ValueError):
        christoffersen_independence_test([1])


def test_non_binary_input_raises():
    with pytest.raises(ValueError):
        christoffersen_independence_test([0, 1, 2, 0])


def test_conditional_coverage_combines_both_statistics():
    kupiec = kupiec_pof_test(n_observations=250, n_exceptions=20, confidence=0.95)
    exceptions = [0] * 230 + [1] * 20
    christoffersen = christoffersen_independence_test(exceptions)
    cc = conditional_coverage_test(kupiec, christoffersen)
    assert cc.lr_statistic == pytest.approx(kupiec.lr_statistic + christoffersen.lr_statistic)
