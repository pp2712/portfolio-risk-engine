"""Read queries used by the orchestration layer.

Note the deliberate distinction from `validation/data_access.py`:
- Here (`get_returns_matrix`), `as_of_date` means "using all data known as of the end of this
  date" -- i.e. `<=`. This is correct for a live risk run: "what is my forward-looking VaR right
  now, given everything I know through today" legitimately includes today's own realised return.
- In `validation/data_access.get_returns_before`, `as_of_date` means "strictly before this date"
  (`<`) -- because that function feeds the backtest loop, which is forecasting THAT SPECIFIC
  DATE's own outcome and must not have seen it yet.
Both are correct; they answer different questions. Do not merge them.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.data.returns import build_aligned_return_matrix
from risk_engine.db.models import Asset, Position, Price, Return


def get_latest_positions(db: Session, portfolio_id: int, as_of_date: dt.date) -> dict[str, float]:
    """Most recent position snapshot at or before `as_of_date`, per asset.

    Positions are recorded per (portfolio, asset, as_of_date); "current" holdings as of a given
    date is the latest recorded as_of_date <= that date for each asset.
    """
    subq = (
        select(Position.asset_id, Position.quantity, Position.as_of_date, Asset.ticker)
        .join(Asset, Asset.asset_id == Position.asset_id)
        .where(Position.portfolio_id == portfolio_id, Position.as_of_date <= as_of_date)
        .order_by(Position.asset_id, Position.as_of_date.desc())
    )
    rows = db.execute(subq).all()

    latest: dict[str, float] = {}
    seen_assets: set[int] = set()
    for asset_id, quantity, _pos_date, ticker in rows:
        if asset_id in seen_assets:
            continue
        seen_assets.add(asset_id)
        latest[ticker] = float(quantity)
    return latest


def get_latest_prices(db: Session, tickers: list[str], as_of_date: dt.date) -> dict[str, float]:
    """Latest adj_close at or before `as_of_date`, per ticker (latest ingested_at wins per date)."""
    if not tickers:
        return {}
    rows = db.execute(
        select(Asset.ticker, Price.price_date, Price.adj_close, Price.ingested_at)
        .join(Price, Price.asset_id == Asset.asset_id)
        .where(Asset.ticker.in_(tickers), Price.price_date <= as_of_date)
        .order_by(Asset.ticker, Price.price_date.desc(), Price.ingested_at.desc())
    ).all()

    latest: dict[str, float] = {}
    seen: set[str] = set()
    for ticker, _price_date, adj_close, _ingested_at in rows:
        if ticker in seen:
            continue
        seen.add(ticker)
        latest[ticker] = float(adj_close)
    return latest


def get_returns_matrix(
    db: Session, tickers: list[str], as_of_date: dt.date, lookback_days: int, column: str = "log_return"
) -> pd.DataFrame:
    """Aligned (inner-joined) return matrix for `tickers`, using the most recent `lookback_days`
    observations with return_date <= as_of_date (see module docstring). `column` selects
    log_return (default, for risk models) or simple_return (for P&L/drawdown -- CLAUDE.md)."""
    if not tickers:
        return pd.DataFrame()

    by_ticker: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        rows = db.execute(
            select(Return.return_date, Return.log_return, Return.simple_return, Return.ingested_at)
            .join(Asset, Asset.asset_id == Return.asset_id)
            .where(Asset.ticker == ticker, Return.return_date <= as_of_date)
            .order_by(Return.return_date.desc(), Return.ingested_at.desc())
            .limit(lookback_days * 2)  # headroom in case of duplicate-date correction rows
        ).all()
        if not rows:
            continue
        df = pd.DataFrame(rows, columns=["return_date", "log_return", "simple_return", "ingested_at"])
        df = df.drop_duplicates("return_date", keep="first").sort_values("return_date")
        by_ticker[ticker] = df.tail(lookback_days)

    if not by_ticker:
        return pd.DataFrame()
    return build_aligned_return_matrix(by_ticker, column=column)


def get_simple_returns_window(
    db: Session, tickers: list[str], start: dt.date, end: dt.date
) -> pd.DataFrame:
    """Simple-return matrix (for P&L/stress scenarios, see CLAUDE.md) over an explicit date range,
    inclusive. Tickers with no data in the window are simply absent as columns (see
    stress/engine.py's excluded_assets handling)."""
    if not tickers:
        return pd.DataFrame()

    series = {}
    for ticker in tickers:
        rows = db.execute(
            select(Return.return_date, Return.simple_return, Return.ingested_at)
            .join(Asset, Asset.asset_id == Return.asset_id)
            .where(Asset.ticker == ticker, Return.return_date.between(start, end))
            .order_by(Return.return_date, Return.ingested_at.desc())
        ).all()
        if not rows:
            continue
        df = pd.DataFrame(rows, columns=["return_date", "simple_return", "ingested_at"])
        df = df.drop_duplicates("return_date", keep="first").set_index("return_date")["simple_return"]
        df.index = pd.to_datetime(df.index)
        series[ticker] = df

    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).sort_index()
