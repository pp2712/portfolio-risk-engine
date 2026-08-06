"""Seed the `scenarios` table from stress/scenarios.py's data-driven definitions (idempotent)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from risk_engine.db.models import Scenario  # noqa: E402
from risk_engine.db.session import SessionLocal  # noqa: E402
from risk_engine.stress.scenarios import (  # noqa: E402
    FACTOR_SHOCK_SCENARIOS,
    HISTORICAL_REPLAY_SCENARIOS,
)


def main() -> None:
    db = SessionLocal()
    try:
        for spec in (*HISTORICAL_REPLAY_SCENARIOS, *FACTOR_SHOCK_SCENARIOS):
            existing = db.execute(
                select(Scenario).where(Scenario.name == spec.name, Scenario.version == spec.version)
            ).scalar_one_or_none()
            if existing is not None:
                print(f"exists: {spec.name}")
                continue
            db.add(
                Scenario(
                    name=spec.name, scenario_type=spec.scenario_type, description=spec.description,
                    historical_start=spec.historical_start, historical_end=spec.historical_end,
                    factor_shocks=spec.factor_shocks or None, version=spec.version,
                )
            )
            print(f"created: {spec.name}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
