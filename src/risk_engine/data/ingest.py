"""Ingestion orchestration: vendor download -> validate -> persist prices -> compute + persist returns.

This is the impure layer (DB + network) that wraps the pure functions in `vendors.py`,
`validation.py`, and `returns.py`. Idempotent: re-running for a date range that's already been
ingested with unchanged vendor values inserts nothing new; a genuine correction (vendor revises a
historical adjusted close) inserts a new row rather than mutating the old one (see CLAUDE.md
"Immutable data").
"""

from __future__ import annotations

import datetime as dt
import logging

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.data.returns import compute_returns_for_asset
from risk_engine.data.universe import AssetSpec
from risk_engine.data.validation import validate_raw_prices
from risk_engine.data.vendors import fetch_from_stooq, fetch_from_yfinance
from risk_engine.db.models import Asset, Price, Return

logger = logging.getLogger(__name__)

PRICE_TOLERANCE = 1e-6  # relative tolerance for deciding "value unchanged" vs "correction"


def get_or_create_asset(db: Session, spec: AssetSpec) -> Asset:
    asset = db.execute(select(Asset).where(Asset.ticker == spec.ticker)).scalar_one_or_none()
    if asset is not None:
        return asset
    asset = Asset(ticker=spec.ticker, name=spec.name, asset_class=spec.asset_class, currency="USD")
    db.add(asset)
    db.flush()
    return asset


def _fetch_with_fallback(ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    raw = fetch_from_yfinance(ticker, start, end)
    if raw.empty:
        logger.warning("falling back to stooq for %s", ticker)
        raw = fetch_from_stooq(ticker, start, end)
    return raw


def _existing_prices(db: Session, asset_id: int, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Latest (max ingested_at) row per price_date, for idempotency comparison."""
    rows = db.execute(
        select(Price.price_date, Price.adj_close, Price.close, Price.ingested_at)
        .where(Price.asset_id == asset_id, Price.price_date.between(start, end))
        .order_by(Price.price_date, Price.ingested_at.desc())
    ).all()
    if not rows:
        return pd.DataFrame(columns=["price_date", "adj_close", "close"])
    df = pd.DataFrame(rows, columns=["price_date", "adj_close", "close", "ingested_at"])
    return df.drop_duplicates("price_date", keep="first")  # first = latest ingested_at, thanks to sort


def ingest_asset(db: Session, spec: AssetSpec, start: dt.date, end: dt.date) -> dict:
    """Full pipeline for one asset. Returns a summary dict for logging/observability."""
    asset = get_or_create_asset(db, spec)

    raw = _fetch_with_fallback(spec.ticker, start, end)
    if raw.empty:
        logger.error("no data available for %s from any vendor", spec.ticker)
        return {"ticker": spec.ticker, "rows_fetched": 0, "rows_inserted": 0, "issues": 0}

    validation = validate_raw_prices(raw, as_of=dt.date.today())
    for issue in validation.issues:
        level = logging.WARNING if issue.issue_type == "large_move_flagged" else logging.ERROR
        logger.log(level, "data_quality_issue", extra={"ticker": issue.ticker, "date": str(issue.price_date), "type": issue.issue_type, "detail": issue.detail})

    clean = validation.clean
    existing = _existing_prices(db, asset.asset_id, start, end)
    existing_by_date = existing.set_index("price_date") if not existing.empty else None

    rows_inserted = 0
    for _, row in clean.iterrows():
        needs_insert = True
        if existing_by_date is not None and row["price_date"] in existing_by_date.index:
            prev = existing_by_date.loc[row["price_date"]]
            same = abs(float(prev["adj_close"]) - float(row["adj_close"])) < PRICE_TOLERANCE * max(1.0, abs(float(row["adj_close"])))
            needs_insert = not same
            if needs_insert:
                logger.info("price correction for %s on %s: %.4f -> %.4f", spec.ticker, row["price_date"], prev["adj_close"], row["adj_close"])
        if needs_insert:
            db.add(
                Price(
                    asset_id=asset.asset_id,
                    price_date=row["price_date"],
                    adj_close=float(row["adj_close"]),
                    close=float(row["close"]),
                    volume=int(row["volume"]) if pd.notna(row["volume"]) else None,
                    source=row["source"],
                )
            )
            rows_inserted += 1
    db.flush()

    _recompute_returns(db, asset, start, end)

    return {"ticker": spec.ticker, "rows_fetched": len(raw), "rows_inserted": rows_inserted, "issues": len(validation.issues)}


def _recompute_returns(db: Session, asset: Asset, start: dt.date, end: dt.date) -> None:
    """Recompute returns for the ingested window from the latest price series and insert any
    return rows not already present with the same value (idempotent, same principle as prices).
    """
    price_rows = db.execute(
        select(Price.price_date, Price.adj_close, Price.ingested_at)
        .where(Price.asset_id == asset.asset_id)
        .order_by(Price.price_date, Price.ingested_at.desc())
    ).all()
    if not price_rows:
        return
    prices_df = pd.DataFrame(price_rows, columns=["price_date", "adj_close", "ingested_at"])
    prices_df = prices_df.drop_duplicates("price_date", keep="first")  # latest ingested_at per date

    returns_df = compute_returns_for_asset(prices_df.rename(columns={"price_date": "price_date"}))
    if returns_df.empty:
        return

    window_mask = (returns_df["return_date"] >= start) & (returns_df["return_date"] <= end)
    returns_df = returns_df[window_mask]

    existing = db.execute(
        select(Return.return_date, Return.log_return)
        .where(Return.asset_id == asset.asset_id, Return.return_date.between(start, end))
        .order_by(Return.return_date, Return.ingested_at.desc())
    ).all()
    existing_by_date = (
        pd.DataFrame(existing, columns=["return_date", "log_return"]).drop_duplicates("return_date", keep="first").set_index("return_date")
        if existing
        else None
    )

    for _, row in returns_df.iterrows():
        needs_insert = True
        if existing_by_date is not None and row["return_date"] in existing_by_date.index:
            prev = existing_by_date.loc[row["return_date"], "log_return"]
            needs_insert = abs(float(prev) - float(row["log_return"])) > 1e-9
        if needs_insert:
            db.add(
                Return(
                    asset_id=asset.asset_id,
                    return_date=row["return_date"],
                    log_return=float(row["log_return"]),
                    simple_return=float(row["simple_return"]),
                )
            )
    db.flush()


def ingest_universe(db: Session, universe: tuple[AssetSpec, ...], start: dt.date, end: dt.date) -> list[dict]:
    summaries = []
    for spec in universe:
        summary = ingest_asset(db, spec, start, end)
        summaries.append(summary)
        db.commit()
    return summaries
