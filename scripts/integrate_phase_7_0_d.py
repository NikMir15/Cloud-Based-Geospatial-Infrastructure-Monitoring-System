#!/usr/bin/env python3

from pathlib import Path
import shutil
import sys
from datetime import datetime

MAIN = Path("backend/main.py")

MARKER_START = "# PHASE 7.0D - PREDICTIVE OPERATIONS INTEGRATION"
MARKER_END = "# END PHASE 7.0D - PREDICTIVE OPERATIONS INTEGRATION"

if not MAIN.exists():
    print(f"❌ {MAIN} not found")
    sys.exit(1)

source = MAIN.read_text()

if MARKER_START in source:
    print("ℹ️ Phase 7.0D integration already exists.")
    print("No changes made.")
    sys.exit(0)

required_existing = [
    "engine = create_engine(",
    "def load_sensor_history(",
    '@app.get("/risk")',
]

missing = [item for item in required_existing if item not in source]

if missing:
    print("❌ Required existing integration points were not found:")
    for item in missing:
        print(f"   - {item}")
    print("No changes made.")
    sys.exit(1)

backup = Path(
    f"/tmp/main.py.before-phase-7-0d-"
    f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
)
shutil.copy2(MAIN, backup)

block = r'''

# ============================================================
# PHASE 7.0D - PREDICTIVE OPERATIONS INTEGRATION
# ============================================================

from anomaly_engine import (
    analyze_asset as phase70_analyze_asset,
    build_anomaly_event_rows as phase70_build_anomaly_event_rows,
)

from prediction_engine import (
    analyze_asset_trends as phase70_analyze_asset_trends,
)

from predictive_risk_engine import (
    score_asset_risk as phase70_score_asset_risk,
)


def phase70_asset_exists(asset_id: int) -> bool:
    """Return True when asset_id exists in infrastructure_points."""

    if not isinstance(asset_id, int) or asset_id <= 0:
        return False

    query = text("""
        SELECT EXISTS (
            SELECT 1
            FROM infrastructure_points
            WHERE id = :asset_id
        )
    """)

    with engine.connect() as conn:
        return bool(
            conn.execute(
                query,
                {"asset_id": asset_id},
            ).scalar()
        )


def phase70_require_asset(asset_id: int) -> None:
    """Validate a Phase 7 asset identifier."""

    if asset_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="asset_id must be a positive integer",
        )

    if not phase70_asset_exists(asset_id):
        raise HTTPException(
            status_code=404,
            detail=f"Infrastructure asset {asset_id} not found",
        )


def phase70_current_telemetry(asset_id: int):
    """
    Return current locally generated telemetry for an asset.

    sensor_telemetry has historically used both integer and string
    dictionary keys, so support both representations.
    """

    current = sensor_telemetry.get(asset_id)

    if current is None:
        current = sensor_telemetry.get(str(asset_id))

    if current is None:
        return {}

    return dict(current)


def phase70_history(asset_id: int, hours: int = 24, limit: int = 1000):
    """
    Load telemetry history and return it oldest -> newest.

    load_sensor_history() returns newest -> oldest because the underlying
    query orders by recorded_at DESC. Predictive trend analysis should
    receive chronological observations.
    """

    rows = load_sensor_history(
        asset_id,
        hours=hours,
        limit=limit,
    )

    return list(reversed(rows))


def phase70_persist_anomaly_rows(rows):
    """Persist locally-derived anomaly events."""

    if not rows:
        return 0

    statement = text("""
        INSERT INTO anomaly_events (
            asset_id,
            metric,
            current_value,
            baseline_mean,
            baseline_stddev,
            deviation,
            deviation_percent,
            z_score,
            anomaly_score,
            status,
            sample_count,
            source,
            external,
            detected_at
        )
        VALUES (
            :asset_id,
            :metric,
            :current_value,
            :baseline_mean,
            :baseline_stddev,
            :deviation,
            :deviation_percent,
            :z_score,
            :anomaly_score,
            :status,
            :sample_count,
            'LOCAL_PROJECT',
            FALSE,
            NOW()
        )
    """)

    inserted = 0

    with engine.begin() as conn:
        for row in rows:
            status = str(row.get("status", "WATCH")).upper()

            # The DB constraint allows these three values.
            if status not in {"WATCH", "ANOMALOUS", "CRITICAL"}:
                continue

            conn.execute(
                statement,
                {
                    "asset_id": int(row["asset_id"]),
                    "metric": str(row["metric"]),
                    "current_value": float(row["current_value"]),
                    "baseline_mean": float(row["baseline_mean"]),
                    "baseline_stddev": float(
                        row.get("baseline_stddev") or 0
                    ),
                    "deviation": float(row["deviation"]),
                    "deviation_percent": (
                        None
                        if row.get("deviation_percent") is None
                        else float(row["deviation_percent"])
                    ),
                    "z_score": float(row["z_score"]),
                    "anomaly_score": float(row["anomaly_score"]),
                    "status": status,
                    "sample_count": max(
                        1,
                        int(row.get("sample_count") or 1),
                    ),
                },
            )

            inserted += 1

    return inserted


def phase70_anomaly_analysis(
    asset_id: int,
    *,
    persist: bool = True,
):
    phase70_require_asset(asset_id)

    history = phase70_history(asset_id)
    current = phase70_current_telemetry(asset_id)

    if not current:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Current local telemetry is not available "
                f"for asset {asset_id}"
            ),
        )

    analysis = phase70_analyze_asset(
        asset_id=asset_id,
        current=current,
        history=history,
    )

    persisted = 0

    if persist:
        rows = phase70_build_anomaly_event_rows(analysis)
        persisted = phase70_persist_anomaly_rows(rows)

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "asset_id": asset_id,
        "persisted_events": persisted,
        "result": analysis,
    }


@app.get("/predictive/anomalies/{asset_id}")
def phase70_get_anomalies(asset_id: int):
    return phase70_anomaly_analysis(
        asset_id,
        persist=True,
    )


@app.post("/predictive/anomalies/{asset_id}/evaluate")
def phase70_evaluate_anomalies(asset_id: int):
    return phase70_anomaly_analysis(
        asset_id,
        persist=True,
    )


@app.get("/predictive/trends/{asset_id}")
def phase70_get_trends(asset_id: int):
    phase70_require_asset(asset_id)

    history = phase70_history(asset_id)

    result = phase70_analyze_asset_trends(
        asset_id=asset_id,
        history=history,
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "asset_id": asset_id,
        "result": result,
    }


@app.get("/predictive/risk/{asset_id}")
def phase70_get_predictive_risk(asset_id: int):
    phase70_require_asset(asset_id)

    history = phase70_history(asset_id)
    current = phase70_current_telemetry(asset_id)

    if not current:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Current local telemetry is not available "
                f"for asset {asset_id}"
            ),
        )

    anomaly = phase70_analyze_asset(
        asset_id=asset_id,
        current=current,
        history=history,
    )

    trend = phase70_analyze_asset_trends(
        asset_id=asset_id,
        history=history,
    )

    anomaly_metrics = {
        item.get("metric"): item
        for item in anomaly.get("metrics", [])
        if isinstance(item, dict) and item.get("metric")
    }

    trend_metrics = {
        item.get("metric"): item
        for item in trend.get("metrics", [])
        if isinstance(item, dict) and item.get("metric")
    }

    metric_names = sorted(
        set(anomaly_metrics) | set(trend_metrics)
    )

    metric_inputs = []

    for metric in metric_names:
        metric_inputs.append(
            {
                "metric": metric,
                "anomaly": anomaly_metrics.get(metric),
                "trend": trend_metrics.get(metric),
            }
        )

    risk = phase70_score_asset_risk(
        asset_id=asset_id,
        metric_inputs=metric_inputs,
        current_health=current.get("health"),
    )

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "asset_id": asset_id,
        "result": risk,
        "anomaly": anomaly,
        "trend": trend,
    }


@app.get("/anomaly-events")
def phase70_get_anomaly_events(
    asset_id: int | None = None,
    limit: int = 250,
):
    if asset_id is not None:
        phase70_require_asset(asset_id)

    limit = max(
        1,
        min(int(limit), 1000),
    )

    if asset_id is None:
        statement = text("""
            SELECT
                id,
                asset_id,
                metric,
                current_value::float AS current_value,
                baseline_mean::float AS baseline_mean,
                baseline_stddev::float AS baseline_stddev,
                deviation::float AS deviation,
                deviation_percent::float AS deviation_percent,
                z_score::float AS z_score,
                anomaly_score::float AS anomaly_score,
                status,
                sample_count,
                source,
                external,
                detected_at
            FROM anomaly_events
            ORDER BY detected_at DESC
            LIMIT :limit
        """)

        params = {"limit": limit}

    else:
        statement = text("""
            SELECT
                id,
                asset_id,
                metric,
                current_value::float AS current_value,
                baseline_mean::float AS baseline_mean,
                baseline_stddev::float AS baseline_stddev,
                deviation::float AS deviation,
                deviation_percent::float AS deviation_percent,
                z_score::float AS z_score,
                anomaly_score::float AS anomaly_score,
                status,
                sample_count,
                source,
                external,
                detected_at
            FROM anomaly_events
            WHERE asset_id = :asset_id
            ORDER BY detected_at DESC
            LIMIT :limit
        """)

        params = {
            "asset_id": asset_id,
            "limit": limit,
        }

    with engine.connect() as conn:
        rows = [
            dict(row._mapping)
            for row in conn.execute(
                statement,
                params,
            ).fetchall()
        ]

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "count": len(rows),
        "events": rows,
    }


@app.get("/predictive/summary")
def phase70_predictive_summary():
    statement = text("""
        SELECT
            COUNT(*)::integer AS total_events,
            COUNT(*) FILTER (
                WHERE status = 'WATCH'
            )::integer AS watch,
            COUNT(*) FILTER (
                WHERE status = 'ANOMALOUS'
            )::integer AS anomalous,
            COUNT(*) FILTER (
                WHERE status = 'CRITICAL'
            )::integer AS critical,
            COUNT(DISTINCT asset_id)::integer AS affected_assets,
            MAX(detected_at) AS latest_event_at
        FROM anomaly_events
    """)

    with engine.connect() as conn:
        row = conn.execute(statement).mappings().one()

    return {
        "source": "LOCAL_PROJECT",
        "external": False,
        "phase": "7.0D",
        "capabilities": {
            "anomaly_detection": True,
            "trend_prediction": True,
            "predictive_risk": True,
            "anomaly_persistence": True,
        },
        "anomaly_events": dict(row),
    }


# ============================================================
# END PHASE 7.0D - PREDICTIVE OPERATIONS INTEGRATION
# ============================================================
'''

# Append the integration after the existing application implementation.
# This avoids touching established Phase 6.x routes and preserves /risk.
updated = source.rstrip() + "\n" + block + "\n"

MAIN.write_text(updated)

print("✅ Phase 7.0D integration appended to backend/main.py")
print(f"✅ Backup: {backup}")
print()
print("Added API contract:")
print("  GET  /predictive/anomalies/{asset_id}")
print("  POST /predictive/anomalies/{asset_id}/evaluate")
print("  GET  /predictive/trends/{asset_id}")
print("  GET  /predictive/risk/{asset_id}")
print("  GET  /anomaly-events")
print("  GET  /predictive/summary")
print()
print("Existing /risk route was not modified.")
