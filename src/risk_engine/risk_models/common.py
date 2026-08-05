"""Shared conventions for all VaR/CVaR estimators.

**Sign/quantile convention (read this before touching any risk_models code):**

- VaR_alpha and CVaR_alpha are always reported as POSITIVE loss numbers. A VaR_95 of 0.03 means
  "a 3% loss is the threshold not expected to be exceeded 95% of the time", not -0.03.
- `z_alpha` used throughout this package is `Phi^-1(alpha)` (the POSITIVE convention -- e.g.
  z_0.95 = +1.645), so that `VaR = z_alpha * sigma - mu` directly yields a positive number for
  a typical near-zero-mean, positive-sigma return series.

  Note: the source blueprint's Section 7.2 describes z_alpha as "the standard normal quantile,
  e.g. 1.645 for 95%" (implying the positive convention) but then writes the formula as
  `VaR_alpha = -(mu + z_alpha * sigma)`, which only gives a positive VaR if z_alpha is NEGATIVE
  (i.e. z_alpha = Phi^-1(1-alpha) = -1.645 at 95%, as Section 8 separately and correctly states).
  Taking the positive z_alpha=1.645 into the "-(mu + z*sigma)" formula literally produces a
  NEGATIVE VaR for a typical portfolio -- a real sign error if implemented as literally written.
  Both forms are mathematically equivalent once the sign of z_alpha is fixed consistently; this
  module standardises on the positive-z convention (`VaR = z_alpha * sigma - mu`) since it is the
  less error-prone of the two to implement and read. See docs/QUANTITATIVE_METHODOLOGY.md.

- Empirical (historical / Monte Carlo) VaR/CVaR use the "k worst observations" estimator rather
  than `numpy.quantile`'s interpolation, to avoid an ambiguous/ill-defined empirical quantile and
  to make the CVaR >= VaR invariant hold by construction (not by luck of the interpolation
  scheme):
    k = ceil((1 - alpha) * T), floored at 1
    sorted ascending returns -> VaR = -sorted[k-1] (the k-th worst return)
                                 CVaR = -mean(sorted[:k]) (average of the k worst returns)
"""

from __future__ import annotations

import numpy as np
from scipy import stats


def z_score(confidence: float) -> float:
    """Positive-convention standard normal quantile, e.g. z_score(0.95) = 1.645..."""
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    return float(stats.norm.ppf(confidence))


def tail_size(n_observations: int, confidence: float) -> int:
    """Number of worst observations making up the (1-confidence) tail. Always >= 1."""
    if n_observations <= 0:
        raise ValueError("n_observations must be positive")
    # Subtract a small epsilon before ceil so e.g. (1-0.95)*100 (which is 5.000000000000001 in
    # binary float, not exactly 5) doesn't spuriously round up to 6.
    raw = (1.0 - confidence) * n_observations
    return max(1, int(np.ceil(raw - 1e-9)))


def empirical_var_cvar(returns: np.ndarray, confidence: float) -> tuple[float, float]:
    """Historical/Monte-Carlo VaR + CVaR from a sample of simulated or realised returns.

    Returns (VaR, CVaR), both positive loss numbers. CVaR >= VaR always holds by construction
    (see module docstring).
    """
    returns = np.asarray(returns, dtype=float)
    if returns.ndim != 1:
        raise ValueError("returns must be a 1-D array")
    if len(returns) == 0:
        raise ValueError("returns must not be empty")

    k = tail_size(len(returns), confidence)
    sorted_returns = np.sort(returns)  # ascending: worst losses first
    var = -float(sorted_returns[k - 1])
    cvar = -float(sorted_returns[:k].mean())
    return var, cvar
