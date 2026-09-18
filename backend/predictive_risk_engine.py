"""
GeoInfra Phase 7.0C
Predictive Operational Risk Engine

Combines deterministic anomaly, trend, and optional health context into an
explainable operational-risk score.

This module is intentionally:
- deterministic
- API-independent
- database-independent
- explainable
- local-project only

The score is an operational prioritisation heuristic. It is not a guaranteed
prediction of failure, damage, outage, or future behaviour.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence


SOURCE = "LOCAL_PROJECT"
EXTERNAL = False

MIN_SCORE = 0.0
MAX_SCORE = 100.0

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_CRITICAL = "CRITICAL"

RISK_LEVELS = (
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
)

# Explicit deterministic score boundaries.
MEDIUM_THRESHOLD = 25.0
HIGH_THRESHOLD = 50.0
CRITICAL_THRESHOLD = 75.0

# Anomaly contribution is intentionally the largest single component.
ANOMALY_WEIGHTS = {
    "NONE": 0.0,
    "LOW": 10.0,
    "MEDIUM": 25.0,
    "HIGH": 40.0,
    "CRITICAL": 55.0,
}

# Trend contribution represents predictive direction.
#
# Whether INCREASING or DECREASING is harmful depends on the metric.
# For example:
#   CPU / latency / packet loss / temperature:
#       increasing is normally worsening
#
#   health / signal strength:
#       decreasing is normally worsening
TREND_WORSENING_WEIGHT = 25.0
TREND_STABLE_WEIGHT = 0.0
TREND_IMPROVING_WEIGHT = -5.0

# Optional current-health contribution.
HEALTH_CRITICAL_THRESHOLD = 40.0
HEALTH_HIGH_THRESHOLD = 60.0
HEALTH_MEDIUM_THRESHOLD = 80.0

HEALTH_CRITICAL_WEIGHT = 20.0
HEALTH_HIGH_WEIGHT = 15.0
HEALTH_MEDIUM_WEIGHT = 8.0
HEALTH_GOOD_WEIGHT = 0.0

HIGHER_IS_WORSE_METRICS = {
    "cpu_percent",
    "temperature_c",
    "latency_ms",
    "packet_loss_percent",
}

LOWER_IS_WORSE_METRICS = {
    "health",
    "signal_strength",
}

SUPPORTED_METRICS = (
    "health",
    "cpu_percent",
    "temperature_c",
    "latency_ms",
    "packet_loss_percent",
    "signal_strength",
)

VALID_TRENDS = {
    "STABLE",
    "INCREASING",
    "DECREASING",
}

EPSILON = 1e-9


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def clamp_score(value: Any) -> float:
    """
    Clamp a numeric score into the inclusive 0..100 range.
    """

    number = _as_float(value)

    if number is None:
        return MIN_SCORE

    return max(MIN_SCORE, min(MAX_SCORE, number))


def classify_risk(score: Any) -> str:
    """
    Convert a numeric score into a deterministic risk level.

        0 <= score < 25   -> LOW
       25 <= score < 50   -> MEDIUM
       50 <= score < 75   -> HIGH
       75 <= score <= 100 -> CRITICAL
    """

    number = clamp_score(score)

    if number >= CRITICAL_THRESHOLD:
        return RISK_CRITICAL

    if number >= HIGH_THRESHOLD:
        return RISK_HIGH

    if number >= MEDIUM_THRESHOLD:
        return RISK_MEDIUM

    return RISK_LOW


def normalize_anomaly_severity(value: Any) -> str:
    """
    Normalize anomaly severity into the Phase 7.0C scoring vocabulary.
    """

    if value is None:
        return "NONE"

    severity = str(value).strip().upper()

    aliases = {
        "NORMAL": "NONE",
        "OK": "NONE",
        "INFO": "LOW",
        "WARNING": "MEDIUM",
        "WARN": "MEDIUM",
        "SEVERE": "HIGH",
    }

    severity = aliases.get(severity, severity)

    if severity not in ANOMALY_WEIGHTS:
        return "NONE"

    return severity


def anomaly_contribution(severity: Any) -> dict[str, Any]:
    """
    Return deterministic anomaly contribution.
    """

    normalized = normalize_anomaly_severity(severity)
    points = ANOMALY_WEIGHTS[normalized]

    return {
        "severity": normalized,
        "points": points,
        "reason": (
            f"Anomaly severity {normalized} contributes "
            f"{points:.1f} risk points."
        ),
    }


def trend_direction_for_metric(
    metric: str,
    trend: Any,
) -> str:
    """
    Interpret raw trend direction in operational-risk terms.

    Returns:
        WORSENING
        IMPROVING
        STABLE
        UNKNOWN
    """

    if metric not in SUPPORTED_METRICS:
        return "UNKNOWN"

    normalized = str(trend or "").strip().upper()

    if normalized not in VALID_TRENDS:
        return "UNKNOWN"

    if normalized == "STABLE":
        return "STABLE"

    if metric in HIGHER_IS_WORSE_METRICS:
        if normalized == "INCREASING":
            return "WORSENING"
        return "IMPROVING"

    if metric in LOWER_IS_WORSE_METRICS:
        if normalized == "DECREASING":
            return "WORSENING"
        return "IMPROVING"

    return "UNKNOWN"


def trend_contribution(
    metric: str,
    trend: Any,
) -> dict[str, Any]:
    """
    Convert a raw metric trend into deterministic risk points.
    """

    raw_trend = str(trend or "UNKNOWN").strip().upper()

    direction = trend_direction_for_metric(
        metric,
        raw_trend,
    )

    if direction == "WORSENING":
        points = TREND_WORSENING_WEIGHT

    elif direction == "IMPROVING":
        points = TREND_IMPROVING_WEIGHT

    else:
        points = TREND_STABLE_WEIGHT

    return {
        "metric": metric,
        "trend": raw_trend,
        "direction": direction,
        "points": points,
        "reason": (
            f"{metric} trend {raw_trend} is interpreted as "
            f"{direction} and contributes {points:+.1f} risk points."
        ),
    }


def health_contribution(
    health: Any,
) -> dict[str, Any]:
    """
    Convert optional 0..100 health into risk points.

    Missing health contributes zero points rather than fabricating risk.
    """

    value = _as_float(health)

    if value is None:
        return {
            "health": None,
            "band": "UNKNOWN",
            "points": 0.0,
            "reason": (
                "Current health is unavailable; "
                "no health risk points were added."
            ),
        }

    value = max(0.0, min(100.0, value))

    if value < HEALTH_CRITICAL_THRESHOLD:
        band = "CRITICAL"
        points = HEALTH_CRITICAL_WEIGHT

    elif value < HEALTH_HIGH_THRESHOLD:
        band = "HIGH"
        points = HEALTH_HIGH_WEIGHT

    elif value < HEALTH_MEDIUM_THRESHOLD:
        band = "MEDIUM"
        points = HEALTH_MEDIUM_WEIGHT

    else:
        band = "GOOD"
        points = HEALTH_GOOD_WEIGHT

    return {
        "health": value,
        "band": band,
        "points": points,
        "reason": (
            f"Current health {value:.1f} is in the {band} band "
            f"and contributes {points:.1f} risk points."
        ),
    }


def _extract_anomaly_severity(
    anomaly: Optional[Mapping[str, Any]],
) -> Any:
    if not anomaly:
        return None

    for key in (
        "severity",
        "anomaly_severity",
        "risk_level",
        "level",
    ):
        if anomaly.get(key) is not None:
            return anomaly.get(key)

    return None


def _extract_trend(
    trend: Optional[Mapping[str, Any]],
) -> Any:
    if not trend:
        return None

    for key in (
        "trend",
        "direction",
        "trend_direction",
    ):
        if trend.get(key) is not None:
            return trend.get(key)

    return None


def score_metric_risk(
    metric: str,
    *,
    anomaly: Optional[Mapping[str, Any]] = None,
    trend: Optional[Mapping[str, Any]] = None,
    current_health: Any = None,
) -> dict[str, Any]:
    """
    Score operational risk for one metric.

    Formula:

        raw_score =
            anomaly_points
            + trend_points
            + health_points

        final_score = clamp(raw_score, 0, 100)

    Missing evidence contributes zero points and is explicitly reported.
    """

    if metric not in SUPPORTED_METRICS:
        raise ValueError(f"Unsupported metric: {metric}")

    anomaly_severity = _extract_anomaly_severity(anomaly)
    raw_trend = _extract_trend(trend)

    anomaly_result = anomaly_contribution(
        anomaly_severity,
    )

    trend_result = trend_contribution(
        metric,
        raw_trend,
    )

    health_result = health_contribution(
        current_health,
    )

    raw_score = (
        anomaly_result["points"]
        + trend_result["points"]
        + health_result["points"]
    )

    score = clamp_score(raw_score)
    risk_level = classify_risk(score)

    evidence_available = {
        "anomaly": anomaly is not None,
        "trend": trend is not None,
        "health": _as_float(current_health) is not None,
    }

    missing_data = [
        name
        for name, available in evidence_available.items()
        if not available
    ]

    factors = [
        anomaly_result,
        trend_result,
        health_result,
    ]

    positive_factors = [
        item["reason"]
        for item in factors
        if item["points"] > 0
    ]

    mitigating_factors = [
        item["reason"]
        for item in factors
        if item["points"] < 0
    ]

    explanation_parts = [
        f"{metric} operational risk score is {score:.1f}/100 "
        f"({risk_level})."
    ]

    if positive_factors:
        explanation_parts.append(
            "Risk contributors: "
            + " ".join(positive_factors)
        )
    else:
        explanation_parts.append(
            "No positive risk contributors were detected."
        )

    if mitigating_factors:
        explanation_parts.append(
            "Mitigating evidence: "
            + " ".join(mitigating_factors)
        )

    if missing_data:
        explanation_parts.append(
            "Missing evidence: "
            + ", ".join(missing_data)
            + ". Missing evidence contributes zero points."
        )

    return {
        "metric": metric,
        "score": round(score, 2),
        "raw_score": round(raw_score, 2),
        "risk_level": risk_level,
        "components": {
            "anomaly": anomaly_result,
            "trend": trend_result,
            "health": health_result,
        },
        "evidence_available": evidence_available,
        "missing_data": missing_data,
        "explanation": " ".join(explanation_parts),
        "source": SOURCE,
        "external": EXTERNAL,
        "evaluated_at": utc_now_iso(),
        "prediction_notice": (
            "Operational prioritisation heuristic based on available "
            "local telemetry evidence; not a guaranteed future prediction."
        ),
    }


def score_asset_risk(
    asset_id: int,
    metric_inputs: Sequence[Mapping[str, Any]],
    *,
    current_health: Any = None,
) -> dict[str, Any]:
    """
    Aggregate metric-level predictive risk for one asset.

    Asset score uses the maximum metric score. This intentionally prevents
    one severe metric from being hidden by averaging it with healthy metrics.

    The returned result remains explainable because every metric score and
    component is retained.
    """

    try:
        normalized_asset_id = int(asset_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "asset_id must be a positive integer"
        ) from exc

    if normalized_asset_id <= 0:
        raise ValueError(
            "asset_id must be a positive integer"
        )

    results: list[dict[str, Any]] = []

    for item in metric_inputs:
        metric = item.get("metric")

        if metric not in SUPPORTED_METRICS:
            continue

        results.append(
            score_metric_risk(
                metric,
                anomaly=item.get("anomaly"),
                trend=item.get("trend"),
                current_health=current_health,
            )
        )

    if results:
        score = max(
            result["score"]
            for result in results
        )
    else:
        score = 0.0

    risk_level = classify_risk(score)

    highest_risk_metrics = [
        result["metric"]
        for result in results
        if abs(result["score"] - score) <= EPSILON
    ]

    missing_evidence_count = sum(
        len(result["missing_data"])
        for result in results
    )

    explanation = (
        f"Asset {normalized_asset_id} operational risk is "
        f"{score:.1f}/100 ({risk_level}). "
        "Asset risk uses the highest metric risk so a severe local "
        "signal is not hidden by averaging."
    )

    if highest_risk_metrics:
        explanation += (
            " Highest-risk metric(s): "
            + ", ".join(highest_risk_metrics)
            + "."
        )

    if not results:
        explanation += (
            " No supported metric evidence was available, "
            "so the score defaults to 0."
        )

    return {
        "asset_id": normalized_asset_id,
        "score": round(score, 2),
        "risk_level": risk_level,
        "metrics_checked": len(results),
        "highest_risk_metrics": highest_risk_metrics,
        "missing_evidence_count": missing_evidence_count,
        "metric_risks": results,
        "explanation": explanation,
        "source": SOURCE,
        "external": EXTERNAL,
        "evaluated_at": utc_now_iso(),
        "prediction_notice": (
            "Operational prioritisation heuristic based on available "
            "local telemetry evidence; not a guaranteed future prediction."
        ),
    }


# Compatibility aliases for later integration work.
calculate_metric_risk = score_metric_risk
calculate_asset_risk = score_asset_risk
