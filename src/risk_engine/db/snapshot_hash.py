"""Data-snapshot hashing -- the mechanism that makes reproducibility enforceable rather than
aspirational (CLAUDE.md / blueprint Section 24). Hashes the exact tickers, as_of_date, and return
values used by a risk calculation, so if underlying data is later corrected/restated, old reports
remain provably tied to the data that actually produced them.
"""

from __future__ import annotations

import datetime as dt
import hashlib

import pandas as pd


def compute_data_snapshot_hash(tickers: list[str], as_of_date: dt.date, returns_matrix: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(f"{sorted(tickers)}|{as_of_date.isoformat()}|{returns_matrix.shape}".encode())
    if not returns_matrix.empty:
        # Sort columns for determinism regardless of dict/query ordering, then hash raw bytes.
        ordered = returns_matrix[sorted(returns_matrix.columns)]
        h.update(ordered.to_numpy().tobytes())
        h.update(str(list(ordered.index)).encode())
    return h.hexdigest()
