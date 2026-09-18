"""
GeoInfra Phase 7.0A
Telemetry Anomaly Detection Engine

Provides explainable statistical anomaly detection for locally generated
infrastructure telemetry.

The engine is intentionally independent of FastAPI. Phase 7.0D will expose
the engine through API routes.

Provenance:
    source   = LOCAL_PROJECT
    external = False
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import fmean, pstdev
from typing import Any, Iterable, Mapping, Optional, Sequence


SOURCE = "LOCAL_PROJECT"
EXTERNAL = False

SUPPORTED_METRICS = (
    "health",
    "cpu_percent",
    "temperature_c",
    "latency_ms",
    "packet_loss_percent",
    "signal_strength",
)

# Severity is based primarily on the absolute Z-score.
#
# NORMAL     < 1.5
# WATCH      1.5 - < 2.0
# ANOMALOUS  2.0 - < 3.0
# CRITICAL   >= 3.0
Z_WATCH = 1.5
Z_ANOMALOUS = 2.0
Z_CRITICAL = 3.0

MIN_BASELINE_SAMPLES = 5
EPSILON = 1e-9


@dataclass(frozen=True)
class MetricAnalysis:
    metric: str
    current_value: float
    baseline_mean: float
    baseline_stddev: float
    deviation: float
    deviation_percent: Optional[float]
    z_score: float
    anomaly_score: float
    status: str
    sample_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "current_value": round(self.current_value, 4),
            "baseline_mean": round(self.baseline_mean, 4),
            "baseline_stddev": round(self.baseline_stddev, 4),
            "deviation": round(self.deviation, 4),
            "deviation_percent": (
                round(self.deviation_percent, 4)
                if self.deviation_percent is not None
                else None
            ),
            "z_score": round(self.z_score, 4),
            "anomaly_score": round(self.anomaly_score, 4),
            "status": self.status,
            "sample_count": self.sample_count,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def classify_z_score(z_score: float) -> str:
    """Convert an absolute Z-score into a Phase 7.0A anomaly state."""
    score = abs(float(z_score))

    if score >= Z_CRITICAL:
        return "CRITICAL"
    if score >= Z_ANOMALOUS:
        return "ANOMALOUS"
    if score >= Z_WATCH:
        return "WATCH"
    return "NORMAL"


def severity_rank(status: str) -> int:
    return {
        "NORMAL": 0,
        "WATCH": 1,
        "ANOMALOUS": 2,
        "CRITICAL": 3,
    }.get(str(status).upper(), -1)


def analyze_metric(
    metric: str,
    current_value: Any,
    baseline_values: Iterable[Any],
    *,
    min_samples: int = MIN_BASELINE_SAMPLES,
) -> dict[str, Any]:
    """
    Analyse one telemetry metric against a historical baseline.

    The current value is intentionally NOT included in the baseline.
    """

    if metric not in SUPPORTED_METRICS:
        raise ValueError(f"Unsupported metric: {metric}")

    current = _as_float(current_value)
    if current is None:
        raise ValueError(f"Current value for {metric} is not numeric")

    baseline = [
        number
        for value in baseline_values
        if (number := _as_float(value)) is not None
    ]

    if len(baseline) < min_samples:
        raise ValueError(
            f"Insufficient baseline samples for {metric}: "
            f"{len(baseline)} < {min_samples}"
        )

    mean = fmean(baseline)
    stddev = pstdev(baseline)
    deviation = current - mean

    if abs(mean) > EPSILON:
        deviation_percent = (deviation / abs(mean)) * 100.0
    else:
        deviation_percent = None

    # A perfectly flat baseline has zero variance. In that case an unchanged
    # value is normal, while a changed value is treated as a critical
    # deviation because it lies outside a zero-variance baseline.
    if stddev <= EPSILON:
        z_score = 0.0 if abs(deviation) <= EPSILON else Z_CRITICAL
    else:
        z_score = deviation / stddev

    anomaly_score = abs(z_score)
    status = classify_z_score(anomaly_score)

    return MetricAnalysis(
        metric=metric,
        current_value=current,
        baseline_mean=mean,
        baseline_stddev=stddev,
        deviation=deviation,
        deviation_percent=deviation_percent,
        z_score=z_score,
        anomaly_score=anomaly_score,
        status=status,
        sample_count=len(baseline),
    ).as_dict()


def analyze_asset(
    asset_id: int,
    current: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    *,
    min_samples: int = MIN_BASELINE_SAMPLES,
) -> dict[str, Any]:
    """
    Analyse all supported metrics for one infrastructure asset.

    `current` is the newest telemetry sample.
    `history` contains older baseline samples.
    """

    if int(asset_id) <= 0:
        raise ValueError("asset_id must be greater than zero")

    if not history:
        raise ValueError("Historical telemetry baseline is empty")

    analyses: list[dict[str, Any]] = []
    skipped_metrics: list[dict[str, str]] = []

    for metric in SUPPORTED_METRICS:
        current_value = current.get(metric)

        if _as_float(current_value) is None:
            skipped_metrics.append(
                {
                    "metric": metric,
                    "reason": "current value unavailable",
                }
            )
            continue

        baseline_values = [
            row.get(metric)
            for row in history
            if _as_float(row.get(metric)) is not None
        ]

        if len(baseline_values) < min_samples:
            skipped_metrics.append(
                {
                    "metric": metric,
                    "reason": (
                        f"insufficient baseline samples "
                        f"({len(baseline_values)} < {min_samples})"
                    ),
                }
            )
            continue

        analyses.append(
            analyze_metric(
                metric,
                current_value,
                baseline_values,
                min_samples=min_samples,
            )
        )

    if analyses:
        overall = max(
            analyses,
            key=lambda item: (
                severity_rank(item["status"]),
                item["anomaly_score"],
            ),
        )
        overall_status = overall["status"]
        overall_score = overall["anomaly_score"]
    else:
        overall_status = "UNKNOWN"
        overall_score = 0.0

    anomalous_metrics = [
        item["metric"]
        for item in analyses
        if item["status"] in {"ANOMALOUS", "CRITICAL"}
    ]

    watch_metrics = [
        item["metric"]
        for item in analyses
        if item["status"] == "WATCH"
    ]

    return {
        "asset_id": int(asset_id),
        "status": overall_status,
        "anomaly_score": round(overall_score, 4),
        "metrics_checked": len(analyses),
        "anomalous_metrics": anomalous_metrics,
        "watch_metrics": watch_metrics,
        "metrics": analyses,
        "skipped_metrics": skipped_metrics,
        "source": SOURCE,
        "external": EXTERNAL,
        "evaluated_at": utc_now_iso(),
    }


def analyse_asset(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """British-English compatibility alias."""
    return analyze_asset(*args, **kwargs)


def build_anomaly_event_rows(
    analysis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """
    Convert an asset analysis into rows suitable for anomaly_events.

    NORMAL metrics are intentionally not persisted. WATCH and above are
    persisted so operators can inspect developing conditions.
    """

    asset_id = int(analysis["asset_id"])
    rows: list[dict[str, Any]] = []

    for metric in analysis.get("metrics", []):
        if metric.get("status") == "NORMAL":
            continue

        rows.append(
            {
                "asset_id": asset_id,
                "metric": metric["metric"],
                "current_value": metric["current_value"],
                "baseline_mean": metric["baseline_mean"],
                "baseline_stddev": metric["baseline_stddev"],
                "deviation": metric["deviation"],
                "deviation_percent": metric["deviation_percent"],
                "z_score": metric["z_score"],
                "anomaly_score": metric["anomaly_score"],
                "status": metric["status"],
                "sample_count": metric["sample_count"],
                "source": SOURCE,
                "external": EXTERNAL,
            }
        )

    return rows
