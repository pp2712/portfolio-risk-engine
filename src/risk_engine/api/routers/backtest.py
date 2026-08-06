from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.api.deps import get_db, require_api_key
from risk_engine.api.schemas.backtest import (
    BacktestAccepted,
    BacktestRequest,
    BacktestResultOut,
    BacktestSummaryOut,
    ExceptionPoint,
)
from risk_engine.api.services.backtest_service import BacktestError, execute_backtest
from risk_engine.db.models import BacktestException, BacktestResult

router = APIRouter(prefix="/risk", tags=["backtest"])


@router.get("/backtest", response_model=list[BacktestSummaryOut])
def list_backtests(portfolio_id: int, db: Session = Depends(get_db)) -> list[BacktestResult]:
    return list(
        db.execute(select(BacktestResult).where(BacktestResult.portfolio_id == portfolio_id).order_by(BacktestResult.calculated_at.desc())).scalars()
    )


@router.post("/backtest", response_model=BacktestAccepted, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)])
def trigger_backtest(body: BacktestRequest, db: Session = Depends(get_db)) -> BacktestAccepted:
    try:
        result = execute_backtest(
            db, body.portfolio_id, body.config_id, body.method, body.confidence, body.window_start, body.window_end
        )
        db.commit()
    except BacktestError as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    return BacktestAccepted(backtest_id=result.backtest_id)


@router.get("/backtest/{backtest_id}", response_model=BacktestResultOut)
def get_backtest(backtest_id: int, db: Session = Depends(get_db)) -> BacktestResultOut:
    result = db.get(BacktestResult, backtest_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"backtest {backtest_id} not found")

    exceptions = db.execute(
        select(BacktestException).where(BacktestException.backtest_id == backtest_id).order_by(BacktestException.as_of_date)
    ).scalars().all()

    return BacktestResultOut(
        backtest_id=result.backtest_id,
        portfolio_id=result.portfolio_id,
        method=result.method,
        confidence_level=result.confidence_level,
        window_start=result.window_start,
        window_end=result.window_end,
        num_observations=result.num_observations,
        num_exceptions=result.num_exceptions,
        kupiec_stat=result.kupiec_stat,
        kupiec_pvalue=result.kupiec_pvalue,
        kupiec_pass=result.kupiec_pass,
        christoffersen_stat=result.christoffersen_stat,
        christoffersen_pvalue=result.christoffersen_pvalue,
        christoffersen_pass=result.christoffersen_pass,
        conditional_coverage_stat=result.conditional_coverage_stat,
        conditional_coverage_pvalue=result.conditional_coverage_pvalue,
        conditional_coverage_pass=result.conditional_coverage_pass,
        traffic_light_zone=result.traffic_light_zone,
        exceptions=[
            ExceptionPoint(
                as_of_date=e.as_of_date, var_forecast=e.var_forecast, realised_return=e.realised_return,
                realised_pnl=e.realised_pnl, is_exception=e.is_exception,
            )
            for e in exceptions
        ],
    )
