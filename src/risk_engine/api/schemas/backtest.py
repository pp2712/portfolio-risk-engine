from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    portfolio_id: int
    config_id: int
    method: str = Field(pattern="^(historical|parametric|monte_carlo)$")
    confidence: float = Field(gt=0, lt=1)
    window_start: dt.date
    window_end: dt.date


class BacktestAccepted(BaseModel):
    backtest_id: int
    status: str = "completed"


class ExceptionPoint(BaseModel):
    as_of_date: dt.date
    var_forecast: float
    realised_return: float
    realised_pnl: float
    is_exception: bool


class BacktestResultOut(BaseModel):
    backtest_id: int
    portfolio_id: int
    method: str
    confidence_level: float
    window_start: dt.date
    window_end: dt.date
    num_observations: int
    num_exceptions: int
    kupiec_stat: float
    kupiec_pvalue: float
    kupiec_pass: bool
    christoffersen_stat: float | None
    christoffersen_pvalue: float | None
    christoffersen_pass: bool | None
    conditional_coverage_stat: float | None
    conditional_coverage_pvalue: float | None
    conditional_coverage_pass: bool | None
    traffic_light_zone: str
    exceptions: list[ExceptionPoint]
