"""Kupiec (1995) Proportion-of-Failures (POF) test.

H0: the observed exception rate equals the model's stated exception probability p = 1 - confidence
    (e.g. exactly 5% breaches for a 95% VaR model).
H1: the true exception rate differs from p (two-sided -- too many OR too few breaches both reject).

Likelihood-ratio statistic:
    LR_POF = -2 ln[ (1-p)^(T-x) p^x / ( (1-x/T)^(T-x) (x/T)^x ) ]
where p = 1-alpha, T = number of observations, x = number of exceptions.
Under H0, LR_POF ~ chi-squared(1).

Implemented via `scipy.special.xlogy` (x*log(y), defined as 0 when x==0 regardless of y) so the
x=0 and x=T edge cases -- which naively hit log(0) or 0^0 -- are handled correctly without special
casing, matching the standard MLE convention that "0 events contribute 0 to the log-likelihood".
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy import stats
from scipy.special import xlogy


@dataclass(frozen=True)
class KupiecResult:
    n_observations: int
    n_exceptions: int
    expected_exception_rate: float
    observed_exception_rate: float
    lr_statistic: float
    p_value: float
    reject_h0: bool
    interpretation: str


def kupiec_pof_test(n_observations: int, n_exceptions: int, confidence: float, test_significance: float = 0.05) -> KupiecResult:
    if n_observations <= 0:
        raise ValueError("n_observations must be positive")
    if not 0 <= n_exceptions <= n_observations:
        raise ValueError("n_exceptions must be between 0 and n_observations")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")

    p = 1.0 - confidence
    t = n_observations
    x = n_exceptions
    x_rate = x / t

    lr = -2.0 * (
        xlogy(t - x, 1 - p) + xlogy(x, p) - xlogy(t - x, 1 - x_rate) - xlogy(x, x_rate)
    )
    p_value = float(stats.chi2.sf(lr, df=1))
    reject = p_value < test_significance

    if not reject:
        interpretation = (
            f"Fail to reject H0 (p={p_value:.4f}): the observed exception rate "
            f"({x}/{t} = {x_rate:.2%}) is statistically consistent with the model's stated "
            f"{p:.0%} exception rate."
        )
    elif x_rate > p:
        interpretation = (
            f"Reject H0 (p={p_value:.4f}): the model UNDER-COVERS risk -- {x}/{t} = {x_rate:.2%} "
            f"observed exceptions is significantly more than the expected {p:.0%}."
        )
    else:
        interpretation = (
            f"Reject H0 (p={p_value:.4f}): the model OVER-COVERS risk -- {x}/{t} = {x_rate:.2%} "
            f"observed exceptions is significantly fewer than the expected {p:.0%} (VaR is too "
            f"conservative)."
        )

    return KupiecResult(
        n_observations=t,
        n_exceptions=x,
        expected_exception_rate=p,
        observed_exception_rate=x_rate,
        lr_statistic=float(lr),
        p_value=p_value,
        reject_h0=reject,
        interpretation=interpretation,
    )
