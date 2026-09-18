"""
GeoInfra
Phase 6.9B — Reliability Engineering Engine

Calculates:
- SLI compliance
- SLO compliance
- Error budget
- Error budget consumption
- Reliability status
- Persisted SLO measurements

All telemetry used by this module comes from the project's local
sensor_telemetry_history table.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


SUPPORTED_METRICS = {
    "health",
    "cpu_percent",
    "temperature_c",
    "latency_ms",
    "packet_loss_percent",
}

SUPPORTED_OPERATORS = {
    "<",
    "<=",
    ">",
    ">=",
    "=",
}

RELIABILITY_STATUSES = {
    "HEALTHY",
    "AT_RISK",
    "BREACHED",
    "UNKNOWN",
}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _to_float(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, Decimal):
        return float(value)

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def _row_mapping(row):
    if row is None:
        return None

    if hasattr(row, "_mapping"):
        return row._mapping

    return row


def _objective_to_dict(row) -> dict[str, Any] | None:
    mapping = _row_mapping(row)

    if mapping is None:
        return None

    return {
        "id": mapping["id"],
        "objective_key": mapping["objective_key"],
        "asset_id": mapping["asset_id"],
        "name": mapping["name"],
        "metric": mapping["metric"],
        "comparison_operator": mapping["comparison_operator"],
        "threshold": _to_float(mapping["threshold"]),
        "target_percentage": _to_float(mapping["target_percentage"]),
        "window_minutes": mapping["window_minutes"],
        "enabled": mapping["enabled"],
        "source": mapping["source"],
        "external": mapping["external"],
        "created_at": _iso(mapping["created_at"]),
        "updated_at": _iso(mapping["updated_at"]),
    }


# ------------------------------------------------------------
# SLI / SLO mathematics
# ------------------------------------------------------------

def calculate_sli(
    good_observations: int,
    total_observations: int,
) -> float | None:
    """
    SLI = good observations / total observations * 100
    """

    if total_observations <= 0:
        return None

    good = max(0, min(good_observations, total_observations))

    return round((good / total_observations) * 100.0, 4)


def calculate_error_budget(
    target_percentage: float,
) -> float:
    """
    Error budget percentage = 100 - SLO target.
    """

    return round(max(0.0, 100.0 - float(target_percentage)), 4)


def calculate_error_budget_consumed(
    sli_percentage: float | None,
    target_percentage: float,
) -> float | None:
    """
    Calculates how much of the allowed error budget has been consumed.

    Example:
        SLO target = 99%
        Allowed bad observations = 1%

        SLI = 99.5%
        Actual bad observations = 0.5%

        Budget consumed = 50%
    """

    if sli_percentage is None:
        return None

    error_budget = calculate_error_budget(target_percentage)

    if error_budget <= 0:
        if sli_percentage >= 100.0:
            return 0.0
        return 100.0

    actual_bad_percentage = max(
        0.0,
        100.0 - float(sli_percentage),
    )

    consumed = (
        actual_bad_percentage / error_budget
    ) * 100.0

    return round(consumed, 4)


def reliability_status(
    sli_percentage: float | None,
    target_percentage: float,
    error_budget_consumed_percentage: float | None,
) -> str:
    """
    Status policy:

    UNKNOWN:
        No telemetry observations.

    BREACHED:
        Current SLI is below the configured SLO target.

    AT_RISK:
        SLO is currently satisfied, but >= 80% of the
        available error budget has been consumed.

    HEALTHY:
        SLO is satisfied and error-budget consumption < 80%.
    """

    if sli_percentage is None:
        return "UNKNOWN"

    if sli_percentage < target_percentage:
        return "BREACHED"

    if (
        error_budget_consumed_percentage is not None
        and error_budget_consumed_percentage >= 80.0
    ):
        return "AT_RISK"

    return "HEALTHY"


# ------------------------------------------------------------
# Objective management
# ------------------------------------------------------------

def list_service_objectives(
    engine: Engine,
    enabled_only: bool = False,
) -> list[dict[str, Any]]:

    query = """
        SELECT
            id,
            objective_key,
            asset_id,
            name,
            metric,
            comparison_operator,
            threshold,
            target_percentage,
            window_minutes,
            enabled,
            source,
            external,
            created_at,
            updated_at
        FROM service_objectives
    """

    if enabled_only:
        query += " WHERE enabled = TRUE"

    query += " ORDER BY id"

    with engine.connect() as conn:
        rows = conn.execute(text(query)).fetchall()

    return [
        _objective_to_dict(row)
        for row in rows
    ]


def get_service_objective(
    engine: Engine,
    objective_id: int,
) -> dict[str, Any] | None:

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    id,
                    objective_key,
                    asset_id,
                    name,
                    metric,
                    comparison_operator,
                    threshold,
                    target_percentage,
                    window_minutes,
                    enabled,
                    source,
                    external,
                    created_at,
                    updated_at
                FROM service_objectives
                WHERE id = :objective_id
                """
            ),
            {"objective_id": objective_id},
        ).fetchone()

    return _objective_to_dict(row)


# ------------------------------------------------------------
# SQL condition builder
# ------------------------------------------------------------

def _metric_condition(
    metric: str,
    comparison_operator: str,
) -> str:
    """
    Returns a validated SQL condition.

    Metric names and operators are allow-listed before they are
    inserted into SQL.
    """

    if metric not in SUPPORTED_METRICS:
        raise ValueError(
            f"Unsupported reliability metric: {metric}"
        )

    if comparison_operator not in SUPPORTED_OPERATORS:
        raise ValueError(
            f"Unsupported comparison operator: "
            f"{comparison_operator}"
        )

    return f"{metric} {comparison_operator} :threshold"


# ------------------------------------------------------------
# Objective evaluation
# ------------------------------------------------------------

def evaluate_objective(
    engine: Engine,
    objective_id: int,
    persist: bool = True,
) -> dict[str, Any]:

    objective = get_service_objective(
        engine,
        objective_id,
    )

    if objective is None:
        raise ValueError(
            f"Service objective {objective_id} does not exist."
        )

    if not objective["enabled"]:
        raise ValueError(
            f"Service objective {objective_id} is disabled."
        )

    metric = objective["metric"]
    operator = objective["comparison_operator"]

    condition = _metric_condition(
        metric,
        operator,
    )

    sql = text(
        f"""
        SELECT
            COUNT({metric}) AS total_observations,

            COUNT({metric}) FILTER (
                WHERE {condition}
            ) AS good_observations,

            MIN(recorded_at) AS first_observation,

            MAX(recorded_at) AS last_observation

        FROM sensor_telemetry_history

        WHERE asset_id = :asset_id

        AND recorded_at >=
            NOW() - make_interval(
                mins => :window_minutes
            )
        """
    )

    params = {
        "asset_id": objective["asset_id"],
        "threshold": objective["threshold"],
        "window_minutes": objective["window_minutes"],
    }

    with engine.connect() as conn:
        row = conn.execute(
            sql,
            params,
        ).fetchone()

    mapping = _row_mapping(row)

    total = int(
        mapping["total_observations"] or 0
    )

    good = int(
        mapping["good_observations"] or 0
    )

    sli = calculate_sli(
        good,
        total,
    )

    target = float(
        objective["target_percentage"]
    )

    budget = calculate_error_budget(
        target,
    )

    consumed = calculate_error_budget_consumed(
        sli,
        target,
    )

    status = reliability_status(
        sli,
        target,
        consumed,
    )

    now = datetime.now(timezone.utc)

    window_minutes = int(
        objective["window_minutes"]
    )

    result = {
        "objective_id": objective["id"],
        "objective_key": objective["objective_key"],
        "objective_name": objective["name"],
        "asset_id": objective["asset_id"],
        "metric": metric,
        "comparison_operator": operator,
        "threshold": objective["threshold"],
        "target_percentage": target,
        "window_minutes": window_minutes,
        "good_observations": good,
        "total_observations": total,
        "sli_percentage": sli,
        "error_budget_percentage": budget,
        "error_budget_consumed_percentage": consumed,
        "status": status,
        "first_observation": _iso(
            mapping["first_observation"]
        ),
        "last_observation": _iso(
            mapping["last_observation"]
        ),
        "source": "LOCAL_PROJECT",
        "external": False,
        "evaluated_at": now.isoformat(),
    }

    if persist:
        measurement_id = persist_measurement(
            engine,
            result,
        )

        result["measurement_id"] = measurement_id

    return result


# ------------------------------------------------------------
# Persist measurement
# ------------------------------------------------------------

def persist_measurement(
    engine: Engine,
    result: dict[str, Any],
) -> int:

    with engine.begin() as conn:

        row = conn.execute(
            text(
                """
                INSERT INTO slo_measurements (
                    objective_id,
                    good_observations,
                    total_observations,
                    sli_percentage,
                    error_budget_percentage,
                    error_budget_consumed_percentage,
                    status,
                    window_start,
                    window_end,
                    source,
                    external,
                    evaluated_at
                )
                VALUES (
                    :objective_id,
                    :good_observations,
                    :total_observations,
                    :sli_percentage,
                    :error_budget_percentage,
                    :error_budget_consumed_percentage,
                    :status,
                    NOW() - make_interval(
                        mins => :window_minutes
                    ),
                    NOW(),
                    'LOCAL_PROJECT',
                    FALSE,
                    NOW()
                )
                RETURNING id
                """
            ),
            {
                "objective_id": result["objective_id"],
                "good_observations": result["good_observations"],
                "total_observations": result["total_observations"],
                "sli_percentage": result["sli_percentage"],
                "error_budget_percentage": result[
                    "error_budget_percentage"
                ],
                "error_budget_consumed_percentage": result[
                    "error_budget_consumed_percentage"
                ],
                "status": result["status"],
                "window_minutes": result["window_minutes"],
            },
        ).fetchone()

    return int(row[0])


# ------------------------------------------------------------
# Evaluate all objectives
# ------------------------------------------------------------

def evaluate_all_objectives(
    engine: Engine,
    persist: bool = True,
) -> dict[str, Any]:

    objectives = list_service_objectives(
        engine,
        enabled_only=True,
    )

    results = []
    failures = []

    for objective in objectives:

        try:
            result = evaluate_objective(
                engine,
                objective["id"],
                persist=persist,
            )

            results.append(result)

        except Exception as exc:
            failures.append(
                {
                    "objective_id": objective["id"],
                    "objective_key": objective[
                        "objective_key"
                    ],
                    "error": str(exc),
                }
            )

    counts = {
        "HEALTHY": 0,
        "AT_RISK": 0,
        "BREACHED": 0,
        "UNKNOWN": 0,
    }

    for result in results:
        status = result["status"]

        if status in counts:
            counts[status] += 1

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "objectives_checked": len(objectives),
        "evaluated": len(results),
        "failed": len(failures),
        "healthy": counts["HEALTHY"],
        "at_risk": counts["AT_RISK"],
        "breached": counts["BREACHED"],
        "unknown": counts["UNKNOWN"],
        "results": results,
        "failures": failures,
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


# ------------------------------------------------------------
# Latest measurements
# ------------------------------------------------------------

def latest_slo_measurements(
    engine: Engine,
) -> list[dict[str, Any]]:

    with engine.connect() as conn:

        rows = conn.execute(
            text(
                """
                SELECT DISTINCT ON (sm.objective_id)

                    sm.id,
                    sm.objective_id,
                    so.objective_key,
                    so.name AS objective_name,
                    so.asset_id,
                    so.metric,
                    so.threshold,
                    so.target_percentage,

                    sm.good_observations,
                    sm.total_observations,
                    sm.sli_percentage,
                    sm.error_budget_percentage,
                    sm.error_budget_consumed_percentage,
                    sm.status,

                    sm.window_start,
                    sm.window_end,
                    sm.evaluated_at,

                    sm.source,
                    sm.external

                FROM slo_measurements sm

                JOIN service_objectives so
                    ON so.id = sm.objective_id

                ORDER BY
                    sm.objective_id,
                    sm.evaluated_at DESC,
                    sm.id DESC
                """
            )
        ).mappings().all()

    results = []

    for row in rows:

        results.append(
            {
                "measurement_id": row["id"],
                "objective_id": row["objective_id"],
                "objective_key": row["objective_key"],
                "objective_name": row["objective_name"],
                "asset_id": row["asset_id"],
                "metric": row["metric"],
                "threshold": _to_float(
                    row["threshold"]
                ),
                "target_percentage": _to_float(
                    row["target_percentage"]
                ),
                "good_observations": row[
                    "good_observations"
                ],
                "total_observations": row[
                    "total_observations"
                ],
                "sli_percentage": _to_float(
                    row["sli_percentage"]
                ),
                "error_budget_percentage": _to_float(
                    row["error_budget_percentage"]
                ),
                "error_budget_consumed_percentage": _to_float(
                    row[
                        "error_budget_consumed_percentage"
                    ]
                ),
                "status": row["status"],
                "window_start": _iso(
                    row["window_start"]
                ),
                "window_end": _iso(
                    row["window_end"]
                ),
                "evaluated_at": _iso(
                    row["evaluated_at"]
                ),
                "source": row["source"],
                "external": row["external"],
            }
        )

    return results


# ------------------------------------------------------------
# Reliability summary
# ------------------------------------------------------------

def reliability_summary(
    engine: Engine,
) -> dict[str, Any]:

    measurements = latest_slo_measurements(
        engine
    )

    healthy = sum(
        1
        for item in measurements
        if item["status"] == "HEALTHY"
    )

    at_risk = sum(
        1
        for item in measurements
        if item["status"] == "AT_RISK"
    )

    breached = sum(
        1
        for item in measurements
        if item["status"] == "BREACHED"
    )

    unknown = sum(
        1
        for item in measurements
        if item["status"] == "UNKNOWN"
    )

    valid_sli = [
        item["sli_percentage"]
        for item in measurements
        if item["sli_percentage"] is not None
    ]

    valid_budget = [
        item["error_budget_consumed_percentage"]
        for item in measurements
        if item[
            "error_budget_consumed_percentage"
        ] is not None
    ]

    average_sli = (
        round(
            sum(valid_sli) / len(valid_sli),
            4,
        )
        if valid_sli
        else None
    )

    average_budget_consumed = (
        round(
            sum(valid_budget) / len(valid_budget),
            4,
        )
        if valid_budget
        else None
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "objectives": len(measurements),
        "healthy": healthy,
        "at_risk": at_risk,
        "breached": breached,
        "unknown": unknown,
        "average_sli_percentage": average_sli,
        "average_error_budget_consumed_percentage":
            average_budget_consumed,
        "measurements": measurements,
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }
