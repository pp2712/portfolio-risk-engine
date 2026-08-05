"""Raw price validation & cleaning.

Principle (CLAUDE.md "Data handling rules"): flag, don't silently discard. The only rows dropped
outright are ones that cannot be valid under any interpretation (null/non-positive price, exact
duplicate rows) or that are structurally impossible (future dates). Large single-day moves are
flagged as issues but kept -- a real 12% crash day is exactly the tail-risk observation the risk
models must not lose.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd

OUTLIER_ABS_RETURN_THRESHOLD = 0.30  # 30% single-day move triggers a flag, not a removal
REQUIRED_COLUMNS = {"ticker", "price_date", "open", "high", "low", "close", "adj_close", "volume", "source"}


@dataclass
class ValidationIssue:
    ticker: str
    price_date: dt.date | None
    issue_type: str
    detail: str


@dataclass
class ValidationResult:
    clean: pd.DataFrame
    issues: list[ValidationIssue] = field(default_factory=list)


def validate_raw_prices(df: pd.DataFrame, as_of: dt.date | None = None) -> ValidationResult:
    """Validate + clean one ticker's (or a batch's) raw OHLCV frame.

    Hard rejects (row dropped, always logged): missing required columns entirely raises;
    null/non-positive adj_close or close; price_date in the future relative to `as_of`;
    exact duplicate (ticker, price_date) rows (keeps the first).

    Soft flags (row kept, logged): single-day |return| > OUTLIER_ABS_RETURN_THRESHOLD.
    """
    as_of = as_of or dt.date.today()
    issues: list[ValidationIssue] = []

    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(f"raw price frame missing required columns: {missing_cols}")

    work = df.copy()

    # Future dates -- structurally impossible, hard reject.
    future_mask = pd.to_datetime(work["price_date"]) > pd.Timestamp(as_of)
    for _, row in work[future_mask].iterrows():
        issues.append(
            ValidationIssue(row["ticker"], row["price_date"], "future_date", f"price_date {row['price_date']} > as_of {as_of}")
        )
    work = work[~future_mask]

    # Null / non-positive prices -- hard reject.
    bad_price_mask = (
        work["adj_close"].isna()
        | work["close"].isna()
        | (work["adj_close"] <= 0)
        | (work["close"] <= 0)
    )
    for _, row in work[bad_price_mask].iterrows():
        issues.append(
            ValidationIssue(row["ticker"], row["price_date"], "invalid_price", f"adj_close={row['adj_close']} close={row['close']}")
        )
    work = work[~bad_price_mask]

    # Exact duplicate (ticker, price_date) -- keep first, log the rest.
    dup_mask = work.duplicated(subset=["ticker", "price_date"], keep="first")
    for _, row in work[dup_mask].iterrows():
        issues.append(
            ValidationIssue(row["ticker"], row["price_date"], "duplicate_row", "duplicate (ticker, price_date) in vendor response")
        )
    work = work[~dup_mask]

    # Outlier flag (soft) -- single-day adj_close move > threshold. Computed per ticker.
    work = work.sort_values(["ticker", "price_date"])
    for ticker, grp in work.groupby("ticker"):
        pct_change = grp["adj_close"].pct_change()
        outlier_dates = grp.loc[pct_change.abs() > OUTLIER_ABS_RETURN_THRESHOLD, "price_date"]
        for d in outlier_dates:
            pct = pct_change.loc[grp["price_date"] == d].iloc[0]
            issues.append(
                ValidationIssue(ticker, d, "large_move_flagged", f"single-day adj_close move {pct:+.1%} (kept, not removed)")
            )

    return ValidationResult(clean=work.reset_index(drop=True), issues=issues)
