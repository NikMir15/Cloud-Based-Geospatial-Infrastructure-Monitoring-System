#!/usr/bin/env python3

"""
GeoInfra Phase 7.0A Verification

Deterministically verifies:
- supported telemetry metrics
- Z-score calculation
- deviation calculation
- NORMAL/WATCH/ANOMALOUS/CRITICAL classification
- zero-variance handling
- insufficient-data handling
- asset-level aggregation
- provenance
- anomaly-event persistence payload generation

This verifier does not require FastAPI routes.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from anomaly_engine import (  # noqa: E402
    EXTERNAL,
    MIN_BASELINE_SAMPLES,
    SOURCE,
    SUPPORTED_METRICS,
    analyze_asset,
    analyze_metric,
    build_anomaly_event_rows,
    classify_z_score,
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


def approx(actual, expected, tolerance=1e-4):
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
print("GEOINFRA PHASE 7.0A — ANOMALY ENGINE VERIFICATION")
print("=" * 72)


# ---------------------------------------------------------------------
# A. Constants / provenance
# ---------------------------------------------------------------------

check(SOURCE == "LOCAL_PROJECT", "source is LOCAL_PROJECT")
check(EXTERNAL is False, "external provenance is false")
check(MIN_BASELINE_SAMPLES == 5, "minimum baseline is five samples")

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
    "supported metrics match sensor_telemetry_history",
)


# ---------------------------------------------------------------------
# B. Classification boundaries
# ---------------------------------------------------------------------

check(classify_z_score(0.0) == "NORMAL", "Z=0.0 -> NORMAL")
check(classify_z_score(1.49) == "NORMAL", "Z=1.49 -> NORMAL")
check(classify_z_score(1.50) == "WATCH", "Z=1.50 -> WATCH")
check(classify_z_score(-1.50) == "WATCH", "negative Z uses magnitude")
check(classify_z_score(1.99) == "WATCH", "Z=1.99 -> WATCH")
check(classify_z_score(2.00) == "ANOMALOUS", "Z=2.00 -> ANOMALOUS")
check(classify_z_score(2.99) == "ANOMALOUS", "Z=2.99 -> ANOMALOUS")
check(classify_z_score(3.00) == "CRITICAL", "Z=3.00 -> CRITICAL")
check(classify_z_score(-5.0) == "CRITICAL", "large negative Z -> CRITICAL")


# ---------------------------------------------------------------------
# C. Deterministic metric calculations
# ---------------------------------------------------------------------

baseline = [40, 45, 50, 55, 60]

normal = analyze_metric("cpu_percent", 50, baseline)

check(normal["metric"] == "cpu_percent", "metric name retained")
check(approx(normal["baseline_mean"], 50.0), "baseline mean = 50")
check(approx(normal["deviation"], 0.0), "normal deviation = 0")
check(approx(normal["z_score"], 0.0), "normal Z-score = 0")
check(normal["status"] == "NORMAL", "baseline-centre value -> NORMAL")
check(normal["sample_count"] == 5, "sample count retained")

# Population standard deviation of [40,45,50,55,60] is sqrt(50).
stddev = math.sqrt(50)

watch_value = 50 + (1.75 * stddev)
watch = analyze_metric("cpu_percent", watch_value, baseline)

check(approx(watch["z_score"], 1.75), "WATCH Z-score calculated")
check(watch["status"] == "WATCH", "Z=1.75 -> WATCH")

anomalous_value = 50 + (2.5 * stddev)
anomalous = analyze_metric(
    "latency_ms",
    anomalous_value,
    baseline,
)

check(
    approx(anomalous["z_score"], 2.5),
    "ANOMALOUS Z-score calculated",
)
check(
    anomalous["status"] == "ANOMALOUS",
    "Z=2.5 -> ANOMALOUS",
)

critical_value = 50 + (4.0 * stddev)
critical = analyze_metric(
    "temperature_c",
    critical_value,
    baseline,
)

check(approx(critical["z_score"], 4.0), "CRITICAL Z-score calculated")
check(critical["status"] == "CRITICAL", "Z=4 -> CRITICAL")
check(
    approx(critical["anomaly_score"], 4.0),
    "anomaly score is absolute Z-score",
)
check(
    critical["deviation_percent"] is not None,
    "deviation percentage calculated",
)


# ---------------------------------------------------------------------
# D. Downward deviations
# ---------------------------------------------------------------------

down = analyze_metric(
    "health",
    50 - (3.5 * stddev),
    baseline,
)

check(down["z_score"] < 0, "downward deviation produces negative Z")
check(
    approx(down["anomaly_score"], 3.5),
    "negative Z converted to positive anomaly score",
)
check(
    down["status"] == "CRITICAL",
    "large downward deviation -> CRITICAL",
)


# ---------------------------------------------------------------------
# E. Zero-variance handling
# ---------------------------------------------------------------------

flat_normal = analyze_metric(
    "packet_loss_percent",
    2,
    [2, 2, 2, 2, 2],
)

check(
    flat_normal["baseline_stddev"] == 0,
    "flat baseline has zero standard deviation",
)
check(flat_normal["z_score"] == 0, "unchanged flat baseline -> Z=0")
check(flat_normal["status"] == "NORMAL", "unchanged flat baseline -> NORMAL")

flat_changed = analyze_metric(
    "packet_loss_percent",
    3,
    [2, 2, 2, 2, 2],
)

check(
    flat_changed["status"] == "CRITICAL",
    "changed value outside zero-variance baseline -> CRITICAL",
)


# ---------------------------------------------------------------------
# F. Validation
# ---------------------------------------------------------------------

expect_exception(
    lambda: analyze_metric(
        "not_a_metric",
        10,
        [1, 2, 3, 4, 5],
    ),
    ValueError,
    "unsupported metric rejected",
)

expect_exception(
    lambda: analyze_metric(
        "cpu_percent",
        "bad-value",
        [1, 2, 3, 4, 5],
    ),
    ValueError,
    "non-numeric current value rejected",
)

expect_exception(
    lambda: analyze_metric(
        "cpu_percent",
        10,
        [1, 2, 3],
    ),
    ValueError,
    "insufficient baseline rejected",
)


# ---------------------------------------------------------------------
# G. Asset-level analysis
# ---------------------------------------------------------------------

history = []

for value in [40, 45, 50, 55, 60]:
    history.append(
        {
            "health": value,
            "cpu_percent": value,
            "temperature_c": value,
            "latency_ms": value,
            "packet_loss_percent": value,
            "signal_strength": value,
        }
    )

current = {
    "health": 50,
    "cpu_percent": 50,
    "temperature_c": critical_value,
    "latency_ms": anomalous_value,
    "packet_loss_percent": 50,
    "signal_strength": watch_value,
}

asset = analyze_asset(
    asset_id=17,
    current=current,
    history=history,
)

check(asset["asset_id"] == 17, "asset ID retained")
check(asset["source"] == "LOCAL_PROJECT", "asset result provenance retained")
check(asset["external"] is False, "asset result external=false")
check(asset["metrics_checked"] == 6, "all six telemetry metrics analysed")
check(asset["status"] == "CRITICAL", "overall status uses highest severity")
check(
    asset["anomaly_score"] >= 3.0,
    "overall anomaly score reflects critical metric",
)
check(
    "temperature_c" in asset["anomalous_metrics"],
    "critical temperature listed as anomalous metric",
)
check(
    "latency_ms" in asset["anomalous_metrics"],
    "anomalous latency listed",
)
check(
    "signal_strength" in asset["watch_metrics"],
    "watch signal-strength listed",
)
check(
    len(asset["skipped_metrics"]) == 0,
    "no metrics skipped with complete history",
)
check(
    bool(asset["evaluated_at"]),
    "evaluation timestamp generated",
)


# ---------------------------------------------------------------------
# H. Persistence payload
# ---------------------------------------------------------------------

event_rows = build_anomaly_event_rows(asset)

check(len(event_rows) == 3, "WATCH+ anomaly metrics produce event rows")
check(
    all(row["status"] != "NORMAL" for row in event_rows),
    "NORMAL metrics are not persisted",
)
check(
    all(row["asset_id"] == 17 for row in event_rows),
    "event rows retain asset ID",
)
check(
    all(row["source"] == "LOCAL_PROJECT" for row in event_rows),
    "event rows retain LOCAL_PROJECT provenance",
)
check(
    all(row["external"] is False for row in event_rows),
    "event rows retain external=false",
)
check(
    {row["metric"] for row in event_rows}
    == {"temperature_c", "latency_ms", "signal_strength"},
    "event rows contain expected metrics",
)


# ---------------------------------------------------------------------
# I. Partial data handling
# ---------------------------------------------------------------------

partial_current = {
    "health": 50,
    "cpu_percent": None,
    "temperature_c": 50,
    "latency_ms": 50,
    "packet_loss_percent": 50,
    "signal_strength": 50,
}

partial = analyze_asset(
    17,
    partial_current,
    history,
)

check(partial["metrics_checked"] == 5, "missing metric is skipped safely")
check(
    any(
        item["metric"] == "cpu_percent"
        for item in partial["skipped_metrics"]
    ),
    "skipped metric is explained",
)


# ---------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------

print()
print("=" * 72)
print("PHASE 7.0A RESULT")
print(f"Passed: {passed}")
print(f"Failed: {failed}")

if failed == 0:
    print("✅ Phase 7.0A anomaly engine verification PASSED")
    print("=" * 72)
    sys.exit(0)

print("❌ Phase 7.0A anomaly engine verification FAILED")
print("=" * 72)
sys.exit(1)
