"""Structured JSON logging.

CLAUDE.md: "Every data-quality issue that gets flagged is logged (structured JSON log), not
silently dropped." This module makes that concrete -- one JSON object per log line, with
risk_run_id/portfolio_id/config_id/ticker etc. as top-level fields (via `extra=`) so logs are
directly grep/jq-able without a log-aggregation pipeline. This is the audit trail's log-side
complement to the DB-side audit trail in db/models.py (CLAUDE.md "Observability" /
"Model Versioning & Auditability").
"""

from __future__ import annotations

import datetime as dt
import json
import logging

_RESERVED_LOG_RECORD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": dt.datetime.fromtimestamp(record.created, tz=dt.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Any extra=... fields passed to the log call (e.g. risk_run_id=..., ticker=...).
        for key, value in vars(record).items():
            if key not in _RESERVED_LOG_RECORD_ATTRS:
                payload[key] = value

        return json.dumps(payload, default=str)


def setup_json_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
