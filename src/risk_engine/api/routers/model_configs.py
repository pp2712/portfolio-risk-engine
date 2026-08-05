"""Not in the blueprint's Section 16 endpoint table, but a risk run needs a config_id and there is
no other way to create one without direct DB access -- a small, obviously-necessary addition."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from risk_engine.api.deps import get_db, require_api_key
from risk_engine.api.schemas.risk import ModelConfigCreate, ModelConfigOut
from risk_engine.db.models import ModelConfig

router = APIRouter(prefix="/model-configs", tags=["model-configs"])


@router.post("", response_model=ModelConfigOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_model_config(body: ModelConfigCreate, db: Session = Depends(get_db)) -> ModelConfig:
    config = ModelConfig(
        model_version=body.model_version,
        lookback_window_days=body.lookback_window_days,
        mc_num_simulations=body.mc_num_simulations,
        mc_random_seed=body.mc_random_seed,
        confidence_levels=body.confidence_levels,
        extra_params=body.extra_params,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config
