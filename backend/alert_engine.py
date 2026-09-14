from datetime import datetime, timezone
from typing import Any, Dict, List


# ============================================================
# PHASE 6.3
# SENSOR HEALTH + ALERT ENGINE
# ============================================================

CPU_WARNING = 70.0
CPU_CRITICAL = 85.0

TEMPERATURE_WARNING = 60.0
TEMPERATURE_CRITICAL = 75.0

LATENCY_WARNING = 100.0
LATENCY_CRITICAL = 200.0

PACKET_LOSS_WARNING = 1.0
PACKET_LOSS_CRITICAL = 5.0

HEALTH_WARNING = 80.0
HEALTH_CRITICAL = 60.0


SEVERITY_PRIORITY = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_alert(
    asset_id: int,
    asset_name: str,
    alert_type: str,
    severity: str,
    message: str,
    metric: str,
    value: float,
    threshold: float,
) -> Dict[str, Any]:

    return {
        "alert_id": f"{asset_id}:{alert_type}",
        "asset_id": asset_id,
        "asset_name": asset_name,
        "alert_type": alert_type,
        "severity": severity,
        "message": message,
        "metric": metric,
        "value": round(float(value), 2),
        "threshold": threshold,
        "source": "LOCAL_PROJECT",
        "external": False,
        "active": True,
        "generated_at": utc_now_iso(),
    }


def evaluate_sensor(sensor: Dict[str, Any]) -> List[Dict[str, Any]]:

    alerts: List[Dict[str, Any]] = []

    asset_id = sensor.get("asset_id")
    asset_name = sensor.get("name", f"Asset {asset_id}")

    cpu = float(sensor.get("cpu_percent", 0))
    temperature = float(sensor.get("temperature_c", 0))
    latency = float(sensor.get("latency_ms", 0))
    packet_loss = float(sensor.get("packet_loss_percent", 0))
    health = float(sensor.get("health", 100))

    status = sensor.get("status", "online")


    # ========================================================
    # OFFLINE SENSOR
    # ========================================================

    if status == "offline":

        alerts.append(
            make_alert(
                asset_id,
                asset_name,
                "sensor_offline",
                "critical",
                "Infrastructure telemetry source is offline",
                "status",
                0,
                1,
            )
        )


    # ========================================================
    # CPU
    # ========================================================

    if cpu >= CPU_CRITICAL:

        alerts.append(
            make_alert(
                asset_id,
                asset_name,
                "cpu_critical",
                "critical",
                "CPU usage is critically high",
                "cpu_percent",
                cpu,
                CPU_CRITICAL,
            )
        )

    elif cpu >= CPU_WARNING:

        alerts.append(
            make_alert(
                asset_id,
                asset_name,
                "cpu_warning",
                "medium",
                "CPU usage is elevated",
                "cpu_percent",
                cpu,
                CPU_WARNING,
            )
        )


    # ========================================================
    # TEMPERATURE
    # ========================================================

    if temperature >= TEMPERATURE_CRITICAL:

        alerts.append(
            make_alert(
                asset_id,
                asset_name,
                "temperature_critical",
                "critical",
                "Infrastructure temperature is critically high",
                "temperature_c",
                temperature,
                TEMPERATURE_CRITICAL,
            )
        )

    elif temperature >= TEMPERATURE_WARNING:

        alerts.append(
            make_alert(
                asset_id,
                asset_name,
                "temperature_warning",
                "high",
                "Infrastructure temperature is elevated",
                "temperature_c",
                temperature,
                TEMPERATURE_WARNING,
            )
        )


    # ========================================================
    # LATENCY
    # ========================================================

    if latency >= LATENCY_CRITICAL:

        alerts.append(
            make_alert(
                asset_id,
                asset_name,
                "latency_critical",
                "critical",
                "Network latency is critically high",
                "latency_ms",
                latency,
                LATENCY_CRITICAL,
            )
        )

    elif latency >= LATENCY_WARNING:

        alerts.append(
            make_alert(
                asset_id,
                asset_name,
                "latency_warning",
                "medium",
                "Network latency is elevated",
                "latency_ms",
                latency,
                LATENCY_WARNING,
            )
        )


    # ========================================================
    # PACKET LOSS
    # ========================================================

    if packet_loss >= PACKET_LOSS_CRITICAL:

        alerts.append(
            make_alert(
                asset_id,
                asset_name,
                "packet_loss_critical",
                "critical",
                "Packet loss is critically high",
                "packet_loss_percent",
                packet_loss,
                PACKET_LOSS_CRITICAL,
            )
        )

    elif packet_loss >= PACKET_LOSS_WARNING:

        alerts.append(
            make_alert(
                asset_id,
                asset_name,
                "packet_loss_warning",
                "medium",
                "Packet loss has exceeded the warning threshold",
                "packet_loss_percent",
                packet_loss,
                PACKET_LOSS_WARNING,
            )
        )


    # ========================================================
    # HEALTH SCORE
    # ========================================================

    if health < HEALTH_CRITICAL:

        alerts.append(
            make_alert(
                asset_id,
                asset_name,
                "health_critical",
                "critical",
                "Infrastructure health score is critically low",
                "health",
                health,
                HEALTH_CRITICAL,
            )
        )

    elif health < HEALTH_WARNING:

        alerts.append(
            make_alert(
                asset_id,
                asset_name,
                "health_warning",
                "high",
                "Infrastructure health score is degraded",
                "health",
                health,
                HEALTH_WARNING,
            )
        )


    alerts.sort(
        key=lambda alert: SEVERITY_PRIORITY.get(
            alert["severity"],
            0,
        ),
        reverse=True,
    )

    return alerts


def evaluate_all_sensors(
    sensors: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    alerts: List[Dict[str, Any]] = []

    for sensor in sensors:
        alerts.extend(
            evaluate_sensor(sensor)
        )

    alerts.sort(
        key=lambda alert: SEVERITY_PRIORITY.get(
            alert["severity"],
            0,
        ),
        reverse=True,
    )

    return alerts


def calculate_sensor_health_summary(
    sensors: List[Dict[str, Any]]
) -> Dict[str, Any]:

    total = len(sensors)

    online = 0
    degraded = 0
    offline = 0

    health_values = []

    for sensor in sensors:

        status = sensor.get(
            "status",
            "online",
        )

        if status == "online":
            online += 1

        elif status == "degraded":
            degraded += 1

        elif status == "offline":
            offline += 1

        try:
            health_values.append(
                float(
                    sensor.get(
                        "health",
                        0,
                    )
                )
            )
        except (TypeError, ValueError):
            pass

    average_health = (
        round(
            sum(health_values)
            / len(health_values),
            2,
        )
        if health_values
        else 0
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "total": total,
        "online": online,
        "degraded": degraded,
        "offline": offline,
        "average_health": average_health,
        "generated_at": utc_now_iso(),
    }


def calculate_alert_summary(
    alerts: List[Dict[str, Any]]
) -> Dict[str, Any]:

    summary = {
        "total": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }

    for alert in alerts:

        severity = alert.get(
            "severity",
            "low",
        )

        summary["total"] += 1

        if severity in summary:
            summary[severity] += 1

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        **summary,
        "generated_at": utc_now_iso(),
    }
