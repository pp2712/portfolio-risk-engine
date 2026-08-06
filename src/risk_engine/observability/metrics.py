"""Metrics: a Prometheus counter/histogram setup (blueprint Section 23: "a simple Prometheus
counter/histogram setup is enough; a full Grafana dashboard is a nice-to-have, not required").

- `http_requests_total` / `http_request_duration_seconds`: API request count/latency/error rate by
  endpoint, via `RequestMetricsMiddleware`.
- `risk_calculation_duration_seconds`: calculation duration by model type (historical/parametric/
  monte_carlo), recorded around each risk_models call site.
- `pipeline_run_total`: daily pipeline success/failure count.

Exposed at GET /metrics in Prometheus text format.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from prometheus_client import Counter, Histogram
from starlette.requests import Request
from starlette.responses import Response

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status_code"]
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "path"]
)
risk_calculation_duration_seconds = Histogram(
    "risk_calculation_duration_seconds", "Risk calculation duration by method", ["method"]
)
pipeline_run_total = Counter(
    "pipeline_run_total", "Daily pipeline run outcomes", ["status"]
)


async def request_metrics_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    path = request.url.path
    http_requests_total.labels(method=request.method, path=path, status_code=response.status_code).inc()
    http_request_duration_seconds.labels(method=request.method, path=path).observe(duration)
    return response


class timed_calculation:
    """Context manager: `with timed_calculation("monte_carlo"): ...` records duration."""

    def __init__(self, method: str) -> None:
        self.method = method
        self._start = 0.0

    def __enter__(self) -> timed_calculation:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_info: object) -> None:
        risk_calculation_duration_seconds.labels(method=self.method).observe(time.perf_counter() - self._start)
