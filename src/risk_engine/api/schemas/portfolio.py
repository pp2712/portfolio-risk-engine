from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_currency: str = Field(default="USD", min_length=3, max_length=3)


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    portfolio_id: int
    name: str
    base_currency: str
    created_at: dt.datetime


class PositionIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    quantity: float = Field(gt=0, description="Long-only: quantity must be positive (see docs/KNOWN_LIMITATIONS.md)")


class PositionsSetRequest(BaseModel):
    as_of_date: dt.date
    positions: list[PositionIn] = Field(min_length=1)


class PositionOut(BaseModel):
    ticker: str
    quantity: float
    as_of_date: dt.date
    market_value: float | None = None
    weight: float | None = None


class PortfolioDetailOut(BaseModel):
    portfolio_id: int
    name: str
    base_currency: str
    created_at: dt.datetime
    positions: list[PositionOut]
    portfolio_value: float | None = None
    concentration_hhi: float | None = None
    valuation_date: dt.date | None = None
