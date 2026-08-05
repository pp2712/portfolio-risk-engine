from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class HistoryPoint(BaseModel):
    as_of_date: dt.date
    risk_run_id: int
    var: dict[str, dict[str, float]]
    cvar: dict[str, dict[str, float]]


class HistoryOut(BaseModel):
    portfolio_id: int
    points: list[HistoryPoint]
