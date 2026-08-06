from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from risk_engine.api.deps import get_db, require_api_key
from risk_engine.db.models import Report
from risk_engine.reporting.generator import ReportGenerationError, generate_report

router = APIRouter(prefix="/reports", tags=["reports"])


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
