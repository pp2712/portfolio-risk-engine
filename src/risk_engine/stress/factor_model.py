"""Factor-exposure estimation for stress testing (not a return-prediction model).

Used purely to answer "how much does this asset move for a given factor shock", via OLS
regression of the asset's historical returns on one or more factor return series. If a
Fama-French-style factor set is supplied, this is where it earns its place -- as a factor-exposure
estimation tool, not (mis)used as a return-forecasting model. See docs/QUANTITATIVE_METHODOLOGY.md.

`estimate_factor_betas` is generic over whatever factor return series the caller supplies. In this
project the one factor genuinely regression-estimated is `equity_market`, using SPY as the market
proxy (data/universe.py: MARKET_FACTOR_PROXY) -- SPY is ingested purely for this purpose and is
never an investable holding. Sector-membership factors (e.g. "rate_sensitive_financials") are not
regression-estimated; they're a direct, documented simplification (1.0 for sector members, 0.0
otherwise) -- see stress/scenarios.py and docs/KNOWN_LIMITATIONS.md for why (no bond/duration data
in scope, so there is no rates factor return series to regress against).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FactorBetaResult:
    betas: dict[str, float]  # factor name -> beta
    alpha: float
    r_squared: float
    n_observations: int


def estimate_factor_betas(asset_returns: pd.Series, factor_returns: pd.DataFrame) -> FactorBetaResult:
    """OLS regression: asset_returns ~ alpha + sum_f(beta_f * factor_returns[f]).

    Aligns the two inputs to their common dates (inner join) before regressing -- callers must
    already have applied any as_of_date cutoff upstream (this function itself has no leakage
    concern since it isn't used inside the backtest loop, only for point-in-time stress scenario
    setup, but it still must not silently include mismatched dates).
    """
    aligned = pd.concat([asset_returns.rename("asset"), factor_returns], axis=1, join="inner").dropna()
    if len(aligned) < 10:
        raise ValueError(f"insufficient overlapping observations for regression: {len(aligned)}")

    factor_names = list(factor_returns.columns)
    y = aligned["asset"].to_numpy(dtype=float)
    x_factors = aligned[factor_names].to_numpy(dtype=float)
    x = np.column_stack([np.ones(len(aligned)), x_factors])

    coeffs, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
    alpha = float(coeffs[0])
    betas = dict(zip(factor_names, coeffs[1:].tolist(), strict=True))

    fitted = x @ coeffs
    residuals = y - fitted
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return FactorBetaResult(betas=betas, alpha=alpha, r_squared=r_squared, n_observations=len(aligned))


def sector_membership_betas(
    tickers: list[str], sector_by_ticker: dict[str, str], factor_name: str, member_sectors: set[str]
) -> dict[str, float]:
    """Direct (non-regression) factor exposure: 1.0 for assets in `member_sectors`, else 0.0.

    Used for factors with no available return series to regress against (e.g. the rates proxy --
    fixed-income data is out of scope, see docs/KNOWN_LIMITATIONS.md). Documented as a
    simplification, not presented as an estimated beta.
    """
    return {t: (1.0 if sector_by_ticker.get(t) in member_sectors else 0.0) for t in tickers}
