#!/usr/bin/env python3

"""
GeoInfra Phase 7.0C Verification

Deterministically verifies:
- score boundaries
- score clamping
- anomaly contribution
- trend direction
- health contribution
- missing-data behaviour
- provenance
- explainability
- asset-level aggregation

No FastAPI routes or database connection are required.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from predictive_risk_engine import (  # noqa: E402
    ANOMALY_WEIGHTS,
    EXTERNAL,
    RISK_CRITICAL,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    SOURCE,
    anomaly_contribution,
    classify_risk,
    clamp_score,
    health_contribution,
    score_asset_risk,
    score_metric_risk,
    trend_contribution,
    trend_direction_for_metric,
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


def approx(actual, expected, tolerance=1e-6):
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
        print(
            f"❌ FAIL: {description} "
            "(no exception raised)"
        )


print("=" * 72)
print("GEOINFRA PHASE 7.0C — PREDICTIVE RISK VERIFICATION")
print("=" * 72)


# ---------------------------------------------------------------------
# A. Provenance constants
# ---------------------------------------------------------------------

check(
    SOURCE == "LOCAL_PROJECT",
    "source is LOCAL_PROJECT",
)

check(
    EXTERNAL is False,
    "external provenance is false",
)


# ---------------------------------------------------------------------
# B. Score clamping
# ---------------------------------------------------------------------

check(
    approx(clamp_score(-50), 0),
    "negative score clamps to 0",
)

check(
    approx(clamp_score(0), 0),
    "zero remains zero",
)

check(
    approx(clamp_score(42.5), 42.5),
    "mid-range score retained",
)

check(
    approx(clamp_score(100), 100),
    "100 remains 100",
)

check(
    approx(clamp_score(150), 100),
    "score above 100 clamps to 100",
)

check(
    approx(clamp_score(None), 0),
    "missing numeric score safely defaults to zero",
)


# ---------------------------------------------------------------------
# C. Exact risk boundaries
# ---------------------------------------------------------------------

boundary_cases = [
    (0.0, RISK_LOW),
    (24.99, RISK_LOW),
    (25.0, RISK_MEDIUM),
    (49.99, RISK_MEDIUM),
    (50.0, RISK_HIGH),
    (74.99, RISK_HIGH),
    (75.0, RISK_CRITICAL),
    (100.0, RISK_CRITICAL),
]

for score, expected in boundary_cases:
    check(
        classify_risk(score) == expected,
        f"score {score} -> {expected}",
    )


# ---------------------------------------------------------------------
# D. Anomaly contribution
# ---------------------------------------------------------------------

expected_anomaly_points = {
    "NONE": 0.0,
    "LOW": 10.0,
    "MEDIUM": 25.0,
    "HIGH": 40.0,
    "CRITICAL": 55.0,
}

check(
    ANOMALY_WEIGHTS == expected_anomaly_points,
    "anomaly scoring weights are deterministic",
)

for severity, expected_points in expected_anomaly_points.items():
    result = anomaly_contribution(severity)

    check(
        approx(result["points"], expected_points),
        f"{severity} anomaly contributes {expected_points} points",
    )

check(
    anomaly_contribution("warning")["severity"] == "MEDIUM",
    "WARNING anomaly alias normalizes to MEDIUM",
)

check(
    anomaly_contribution(None)["severity"] == "NONE",
    "missing anomaly normalizes to NONE",
)


# ---------------------------------------------------------------------
# E. Trend direction
# ---------------------------------------------------------------------

check(
    trend_direction_for_metric(
        "cpu_percent",
        "INCREASING",
    ) == "WORSENING",
    "increasing CPU is worsening",
)

check(
    trend_direction_for_metric(
        "cpu_percent",
        "DECREASING",
    ) == "IMPROVING",
    "decreasing CPU is improving",
)

check(
    trend_direction_for_metric(
        "latency_ms",
        "INCREASING",
    ) == "WORSENING",
    "increasing latency is worsening",
)

check(
    trend_direction_for_metric(
        "packet_loss_percent",
        "INCREASING",
    ) == "WORSENING",
    "increasing packet loss is worsening",
)

check(
    trend_direction_for_metric(
        "health",
        "DECREASING",
    ) == "WORSENING",
    "decreasing health is worsening",
)

check(
    trend_direction_for_metric(
        "health",
        "INCREASING",
    ) == "IMPROVING",
    "increasing health is improving",
)

check(
    trend_direction_for_metric(
        "signal_strength",
        "DECREASING",
    ) == "WORSENING",
    "decreasing signal strength is worsening",
)

check(
    trend_direction_for_metric(
        "temperature_c",
        "STABLE",
    ) == "STABLE",
    "stable temperature remains stable",
)

check(
    trend_direction_for_metric(
        "not_a_metric",
        "INCREASING",
    ) == "UNKNOWN",
    "unknown metric trend direction is UNKNOWN",
)


# ---------------------------------------------------------------------
# F. Trend contribution points
# ---------------------------------------------------------------------

worsening = trend_contribution(
    "cpu_percent",
    "INCREASING",
)

improving = trend_contribution(
    "cpu_percent",
    "DECREASING",
)

stable = trend_contribution(
    "cpu_percent",
    "STABLE",
)

check(
    approx(worsening["points"], 25),
    "worsening trend adds 25 points",
)

check(
    approx(improving["points"], -5),
    "improving trend removes 5 points",
)

check(
    approx(stable["points"], 0),
    "stable trend adds zero points",
)


# ---------------------------------------------------------------------
# G. Health contribution
# ---------------------------------------------------------------------

check(
    approx(health_contribution(90)["points"], 0),
    "healthy current state adds zero points",
)

check(
    approx(health_contribution(70)["points"], 8),
    "medium health band adds 8 points",
)

check(
    approx(health_contribution(50)["points"], 15),
    "high health-risk band adds 15 points",
)

check(
    approx(health_contribution(30)["points"], 20),
    "critical health-risk band adds 20 points",
)

check(
    approx(health_contribution(None)["points"], 0),
    "missing health adds zero points",
)


# ---------------------------------------------------------------------
# H. Deterministic metric scores
# ---------------------------------------------------------------------

low = score_metric_risk(
    "cpu_percent",
    anomaly={"severity": "NONE"},
    trend={"trend": "STABLE"},
    current_health=95,
)

check(
    approx(low["score"], 0),
    "normal stable healthy metric scores 0",
)

check(
    low["risk_level"] == RISK_LOW,
    "normal stable healthy metric is LOW",
)


medium = score_metric_risk(
    "cpu_percent",
    anomaly={"severity": "MEDIUM"},
    trend={"trend": "STABLE"},
    current_health=95,
)

check(
    approx(medium["score"], 25),
    "medium anomaly alone scores 25",
)

check(
    medium["risk_level"] == RISK_MEDIUM,
    "score 25 classified MEDIUM",
)


high = score_metric_risk(
    "cpu_percent",
    anomaly={"severity": "MEDIUM"},
    trend={"trend": "INCREASING"},
    current_health=95,
)

check(
    approx(high["score"], 50),
    "medium anomaly plus worsening trend scores 50",
)

check(
    high["risk_level"] == RISK_HIGH,
    "score 50 classified HIGH",
)


critical = score_metric_risk(
    "latency_ms",
    anomaly={"severity": "HIGH"},
    trend={"trend": "INCREASING"},
    current_health=50,
)

# 40 anomaly + 25 worsening + 15 health = 80
check(
    approx(critical["score"], 80),
    "high anomaly + worsening trend + poor health scores 80",
)

check(
    critical["risk_level"] == RISK_CRITICAL,
    "score 80 classified CRITICAL",
)


# ---------------------------------------------------------------------
# I. Anomaly contribution changes score deterministically
# ---------------------------------------------------------------------

without_anomaly = score_metric_risk(
    "cpu_percent",
    anomaly={"severity": "NONE"},
    trend={"trend": "INCREASING"},
    current_health=90,
)

with_anomaly = score_metric_risk(
    "cpu_percent",
    anomaly={"severity": "HIGH"},
    trend={"trend": "INCREASING"},
    current_health=90,
)

check(
    approx(
        with_anomaly["score"] - without_anomaly["score"],
        40,
    ),
    "HIGH anomaly adds exactly 40 risk points",
)


# ---------------------------------------------------------------------
# J. Trend direction changes score
# ---------------------------------------------------------------------

cpu_worsening = score_metric_risk(
    "cpu_percent",
    anomaly={"severity": "MEDIUM"},
    trend={"trend": "INCREASING"},
    current_health=90,
)

cpu_improving = score_metric_risk(
    "cpu_percent",
    anomaly={"severity": "MEDIUM"},
    trend={"trend": "DECREASING"},
    current_health=90,
)

check(
    cpu_worsening["score"] > cpu_improving["score"],
    "worsening CPU scores above improving CPU",
)


health_worsening = score_metric_risk(
    "health",
    anomaly={"severity": "MEDIUM"},
    trend={"trend": "DECREASING"},
    current_health=90,
)

health_improving = score_metric_risk(
    "health",
    anomaly={"severity": "MEDIUM"},
    trend={"trend": "INCREASING"},
    current_health=90,
)

check(
    health_worsening["score"] > health_improving["score"],
    "decreasing health scores above improving health",
)


# ---------------------------------------------------------------------
# K. Missing data
# ---------------------------------------------------------------------

missing_all = score_metric_risk(
    "cpu_percent",
)

check(
    approx(missing_all["score"], 0),
    "all missing evidence defaults to score zero",
)

check(
    missing_all["risk_level"] == RISK_LOW,
    "all missing evidence defaults to LOW",
)

check(
    set(missing_all["missing_data"])
    == {"anomaly", "trend", "health"},
    "all missing evidence is explicitly listed",
)

check(
    "Missing evidence" in missing_all["explanation"],
    "missing evidence appears in explanation",
)


missing_health = score_metric_risk(
    "cpu_percent",
    anomaly={"severity": "HIGH"},
    trend={"trend": "INCREASING"},
)

check(
    "health" in missing_health["missing_data"],
    "missing health is reported",
)

check(
    approx(missing_health["score"], 65),
    "missing health adds zero rather than fabricated points",
)


# ---------------------------------------------------------------------
# L. Score floor with mitigating trend
# ---------------------------------------------------------------------

improving_only = score_metric_risk(
    "cpu_percent",
    anomaly={"severity": "NONE"},
    trend={"trend": "DECREASING"},
    current_health=95,
)

check(
    approx(improving_only["raw_score"], -5),
    "improving-only raw score records mitigation",
)

check(
    approx(improving_only["score"], 0),
    "negative final risk clamps to zero",
)


# ---------------------------------------------------------------------
# M. Provenance
# ---------------------------------------------------------------------

check(
    critical["source"] == "LOCAL_PROJECT",
    "metric risk source is LOCAL_PROJECT",
)

check(
    critical["external"] is False,
    "metric risk external=false",
)

check(
    bool(critical["evaluated_at"]),
    "metric risk includes evaluation timestamp",
)

check(
    "not a guaranteed" in critical["prediction_notice"],
    "metric result contains prediction limitation",
)


# ---------------------------------------------------------------------
# N. Explainability
# ---------------------------------------------------------------------

check(
    isinstance(critical["components"], dict),
    "component breakdown is present",
)

check(
    set(critical["components"])
    == {"anomaly", "trend", "health"},
    "all three risk components are exposed",
)

check(
    approx(
        critical["components"]["anomaly"]["points"],
        40,
    ),
    "anomaly component exposes exact contribution",
)

check(
    approx(
        critical["components"]["trend"]["points"],
        25,
    ),
    "trend component exposes exact contribution",
)

check(
    approx(
        critical["components"]["health"]["points"],
        15,
    ),
    "health component exposes exact contribution",
)

check(
    "80.0/100" in critical["explanation"],
    "explanation contains final score",
)

check(
    "CRITICAL" in critical["explanation"],
    "explanation contains risk level",
)

check(
    "Risk contributors" in critical["explanation"],
    "explanation identifies risk contributors",
)


# ---------------------------------------------------------------------
# O. Asset aggregation
# ---------------------------------------------------------------------

asset = score_asset_risk(
    17,
    [
        {
            "metric": "cpu_percent",
            "anomaly": {"severity": "MEDIUM"},
            "trend": {"trend": "INCREASING"},
        },
        {
            "metric": "latency_ms",
            "anomaly": {"severity": "HIGH"},
            "trend": {"trend": "INCREASING"},
        },
        {
            "metric": "packet_loss_percent",
            "anomaly": {"severity": "NONE"},
            "trend": {"trend": "STABLE"},
        },
    ],
    current_health=50,
)

# CPU: 25 + 25 + 15 = 65
# Latency: 40 + 25 + 15 = 80
# Packet loss: 0 + 0 + 15 = 15
# Asset = maximum = 80
check(
    asset["asset_id"] == 17,
    "asset ID retained",
)

check(
    approx(asset["score"], 80),
    "asset risk uses highest metric score",
)

check(
    asset["risk_level"] == RISK_CRITICAL,
    "asset score 80 is CRITICAL",
)

check(
    asset["metrics_checked"] == 3,
    "asset reports number of metrics checked",
)

check(
    asset["highest_risk_metrics"] == ["latency_ms"],
    "highest-risk metric identified",
)

check(
    len(asset["metric_risks"]) == 3,
    "metric-level explanations retained",
)

check(
    asset["source"] == "LOCAL_PROJECT",
    "asset source is LOCAL_PROJECT",
)

check(
    asset["external"] is False,
    "asset external=false",
)

check(
    "highest metric risk" in asset["explanation"],
    "asset aggregation method is explained",
)


# ---------------------------------------------------------------------
# P. Empty and unsupported evidence
# ---------------------------------------------------------------------

empty_asset = score_asset_risk(
    3,
    [],
)

check(
    approx(empty_asset["score"], 0),
    "empty asset evidence scores zero",
)

check(
    empty_asset["risk_level"] == RISK_LOW,
    "empty asset evidence is LOW",
)

check(
    empty_asset["metrics_checked"] == 0,
    "empty asset checks zero metrics",
)

check(
    "No supported metric evidence" in empty_asset["explanation"],
    "empty asset behaviour is explained",
)


unsupported_only = score_asset_risk(
    4,
    [
        {
            "metric": "unsupported_metric",
            "anomaly": {"severity": "CRITICAL"},
            "trend": {"trend": "INCREASING"},
        }
    ],
)

check(
    unsupported_only["metrics_checked"] == 0,
    "unsupported asset metric is ignored safely",
)

expect_exception(
    lambda: score_metric_risk(
        "unsupported_metric",
        anomaly={"severity": "HIGH"},
    ),
    ValueError,
    "unsupported direct metric rejected",
)

expect_exception(
    lambda: score_asset_risk(
        0,
        [],
    ),
    ValueError,
    "non-positive asset ID rejected",
)


# ---------------------------------------------------------------------
# RESULT
# ---------------------------------------------------------------------

print()
print("=" * 72)
print("PHASE 7.0C RESULT")
print(f"Passed: {passed}")
print(f"Failed: {failed}")

if failed == 0:
    print(
        "✅ Phase 7.0C predictive operational risk "
        "verification PASSED"
    )
    print("=" * 72)
    sys.exit(0)

print(
    "❌ Phase 7.0C predictive operational risk "
    "verification FAILED"
)
print("=" * 72)
sys.exit(1)
