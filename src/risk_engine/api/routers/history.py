from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.api.deps import get_db
from risk_engine.api.schemas.history import HistoryOut, HistoryPoint
from risk_engine.db.models import CvarResult, RiskRun, VarResult

router = APIRouter(prefix="/risk", tags=["history"])


@router.get("/history/{portfolio_id}", response_model=HistoryOut)
def get_risk_history(portfolio_id: int, db: Session = Depends(get_db)) -> HistoryOut:
    """Time-ordered VaR/CVaR across dates for a portfolio -- a straightforward query across
    risk_runs joined to var_results/cvar_results (blueprint Section 19), since every risk_run is
    already stored with its as_of_date."""
    runs = db.execute(
        select(RiskRun).where(RiskRun.portfolio_id == portfolio_id).order_by(RiskRun.as_of_date)
    ).scalars().all()

    points = []
    for run in runs:
        var_rows = db.execute(select(VarResult).where(VarResult.risk_run_id == run.risk_run_id)).scalars().all()
        cvar_rows = db.execute(select(CvarResult).where(CvarResult.risk_run_id == run.risk_run_id)).scalars().all()

        var: dict[str, dict[str, float]] = {}
        for v in var_rows:
            var.setdefault(v.method, {})[f"{v.confidence_level:.2f}"] = v.var_value
        cvar: dict[str, dict[str, float]] = {}
        for c in cvar_rows:
            cvar.setdefault(c.method, {})[f"{c.confidence_level:.2f}"] = c.cvar_value

        points.append(HistoryPoint(as_of_date=run.as_of_date, risk_run_id=run.risk_run_id, var=var, cvar=cvar))

    return HistoryOut(portfolio_id=portfolio_id, points=points)
