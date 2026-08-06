# Multi-stage build: install dependencies in a builder layer, copy only what's needed into the
# final runtime image. Not executed/validated in this dev sandbox (no Docker available -- see
# CLAUDE.md "Important architectural decisions" and docs/KNOWN_LIMITATIONS.md); written to the
# same standard as the rest of the codebase and reviewed carefully, but flagged honestly.

FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

FROM python:3.11-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
COPY frontend/ frontend/

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "risk_engine.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
