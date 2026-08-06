from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.api.deps import get_db, require_api_key
from risk_engine.api.schemas.portfolio import (
    PortfolioCreate,
    PortfolioDetailOut,
    PortfolioOut,
    PositionOut,
    PositionsSetRequest,
)
from risk_engine.db.models import Asset, Portfolio, Position
from risk_engine.db.queries import get_latest_prices
from risk_engine.portfolio.calculations import (
    compute_portfolio_value,
    compute_position_values,
    compute_weights,
    herfindahl_hirschman_index,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.get("", response_model=list[PortfolioOut])
def list_portfolios(db: Session = Depends(get_db)) -> list[Portfolio]:
    return list(db.execute(select(Portfolio).order_by(Portfolio.portfolio_id)).scalars())


@router.post("", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_portfolio(body: PortfolioCreate, db: Session = Depends(get_db)) -> Portfolio:
    portfolio = Portfolio(name=body.name, base_currency=body.base_currency.upper())
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


@router.get("/{portfolio_id}", response_model=PortfolioDetailOut)
def get_portfolio(portfolio_id: int, db: Session = Depends(get_db)) -> PortfolioDetailOut:
    """Position detail plus market value / weight / concentration, computed live from the latest
    available prices for the current holding dates -- the same pure functions
    (`portfolio/calculations.py`) already used by the HTML report generator, just also returned
    here as JSON. If no price is available for a ticker (e.g. no ingested history yet), valuation
    fields degrade to null rather than failing the whole request -- the position itself is still
    real and returned.
    """
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"portfolio {portfolio_id} not found")

    rows = db.execute(
        select(Asset.ticker, Position.quantity, Position.as_of_date)
        .join(Asset, Asset.asset_id == Position.asset_id)
        .where(Position.portfolio_id == portfolio_id)
        .order_by(Position.as_of_date.desc())
    ).all()

    valuation_date: dt.date | None = max((d for _t, _q, d in rows), default=None)
    market_value_by_ticker: dict[str, float] = {}
    weight_by_ticker: dict[str, float] = {}
    portfolio_value: float | None = None
    hhi: float | None = None

    if rows and valuation_date is not None:
        tickers = [t for t, _q, _d in rows]
        prices = get_latest_prices(db, tickers, valuation_date)
        quantities = {t: float(q) for t, q, _d in rows if t in prices}
        if quantities:
            market_value_by_ticker = compute_position_values(quantities, prices)
            portfolio_value = compute_portfolio_value(market_value_by_ticker)
            weight_by_ticker = compute_weights(market_value_by_ticker, portfolio_value)
            hhi = herfindahl_hirschman_index(weight_by_ticker)

    positions = [
        PositionOut(
            ticker=t, quantity=float(q), as_of_date=d,
            market_value=market_value_by_ticker.get(t), weight=weight_by_ticker.get(t),
        )
        for t, q, d in rows
    ]

    return PortfolioDetailOut(
        portfolio_id=portfolio.portfolio_id,
        name=portfolio.name,
        base_currency=portfolio.base_currency,
        created_at=portfolio.created_at,
        positions=positions,
        portfolio_value=portfolio_value,
        concentration_hhi=hhi,
        valuation_date=valuation_date,
    )


@router.post("/{portfolio_id}/positions", response_model=PortfolioDetailOut, dependencies=[Depends(require_api_key)])
def set_positions(portfolio_id: int, body: PositionsSetRequest, db: Session = Depends(get_db)) -> PortfolioDetailOut:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"portfolio {portfolio_id} not found")

    unknown_tickers = []
    for pos in body.positions:
        asset = db.execute(select(Asset).where(Asset.ticker == pos.ticker)).scalar_one_or_none()
        if asset is None:
            unknown_tickers.append(pos.ticker)
            continue
        db.add(Position(portfolio_id=portfolio_id, asset_id=asset.asset_id, as_of_date=body.as_of_date, quantity=pos.quantity))
    if unknown_tickers:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"unknown tickers (not in asset universe): {unknown_tickers}")

    db.commit()
    return get_portfolio(portfolio_id, db)
