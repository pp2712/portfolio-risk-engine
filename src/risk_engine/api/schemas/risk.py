from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class ModelConfigCreate(BaseModel):
    model_version: str = "v1.0"
    lookback_window_days: int = Field(default=250, gt=1)
    mc_num_simulations: int = Field(default=25_000, gt=0)
    mc_random_seed: int = 42
    confidence_levels: list[float] = Field(default_factory=lambda: [0.95, 0.99])
    extra_params: dict = Field(default_factory=dict)


class ModelConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    config_id: int
    model_version: str
    lookback_window_days: int
    mc_num_simulations: int
    mc_random_seed: int
    confidence_levels: list[float]


class RiskRunRequest(BaseModel):
    portfolio_id: int
    config_id: int
    as_of_date: dt.date


class RiskRunAccepted(BaseModel):
    risk_run_id: int
    status: str


class DecompositionEntry(BaseModel):
    ticker: str
    component_var: float
    marginal_var: float
    pct_contribution: float


class RiskRunResultOut(BaseModel):
    risk_run_id: int
    portfolio_id: int
    as_of_date: dt.date
    var: dict[str, dict[str, float]]  # method -> {confidence_str: value}
    cvar: dict[str, dict[str, float]]
    decomposition: list[DecompositionEntry]
    config: ModelConfigOut
    data_snapshot_hash: str
    calculated_at: dt.datetime
    volatility: float | None = None  # annualised, over the run's lookback window
    max_drawdown: float | None = None  # over the same window, positive fraction
