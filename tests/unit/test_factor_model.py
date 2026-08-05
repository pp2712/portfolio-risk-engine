from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_engine.stress.factor_model import estimate_factor_betas, sector_membership_betas


def test_estimate_factor_betas_recovers_known_exact_relationship():
    # Construct asset_returns = 0.0001 + 1.5 * factor, with zero noise -- regression must recover
    # alpha=0.0001, beta=1.5, R^2=1.0 exactly (to float tolerance).
    dates = pd.bdate_range("2020-01-01", periods=100)
    rng = np.random.default_rng(0)
    factor = pd.Series(rng.normal(0, 0.01, 100), index=dates, name="equity_market")
    asset = 0.0001 + 1.5 * factor
    asset.name = "asset"

    result = estimate_factor_betas(asset, factor.to_frame())

    assert result.betas["equity_market"] == pytest.approx(1.5, abs=1e-8)
    assert result.alpha == pytest.approx(0.0001, abs=1e-8)
    assert result.r_squared == pytest.approx(1.0, abs=1e-8)
    assert result.n_observations == 100


def test_estimate_factor_betas_recovers_beta_with_noise_approximately():
    dates = pd.bdate_range("2020-01-01", periods=2000)
    rng = np.random.default_rng(1)
    factor = pd.Series(rng.normal(0, 0.01, 2000), index=dates, name="equity_market")
    noise = rng.normal(0, 0.002, 2000)
    asset = pd.Series(0.8 * factor.to_numpy() + noise, index=dates, name="asset")

    result = estimate_factor_betas(asset, factor.to_frame())
    assert result.betas["equity_market"] == pytest.approx(0.8, abs=0.05)
    assert 0.0 < result.r_squared < 1.0


def test_estimate_factor_betas_multi_factor():
    dates = pd.bdate_range("2020-01-01", periods=500)
    rng = np.random.default_rng(2)
    f1 = pd.Series(rng.normal(0, 0.01, 500), index=dates)
    f2 = pd.Series(rng.normal(0, 0.01, 500), index=dates)
    asset = pd.Series(0.5 * f1.to_numpy() + 0.3 * f2.to_numpy(), index=dates, name="asset")
    factors = pd.DataFrame({"f1": f1, "f2": f2})

    result = estimate_factor_betas(asset, factors)
    assert result.betas["f1"] == pytest.approx(0.5, abs=1e-6)
    assert result.betas["f2"] == pytest.approx(0.3, abs=1e-6)


def test_estimate_factor_betas_misaligned_dates_uses_inner_join():
    dates_a = pd.bdate_range("2020-01-01", periods=50)
    dates_f = pd.bdate_range("2020-02-01", periods=50)  # only partial overlap
    asset = pd.Series(np.random.default_rng(3).normal(0, 0.01, 50), index=dates_a, name="asset")
    factor = pd.Series(np.random.default_rng(4).normal(0, 0.01, 50), index=dates_f, name="f")

    result = estimate_factor_betas(asset, factor.to_frame())
    assert result.n_observations < 50


def test_estimate_factor_betas_too_few_observations_raises():
    dates = pd.bdate_range("2020-01-01", periods=5)
    asset = pd.Series([0.01] * 5, index=dates, name="asset")
    factor = pd.Series([0.01] * 5, index=dates, name="f")
    with pytest.raises(ValueError, match="insufficient"):
        estimate_factor_betas(asset, factor.to_frame())


def test_sector_membership_betas():
    betas = sector_membership_betas(
        tickers=["JPM", "AAPL", "XLF"],
        sector_by_ticker={"JPM": "Financials", "AAPL": "Technology", "XLF": "Financials"},
        factor_name="rate_sensitive_financials",
        member_sectors={"Financials"},
    )
    assert betas == {"JPM": 1.0, "AAPL": 0.0, "XLF": 1.0}
