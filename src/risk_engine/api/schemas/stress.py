from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class ScenarioCreate(BaseModel):
    name: str
    scenario_type: str = Field(pattern="^(HISTORICAL_REPLAY|FACTOR_SHOCK)$")
    description: str = ""
    historical_start: dt.date | None = None
    historical_end: dt.date | None = None
    factor_shocks: dict[str, float] = Field(default_factory=dict)
    version: int = 1


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    scenario_id: int
    name: str
    scenario_type: str
    description: str | None
    historical_start: dt.date | None
    historical_end: dt.date | None
    factor_shocks: dict[str, float] | None
    version: int


class StressRunRequest(BaseModel):
    portfolio_id: int
    scenario_id: int
    as_of_date: dt.date


class StressRunResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stress_result_id: int
    scenario_id: int
    portfolio_id: int
    as_of_date: dt.date
    portfolio_pnl: float
    portfolio_pnl_pct: float
    position_contributions: dict[str, float]


class StressRunSummaryOut(BaseModel):
    stress_result_id: int
    scenario_id: int
    scenario_name: str
    as_of_date: dt.date
    portfolio_pnl: float
    portfolio_pnl_pct: float
