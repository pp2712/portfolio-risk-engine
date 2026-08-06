"""Sanity checks that the schema round-trips through Postgres correctly."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from risk_engine.db.models import Asset, Portfolio, Position, Price

pytestmark = pytest.mark.integration


def test_insert_and_query_asset(db_session):
    asset = Asset(ticker="AAPL", name="Apple Inc.", asset_class="EQUITY", currency="USD")
    db_session.add(asset)
    db_session.commit()

    fetched = db_session.query(Asset).filter_by(ticker="AAPL").one()
    assert fetched.name == "Apple Inc."
    assert fetched.asset_id is not None


def test_price_immutability_allows_correction_rows(db_session):
    asset = Asset(ticker="MSFT", name="Microsoft", asset_class="EQUITY", currency="USD")
    db_session.add(asset)
    db_session.flush()

    p1 = Price(
        asset_id=asset.asset_id,
        price_date=dt.date(2024, 1, 2),
        adj_close=100.0,
        close=100.0,
        source="yfinance",
    )
    db_session.add(p1)
    db_session.commit()

    # A "correction" -- same (asset_id, price_date), later ingested_at, different value.
    p2 = Price(
        asset_id=asset.asset_id,
        price_date=dt.date(2024, 1, 2),
        adj_close=100.5,
        close=100.5,
        source="yfinance",
    )
    db_session.add(p2)
    db_session.commit()  # must not raise -- append-only, no unique(asset_id, price_date) constraint

    rows = db_session.query(Price).filter_by(asset_id=asset.asset_id).all()
    assert len(rows) == 2


def test_position_uniqueness_per_asset_date(db_session):
    portfolio = Portfolio(name="Test Portfolio", base_currency="USD")
    asset = Asset(ticker="XOM", name="Exxon", asset_class="EQUITY", currency="USD")
    db_session.add_all([portfolio, asset])
    db_session.flush()

    db_session.add(
        Position(
            portfolio_id=portfolio.portfolio_id,
            asset_id=asset.asset_id,
            as_of_date=dt.date(2024, 1, 2),
            quantity=100,
        )
    )
    db_session.commit()

    db_session.add(
        Position(
            portfolio_id=portfolio.portfolio_id,
            asset_id=asset.asset_id,
            as_of_date=dt.date(2024, 1, 2),
            quantity=50,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_position_quantity_must_be_positive_at_db_level(db_session):
    """Long-only is enforced structurally (CHECK constraint), not just by the API's Pydantic
    schema -- a direct DB write bypassing the API must still be rejected."""
    portfolio = Portfolio(name="Test Portfolio", base_currency="USD")
    asset = Asset(ticker="BAC", name="Bank of America", asset_class="EQUITY", currency="USD")
    db_session.add_all([portfolio, asset])
    db_session.flush()

    db_session.add(
        Position(portfolio_id=portfolio.portfolio_id, asset_id=asset.asset_id, as_of_date=dt.date(2024, 1, 2), quantity=-10)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
