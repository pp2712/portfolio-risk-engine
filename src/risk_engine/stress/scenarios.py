"""Stress scenarios represented as data, not code (CLAUDE.md architecture principle #2).

A new historical-replay scenario is a new `ScenarioSpec` (or a new `scenarios` DB row) with a
date range -- it never requires touching `engine.py`. `engine.py` dispatches on `scenario_type`
and has exactly two execution paths.

Seed scenarios below match the blueprint's Section 11-13 recommendations:
- 2008 GFC (Sept-Nov 2008): slower-moving, credit-driven shock.
- 2020 COVID crash (Feb-Mar 2020): faster, liquidity-driven shock.
Comparing the two (different loss *shapes* despite comparable magnitude, per-position/sector
contribution) is Experiment 6 in notebooks/03_stress_scenarios.ipynb.

Factor shocks are equity-only (bonds/duration are out of scope -- see docs/KNOWN_LIMITATIONS.md).
The "rates" shock is deliberately implemented as a simplified equity-sensitivity-to-rates proxy
(shocking rate-sensitive sectors -- Financials -- harder than the broad market) rather than a true
fixed-income duration calculation, exactly as the blueprint suggests as the honest simplification.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Literal

ScenarioType = Literal["HISTORICAL_REPLAY", "FACTOR_SHOCK"]


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    scenario_type: ScenarioType
    version: int = 1
    description: str = ""
    historical_start: dt.date | None = None
    historical_end: dt.date | None = None
    factor_shocks: dict[str, float] = field(default_factory=dict)


HISTORICAL_REPLAY_SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        name="2008 Global Financial Crisis",
        scenario_type="HISTORICAL_REPLAY",
        historical_start=dt.date(2008, 9, 1),
        historical_end=dt.date(2008, 11, 30),
        description=(
            "Replays realised asset returns from Sept-Nov 2008 onto today's portfolio weights. "
            "Slower-moving, credit-driven shock. Assets without price history in this window "
            "(e.g. META, IPO 2012) are excluded from the replay and flagged in the result rather "
            "than silently assumed flat or dropped from the portfolio weighting."
        ),
    ),
    ScenarioSpec(
        name="2020 COVID Crash",
        scenario_type="HISTORICAL_REPLAY",
        historical_start=dt.date(2020, 2, 19),
        historical_end=dt.date(2020, 3, 23),
        description=(
            "Replays realised asset returns from the Feb 19 - Mar 23 2020 crash onto today's "
            "portfolio weights. Faster, liquidity-driven shock -- contrast with 2008 in "
            "notebooks/03_stress_scenarios.ipynb Experiment 6."
        ),
    ),
)

FACTOR_SHOCK_SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        name="Equity Market -20%",
        scenario_type="FACTOR_SHOCK",
        factor_shocks={"equity_market": -0.20},
        description="Broad equity market shock applied via each asset's estimated market beta.",
    ),
    ScenarioSpec(
        name="Equity Market -40% (Severe)",
        scenario_type="FACTOR_SHOCK",
        factor_shocks={"equity_market": -0.40},
        description="Severe broad equity market shock, double the base scenario.",
    ),
    ScenarioSpec(
        name="Rate Shock +150bps (Financials proxy)",
        scenario_type="FACTOR_SHOCK",
        factor_shocks={"rate_sensitive_financials": -0.10, "equity_market": -0.03},
        description=(
            "Simplified equity-only proxy for a +150bps rate shock: fixed-income/duration is out "
            "of scope, so this shocks rate-sensitive financial-sector exposure (-10%) and the "
            "broad market modestly (-3%) rather than computing a true duration-based bond "
            "revaluation. Documented simplification, not a hidden approximation."
        ),
    ),
)
