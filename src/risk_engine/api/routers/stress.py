from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.api.deps import get_db, require_api_key
from risk_engine.api.schemas.stress import (
    ScenarioCreate,
    ScenarioOut,
    StressRunRequest,
    StressRunResultOut,
    StressRunSummaryOut,
)
from risk_engine.api.services.stress_service import StressRunError, execute_stress_run
from risk_engine.db.models import Scenario, StressResult

router = APIRouter(tags=["stress"])


@router.get("/stress/runs", response_model=list[StressRunSummaryOut])
def list_stress_runs(portfolio_id: int, db: Session = Depends(get_db)) -> list[StressRunSummaryOut]:
    rows = db.execute(
        select(StressResult, Scenario.name)
        .join(Scenario, Scenario.scenario_id == StressResult.scenario_id)
        .where(StressResult.portfolio_id == portfolio_id)
        .order_by(StressResult.calculated_at.desc())
    ).all()
    return [
        StressRunSummaryOut(
            stress_result_id=sr.stress_result_id, scenario_id=sr.scenario_id, scenario_name=name,
            as_of_date=sr.as_of_date, portfolio_pnl=sr.portfolio_pnl, portfolio_pnl_pct=sr.portfolio_pnl_pct,
        )
        for sr, name in rows
    ]


@router.get("/scenarios", response_model=list[ScenarioOut])
def list_scenarios(db: Session = Depends(get_db)) -> list[Scenario]:
    return list(db.query(Scenario).order_by(Scenario.scenario_id).all())


@router.post("/scenarios", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_scenario(body: ScenarioCreate, db: Session = Depends(get_db)) -> Scenario:
    scenario = Scenario(
        name=body.name, scenario_type=body.scenario_type, description=body.description,
        historical_start=body.historical_start, historical_end=body.historical_end,
        factor_shocks=body.factor_shocks or None, version=body.version,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.post("/stress/runs", response_model=StressRunResultOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def trigger_stress_run(body: StressRunRequest, db: Session = Depends(get_db)) -> StressResult:
    try:
        result = execute_stress_run(db, body.portfolio_id, body.scenario_id, body.as_of_date)
        db.commit()
    except StressRunError as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    return result


@router.get("/stress/runs/{stress_result_id}", response_model=StressRunResultOut)
def get_stress_run(stress_result_id: int, db: Session = Depends(get_db)) -> StressResult:
    result = db.get(StressResult, stress_result_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"stress run {stress_result_id} not found")
    return result
