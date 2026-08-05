"""Christoffersen (1998) independence test + combined conditional-coverage test.

Kupiec alone can't distinguish "12 exceptions spread evenly through the year" from "12 exceptions
all clustered in one crisis week" -- the latter means the model fails exactly when it matters
(during regime shifts), even though the total count looks fine. Christoffersen tests whether
exceptions are independent over time by building a first-order Markov transition matrix over the
binary exception series.

n00 = count of (no exception -> no exception), n01 = (no exception -> exception),
n10 = (exception -> no exception), n11 = (exception -> exception).

pi01 = P(exception tomorrow | no exception today) = n01 / (n00+n01)
pi11 = P(exception tomorrow | exception today)    = n11 / (n10+n11)
pi   = P(exception) unconditional                  = (n01+n11) / T

H0 (independence): pi01 == pi11 (== pi). Likelihood-ratio statistic ~ chi-squared(1) under H0:

    LR_ind = -2 ln[ (1-pi)^(n00+n10) pi^(n01+n11) /
                     ( (1-pi01)^n00 pi01^n01 (1-pi11)^n10 pi11^n11 ) ]

Combined conditional-coverage test (the criterion regulators actually use): tests correct coverage
AND independence jointly.
    LR_cc = LR_POF + LR_ind ~ chi-squared(2)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats
from scipy.special import xlogy

from risk_engine.validation.kupiec import KupiecResult


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator > 0 else 0.0


@dataclass(frozen=True)
class ChristoffersenResult:
    n00: int
    n01: int
    n10: int
    n11: int
    pi01: float
    pi11: float
    pi_unconditional: float
    lr_statistic: float
    p_value: float
    reject_h0: bool
    applicable: bool  # False when there are 0 or 1 exceptions -- clustering isn't meaningfully testable
    interpretation: str


def christoffersen_independence_test(
    exceptions: Sequence[bool] | np.ndarray, test_significance: float = 0.05
) -> ChristoffersenResult:
    x = np.asarray(exceptions, dtype=int)
    if len(x) < 2:
        raise ValueError("need at least 2 observations to test exception transitions")
    if not np.isin(x, [0, 1]).all():
        raise ValueError("exceptions must be a binary (0/1 or bool) sequence")

    prev, curr = x[:-1], x[1:]
    n00 = int(np.sum((prev == 0) & (curr == 0)))
    n01 = int(np.sum((prev == 0) & (curr == 1)))
    n10 = int(np.sum((prev == 1) & (curr == 0)))
    n11 = int(np.sum((prev == 1) & (curr == 1)))
    t = n00 + n01 + n10 + n11

    pi01 = _safe_ratio(n01, n00 + n01)
    pi11 = _safe_ratio(n11, n10 + n11)
    pi = _safe_ratio(n01 + n11, t)

    lr = -2.0 * (
        xlogy(n00 + n10, 1 - pi)
        + xlogy(n01 + n11, pi)
        - xlogy(n00, 1 - pi01)
        - xlogy(n01, pi01)
        - xlogy(n10, 1 - pi11)
        - xlogy(n11, pi11)
    )
    p_value = float(stats.chi2.sf(lr, df=1))

    total_exceptions = n01 + n11
    applicable = total_exceptions >= 2  # need >=2 exceptions for a transition-clustering signal
    reject = applicable and p_value < test_significance

    if not applicable:
        interpretation = (
            f"Not applicable: only {total_exceptions} exception(s) observed -- too few to test "
            "for clustering."
        )
    elif not reject:
        interpretation = (
            f"Fail to reject H0 (p={p_value:.4f}): exceptions show no significant clustering -- "
            f"P(exception|prior exception)={pi11:.2%} is statistically consistent with "
            f"P(exception|prior no exception)={pi01:.2%}."
        )
    else:
        interpretation = (
            f"Reject H0 (p={p_value:.4f}): exceptions are significantly CLUSTERED -- "
            f"P(exception|prior exception)={pi11:.2%} vs. P(exception|prior no exception)="
            f"{pi01:.2%}. The model tends to fail in runs, e.g. during regime shifts, even if its "
            "overall exception rate looks acceptable."
        )

    return ChristoffersenResult(
        n00=n00, n01=n01, n10=n10, n11=n11,
        pi01=pi01, pi11=pi11, pi_unconditional=pi,
        lr_statistic=float(lr), p_value=p_value, reject_h0=reject,
        applicable=applicable, interpretation=interpretation,
    )


@dataclass(frozen=True)
class ConditionalCoverageResult:
    lr_statistic: float
    p_value: float
    reject_h0: bool
    interpretation: str


def conditional_coverage_test(
    kupiec: KupiecResult, christoffersen: ChristoffersenResult, test_significance: float = 0.05
) -> ConditionalCoverageResult:
    """LR_cc = LR_POF + LR_ind ~ chi-squared(2). Tests correct coverage AND independence jointly
    -- this is the combined criterion regulators actually use."""
    lr_cc = kupiec.lr_statistic + christoffersen.lr_statistic
    p_value = float(stats.chi2.sf(lr_cc, df=2))
    reject = p_value < test_significance

    if not reject:
        interpretation = (
            f"Fail to reject H0 (p={p_value:.4f}): the model has both correct unconditional "
            "coverage and independent exceptions."
        )
    else:
        interpretation = (
            f"Reject H0 (p={p_value:.4f}): the model fails on coverage and/or independence -- "
            "see the individual Kupiec and Christoffersen results for which."
        )

    return ConditionalCoverageResult(
        lr_statistic=float(lr_cc), p_value=p_value, reject_h0=reject, interpretation=interpretation
    )
