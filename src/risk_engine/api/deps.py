"""FastAPI dependencies: DB session, API-key auth.

CLAUDE.md: "All API write endpoints require the X-API-Key header... Full multi-user auth/RBAC is
explicitly out of scope for this project, not half-implemented." This is intentionally a single
shared-secret header check, not a user/session/RBAC system.
"""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from risk_engine.config import get_settings
from risk_engine.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if x_api_key is None or x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing or invalid X-API-Key header")
