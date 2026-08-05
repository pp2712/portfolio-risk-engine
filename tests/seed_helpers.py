"""Shared synthetic-data seeding for integration tests (not a conftest fixture -- imported
directly so each test controls exactly when/how it seeds)."""

from __future__ import annotations

import datetime as dt

import numpy as np
from sqlalchemy import select

from risk_engine.db.models import Asset, ModelConfig, Portfolio, Position, Price, Return


def seed_synthetic_portfolio(db, n_days=300, n_assets=3, seed=0, start=dt.date(2023, 1, 2), ticker_prefix="SYN"):
    rng = np.random.default_rng(seed)
    tickers = [f"{ticker_prefix}{i}" for i in range(n_assets)]
    dates = [start + dt.timedelta(days=i) for i in range(n_days)]

    assets = []
    for t in tickers:
        asset = Asset(ticker=t, name=t, asset_class="EQUITY", currency="USD")
        db.add(asset)
        assets.append(asset)
    db.flush()

    for asset in assets:
        price = 100.0
        for d in dates:
            r = rng.normal(0.0003, 0.015)
            price *= 1 + r
            db.add(Price(asset_id=asset.asset_id, price_date=d, adj_close=price, close=price, source="synthetic"))
    db.flush()

    for asset in assets:
        rows = db.execute(
            select(Price.price_date, Price.adj_close)
            .where(Price.asset_id == asset.asset_id)
            .order_by(Price.price_date)
        ).all()
        prev = None
        for price_date, adj_close in rows:
            if prev is not None:
                log_r = float(np.log(float(adj_close) / float(prev)))
                simple_r = float(adj_close) / float(prev) - 1.0
                db.add(Return(asset_id=asset.asset_id, return_date=price_date, log_return=log_r, simple_return=simple_r))
            prev = adj_close
    db.flush()

    portfolio = Portfolio(name="Synthetic Test Portfolio", base_currency="USD")
    db.add(portfolio)
    db.flush()
    for asset in assets:
        db.add(Position(portfolio_id=portfolio.portfolio_id, asset_id=asset.asset_id, as_of_date=dates[-1], quantity=100))
    db.flush()

    config = ModelConfig(
        model_version="v1.0", lookback_window_days=250, mc_num_simulations=5000, mc_random_seed=42,
        confidence_levels=[0.95, 0.99],
    )
    db.add(config)
    db.flush()

    return portfolio, config, dates[-1], tickers
