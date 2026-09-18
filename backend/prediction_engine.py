"""
GeoInfra Phase 7.0B
Predictive Telemetry Trend Engine

Provides deterministic, explainable linear trend analysis over ordered
historical telemetry samples.

This is statistical projection, not a guaranteed future prediction.

Phase 7.0B remains independent of FastAPI and database access.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import fmean
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

TREND_STABLE = "STABLE"
TREND_INCREASING = "INCREASING"
TREND_DECREASING = "DECREASING"

MIN_TREND_SAMPLES = 5

# Slope is normalized against the mean absolute magnitude of the series.
# A change smaller than 1% of that magnitude per sample is treated as stable.
DEFAULT_STABLE_SLOPE_RATIO = 0.01

EPSILON = 1e-9


@dataclass(frozen=True)
class TrendAnalysis:
    metric: str
    trend: str
    slope: float
    normalized_slope: float
    intercept: float
    confidence: float
    r_squared: float
    current_value: float
    projected_value: float
    projection_steps: int
    sample_count: int
    minimum_value: float
    maximum_value: float
    mean_value: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "trend": self.trend,
            "slope": round(self.slope, 6),
            "normalized_slope": round(self.normalized_slope, 6),
            "intercept": round(self.intercept, 6),
            "confidence": round(self.confidence, 6),
            "r_squared": round(self.r_squared, 6),
            "current_value": round(self.current_value, 6),
            "projected_value": round(self.projected_value, 6),
            "projection_steps": self.projection_steps,
            "sample_count": self.sample_count,
            "minimum_value": round(self.minimum_value, 6),
            "maximum_value": round(self.maximum_value, 6),
            "mean_value": round(self.mean_value, 6),
        }


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


def _clean_values(values: Iterable[Any]) -> list[float]:
    cleaned: list[float] = []

    for value in values:
        number = _as_float(value)
        if number is not None:
            cleaned.append(number)

    return cleaned


def linear_regression(values: Sequence[float]) -> tuple[float, float, float]:
    """
    Return:
        slope,
        intercept,
        r_squared

    x values are deterministic sample positions: 0, 1, 2, ...
    """

    if len(values) < 2:
        raise ValueError("At least two samples are required for regression")

    y = [float(value) for value in values]
    x = [float(index) for index in range(len(y))]

    x_mean = fmean(x)
    y_mean = fmean(y)

    denominator = sum((value - x_mean) ** 2 for value in x)

    if denominator <= EPSILON:
        slope = 0.0
    else:
        slope = (
            sum(
                (x_value - x_mean) * (y_value - y_mean)
                for x_value, y_value in zip(x, y)
            )
            / denominator
        )

    intercept = y_mean - (slope * x_mean)

    predicted = [
        intercept + (slope * x_value)
        for x_value in x
    ]

    ss_res = sum(
        (actual - estimate) ** 2
        for actual, estimate in zip(y, predicted)
    )

    ss_tot = sum(
        (actual - y_mean) ** 2
        for actual in y
    )

    if ss_tot <= EPSILON:
        # A perfectly flat series is perfectly represented by a flat line.
        r_squared = 1.0
    else:
        r_squared = 1.0 - (ss_res / ss_tot)
        r_squared = max(0.0, min(1.0, r_squared))

    return slope, intercept, r_squared


def normalized_slope(
    slope: float,
    values: Sequence[float],
) -> float:
    """
    Express slope relative to the typical magnitude of the metric.

    Example:
        mean magnitude ~= 50
        slope = 0.5/sample
        normalized slope ~= 0.01 (1% per sample)
    """

    magnitude = fmean(abs(value) for value in values)

    if magnitude <= EPSILON:
        return 0.0 if abs(slope) <= EPSILON else math.copysign(
            float("inf"),
            slope,
        )

    return slope / magnitude


def classify_trend(
    slope: float,
    values: Sequence[float],
    *,
    stable_slope_ratio: float = DEFAULT_STABLE_SLOPE_RATIO,
) -> str:
    """
    Classify a trend using a scale-aware normalized slope threshold.
    """

    if stable_slope_ratio < 0:
        raise ValueError("stable_slope_ratio cannot be negative")

    ratio = normalized_slope(slope, values)

    if abs(ratio) <= stable_slope_ratio:
        return TREND_STABLE

    if slope > 0:
        return TREND_INCREASING

    return TREND_DECREASING


def analyze_trend(
    metric: str,
    values: Iterable[Any],
    *,
    projection_steps: int = 3,
    min_samples: int = MIN_TREND_SAMPLES,
    stable_slope_ratio: float = DEFAULT_STABLE_SLOPE_RATIO,
) -> dict[str, Any]:
    """
    Analyse one ordered telemetry series.

    Input ordering MUST be oldest -> newest.

    projected_value is the regression line projected `projection_steps`
    beyond the latest observed sample.
    """

    if metric not in SUPPORTED_METRICS:
        raise ValueError(f"Unsupported metric: {metric}")

    if projection_steps < 1:
        raise ValueError("projection_steps must be at least 1")

    if min_samples < 2:
        raise ValueError("min_samples must be at least 2")

    cleaned = _clean_values(values)

    if len(cleaned) < min_samples:
        raise ValueError(
            f"Insufficient trend samples for {metric}: "
            f"{len(cleaned)} < {min_samples}"
        )

    slope, intercept, r_squared = linear_regression(cleaned)

    ratio = normalized_slope(slope, cleaned)

    trend = classify_trend(
        slope,
        cleaned,
        stable_slope_ratio=stable_slope_ratio,
    )

    # Latest observed sample uses x = len(values) - 1.
    # Project N additional sample intervals into the future.
    projected_x = (len(cleaned) - 1) + projection_steps
    projected_value = intercept + (slope * projected_x)

    # R² is used as an explainable measure of how closely the samples
    # follow the fitted linear trend. It is not a probability.
    confidence = r_squared

    result = TrendAnalysis(
        metric=metric,
        trend=trend,
        slope=slope,
        normalized_slope=ratio,
        intercept=intercept,
        confidence=confidence,
        r_squared=r_squared,
        current_value=cleaned[-1],
        projected_value=projected_value,
        projection_steps=projection_steps,
        sample_count=len(cleaned),
        minimum_value=min(cleaned),
        maximum_value=max(cleaned),
        mean_value=fmean(cleaned),
    )

    payload = result.as_dict()
    payload.update(
        {
            "source": SOURCE,
            "external": EXTERNAL,
            "evaluated_at": utc_now_iso(),
            "projection_notice": (
                "Statistical linear projection; "
                "not a guaranteed future prediction."
            ),
        }
    )

    return payload


def analyze_asset_trends(
    asset_id: int,
    history: Sequence[Mapping[str, Any]],
    *,
    projection_steps: int = 3,
    min_samples: int = MIN_TREND_SAMPLES,
    stable_slope_ratio: float = DEFAULT_STABLE_SLOPE_RATIO,
) -> dict[str, Any]:
    """
    Analyse all available Phase 7.0 telemetry metrics for one asset.

    `history` MUST be ordered oldest -> newest.
    """

    if int(asset_id) <= 0:
        raise ValueError("asset_id must be greater than zero")

    if not history:
        raise ValueError("Historical telemetry is empty")

    trends: list[dict[str, Any]] = []
    skipped_metrics: list[dict[str, str]] = []

    for metric in SUPPORTED_METRICS:
        values = [
            row.get(metric)
            for row in history
            if _as_float(row.get(metric)) is not None
        ]

        if len(values) < min_samples:
            skipped_metrics.append(
                {
                    "metric": metric,
                    "reason": (
                        f"insufficient trend samples "
                        f"({len(values)} < {min_samples})"
                    ),
                }
            )
            continue

        trends.append(
            analyze_trend(
                metric,
                values,
                projection_steps=projection_steps,
                min_samples=min_samples,
                stable_slope_ratio=stable_slope_ratio,
            )
        )

    counts = {
        TREND_STABLE: 0,
        TREND_INCREASING: 0,
        TREND_DECREASING: 0,
    }

    for trend in trends:
        counts[trend["trend"]] += 1

    changing = [
        item["metric"]
        for item in trends
        if item["trend"] != TREND_STABLE
    ]

    return {
        "asset_id": int(asset_id),
        "metrics_checked": len(trends),
        "stable_count": counts[TREND_STABLE],
        "increasing_count": counts[TREND_INCREASING],
        "decreasing_count": counts[TREND_DECREASING],
        "changing_metrics": changing,
        "trends": trends,
        "skipped_metrics": skipped_metrics,
        "source": SOURCE,
        "external": EXTERNAL,
        "evaluated_at": utc_now_iso(),
        "projection_notice": (
            "Statistical linear projection; "
            "not a guaranteed future prediction."
        ),
    }


def analyse_trend(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """British-English compatibility alias."""
    return analyze_trend(*args, **kwargs)


def analyse_asset_trends(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """British-English compatibility alias."""
    return analyze_asset_trends(*args, **kwargs)
