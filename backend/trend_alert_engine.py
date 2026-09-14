from datetime import datetime, timezone
from typing import Any, Dict, List


SEVERITY_PRIORITY = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


ABSOLUTE_RULES = {
    "cpu_percent": {
        "label": "CPU",
        "direction": "high",
        "warning": 70.0,
        "critical": 85.0,
        "warning_severity": "medium",
        "critical_severity": "critical",
        "unit": "%",
    },
    "temperature_c": {
        "label": "Temperature",
        "direction": "high",
        "warning": 60.0,
        "critical": 75.0,
        "warning_severity": "high",
        "critical_severity": "critical",
        "unit": "°C",
    },
    "latency_ms": {
        "label": "Latency",
        "direction": "high",
        "warning": 100.0,
        "critical": 200.0,
        "warning_severity": "medium",
        "critical_severity": "critical",
        "unit": " ms",
    },
    "packet_loss_percent": {
        "label": "Packet loss",
        "direction": "high",
        "warning": 1.0,
        "critical": 5.0,
        "warning_severity": "medium",
        "critical_severity": "critical",
        "unit": "%",
    },
    "health": {
        "label": "Health",
        "direction": "low",
        "warning": 80.0,
        "critical": 60.0,
        "warning_severity": "high",
        "critical_severity": "critical",
        "unit": "%",
    },
}


TREND_RULES = {
    "cpu_percent": {
        "label": "CPU",
        "direction": "up",
        "warning_delta": 10.0,
        "critical_delta": 20.0,
        "warning_severity": "medium",
        "critical_severity": "high",
        "unit": "%",
    },
    "temperature_c": {
        "label": "Temperature",
        "direction": "up",
        "warning_delta": 5.0,
        "critical_delta": 10.0,
        "warning_severity": "medium",
        "critical_severity": "high",
        "unit": "°C",
    },
    "latency_ms": {
        "label": "Latency",
        "direction": "up",
        "warning_delta": 40.0,
        "critical_delta": 80.0,
        "warning_severity": "medium",
        "critical_severity": "high",
        "unit": " ms",
    },
    "packet_loss_percent": {
        "label": "Packet loss",
        "direction": "up",
        "warning_delta": 1.0,
        "critical_delta": 2.5,
        "warning_severity": "medium",
        "critical_severity": "high",
        "unit": "%",
    },
    "health": {
        "label": "Health",
        "direction": "down",
        "warning_delta": 8.0,
        "critical_delta": 15.0,
        "warning_severity": "medium",
        "critical_severity": "high",
        "unit": "%",
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _make_alert(
    *,
    asset_id: int,
    asset_name: str,
    metric: str,
    metric_label: str,
    severity: str,
    alert_kind: str,
    message: str,
    latest_value: float,
    reference_value: float | None = None,
    threshold: float | None = None,
    delta: float | None = None,
    sample_count: int = 0,
    window_minutes: int | None = None,
    unit: str = "",
) -> Dict[str, Any]:
    return {
        "alert_id": f"{asset_id}:{metric}:{alert_kind}",
        "asset_id": asset_id,
        "asset_name": asset_name,
        "metric": metric,
        "metric_label": metric_label,
        "severity": severity,
        "alert_kind": alert_kind,
        "message": message,
        "latest_value": round(latest_value, 2),
        "reference_value": (
            round(reference_value, 2)
            if reference_value is not None
            else None
        ),
        "threshold": (
            round(threshold, 2)
            if threshold is not None
            else None
        ),
        "delta": (
            round(delta, 2)
            if delta is not None
            else None
        ),
        "sample_count": sample_count,
        "window_minutes": window_minutes,
        "unit": unit,
        "source": "LOCAL_PROJECT",
        "external": False,
        "active": True,
        "generated_at": utc_now_iso(),
    }


def evaluate_absolute_thresholds(
    sensor: Dict[str, Any],
) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []

    asset_id = int(sensor.get("asset_id", 0))
    asset_name = str(sensor.get("name", f"Asset {asset_id}"))

    for metric, rule in ABSOLUTE_RULES.items():
        value = _to_float(sensor.get(metric))

        if rule["direction"] == "high":
            if value >= rule["critical"]:
                alerts.append(
                    _make_alert(
                        asset_id=asset_id,
                        asset_name=asset_name,
                        metric=metric,
                        metric_label=rule["label"],
                        severity=rule["critical_severity"],
                        alert_kind="threshold",
                        message=f'{rule["label"]} is above the critical threshold',
                        latest_value=value,
                        threshold=rule["critical"],
                        unit=rule["unit"],
                    )
                )
            elif value >= rule["warning"]:
                alerts.append(
                    _make_alert(
                        asset_id=asset_id,
                        asset_name=asset_name,
                        metric=metric,
                        metric_label=rule["label"],
                        severity=rule["warning_severity"],
                        alert_kind="threshold",
                        message=f'{rule["label"]} is above the warning threshold',
                        latest_value=value,
                        threshold=rule["warning"],
                        unit=rule["unit"],
                    )
                )
        else:
            if value < rule["critical"]:
                alerts.append(
                    _make_alert(
                        asset_id=asset_id,
                        asset_name=asset_name,
                        metric=metric,
                        metric_label=rule["label"],
                        severity=rule["critical_severity"],
                        alert_kind="threshold",
                        message=f'{rule["label"]} is below the critical threshold',
                        latest_value=value,
                        threshold=rule["critical"],
                        unit=rule["unit"],
                    )
                )
            elif value < rule["warning"]:
                alerts.append(
                    _make_alert(
                        asset_id=asset_id,
                        asset_name=asset_name,
                        metric=metric,
                        metric_label=rule["label"],
                        severity=rule["warning_severity"],
                        alert_kind="threshold",
                        message=f'{rule["label"]} is below the warning threshold',
                        latest_value=value,
                        threshold=rule["warning"],
                        unit=rule["unit"],
                    )
                )

    if str(sensor.get("status", "")).lower() == "offline":
        alerts.append(
            _make_alert(
                asset_id=asset_id,
                asset_name=asset_name,
                metric="status",
                metric_label="Status",
                severity="critical",
                alert_kind="status",
                message="Infrastructure telemetry source is offline",
                latest_value=0.0,
                threshold=1.0,
            )
        )

    return alerts


def evaluate_metric_trend(
    *,
    asset_id: int,
    asset_name: str,
    records: List[Dict[str, Any]],
    metric: str,
    window_minutes: int,
) -> Dict[str, Any] | None:
    rule = TREND_RULES.get(metric)

    if not rule or len(records) < 3:
        return None

    chronological = list(reversed(records))

    values = []
    for record in chronological:
        try:
            values.append(float(record.get(metric)))
        except (TypeError, ValueError):
            pass

    if len(values) < 3:
        return None

    first_value = values[0]
    latest_value = values[-1]
    delta = latest_value - first_value

    if rule["direction"] == "down":
        effective_delta = first_value - latest_value
        trend_word = "decreased"
    else:
        effective_delta = latest_value - first_value
        trend_word = "increased"

    if effective_delta >= rule["critical_delta"]:
        severity = rule["critical_severity"]
        threshold = rule["critical_delta"]
    elif effective_delta >= rule["warning_delta"]:
        severity = rule["warning_severity"]
        threshold = rule["warning_delta"]
    else:
        return None

    return _make_alert(
        asset_id=asset_id,
        asset_name=asset_name,
        metric=metric,
        metric_label=rule["label"],
        severity=severity,
        alert_kind="trend",
        message=(
            f'{rule["label"]} has {trend_word} abnormally '
            f'over the recent telemetry window'
        ),
        latest_value=latest_value,
        reference_value=first_value,
        threshold=threshold,
        delta=delta,
        sample_count=len(values),
        window_minutes=window_minutes,
        unit=rule["unit"],
    )


def evaluate_asset_telemetry(
    *,
    sensor: Dict[str, Any],
    history_records: List[Dict[str, Any]],
    window_minutes: int,
) -> List[Dict[str, Any]]:
    asset_id = int(sensor.get("asset_id", 0))
    asset_name = str(sensor.get("name", f"Asset {asset_id}"))

    alerts = evaluate_absolute_thresholds(sensor)

    for metric in TREND_RULES:
        trend_alert = evaluate_metric_trend(
            asset_id=asset_id,
            asset_name=asset_name,
            records=history_records,
            metric=metric,
            window_minutes=window_minutes,
        )

        if trend_alert is not None:
            alerts.append(trend_alert)

    alerts.sort(
        key=lambda item: SEVERITY_PRIORITY.get(
            item.get("severity", "low"),
            0,
        ),
        reverse=True,
    )

    return alerts


def build_alert_summary(
    alerts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    summary = {
        "total": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "threshold_alerts": 0,
        "trend_alerts": 0,
        "affected_assets": 0,
    }

    affected_assets = set()

    for alert in alerts:
        severity = str(alert.get("severity", "low"))
        kind = str(alert.get("alert_kind", ""))

        summary["total"] += 1

        if severity in {"critical", "high", "medium", "low"}:
            summary[severity] += 1

        if kind == "threshold":
            summary["threshold_alerts"] += 1
        elif kind == "trend":
            summary["trend_alerts"] += 1

        asset_id = int(alert.get("asset_id", 0))
        if asset_id > 0:
            affected_assets.add(asset_id)

    summary["affected_assets"] = len(affected_assets)

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        **summary,
        "generated_at": utc_now_iso(),
    }
