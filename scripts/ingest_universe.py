"""CLI entrypoint: ingest the full asset universe's price/return history.

Usage:
    .venv\\Scripts\\python.exe scripts\\ingest_universe.py --start 2007-01-01 --end 2026-08-05
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from risk_engine.data.ingest import ingest_universe  # noqa: E402
from risk_engine.data.universe import UNIVERSE  # noqa: E402
from risk_engine.db.session import SessionLocal  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2007, 1, 1))
    parser.add_argument("--end", type=dt.date.fromisoformat, default=dt.date.today())
    args = parser.parse_args()

    db = SessionLocal()
    try:
        summaries = ingest_universe(db, UNIVERSE, args.start, args.end)
    finally:
        db.close()

    total_fetched = sum(s["rows_fetched"] for s in summaries)
    total_inserted = sum(s["rows_inserted"] for s in summaries)
    total_issues = sum(s["issues"] for s in summaries)
    print(f"\n{'ticker':<8}{'fetched':>10}{'inserted':>10}{'issues':>10}")
    for s in summaries:
        print(f"{s['ticker']:<8}{s['rows_fetched']:>10}{s['rows_inserted']:>10}{s['issues']:>10}")
    print(f"\nTOTAL: {total_fetched} fetched, {total_inserted} inserted, {total_issues} data-quality issues flagged")


if __name__ == "__main__":
    main()
