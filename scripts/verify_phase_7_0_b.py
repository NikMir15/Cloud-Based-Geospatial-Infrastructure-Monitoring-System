#!/usr/bin/env python3

"""
GeoInfra Phase 7.0B Verification

Deterministically verifies:
- linear regression
- STABLE trends
- INCREASING trends
- DECREASING trends
- projection
- R²/confidence
- scale-aware slope classification
- validation
- partial telemetry handling
- asset-level aggregation
- LOCAL_PROJECT provenance
"""

from __future__ import annotations

import math
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from prediction_engine import (  # noqa: E402
    EXTERNAL,
    MIN_TREND_SAMPLES,
    SOURCE,
    SUPPORTED_METRICS,
    TREND_DECREASING,
    TREND_INCREASING,
    TREND_STABLE,
    analyze_asset_trends,
    analyze_trend,
    classify_trend,
    linear_regression,
    normalized_slope,
)


passed = 0
failed = 0


def check(condition, description):
    global passed, failed

    if condition:
        passed += 1
        print(f"✅ PASS: {description}")
    else:
        failed += 1
        print(f"❌ FAIL: {description}")


def approx(actual, expected, tolerance=1e-5):
    return math.isclose(
        float(actual),
        float(expected),
        rel_tol=tolerance,
        abs_tol=tolerance,
    )


def expect_exception(fn, exception_type, description):
    global passed, failed

    try:
        fn()
    except exception_type:
        passed += 1
        print(f"✅ PASS: {description}")
    except Exception as exc:
        failed += 1
        print(
            f"❌ FAIL: {description} "
            f"(unexpected {type(exc).__name__}: {exc})"
        )
    else:
        failed += 1
        print(f"❌ FAIL: {description} (no exception raised)")


print("=" * 72)
print("GEOINFRA PHASE 7.0B — PREDICTIVE TREND VERIFICATION")
print("=" * 72)


# ---------------------------------------------------------------------
# A. Constants
# ---------------------------------------------------------------------

check(SOURCE == "LOCAL_PROJECT", "source is LOCAL_PROJECT")
check(EXTERNAL is False, "external provenance is false")
check(MIN_TREND_SAMPLES == 5, "minimum trend sample count is five")

expected_metrics = {
    "health",
    "cpu_percent",
    "temperature_c",
    "latency_ms",
    "packet_loss_percent",
    "signal_strength",
}

check(
    set(SUPPORTED_METRICS) == expected_metrics,
    "supported metrics match historical telemetry schema",
)


# ---------------------------------------------------------------------
# B. Exact linear regression
# ---------------------------------------------------------------------

slope, intercept, r2 = linear_regression([40, 50, 60, 70, 80])

check(approx(slope, 10.0), "increasing regression slope = 10")
check(approx(intercept, 40.0), "increasing intercept = 40")
check(approx(r2, 1.0), "perfect increasing sequence R² = 1")

slope, intercept, r2 = linear_regression([90, 80, 70, 60, 50])

check(approx(slope, -10.0), "decreasing regression slope = -10")
check(approx(intercept, 90.0), "decreasing intercept = 90")
check(approx(r2, 1.0), "perfect decreasing sequence R² = 1")

slope, intercept, r2 = linear_regression([50, 50, 50, 50, 50])

check(approx(slope, 0.0), "flat regression slope = 0")
check(approx(intercept, 50.0), "flat intercept = 50")
check(approx(r2, 1.0), "perfect flat sequence R² = 1")


# ---------------------------------------------------------------------
# C. Required deterministic classifications
# ---------------------------------------------------------------------

stable = analyze_trend(
    "cpu_percent",
    [50, 50, 51, 50, 49],
)

check(
    stable["trend"] == TREND_STABLE,
    "50,50,51,50,49 -> STABLE",
)
check(
    abs(stable["normalized_slope"]) <= 0.01,
    "stable normalized slope within threshold",
)
check(stable["sample_count"] == 5, "stable sample count retained")


increasing = analyze_trend(
    "cpu_percent",
    [40, 50, 60, 70, 80],
)

check(
    increasing["trend"] == TREND_INCREASING,
    "40,50,60,70,80 -> INCREASING",
)
check(increasing["slope"] > 0, "increasing trend has positive slope")
check(approx(increasing["slope"], 10.0), "increasing slope = 10")
check(
    approx(increasing["confidence"], 1.0),
    "perfect increasing trend confidence = 1",
)


decreasing = analyze_trend(
    "cpu_percent",
    [90, 80, 70, 60, 50],
)

check(
    decreasing["trend"] == TREND_DECREASING,
    "90,80,70,60,50 -> DECREASING",
)
check(decreasing["slope"] < 0, "decreasing trend has negative slope")
check(approx(decreasing["slope"], -10.0), "decreasing slope = -10")
check(
    approx(decreasing["confidence"], 1.0),
    "perfect decreasing trend confidence = 1",
)


# ---------------------------------------------------------------------
# D. Projection
# ---------------------------------------------------------------------

projection = analyze_trend(
    "latency_ms",
    [100, 110, 120, 130, 140],
    projection_steps=3,
)

# Regression:
# x=0 -> 100
# x=4 -> 140
# projection x=7 -> 170
check(
    approx(projection["projected_value"], 170.0),
    "three-step projection produces 170",
)
check(
    projection["projection_steps"] == 3,
    "projection horizon retained",
)
check(
    projection["current_value"] == 140,
    "current value is newest sample",
)
check(
    "not a guaranteed" in projection["projection_notice"],
    "projection limitation explicitly stated",
)


# ---------------------------------------------------------------------
# E. Scale-aware classification
# ---------------------------------------------------------------------

small_change_large_metric = [1000, 1002, 1004, 1006, 1008]
slope, _, _ = linear_regression(small_change_large_metric)

check(
    classify_trend(slope, small_change_large_metric) == TREND_STABLE,
    "small relative change on large metric -> STABLE",
)

strong_change = [10, 20, 30, 40, 50]
slope, _, _ = linear_regression(strong_change)

check(
    classify_trend(slope, strong_change) == TREND_INCREASING,
    "strong relative positive change -> INCREASING",
)

check(
    normalized_slope(0.0, [0, 0, 0, 0, 0]) == 0.0,
    "zero slope on zero-valued series handled safely",
)


# ---------------------------------------------------------------------
# F. Numeric cleanup
# ---------------------------------------------------------------------

numeric_strings = analyze_trend(
    "temperature_c",
    ["20", "25", "30", "35", "40"],
)

check(
    numeric_strings["trend"] == TREND_INCREASING,
    "numeric strings accepted",
)

with_missing = analyze_trend(
    "latency_ms",
    [100, None, 120, 130, 140, 150],
)

check(
    with_missing["sample_count"] == 5,
    "None sample ignored safely",
)
check(
    with_missing["trend"] == TREND_INCREASING,
    "trend still calculated after missing sample removal",
)


# ---------------------------------------------------------------------
# G. Validation
# ---------------------------------------------------------------------

expect_exception(
    lambda: analyze_trend(
        "not_a_metric",
        [1, 2, 3, 4, 5],
    ),
    ValueError,
    "unsupported metric rejected",
)

expect_exception(
    lambda: analyze_trend(
        "cpu_percent",
        [1, 2, 3],
    ),
    ValueError,
    "insufficient samples rejected",
)

expect_exception(
    lambda: analyze_trend(
        "cpu_percent",
        [1, 2, 3, 4, 5],
        projection_steps=0,
    ),
    ValueError,
    "invalid projection horizon rejected",
)

expect_exception(
    lambda: classify_trend(
        1,
        [1, 2, 3, 4, 5],
        stable_slope_ratio=-1,
    ),
    ValueError,
    "negative stability threshold rejected",
)

expect_exception(
    lambda: linear_regression([1]),
    ValueError,
    "regression requires at least two samples",
)


# ---------------------------------------------------------------------
# H. Asset-level deterministic analysis
# ---------------------------------------------------------------------

history = [
    {
        "health": 90,
        "cpu_percent": 40,
        "temperature_c": 50,
        "latency_ms": 90,
        "packet_loss_percent": 2,
        "signal_strength": 70,
    },
    {
        "health": 80,
        "cpu_percent": 50,
        "temperature_c": 50,
        "latency_ms": 80,
        "packet_loss_percent": 2,
        "signal_strength": 70,
    },
    {
        "health": 70,
        "cpu_percent": 60,
        "temperature_c": 51,
        "latency_ms": 70,
        "packet_loss_percent": 2,
        "signal_strength": 70,
    },
    {
        "health": 60,
        "cpu_percent": 70,
        "temperature_c": 50,
        "latency_ms": 60,
        "packet_loss_percent": 2,
        "signal_strength": 70,
    },
    {
        "health": 50,
        "cpu_percent": 80,
        "temperature_c": 49,
        "latency_ms": 50,
        "packet_loss_percent": 2,
        "signal_strength": 70,
    },
]

asset = analyze_asset_trends(
    asset_id=17,
    history=history,
)

check(asset["asset_id"] == 17, "asset ID retained")
check(asset["metrics_checked"] == 6, "all six metrics analysed")
check(asset["source"] == "LOCAL_PROJECT", "asset provenance retained")
check(asset["external"] is False, "asset external=false")

check(
    asset["increasing_count"] == 1,
    "asset has one increasing metric",
)

check(
    asset["decreasing_count"] == 2,
    "asset has two decreasing metrics",
)

check(
    asset["stable_count"] == 3,
    "asset has three stable metrics",
)

check(
    "cpu_percent" in asset["changing_metrics"],
    "CPU listed as changing",
)

check(
    "health" in asset["changing_metrics"],
    "health listed as changing",
)

check(
    "latency_ms" in asset["changing_metrics"],
    "latency listed as changing",
)

check(
    len(asset["skipped_metrics"]) == 0,
    "complete asset history skips no metrics",
)

check(
    bool(asset["evaluated_at"]),
    "asset evaluation timestamp generated",
)


# ---------------------------------------------------------------------
# I. Partial asset history
# ---------------------------------------------------------------------

partial_history = [
    {
        "health": 90,
        "cpu_percent": 40,
        "temperature_c": None,
        "latency_ms": 100,
        "packet_loss_percent": 1,
        "signal_strength": 80,
    },
    {
        "health": 80,
        "cpu_percent": 50,
        "temperature_c": None,
        "latency_ms": 110,
        "packet_loss_percent": 1,
        "signal_strength": 80,
    },
    {
        "health": 70,
        "cpu_percent": 60,
        "temperature_c": None,
        "latency_ms": 120,
        "packet_loss_percent": 1,
        "signal_strength": 80,
    },
    {
        "health": 60,
        "cpu_percent": 70,
        "temperature_c": None,
        "latency_ms": 130,
        "packet_loss_percent": 1,
        "signal_strength": 80,
    },
    {
        "health": 50,
        "cpu_percent": 80,
        "temperature_c": 30,
        "latency_ms": 140,
        "packet_loss_percent": 1,
        "signal_strength": 80,
    },
]

partial = analyze_asset_trends(
    asset_id=3,
    history=partial_history,
)

check(
    partial["metrics_checked"] == 5,
    "metric with insufficient history skipped",
)

check(
    any(
        item["metric"] == "temperature_c"
        for item in partial["skipped_metrics"]
    ),
    "skipped temperature metric explained",
)


# ---------------------------------------------------------------------
# J. Provenance on every metric result
# ---------------------------------------------------------------------

check(
    all(item["source"] == "LOCAL_PROJECT" for item in asset["trends"]),
    "every trend result uses LOCAL_PROJECT",
)

check(
    all(item["external"] is False for item in asset["trends"]),
    "every trend result uses external=false",
)

check(
    all(0.0 <= item["confidence"] <= 1.0 for item in asset["trends"]),
    "all confidence values bounded 0..1",
)


# ---------------------------------------------------------------------
# RESULT
# ---------------------------------------------------------------------

print()
print("=" * 72)
print("PHASE 7.0B RESULT")
print(f"Passed: {passed}")
print(f"Failed: {failed}")

if failed == 0:
    print("✅ Phase 7.0B predictive trend verification PASSED")
    print("=" * 72)
    sys.exit(0)

print("❌ Phase 7.0B predictive trend verification FAILED")
print("=" * 72)
sys.exit(1)
