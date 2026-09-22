"""
GeoInfra Phase 9.1
Prometheus observability metrics for the FastAPI backend.

This module is intentionally independent from the Phase 8 database
and Kubernetes architecture. It does not modify application data.
"""

from prometheus_client import Counter, Gauge, Histogram


HTTP_REQUESTS_TOTAL = Counter(
    "geoinfra_http_requests_total",
    "Total HTTP requests processed by the GeoInfra backend.",
    ["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "geoinfra_http_request_duration_seconds",
    "HTTP request processing duration in seconds.",
    ["method", "path"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "geoinfra_http_requests_in_progress",
    "Number of HTTP requests currently being processed.",
    ["method"],
)

APPLICATION_INFO = Gauge(
    "geoinfra_application_info",
    "GeoInfra application information.",
    ["phase", "component"],
)

INFRASTRUCTURE_ASSETS = Gauge(
    "geoinfra_infrastructure_assets",
    "Current number of infrastructure assets known to the application.",
)

APPLICATION_INFO.labels(
    phase="9.1",
    component="fastapi-backend",
).set(1)


def set_infrastructure_asset_count(count: int) -> None:
    """Update the infrastructure asset count exposed to Prometheus."""
    INFRASTRUCTURE_ASSETS.set(max(0, int(count)))
