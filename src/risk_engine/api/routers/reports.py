from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_engine.api.deps import get_db, require_api_key
from risk_engine.db.models import Report, RiskRun
from risk_engine.reporting.generator import ReportGenerationError, generate_report

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportSummaryOut(BaseModel):
    report_id: int
    risk_run_id: int
    as_of_date: str
    status: str
    generated_at: str


@router.get("", response_model=list[ReportSummaryOut])
def list_reports(portfolio_id: int, db: Session = Depends(get_db)) -> list[ReportSummaryOut]:
    rows = db.execute(
        select(Report, RiskRun.as_of_date)
        .join(RiskRun, RiskRun.risk_run_id == Report.risk_run_id)
        .where(RiskRun.portfolio_id == portfolio_id)
        .order_by(Report.generated_at.desc())
    ).all()
    return [
        ReportSummaryOut(
            report_id=r.report_id, risk_run_id=r.risk_run_id, as_of_date=str(as_of_date),
            status=r.status, generated_at=str(r.generated_at),
        )
        for r, as_of_date in rows
    ]


@router.get("/{risk_run_id}", response_class=HTMLResponse)
def get_report(risk_run_id: int, db: Session = Depends(get_db)) -> str:
    """Serve the HTML report for a risk run, generating it on first request if it doesn't exist
    yet (idempotent, matching the risk-run/backtest/stress-run pattern)."""
    existing = db.query(Report).filter(Report.risk_run_id == risk_run_id).order_by(Report.generated_at.desc()).first()
    if existing is not None and Path(existing.storage_path).exists():
        return Path(existing.storage_path).read_text(encoding="utf-8")

    try:
        report = generate_report(db, risk_run_id)
        db.commit()
    except ReportGenerationError as e:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    return Path(report.storage_path).read_text(encoding="utf-8")


@router.post("/{risk_run_id}/regenerate", response_class=HTMLResponse, dependencies=[Depends(require_api_key)])
def regenerate_report(risk_run_id: int, backtest_id: int | None = None, db: Session = Depends(get_db)) -> str:
    """Force regeneration with optional backtest/stress context attached."""
    try:
        report = generate_report(db, risk_run_id, backtest_id=backtest_id)
        db.commit()
    except ReportGenerationError as e:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    return Path(report.storage_path).read_text(encoding="utf-8")
