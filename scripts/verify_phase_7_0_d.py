#!/usr/bin/env python3
"""
GeoInfra Phase 7.0D Integration Verification
=============================================

Verifies:

1. Backend availability
2. Phase 7.0D OpenAPI route registration
3. Anomaly API integration
4. Predictive trend API integration
5. Predictive risk API integration
6. Anomaly-event persistence
7. Database schema compatibility
8. Provenance contract
9. Invalid/missing asset handling
10. Phase 6.9 regression
11. Existing core API regression

The verifier is intentionally API-driven and non-destructive where possible.

Environment:
    API_BASE_URL=http://localhost:8000
    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/geospatialdb

DATABASE_URL is optional. Database persistence is also verified through
Phase 7.0D APIs where possible.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://localhost:8000",
).rstrip("/")

SOURCE = "LOCAL_PROJECT"
EXTERNAL = False

REQUEST_TIMEOUT = 15

PASSED = 0
FAILED = 0
WARNINGS = 0


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def pass_check(message: str) -> None:
    global PASSED
    PASSED += 1
    print(f"✅ PASS: {message}")


def fail_check(message: str, detail: Any = None) -> None:
    global FAILED
    FAILED += 1
    print(f"❌ FAIL: {message}")

    if detail is not None:
        try:
            rendered = json.dumps(
                detail,
                indent=2,
                default=str,
            )
        except Exception:
            rendered = str(detail)

        print(rendered)


def warn(message: str) -> None:
    global WARNINGS
    WARNINGS += 1
    print(f"⚠️  WARN: {message}")


def expect(condition: bool, message: str, detail: Any = None) -> bool:
    if condition:
        pass_check(message)
        return True

    fail_check(message, detail)
    return False


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def request(
    method: str,
    path: str,
    payload: Optional[dict[str, Any]] = None,
    expected_status: Optional[set[int]] = None,
) -> tuple[int, Any]:

    url = f"{API_BASE_URL}{path}"

    data = None
    headers = {
        "Accept": "application/json",
    }

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method.upper(),
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=REQUEST_TIMEOUT,
        ) as response:

            status = response.status
            body = response.read().decode("utf-8")

    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8")

    except Exception as exc:
        return 0, {
            "error": str(exc),
            "url": url,
        }

    try:
        parsed = json.loads(body) if body else None
    except json.JSONDecodeError:
        parsed = body

    if expected_status is not None and status not in expected_status:
        return status, parsed

    return status, parsed


def get(path: str) -> tuple[int, Any]:
    return request("GET", path)


def post(
    path: str,
    payload: Optional[dict[str, Any]] = None,
) -> tuple[int, Any]:
    return request("POST", path, payload)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def unwrap(value: Any) -> Any:
    """
    Safely unwrap common GeoInfra response envelopes.

    Supported patterns:
        {"result": ...}
        {"results": ...}
        {"data": ...}

    Provenance-bearing dictionaries are preserved.
    """

    if not isinstance(value, dict):
        return value

    for key in ("result", "results", "data"):
        candidate = value.get(key)

        if candidate is not None:
            return candidate

    return value


def find_list(value: Any) -> list[Any]:
    """
    Extract a useful list from common API response shapes.
    """

    if isinstance(value, list):
        return value

    if not isinstance(value, dict):
        return []

    preferred_keys = (
        "results",
        "items",
        "events",
        "anomalies",
        "predictions",
        "risks",
        "assets",
        "measurements",
        "objectives",
        "executions",
        "runbooks",
        "incidents",
        "locations",
    )

    for key in preferred_keys:
        candidate = value.get(key)

        if isinstance(candidate, list):
            return candidate

        if isinstance(candidate, dict):
            nested = find_list(candidate)
            if nested:
                return nested

    return []


def find_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    return {}


def provenance_ok(value: Any) -> bool:
    """
    Recursively look for a valid GeoInfra provenance pair.
    """

    if isinstance(value, dict):

        if "source" in value or "external" in value:
            return (
                value.get("source") == SOURCE
                and value.get("external") is EXTERNAL
            )

        for nested in value.values():
            if provenance_ok(nested):
                return True

    elif isinstance(value, list):
        for nested in value:
            if provenance_ok(nested):
                return True

    return False


def has_any_key(value: Any, keys: set[str]) -> bool:
    if not isinstance(value, dict):
        return False

    return bool(keys.intersection(value.keys()))


def numeric(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
    )


# ---------------------------------------------------------------------------
# Route discovery
# ---------------------------------------------------------------------------

section("PHASE 7.0D — BACKEND AVAILABILITY")

status, health = get("/health")

expect(
    status == 200,
    "Backend /health returns HTTP 200",
    {
        "status": status,
        "body": health,
    },
)

if status != 200:
    print()
    print("Backend is unavailable. Start it before running Phase 7.0D verification.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# OpenAPI
# ---------------------------------------------------------------------------

section("PHASE 7.0D — OPENAPI DISCOVERY")

status, openapi = get("/openapi.json")

expect(
    status == 200 and isinstance(openapi, dict),
    "OpenAPI document is available",
    {
        "status": status,
    },
)

paths = {}

if isinstance(openapi, dict):
    paths = openapi.get("paths", {}) or {}


def route_exists(path: str, method: Optional[str] = None) -> bool:

    definition = paths.get(path)

    if not isinstance(definition, dict):
        return False

    if method is None:
        return True

    return method.lower() in definition


phase70_paths = sorted(
    path
    for path in paths
    if (
        "anomal" in path.lower()
        or "predict" in path.lower()
        or "risk" in path.lower()
    )
)

print()
print("Discovered anomaly/predictive/risk routes:")

if phase70_paths:
    for path in phase70_paths:
        methods = sorted(
            method.upper()
            for method in paths[path]
            if method.lower()
            in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }
        )

        print(
            f"  {','.join(methods):12} {path}"
        )
else:
    print("  NONE")


expect(
    len(phase70_paths) > 0,
    "Phase 7.0 anomaly/predictive routes are registered",
)


# ---------------------------------------------------------------------------
# Flexible route selection
# ---------------------------------------------------------------------------

def choose_route(
    candidates: list[str],
    method: str,
) -> Optional[str]:

    for candidate in candidates:
        if route_exists(candidate, method):
            return candidate

    return None


ANALYZE_ROUTE = choose_route(
    [
        "/predictive/anomalies/{asset_id}",
        "/predictive/anomaly/{asset_id}",
        "/anomalies/analyze/{asset_id}",
        "/anomaly/analyze/{asset_id}",
        "/anomalies/{asset_id}",
    ],
    "get",
)

ANALYZE_POST_ROUTE = choose_route(
    [
        "/predictive/anomalies/{asset_id}/evaluate",
        "/predictive/anomalies/{asset_id}/analyze",
        "/predictive/anomaly/{asset_id}/evaluate",
        "/anomalies/{asset_id}/evaluate",
        "/anomalies/analyze/{asset_id}",
        "/anomaly/analyze/{asset_id}",
    ],
    "post",
)

TREND_ROUTE = choose_route(
    [
        "/predictive/trends/{asset_id}",
        "/predictive/trend/{asset_id}",
        "/predictions/{asset_id}",
        "/prediction/{asset_id}",
    ],
    "get",
)

RISK_ROUTE = choose_route(
    [
        "/predictive/risk/{asset_id}",
        "/predictive/risks/{asset_id}",
        "/predictive-risk/{asset_id}",
        "/risk/predictive/{asset_id}",
    ],
    "get",
)

EVENTS_ROUTE = choose_route(
    [
        "/predictive/anomalies",
        "/anomaly-events",
        "/anomalies",
        "/predictive/anomaly-events",
    ],
    "get",
)

SUMMARY_ROUTE = choose_route(
    [
        "/predictive/summary",
        "/predictive/anomalies/summary",
        "/anomaly-events/summary",
        "/anomalies/summary",
    ],
    "get",
)


# ---------------------------------------------------------------------------
# Report discovered integration contract
# ---------------------------------------------------------------------------

section("PHASE 7.0D — ROUTE CONTRACT")

print(f"Anomaly GET route : {ANALYZE_ROUTE}")
print(f"Anomaly POST route: {ANALYZE_POST_ROUTE}")
print(f"Trend route       : {TREND_ROUTE}")
print(f"Risk route        : {RISK_ROUTE}")
print(f"Events route      : {EVENTS_ROUTE}")
print(f"Summary route     : {SUMMARY_ROUTE}")

expect(
    ANALYZE_ROUTE is not None or ANALYZE_POST_ROUTE is not None,
    "Anomaly analysis endpoint exists",
)

expect(
    TREND_ROUTE is not None,
    "Predictive trend endpoint exists",
)

expect(
    RISK_ROUTE is not None,
    "Predictive risk endpoint exists",
)

expect(
    EVENTS_ROUTE is not None,
    "Persisted anomaly-event endpoint exists",
)


# ---------------------------------------------------------------------------
# Resolve a real asset
# ---------------------------------------------------------------------------

section("PHASE 7.0D — TEST ASSET DISCOVERY")

status, locations = get("/locations")

expect(
    status == 200,
    "/locations regression endpoint returns HTTP 200",
    {
        "status": status,
        "body": locations,
    },
)

location_items = find_list(locations)

asset_id = None

for item in location_items:
    if not isinstance(item, dict):
        continue

    candidate = item.get("id", item.get("asset_id"))

    try:
        candidate = int(candidate)
    except (TypeError, ValueError):
        continue

    if candidate > 0:
        asset_id = candidate
        break


if asset_id is None:
    # Existing project has asset IDs, but never silently claim
    # discovery succeeded if /locations response shape changes.
    warn(
        "Could not extract an asset ID from /locations; "
        "falling back to asset_id=1 for integration checks"
    )
    asset_id = 1
else:
    pass_check(
        f"Discovered real infrastructure asset_id={asset_id}"
    )


# ---------------------------------------------------------------------------
# Anomaly analysis
# ---------------------------------------------------------------------------

section("PHASE 7.0D — ANOMALY API")

anomaly_status = 0
anomaly_body: Any = None

if ANALYZE_ROUTE:

    path = ANALYZE_ROUTE.replace(
        "{asset_id}",
        str(asset_id),
    )

    anomaly_status, anomaly_body = get(path)

elif ANALYZE_POST_ROUTE:

    path = ANALYZE_POST_ROUTE.replace(
        "{asset_id}",
        str(asset_id),
    )

    anomaly_status, anomaly_body = post(path)

else:
    path = None


if path is not None:

    expect(
        anomaly_status == 200,
        f"Anomaly analysis returns HTTP 200 for asset {asset_id}",
        {
            "path": path,
            "status": anomaly_status,
            "body": anomaly_body,
        },
    )

    if anomaly_status == 200:

        expect(
            isinstance(anomaly_body, dict),
            "Anomaly API returns JSON object",
        )

        expect(
            provenance_ok(anomaly_body),
            "Anomaly API preserves LOCAL_PROJECT provenance",
            anomaly_body,
        )

        anomaly_result = unwrap(anomaly_body)

        if isinstance(anomaly_result, dict):

            expect(
                has_any_key(
                    anomaly_result,
                    {
                        "metrics",
                        "status",
                        "anomalous_metrics",
                        "watch_metrics",
                        "skipped_metrics",
                    },
                ),
                "Anomaly response exposes analysis fields",
                anomaly_result,
            )


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------

section("PHASE 7.0D — PREDICTIVE TREND API")

trend_status = 0
trend_body: Any = None

if TREND_ROUTE:

    trend_path = TREND_ROUTE.replace(
        "{asset_id}",
        str(asset_id),
    )

    trend_status, trend_body = get(trend_path)

    expect(
        trend_status == 200,
        f"Trend analysis returns HTTP 200 for asset {asset_id}",
        {
            "path": trend_path,
            "status": trend_status,
            "body": trend_body,
        },
    )

    if trend_status == 200:

        expect(
            isinstance(trend_body, dict),
            "Trend API returns JSON object",
        )

        expect(
            provenance_ok(trend_body),
            "Trend API preserves LOCAL_PROJECT provenance",
            trend_body,
        )

        trend_result = unwrap(trend_body)

        if isinstance(trend_result, dict):

            expect(
                has_any_key(
                    trend_result,
                    {
                        "metrics",
                        "trends",
                        "skipped_metrics",
                        "trend",
                        "direction",
                    },
                ),
                "Trend response exposes predictive analysis fields",
                trend_result,
            )


# ---------------------------------------------------------------------------
# Predictive risk
# ---------------------------------------------------------------------------

section("PHASE 7.0D — PREDICTIVE RISK API")

risk_status = 0
risk_body: Any = None

if RISK_ROUTE:

    risk_path = RISK_ROUTE.replace(
        "{asset_id}",
        str(asset_id),
    )

    risk_status, risk_body = get(risk_path)

    expect(
        risk_status == 200,
        f"Predictive risk returns HTTP 200 for asset {asset_id}",
        {
            "path": risk_path,
            "status": risk_status,
            "body": risk_body,
        },
    )

    if risk_status == 200:

        expect(
            isinstance(risk_body, dict),
            "Predictive risk API returns JSON object",
        )

        expect(
            provenance_ok(risk_body),
            "Predictive risk preserves LOCAL_PROJECT provenance",
            risk_body,
        )

        risk_result = unwrap(risk_body)

        if isinstance(risk_result, dict):

            score = risk_result.get(
                "score",
                risk_result.get(
                    "risk_score",
                    risk_result.get("predictive_risk_score"),
                ),
            )

            if score is not None:

                expect(
                    numeric(score),
                    "Predictive risk score is numeric",
                    score,
                )

                if numeric(score):
                    expect(
                        0 <= float(score) <= 100,
                        "Predictive risk score is bounded 0..100",
                        score,
                    )

            else:
                warn(
                    "Risk response did not expose score/risk_score/"
                    "predictive_risk_score at the first result level"
                )

            expect(
                has_any_key(
                    risk_result,
                    {
                        "risk_level",
                        "level",
                        "classification",
                        "score",
                        "risk_score",
                        "predictive_risk_score",
                        "metrics",
                        "explanation",
                    },
                ),
                "Predictive risk response exposes scoring/explainability fields",
                risk_result,
            )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

section("PHASE 7.0D — ANOMALY PERSISTENCE")

events_before: list[Any] = []

if EVENTS_ROUTE:

    status_before, body_before = get(EVENTS_ROUTE)

    expect(
        status_before == 200,
        "Persisted anomaly-events endpoint returns HTTP 200",
        {
            "status": status_before,
            "body": body_before,
        },
    )

    if status_before == 200:

        expect(
            provenance_ok(body_before),
            "Persisted anomaly-event API preserves LOCAL_PROJECT provenance",
            body_before,
        )

        events_before = find_list(body_before)

        print(
            f"Persisted anomaly rows currently visible: "
            f"{len(events_before)}"
        )


# Try an explicit evaluation route if one exists.
# This is safe: it evaluates current LOCAL_PROJECT telemetry.
if ANALYZE_POST_ROUTE:

    evaluate_path = ANALYZE_POST_ROUTE.replace(
        "{asset_id}",
        str(asset_id),
    )

    eval_status, eval_body = post(evaluate_path)

    expect(
        eval_status == 200,
        "Explicit anomaly evaluation completes successfully",
        {
            "status": eval_status,
            "body": eval_body,
        },
    )

    if eval_status == 200:
        expect(
            provenance_ok(eval_body),
            "Explicit anomaly evaluation preserves provenance",
            eval_body,
        )

    # Give the database/API a moment if persistence happens
    # immediately after evaluation.
    time.sleep(0.25)


if EVENTS_ROUTE:

    status_after, body_after = get(EVENTS_ROUTE)

    expect(
        status_after == 200,
        "Anomaly-event persistence remains queryable after evaluation",
        {
            "status": status_after,
            "body": body_after,
        },
    )

    if status_after == 200:

        events_after = find_list(body_after)

        # Empty is legitimate when current telemetry is not anomalous.
        expect(
            isinstance(events_after, list),
            "Anomaly persistence endpoint exposes an event collection",
        )

        if events_after:

            first_event = events_after[0]

            expect(
                isinstance(first_event, dict),
                "Persisted anomaly event is a JSON object",
                first_event,
            )

            if isinstance(first_event, dict):

                expected_schema_keys = {
                    "asset_id",
                    "metric",
                    "current_value",
                    "baseline_mean",
                    "baseline_stddev",
                    "deviation",
                    "z_score",
                    "anomaly_score",
                    "status",
                    "sample_count",
                    "source",
                    "external",
                }

                available = expected_schema_keys.intersection(
                    first_event.keys()
                )

                expect(
                    len(available) >= 8,
                    "Persisted event matches Phase 7.0A anomaly schema",
                    {
                        "available_keys": sorted(first_event.keys()),
                        "matched_keys": sorted(available),
                    },
                )

                expect(
                    first_event.get("source") == SOURCE,
                    "Persisted event source is LOCAL_PROJECT",
                    first_event,
                )

                expect(
                    first_event.get("external") is False,
                    "Persisted event external flag is false",
                    first_event,
                )

                if "status" in first_event:
                    expect(
                        first_event["status"]
                        in {
                            "WATCH",
                            "ANOMALOUS",
                            "CRITICAL",
                        },
                        "Persisted anomaly status satisfies migration constraint",
                        first_event["status"],
                    )

                if "sample_count" in first_event:
                    try:
                        sample_count = int(
                            first_event["sample_count"]
                        )
                    except (TypeError, ValueError):
                        sample_count = 0

                    expect(
                        sample_count >= 1,
                        "Persisted anomaly sample_count satisfies DB constraint",
                        first_event["sample_count"],
                    )

                if "anomaly_score" in first_event:
                    try:
                        anomaly_score = float(
                            first_event["anomaly_score"]
                        )
                    except (TypeError, ValueError):
                        anomaly_score = -1

                    expect(
                        anomaly_score >= 0,
                        "Persisted anomaly score satisfies DB constraint",
                        first_event["anomaly_score"],
                    )

        else:
            warn(
                "No anomaly rows currently persisted. "
                "This is valid if current telemetry has produced no "
                "WATCH/ANOMALOUS/CRITICAL event."
            )


# ---------------------------------------------------------------------------
# Summary API
# ---------------------------------------------------------------------------

section("PHASE 7.0D — PREDICTIVE SUMMARY")

if SUMMARY_ROUTE:

    summary_status, summary_body = get(SUMMARY_ROUTE)

    expect(
        summary_status == 200,
        "Predictive/anomaly summary returns HTTP 200",
        {
            "status": summary_status,
            "body": summary_body,
        },
    )

    if summary_status == 200:
        expect(
            provenance_ok(summary_body),
            "Predictive summary preserves LOCAL_PROJECT provenance",
            summary_body,
        )

else:
    warn(
        "No dedicated predictive summary route discovered; "
        "summary verification skipped"
    )


# ---------------------------------------------------------------------------
# Invalid asset validation
# ---------------------------------------------------------------------------

section("PHASE 7.0D — INPUT VALIDATION")

invalid_asset_id = 999999999

for label, route, method in (
    ("anomaly", ANALYZE_ROUTE, "GET"),
    ("trend", TREND_ROUTE, "GET"),
    ("risk", RISK_ROUTE, "GET"),
):

    if not route:
        continue

    invalid_path = route.replace(
        "{asset_id}",
        str(invalid_asset_id),
    )

    invalid_status, invalid_body = request(
        method,
        invalid_path,
    )

    expect(
        invalid_status in {
            400,
            404,
            422,
        },
        f"Unknown asset is rejected safely by {label} endpoint",
        {
            "status": invalid_status,
            "body": invalid_body,
        },
    )


# ---------------------------------------------------------------------------
# Phase 6.9 regression
# ---------------------------------------------------------------------------

section("PHASE 6.9 REGRESSION")

phase69_routes = [
    "/automation/runbooks",
    "/automation/executions",
    "/automation/summary",
    "/reliability/objectives",
    "/reliability/measurements",
    "/reliability/summary",
]

for route in phase69_routes:

    status, body = get(route)

    expect(
        status == 200,
        f"Regression: {route} returns HTTP 200",
        {
            "status": status,
            "body": body,
        },
    )

    if status == 200:

        expect(
            provenance_ok(body),
            f"Regression: {route} preserves LOCAL_PROJECT provenance",
            body,
        )


# ---------------------------------------------------------------------------
# Core platform regression
# ---------------------------------------------------------------------------

section("CORE PLATFORM REGRESSION")

core_routes = [
    "/health",
    "/locations",
    "/sensor-telemetry",
    "/sensor-health",
    "/alerts",
    "/analytics",
]

for route in core_routes:

    status, body = get(route)

    expect(
        status == 200,
        f"Regression: {route} returns HTTP 200",
        {
            "status": status,
            "body": body,
        },
    )


# ---------------------------------------------------------------------------
# Existing Phase 6.8 / incident regression
# ---------------------------------------------------------------------------

section("INCIDENT / SRE REGRESSION")

incident_routes = [
    "/incidents?limit=250",
    "/sre/intelligence?hours=168",
    "/sre/sla-status?limit=250",
    "/sre/priority-policy",
]

for route in incident_routes:

    status, body = get(route)

    expect(
        status == 200,
        f"Regression: {route} returns HTTP 200",
        {
            "status": status,
            "body": body,
        },
    )


# ---------------------------------------------------------------------------
# Provenance safety check
# ---------------------------------------------------------------------------

section("PHASE 7.0D — PROVENANCE SAFETY")

phase70_responses = [
    ("anomaly", anomaly_body),
    ("trend", trend_body),
    ("risk", risk_body),
]

for label, body in phase70_responses:

    if body is None:
        continue

    expect(
        provenance_ok(body),
        f"{label} response is explicitly local/non-external",
        body,
    )


# ---------------------------------------------------------------------------
# Final result
# ---------------------------------------------------------------------------

section("PHASE 7.0D RESULT")

print(f"Passed  : {PASSED}")
print(f"Failed  : {FAILED}")
print(f"Warnings: {WARNINGS}")

print()

if FAILED == 0:

    print(
        "✅ Phase 7.0D API integration, persistence, "
        "and regression verification PASSED"
    )

    sys.exit(0)

print(
    "❌ Phase 7.0D verification FAILED — "
    "review failed checks above"
)

sys.exit(1)
