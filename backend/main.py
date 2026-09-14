from fastapi import (
    FastAPI,
    WebSocket,
    Query,
    HTTPException
)

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from alert_engine import (
    evaluate_all_sensors,
    calculate_sensor_health_summary,
    calculate_alert_summary
)

from trend_alert_engine import (
    evaluate_asset_telemetry,
    build_alert_summary as build_telemetry_alert_summary
)

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from datetime import datetime, timezone
from contextlib import asynccontextmanager

import asyncio
import json
import os
import random
import time
import uuid


# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is missing"
    )


USGS_FEED_URL = os.getenv(
    "USGS_FEED_URL",
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
)


USGS_CACHE_SECONDS = 60


# =========================================================
# IMPORTANT PRIVACY / PROJECT MODE
# =========================================================
#
# Sensor telemetry is generated ONLY inside this FastAPI
# application.
#
# It is:
#
# - NOT uploaded anywhere
# - NOT sent to USGS
# - NOT sent to another monitoring service
# - NOT sent to a cloud provider
#
# USGS is READ ONLY.
#
# =========================================================

SENSOR_MODE = "LOCAL_SIMULATION"

SENSOR_UPDATE_SECONDS = 5

TELEMETRY_HISTORY_INTERVAL_SECONDS = int(
    os.getenv(
        "TELEMETRY_HISTORY_INTERVAL_SECONDS",
        "60"
    )
)

TELEMETRY_HISTORY_RETENTION_DAYS = int(
    os.getenv(
        "TELEMETRY_HISTORY_RETENTION_DAYS",
        "7"
    )
)


TELEMETRY_ALERT_WINDOW_MINUTES = int(
    os.getenv(
        "TELEMETRY_ALERT_WINDOW_MINUTES",
        "5"
    )
)

TELEMETRY_ALERT_HISTORY_SAMPLES = int(
    os.getenv(
        "TELEMETRY_ALERT_HISTORY_SAMPLES",
        "5"
    )
)

TELEMETRY_ALERT_WEBSOCKET_SECONDS = int(
    os.getenv(
        "TELEMETRY_ALERT_WEBSOCKET_SECONDS",
        "15"
    )
)


TELEMETRY_ALERT_PERSISTENCE_SECONDS = int(
    os.getenv(
        "TELEMETRY_ALERT_PERSISTENCE_SECONDS",
        "15"
    )
)


# =========================================================
# DATABASE
# =========================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


# =========================================================
# LIVE SENSOR TELEMETRY
# =========================================================

sensor_telemetry = {}


# =========================================================
# USGS CACHE
# =========================================================

usgs_cache = {

    "events": [],

    "fetched_at": 0,

    "generated_at": None,

    "error": None
}


# =========================================================
# TEST EVENT
# =========================================================

test_event_state = {

    "event": None
}


# =========================================================
# INCIDENT REGISTRY
# =========================================================

incident_registry = {}


# =========================================================
# REQUEST MODELS
# =========================================================

class TestEventRequest(BaseModel):

    asset_id: int = Field(
        ...,
        gt=0
    )

    magnitude: float = Field(
        default=5.8,
        ge=2.5,
        le=9.5
    )

    radius_km: float | None = Field(
        default=None,
        gt=0,
        le=2000
    )

    latitude_offset: float = 0

    longitude_offset: float = 0




class AlertActionRequest(BaseModel):

    changed_by: str = Field(
        default="operator",
        min_length=1,
        max_length=100
    )

    note: str | None = Field(
        default=None,
        max_length=1000
    )


# =========================================================
# GENERIC HELPERS
# =========================================================

def utc_now_iso():

    return datetime.now(
        timezone.utc
    ).isoformat()


def magnitude_severity(
    magnitude
):

    if magnitude >= 6:
        return "critical"

    if magnitude >= 5:
        return "high"

    if magnitude >= 4:
        return "medium"

    return "low"


def estimated_impact_radius(
    magnitude
):

    if magnitude >= 7:
        return 600

    if magnitude >= 6:
        return 450

    if magnitude >= 5:
        return 300

    if magnitude >= 4:
        return 175

    if magnitude >= 3:
        return 90

    return 45


def milliseconds_to_iso(
    value
):

    if value is None:
        return None

    return datetime.fromtimestamp(
        value / 1000,
        tz=timezone.utc
    ).isoformat()


# =========================================================
# LOAD INFRASTRUCTURE
# =========================================================

def load_locations():

    query = text("""
        SELECT

            id,
            name,
            description,
            infra_type,
            status,
            risk_score,
            severity,

            ST_Y(
                location::geometry
            ) AS latitude,

            ST_X(
                location::geometry
            ) AS longitude

        FROM infrastructure_points

        ORDER BY id;
    """)


    with engine.connect() as conn:

        rows = (
            conn
            .execute(query)
            .fetchall()
        )


    return [

        dict(
            row._mapping
        )

        for row in rows
    ]


# =========================================================
# LOCAL SENSOR INITIALISATION
# =========================================================

def initialise_sensor_telemetry():

    locations = load_locations()


    for asset in locations:

        asset_id = asset["id"]


        if asset_id in sensor_telemetry:
            continue


        sensor_telemetry[
            asset_id
        ] = {

            "asset_id":
                asset_id,

            "name":
                asset["name"],

            "infra_type":
                asset["infra_type"],

            "source":
                "LOCAL_PROJECT",

            "external":
                False,

            "status":
                "online",

            "health":
                random.randint(
                    92,
                    100
                ),

            "cpu_percent":
                round(
                    random.uniform(
                        15,
                        45
                    ),
                    1
                ),

            "temperature_c":
                round(
                    random.uniform(
                        25,
                        45
                    ),
                    1
                ),

            "latency_ms":
                round(
                    random.uniform(
                        5,
                        35
                    ),
                    1
                ),

            "packet_loss_percent":
                round(
                    random.uniform(
                        0,
                        0.5
                    ),
                    2
                ),

            "signal_strength":
                random.randint(
                    80,
                    100
                ),

            "last_updated":
                utc_now_iso()
        }


# =========================================================
# LOCAL SENSOR SIMULATION
# =========================================================

def update_sensor_telemetry():

    initialise_sensor_telemetry()


    for sensor in sensor_telemetry.values():

        sensor[
            "cpu_percent"
        ] += random.uniform(
            -4,
            4
        )


        sensor[
            "cpu_percent"
        ] = round(

            max(
                1,
                min(
                    100,
                    sensor[
                        "cpu_percent"
                    ]
                )
            ),

            1
        )


        sensor[
            "temperature_c"
        ] += random.uniform(
            -1.2,
            1.2
        )


        sensor[
            "temperature_c"
        ] = round(

            max(
                15,
                min(
                    90,
                    sensor[
                        "temperature_c"
                    ]
                )
            ),

            1
        )


        sensor[
            "latency_ms"
        ] += random.uniform(
            -4,
            4
        )


        sensor[
            "latency_ms"
        ] = round(

            max(
                1,
                min(
                    500,
                    sensor[
                        "latency_ms"
                    ]
                )
            ),

            1
        )


        sensor[
            "packet_loss_percent"
        ] += random.uniform(
            -0.10,
            0.10
        )


        sensor[
            "packet_loss_percent"
        ] = round(

            max(
                0,
                min(
                    20,
                    sensor[
                        "packet_loss_percent"
                    ]
                )
            ),

            2
        )


        sensor[
            "signal_strength"
        ] += random.randint(
            -2,
            2
        )


        sensor[
            "signal_strength"
        ] = max(

            0,

            min(
                100,
                sensor[
                    "signal_strength"
                ]
            )
        )


        health = 100


        health -= int(
            sensor[
                "cpu_percent"
            ]
            * 0.10
        )


        health -= int(
            sensor[
                "latency_ms"
            ]
            / 20
        )


        health -= int(
            sensor[
                "packet_loss_percent"
            ]
            * 5
        )


        health = max(
            0,
            min(
                100,
                health
            )
        )


        sensor[
            "health"
        ] = health


        if health >= 80:

            sensor[
                "status"
            ] = "online"

        elif health >= 50:

            sensor[
                "status"
            ] = "degraded"

        else:

            sensor[
                "status"
            ] = "offline"


        sensor[
            "last_updated"
        ] = utc_now_iso()


# =========================================================
# SENSOR BACKGROUND LOOP
# =========================================================

async def sensor_update_loop():

    initialise_sensor_telemetry()


    while True:

        try:

            update_sensor_telemetry()

        except Exception as exc:

            print(
                "Local sensor update error:",
                exc
            )


        await asyncio.sleep(
            SENSOR_UPDATE_SECONDS
        )


# =========================================================
# GET LOCAL SENSOR DATA
# =========================================================

def get_sensor_snapshot():

    initialise_sensor_telemetry()


    return sorted(

        sensor_telemetry.values(),

        key=lambda item:
            item[
                "asset_id"
            ]
    )


# =========================================================
# PHASE 6.4
# SENSOR TELEMETRY HISTORY
# =========================================================

def persist_sensor_history():

    sensors = get_sensor_snapshot()

    if not sensors:
        return 0

    query = text("""
        INSERT INTO sensor_telemetry_history (
            asset_id,
            status,
            health,
            cpu_percent,
            temperature_c,
            latency_ms,
            packet_loss_percent,
            signal_strength,
            source,
            external,
            recorded_at
        )
        VALUES (
            :asset_id,
            :status,
            :health,
            :cpu_percent,
            :temperature_c,
            :latency_ms,
            :packet_loss_percent,
            :signal_strength,
            :source,
            :external,
            NOW()
        );
    """)

    rows = []

    for sensor in sensors:

        rows.append({
            "asset_id":
                int(
                    sensor[
                        "asset_id"
                    ]
                ),

            "status":
                str(
                    sensor.get(
                        "status",
                        "online"
                    )
                ),

            "health":
                float(
                    sensor.get(
                        "health",
                        0
                    )
                ),

            "cpu_percent":
                float(
                    sensor.get(
                        "cpu_percent",
                        0
                    )
                ),

            "temperature_c":
                float(
                    sensor.get(
                        "temperature_c",
                        0
                    )
                ),

            "latency_ms":
                float(
                    sensor.get(
                        "latency_ms",
                        0
                    )
                ),

            "packet_loss_percent":
                float(
                    sensor.get(
                        "packet_loss_percent",
                        0
                    )
                ),

            "signal_strength":
                float(
                    sensor.get(
                        "signal_strength",
                        0
                    )
                ),

            "source":
                "LOCAL_PROJECT",

            "external":
                False
        })

    with engine.begin() as conn:

        conn.execute(
            query,
            rows
        )

    return len(rows)


def cleanup_sensor_history():

    query = text("""
        DELETE FROM sensor_telemetry_history
        WHERE recorded_at <
            NOW()
            -
            (:retention_days * INTERVAL '1 day');
    """)

    with engine.begin() as conn:

        result = conn.execute(
            query,
            {
                "retention_days":
                    TELEMETRY_HISTORY_RETENTION_DAYS
            }
        )

    return result.rowcount


def load_sensor_history(
    asset_id,
    hours=24,
    limit=1000
):

    query = text("""
        SELECT
            id,
            asset_id,
            status,
            health::float AS health,
            cpu_percent::float AS cpu_percent,
            temperature_c::float AS temperature_c,
            latency_ms::float AS latency_ms,
            packet_loss_percent::float AS packet_loss_percent,
            signal_strength::float AS signal_strength,
            source,
            external,
            recorded_at
        FROM sensor_telemetry_history
        WHERE
            asset_id = :asset_id
            AND recorded_at >=
                NOW()
                -
                (:hours * INTERVAL '1 hour')
        ORDER BY recorded_at DESC
        LIMIT :limit;
    """)

    with engine.connect() as conn:

        rows = conn.execute(
            query,
            {
                "asset_id":
                    asset_id,

                "hours":
                    hours,

                "limit":
                    limit
            }
        ).fetchall()

    return [
        dict(
            row._mapping
        )
        for row in rows
    ]


def build_telemetry_summary(
    asset_id,
    hours=24
):

    query = text("""
        SELECT
            COUNT(*)::integer AS samples,
            AVG(health)::float AS avg_health,
            MIN(health)::float AS min_health,
            MAX(health)::float AS max_health,
            AVG(cpu_percent)::float AS avg_cpu_percent,
            MAX(cpu_percent)::float AS max_cpu_percent,
            AVG(temperature_c)::float AS avg_temperature_c,
            MAX(temperature_c)::float AS max_temperature_c,
            AVG(latency_ms)::float AS avg_latency_ms,
            MAX(latency_ms)::float AS max_latency_ms,
            AVG(packet_loss_percent)::float AS avg_packet_loss_percent,
            MAX(packet_loss_percent)::float AS max_packet_loss_percent,
            AVG(signal_strength)::float AS avg_signal_strength,
            MIN(signal_strength)::float AS min_signal_strength,
            MIN(recorded_at) AS first_sample,
            MAX(recorded_at) AS latest_sample
        FROM sensor_telemetry_history
        WHERE
            asset_id = :asset_id
            AND recorded_at >=
                NOW()
                -
                (:hours * INTERVAL '1 hour');
    """)

    with engine.connect() as conn:

        row = conn.execute(
            query,
            {
                "asset_id":
                    asset_id,

                "hours":
                    hours
            }
        ).fetchone()

    return (
        dict(
            row._mapping
        )
        if row
        else {}
    )


async def sensor_history_loop():

    while True:

        try:

            saved = await asyncio.to_thread(
                persist_sensor_history
            )

            print(
                f"Stored {saved} historical "
                "sensor telemetry records"
            )

        except Exception as exc:

            print(
                "Sensor history storage error:",
                exc
            )

        await asyncio.sleep(
            TELEMETRY_HISTORY_INTERVAL_SECONDS
        )


async def sensor_history_cleanup_loop():

    while True:

        try:

            deleted = await asyncio.to_thread(
                cleanup_sensor_history
            )

            if deleted:

                print(
                    f"Removed {deleted} expired "
                    "telemetry history records"
                )

        except Exception as exc:

            print(
                "Sensor history cleanup error:",
                exc
            )

        await asyncio.sleep(
            3600
        )


# =========================================================
# PHASE 6.5
# TELEMETRY TREND ALERTING
# =========================================================

def load_recent_sensor_history(
    asset_id,
    limit=None
):

    sample_limit = (
        int(limit)
        if limit is not None
        else TELEMETRY_ALERT_HISTORY_SAMPLES
    )

    query = text("""
        SELECT
            id,
            asset_id,
            status,
            health::float AS health,
            cpu_percent::float AS cpu_percent,
            temperature_c::float AS temperature_c,
            latency_ms::float AS latency_ms,
            packet_loss_percent::float AS packet_loss_percent,
            signal_strength::float AS signal_strength,
            source,
            external,
            recorded_at
        FROM sensor_telemetry_history
        WHERE asset_id = :asset_id
        ORDER BY recorded_at DESC
        LIMIT :limit;
    """)

    with engine.connect() as conn:

        rows = conn.execute(
            query,
            {
                "asset_id":
                    asset_id,

                "limit":
                    sample_limit
            }
        ).fetchall()

    return [
        dict(
            row._mapping
        )
        for row in rows
    ]


def build_telemetry_alert_snapshot():

    sensors = get_sensor_snapshot()

    alerts = []

    for sensor in sensors:

        asset_id = int(
            sensor[
                "asset_id"
            ]
        )

        history_records = (
            load_recent_sensor_history(
                asset_id,
                TELEMETRY_ALERT_HISTORY_SAMPLES
            )
        )

        alerts.extend(
            evaluate_asset_telemetry(
                sensor=sensor,
                history_records=history_records,
                window_minutes=TELEMETRY_ALERT_WINDOW_MINUTES
            )
        )

    severity_priority = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1
    }

    alerts.sort(
        key=lambda item:
            severity_priority.get(
                item.get(
                    "severity",
                    "low"
                ),
                0
            ),
        reverse=True
    )

    return {
        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "window_minutes":
            TELEMETRY_ALERT_WINDOW_MINUTES,

        "history_samples":
            TELEMETRY_ALERT_HISTORY_SAMPLES,

        "summary":
            build_telemetry_alert_summary(
                alerts
            ),

        "alerts":
            alerts,

        "generated_at":
            utc_now_iso()
    }


# =========================================================
# PHASE 6.6
# TELEMETRY ALERT PERSISTENCE + LIFECYCLE
# =========================================================

def add_telemetry_alert_history_event(
    conn,
    alert_id,
    action,
    from_status,
    to_status,
    severity,
    note=None,
    changed_by="SYSTEM"
):

    conn.execute(
        text("""
            INSERT INTO telemetry_alert_history (
                alert_id,
                action,
                from_status,
                to_status,
                severity,
                note,
                changed_by,
                changed_at
            )
            VALUES (
                :alert_id,
                :action,
                :from_status,
                :to_status,
                :severity,
                :note,
                :changed_by,
                NOW()
            );
        """),
        {
            "alert_id":
                alert_id,

            "action":
                action,

            "from_status":
                from_status,

            "to_status":
                to_status,

            "severity":
                severity,

            "note":
                note,

            "changed_by":
                changed_by
        }
    )


def persist_telemetry_alerts(
    alerts
):

    if alerts is None:
        alerts = []

    persisted = 0

    with engine.begin() as conn:

        for alert in alerts:

            alert_key = str(
                alert[
                    "alert_id"
                ]
            )

            existing_row = conn.execute(
                text("""
                    SELECT
                        id,
                        status,
                        severity
                    FROM telemetry_alerts
                    WHERE alert_key = :alert_key
                    FOR UPDATE;
                """),
                {
                    "alert_key":
                        alert_key
                }
            ).fetchone()

            if existing_row is None:

                inserted = conn.execute(
                    text("""
                        INSERT INTO telemetry_alerts (
                            alert_key,
                            asset_id,
                            asset_name,
                            metric,
                            metric_label,
                            alert_kind,
                            severity,
                            status,
                            message,
                            latest_value,
                            reference_value,
                            threshold,
                            delta,
                            unit,
                            source,
                            external,
                            first_seen_at,
                            last_seen_at
                        )
                        VALUES (
                            :alert_key,
                            :asset_id,
                            :asset_name,
                            :metric,
                            :metric_label,
                            :alert_kind,
                            :severity,
                            'active',
                            :message,
                            :latest_value,
                            :reference_value,
                            :threshold,
                            :delta,
                            :unit,
                            'LOCAL_PROJECT',
                            FALSE,
                            NOW(),
                            NOW()
                        )
                        RETURNING id;
                    """),
                    {
                        "alert_key":
                            alert_key,

                        "asset_id":
                            int(
                                alert[
                                    "asset_id"
                                ]
                            ),

                        "asset_name":
                            str(
                                alert.get(
                                    "asset_name",
                                    ""
                                )
                            ),

                        "metric":
                            str(
                                alert.get(
                                    "metric",
                                    ""
                                )
                            ),

                        "metric_label":
                            str(
                                alert.get(
                                    "metric_label",
                                    ""
                                )
                            ),

                        "alert_kind":
                            str(
                                alert.get(
                                    "alert_kind",
                                    "threshold"
                                )
                            ),

                        "severity":
                            str(
                                alert.get(
                                    "severity",
                                    "low"
                                )
                            ),

                        "message":
                            str(
                                alert.get(
                                    "message",
                                    ""
                                )
                            ),

                        "latest_value":
                            alert.get(
                                "latest_value"
                            ),

                        "reference_value":
                            alert.get(
                                "reference_value"
                            ),

                        "threshold":
                            alert.get(
                                "threshold"
                            ),

                        "delta":
                            alert.get(
                                "delta"
                            ),

                        "unit":
                            str(
                                alert.get(
                                    "unit",
                                    ""
                                )
                            )
                    }
                ).fetchone()

                alert_id = inserted[
                    0
                ]

                add_telemetry_alert_history_event(
                    conn=conn,
                    alert_id=alert_id,
                    action="CREATED",
                    from_status=None,
                    to_status="active",
                    severity=str(
                        alert.get(
                            "severity",
                            "low"
                        )
                    ),
                    note="Telemetry alert created by detection engine",
                    changed_by="SYSTEM"
                )

                persisted += 1

                continue

            existing = dict(
                existing_row._mapping
            )

            previous_status = str(
                existing[
                    "status"
                ]
            )

            previous_severity = str(
                existing[
                    "severity"
                ]
            )

            new_severity = str(
                alert.get(
                    "severity",
                    previous_severity
                )
            )

            new_status = (
                "active"
                if previous_status
                ==
                "resolved"
                else previous_status
            )

            conn.execute(
                text("""
                    UPDATE telemetry_alerts
                    SET
                        asset_name = :asset_name,
                        metric = :metric,
                        metric_label = :metric_label,
                        alert_kind = :alert_kind,
                        severity = :severity,
                        status = :status,
                        message = :message,
                        latest_value = :latest_value,
                        reference_value = :reference_value,
                        threshold = :threshold,
                        delta = :delta,
                        unit = :unit,
                        last_seen_at = NOW(),
                        resolved_at =
                            CASE
                                WHEN :reopened
                                THEN NULL
                                ELSE resolved_at
                            END,
                        resolved_by =
                            CASE
                                WHEN :reopened
                                THEN NULL
                                ELSE resolved_by
                            END,
                        resolution_note =
                            CASE
                                WHEN :reopened
                                THEN NULL
                                ELSE resolution_note
                            END
                    WHERE id = :alert_id;
                """),
                {
                    "alert_id":
                        existing[
                            "id"
                        ],

                    "asset_name":
                        str(
                            alert.get(
                                "asset_name",
                                ""
                            )
                        ),

                    "metric":
                        str(
                            alert.get(
                                "metric",
                                ""
                            )
                        ),

                    "metric_label":
                        str(
                            alert.get(
                                "metric_label",
                                ""
                            )
                        ),

                    "alert_kind":
                        str(
                            alert.get(
                                "alert_kind",
                                "threshold"
                            )
                        ),

                    "severity":
                        new_severity,

                    "status":
                        new_status,

                    "message":
                        str(
                            alert.get(
                                "message",
                                ""
                            )
                        ),

                    "latest_value":
                        alert.get(
                            "latest_value"
                        ),

                    "reference_value":
                        alert.get(
                            "reference_value"
                        ),

                    "threshold":
                        alert.get(
                            "threshold"
                        ),

                    "delta":
                        alert.get(
                            "delta"
                        ),

                    "unit":
                        str(
                            alert.get(
                                "unit",
                                ""
                            )
                        ),

                    "reopened":
                        previous_status
                        ==
                        "resolved"
                }
            )

            if previous_status == "resolved":

                add_telemetry_alert_history_event(
                    conn=conn,
                    alert_id=existing[
                        "id"
                    ],
                    action="REOPENED",
                    from_status="resolved",
                    to_status="active",
                    severity=new_severity,
                    note="Telemetry condition became active again",
                    changed_by="SYSTEM"
                )

            if (
                previous_severity
                !=
                new_severity
            ):

                add_telemetry_alert_history_event(
                    conn=conn,
                    alert_id=existing[
                        "id"
                    ],
                    action="SEVERITY_CHANGED",
                    from_status=new_status,
                    to_status=new_status,
                    severity=new_severity,
                    note=(
                        "Severity changed from "
                        f"{previous_severity} "
                        f"to {new_severity}"
                    ),
                    changed_by="SYSTEM"
                )

            persisted += 1

    return persisted


def auto_resolve_missing_telemetry_alerts(
    active_alerts
):

    active_keys = {
        str(
            alert[
                "alert_id"
            ]
        )
        for alert in (
            active_alerts
            or []
        )
    }

    resolved = 0

    with engine.begin() as conn:

        rows = conn.execute(
            text("""
                SELECT
                    id,
                    alert_key,
                    status,
                    severity
                FROM telemetry_alerts
                WHERE status IN (
                    'active',
                    'acknowledged'
                )
                FOR UPDATE;
            """)
        ).fetchall()

        for row in rows:

            alert = dict(
                row._mapping
            )

            if (
                alert[
                    "alert_key"
                ]
                in
                active_keys
            ):

                continue

            previous_status = str(
                alert[
                    "status"
                ]
            )

            conn.execute(
                text("""
                    UPDATE telemetry_alerts
                    SET
                        status = 'resolved',
                        resolved_at = NOW(),
                        resolved_by = 'SYSTEM',
                        resolution_note =
                            'Metric returned to normal range'
                    WHERE id = :alert_id;
                """),
                {
                    "alert_id":
                        alert[
                            "id"
                        ]
                }
            )

            add_telemetry_alert_history_event(
                conn=conn,
                alert_id=alert[
                    "id"
                ],
                action="AUTO_RESOLVED",
                from_status=previous_status,
                to_status="resolved",
                severity=str(
                    alert[
                        "severity"
                    ]
                ),
                note="Metric returned to normal range",
                changed_by="SYSTEM"
            )

            resolved += 1

    return resolved


def load_persisted_telemetry_alerts(
    status=None,
    severity=None,
    asset_id=None,
    limit=100
):

    query = text("""
        SELECT
            id,
            alert_key,
            asset_id,
            asset_name,
            metric,
            metric_label,
            alert_kind,
            severity,
            status,
            message,
            latest_value::float AS latest_value,
            reference_value::float AS reference_value,
            threshold::float AS threshold,
            delta::float AS delta,
            unit,
            source,
            external,
            first_seen_at,
            last_seen_at,
            acknowledged_at,
            resolved_at,
            acknowledged_by,
            resolved_by,
            resolution_note
        FROM telemetry_alerts
        WHERE
            (
                :status IS NULL
                OR status = :status
            )
            AND (
                :severity IS NULL
                OR severity = :severity
            )
            AND (
                :asset_id IS NULL
                OR asset_id = :asset_id
            )
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 4
                WHEN 'high' THEN 3
                WHEN 'medium' THEN 2
                ELSE 1
            END DESC,
            last_seen_at DESC
        LIMIT :limit;
    """)

    with engine.connect() as conn:

        rows = conn.execute(
            query,
            {
                "status":
                    status,

                "severity":
                    severity,

                "asset_id":
                    asset_id,

                "limit":
                    limit
            }
        ).fetchall()

    return [
        dict(
            row._mapping
        )
        for row in rows
    ]


def load_telemetry_alert_history_events(
    alert_id
):

    query = text("""
        SELECT
            id,
            alert_id,
            action,
            from_status,
            to_status,
            severity,
            note,
            changed_by,
            changed_at
        FROM telemetry_alert_history
        WHERE alert_id = :alert_id
        ORDER BY changed_at ASC;
    """)

    with engine.connect() as conn:

        rows = conn.execute(
            query,
            {
                "alert_id":
                    alert_id
            }
        ).fetchall()

    return [
        dict(
            row._mapping
        )
        for row in rows
    ]


def update_telemetry_alert_status(
    alert_id,
    target_status,
    changed_by,
    note=None
):

    if target_status not in {
        "acknowledged",
        "resolved"
    }:

        raise ValueError(
            "Unsupported telemetry alert status"
        )

    with engine.begin() as conn:

        row = conn.execute(
            text("""
                SELECT
                    id,
                    status,
                    severity
                FROM telemetry_alerts
                WHERE id = :alert_id
                FOR UPDATE;
            """),
            {
                "alert_id":
                    alert_id
            }
        ).fetchone()

        if row is None:

            return None

        alert = dict(
            row._mapping
        )

        previous_status = str(
            alert[
                "status"
            ]
        )

        if (
            target_status
            ==
            "acknowledged"
            and
            previous_status
            ==
            "resolved"
        ):

            raise ValueError(
                "Resolved alerts cannot be acknowledged"
            )

        if (
            previous_status
            ==
            target_status
        ):

            current = conn.execute(
                text("""
                    SELECT *
                    FROM telemetry_alerts
                    WHERE id = :alert_id;
                """),
                {
                    "alert_id":
                        alert_id
                }
            ).fetchone()

            return dict(
                current._mapping
            )

        if target_status == "acknowledged":

            conn.execute(
                text("""
                    UPDATE telemetry_alerts
                    SET
                        status = 'acknowledged',
                        acknowledged_at = NOW(),
                        acknowledged_by = :changed_by
                    WHERE id = :alert_id;
                """),
                {
                    "alert_id":
                        alert_id,

                    "changed_by":
                        changed_by
                }
            )

            action = "ACKNOWLEDGED"

        else:

            conn.execute(
                text("""
                    UPDATE telemetry_alerts
                    SET
                        status = 'resolved',
                        resolved_at = NOW(),
                        resolved_by = :changed_by,
                        resolution_note = :note
                    WHERE id = :alert_id;
                """),
                {
                    "alert_id":
                        alert_id,

                    "changed_by":
                        changed_by,

                    "note":
                        note
                }
            )

            action = "MANUALLY_RESOLVED"

        add_telemetry_alert_history_event(
            conn=conn,
            alert_id=alert_id,
            action=action,
            from_status=previous_status,
            to_status=target_status,
            severity=str(
                alert[
                    "severity"
                ]
            ),
            note=note,
            changed_by=changed_by
        )

        updated = conn.execute(
            text("""
                SELECT
                    id,
                    alert_key,
                    asset_id,
                    asset_name,
                    metric,
                    metric_label,
                    alert_kind,
                    severity,
                    status,
                    message,
                    latest_value::float AS latest_value,
                    reference_value::float AS reference_value,
                    threshold::float AS threshold,
                    delta::float AS delta,
                    unit,
                    source,
                    external,
                    first_seen_at,
                    last_seen_at,
                    acknowledged_at,
                    resolved_at,
                    acknowledged_by,
                    resolved_by,
                    resolution_note
                FROM telemetry_alerts
                WHERE id = :alert_id;
            """),
            {
                "alert_id":
                    alert_id
            }
        ).fetchone()

        return dict(
            updated._mapping
        )


async def telemetry_alert_persistence_loop():

    while True:

        try:

            snapshot = (
                await asyncio.to_thread(
                    build_telemetry_alert_snapshot
                )
            )

            active_alerts = snapshot[
                "alerts"
            ]

            persisted = (
                await asyncio.to_thread(
                    persist_telemetry_alerts,
                    active_alerts
                )
            )

            resolved = (
                await asyncio.to_thread(
                    auto_resolve_missing_telemetry_alerts,
                    active_alerts
                )
            )

            if (
                persisted
                or
                resolved
            ):

                print(
                    "Telemetry alert persistence: "
                    f"{persisted} active, "
                    f"{resolved} resolved"
                )

        except Exception as exc:

            print(
                "Telemetry alert persistence error:",
                exc
            )

        await asyncio.sleep(
            TELEMETRY_ALERT_PERSISTENCE_SECONDS
        )


# =========================================================
# PHASE 6.3 ALERT SNAPSHOT
# =========================================================

def build_alert_snapshot():

    sensors = get_sensor_snapshot()

    alerts = evaluate_all_sensors(
        sensors
    )

    health_summary = (
        calculate_sensor_health_summary(
            sensors
        )
    )

    alert_summary = (
        calculate_alert_summary(
            alerts
        )
    )

    return {

        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "sensor_health":
            health_summary,

        "alert_summary":
            alert_summary,

        "alerts":
            alerts
    }


# =========================================================
# USGS READ-ONLY FEED
# =========================================================

def fetch_usgs_earthquakes(
    force=False
):

    now = time.time()


    cache_age = (

        now
        -
        usgs_cache[
            "fetched_at"
        ]

        if usgs_cache[
            "fetched_at"
        ]

        else None
    )


    if (

        not force

        and usgs_cache[
            "events"
        ]

        and cache_age
        is not None

        and cache_age
        <
        USGS_CACHE_SECONDS

    ):

        return {

            "source":
                "USGS",

            "live":
                True,

            "cache":
                True,

            "read_only":
                True,

            "generated_at":
                usgs_cache[
                    "generated_at"
                ],

            "events":
                usgs_cache[
                    "events"
                ],

            "error":
                None
        }


    request = Request(

        USGS_FEED_URL,

        headers={

            "User-Agent":
                "GeoInfrastructureMonitoring/6.2"
        }
    )


    try:

        with urlopen(
            request,
            timeout=15
        ) as response:

            payload = json.loads(

                response
                .read()
                .decode(
                    "utf-8"
                )
            )


        events = []


        for feature in payload.get(
            "features",
            []
        ):

            properties = (
                feature.get(
                    "properties"
                )
                or {}
            )


            geometry = (
                feature.get(
                    "geometry"
                )
                or {}
            )


            coordinates = (
                geometry.get(
                    "coordinates"
                )
                or []
            )


            if len(
                coordinates
            ) < 2:

                continue


            magnitude = (
                properties.get(
                    "mag"
                )
            )


            if magnitude is None:

                continue


            magnitude = float(
                magnitude
            )


            longitude = float(
                coordinates[0]
            )


            latitude = float(
                coordinates[1]
            )


            depth = (

                float(
                    coordinates[2]
                )

                if len(
                    coordinates
                )
                >= 3

                else None
            )


            events.append({

                "id":
                    feature.get(
                        "id"
                    ),

                "event_type":
                    "earthquake",

                "title":
                    properties.get(
                        "title"
                    )
                    or
                    "Earthquake",

                "place":
                    properties.get(
                        "place"
                    )
                    or
                    "Unknown",

                "magnitude":
                    magnitude,

                "depth_km":
                    depth,

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "timestamp":
                    milliseconds_to_iso(
                        properties.get(
                            "time"
                        )
                    ),

                "updated_at":
                    milliseconds_to_iso(
                        properties.get(
                            "updated"
                        )
                    ),

                "severity":
                    magnitude_severity(
                        magnitude
                    ),

                "radius_km":
                    estimated_impact_radius(
                        magnitude
                    ),

                "source":
                    "USGS",

                "live":
                    True,

                "read_only":
                    True,

                "simulated":
                    False
            })


        generated_at = utc_now_iso()


        metadata = payload.get(
            "metadata",
            {}
        )


        if metadata.get(
            "generated"
        ):

            generated_at = (
                milliseconds_to_iso(
                    metadata[
                        "generated"
                    ]
                )
            )


        usgs_cache[
            "events"
        ] = events


        usgs_cache[
            "fetched_at"
        ] = now


        usgs_cache[
            "generated_at"
        ] = generated_at


        usgs_cache[
            "error"
        ] = None


        return {

            "source":
                "USGS",

            "live":
                True,

            "cache":
                False,

            "read_only":
                True,

            "generated_at":
                generated_at,

            "events":
                events,

            "error":
                None
        }


    except (
        URLError,
        HTTPError,
        TimeoutError,
        json.JSONDecodeError,
        OSError
    ) as exc:

        usgs_cache[
            "error"
        ] = str(
            exc
        )


        return {

            "source":
                "USGS",

            "live":
                False,

            "cache":
                True,

            "read_only":
                True,

            "generated_at":
                usgs_cache[
                    "generated_at"
                ],

            "events":
                usgs_cache[
                    "events"
                ],

            "error":
                str(
                    exc
                )
        }


# =========================================================
# TEST EVENT CREATION
# =========================================================

def load_asset_by_id(
    asset_id
):

    locations = load_locations()


    for asset in locations:

        if (
            asset[
                "id"
            ]
            ==
            asset_id
        ):

            return asset


    return None


def create_test_event_object(
    request_data
):

    asset = load_asset_by_id(
        request_data.asset_id
    )


    if asset is None:

        raise HTTPException(
            status_code=404,
            detail="Infrastructure asset not found"
        )


    radius = (

        request_data.radius_km

        if request_data.radius_km
        is not None

        else estimated_impact_radius(
            request_data.magnitude
        )
    )


    return {

        "id":
            "TEST-"
            +
            uuid.uuid4()
            .hex[
                :8
            ]
            .upper(),

        "event_type":
            "earthquake",

        "title":
            (
                "SIMULATED TEST "
                f"M{request_data.magnitude:.1f} "
                "Earthquake"
            ),

        "place":
            (
                "Internal test near "
                +
                asset[
                    "name"
                ]
            ),

        "magnitude":
            float(
                request_data.magnitude
            ),

        "depth_km":
            10,

        "latitude":
            float(
                asset[
                    "latitude"
                ]
            )
            +
            request_data.latitude_offset,

        "longitude":
            float(
                asset[
                    "longitude"
                ]
            )
            +
            request_data.longitude_offset,

        "timestamp":
            utc_now_iso(),

        "updated_at":
            utc_now_iso(),

        "severity":
            magnitude_severity(
                request_data.magnitude
            ),

        "radius_km":
            float(
                radius
            ),

        "source":
            "TEST",

        "live":
            False,

        "simulated":
            True,

        "external":
            False,

        "project_only":
            True,

        "target_asset_id":
            asset[
                "id"
            ],

        "target_asset_name":
            asset[
                "name"
            ]
    }


# =========================================================
# ACTIVE EVENTS
# =========================================================

def build_active_event_feed():

    usgs_feed = (
        fetch_usgs_earthquakes()
    )


    events = list(
        usgs_feed[
            "events"
        ]
    )


    test_event = (
        test_event_state[
            "event"
        ]
    )


    if test_event:

        events.append(
            test_event
        )


    return {

        "source":
            (
                "USGS+LOCAL_TEST"

                if test_event

                else "USGS"
            ),

        "live":
            usgs_feed[
                "live"
            ],

        "usgs_read_only":
            True,

        "local_sensor_mode":
            SENSOR_MODE,

        "generated_at":
            usgs_feed[
                "generated_at"
            ],

        "usgs_event_count":
            len(
                usgs_feed[
                    "events"
                ]
            ),

        "test_event_count":
            (
                1
                if test_event
                else 0
            ),

        "event_count":
            len(
                events
            ),

        "events":
            events
    }


# =========================================================
# EXPOSURE CALCULATION
# =========================================================

def calculate_exposure_score(
    magnitude,
    distance_km,
    radius_km
):

    magnitude_component = min(

        70,

        max(
            10,

            20
            +
            (
                magnitude
                - 2.5
            )
            * 18
        )
    )


    proximity = max(

        0,

        1
        -
        (
            distance_km
            /
            radius_km
        )
    )


    score = round(

        magnitude_component

        +

        proximity
        * 30
    )


    return int(

        max(
            0,
            min(
                100,
                score
            )
        )
    )


def score_to_severity(
    score
):

    if score >= 75:
        return "critical"

    if score >= 55:
        return "high"

    if score >= 30:
        return "medium"

    return "low"


# =========================================================
# POSTGIS CORRELATION
# =========================================================

def infrastructure_in_event_radius(
    event
):

    query = text("""
        SELECT

            id,
            name,
            description,
            infra_type,
            status,

            ST_Y(
                location::geometry
            ) AS latitude,

            ST_X(
                location::geometry
            ) AS longitude,

            ST_Distance(

                location::geography,

                ST_SetSRID(
                    ST_MakePoint(
                        :longitude,
                        :latitude
                    ),
                    4326
                )::geography

            ) AS distance_meters

        FROM infrastructure_points

        WHERE

            ST_DWithin(

                location::geography,

                ST_SetSRID(
                    ST_MakePoint(
                        :longitude,
                        :latitude
                    ),
                    4326
                )::geography,

                :radius_meters
            )

        ORDER BY distance_meters;
    """)


    with engine.connect() as conn:

        rows = (

            conn.execute(

                query,

                {

                    "longitude":
                        event[
                            "longitude"
                        ],

                    "latitude":
                        event[
                            "latitude"
                        ],

                    "radius_meters":
                        event[
                            "radius_km"
                        ]
                        * 1000
                }

            )
            .fetchall()
        )


    assets = []


    for row in rows:

        asset = dict(
            row._mapping
        )


        distance_km = (
            float(
                asset[
                    "distance_meters"
                ]
            )
            /
            1000
        )


        score = calculate_exposure_score(

            event[
                "magnitude"
            ],

            distance_km,

            event[
                "radius_km"
            ]
        )


        asset[
            "distance_meters"
        ] = float(
            asset[
                "distance_meters"
            ]
        )


        asset[
            "distance_km"
        ] = round(
            distance_km,
            2
        )


        asset[
            "estimated_risk_score"
        ] = score


        asset[
            "estimated_severity"
        ] = score_to_severity(
            score
        )


        assets.append(
            asset
        )


    return assets


# =========================================================
# IMPACT ANALYSIS
# =========================================================

def build_impact_analysis(
    events
):

    results = []


    for event in events:

        assets = (
            infrastructure_in_event_radius(
                event
            )
        )


        results.append({

            **event,

            "affected_count":
                len(
                    assets
                ),

            "affected_assets":
                assets
        })


    return results


# =========================================================
# RISK SNAPSHOT
# =========================================================

def build_asset_risk_snapshot(
    impacts
):

    risks = {}


    for event in impacts:

        for asset in event[
            "affected_assets"
        ]:

            risk = {

                "id":
                    asset[
                        "id"
                    ],

                "name":
                    asset[
                        "name"
                    ],

                "infra_type":
                    asset[
                        "infra_type"
                    ],

                "status":
                    asset[
                        "status"
                    ],

                "latitude":
                    asset[
                        "latitude"
                    ],

                "longitude":
                    asset[
                        "longitude"
                    ],

                "risk_score":
                    asset[
                        "estimated_risk_score"
                    ],

                "severity":
                    asset[
                        "estimated_severity"
                    ],

                "event_id":
                    event[
                        "id"
                    ],

                "event_source":
                    event[
                        "source"
                    ],

                "simulated":
                    event.get(
                        "simulated",
                        False
                    ),

                "magnitude":
                    event[
                        "magnitude"
                    ],

                "distance_km":
                    asset[
                        "distance_km"
                    ]
            }


            current = risks.get(
                asset[
                    "id"
                ]
            )


            if (

                current is None

                or risk[
                    "risk_score"
                ]
                >
                current[
                    "risk_score"
                ]

            ):

                risks[
                    asset[
                        "id"
                    ]
                ] = risk


    return sorted(

        risks.values(),

        key=lambda item:
            item[
                "risk_score"
            ],

        reverse=True
    )


# =========================================================
# DATABASE RISK UPDATE
# =========================================================

def persist_risk_snapshot(
    risks
):

    with engine.begin() as conn:

        conn.execute(
            text("""
                UPDATE infrastructure_points

                SET
                    risk_score = 0,
                    severity = 'low';
            """)
        )


        for asset in risks:

            conn.execute(

                text("""
                    UPDATE infrastructure_points

                    SET
                        risk_score = :risk_score,
                        severity = :severity

                    WHERE
                        id = :id;
                """),

                {

                    "id":
                        asset[
                            "id"
                        ],

                    "risk_score":
                        asset[
                            "risk_score"
                        ],

                    "severity":
                        asset[
                            "severity"
                        ]
                }
            )


# =========================================================
# LIVE SNAPSHOT
# =========================================================

def build_live_snapshot():

    feed = (
        build_active_event_feed()
    )


    impacts = (
        build_impact_analysis(
            feed[
                "events"
            ]
        )
    )


    risk = (
        build_asset_risk_snapshot(
            impacts
        )
    )


    return {

        "feed":
            feed,

        "impacts":
            impacts,

        "risk":
            risk
    }


# =========================================================
# RISK BACKGROUND LOOP
# =========================================================

async def risk_update_loop():

    while True:

        try:

            snapshot = (
                await asyncio.to_thread(
                    build_live_snapshot
                )
            )


            await asyncio.to_thread(

                persist_risk_snapshot,

                snapshot[
                    "risk"
                ]
            )


        except Exception as exc:

            print(
                "Risk update error:",
                exc
            )


        await asyncio.sleep(
            USGS_CACHE_SECONDS
        )


# =========================================================
# APPLICATION LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(
    app: FastAPI
):

    sensor_task = asyncio.create_task(
        sensor_update_loop()
    )


    history_task = asyncio.create_task(
        sensor_history_loop()
    )


    history_cleanup_task = asyncio.create_task(
        sensor_history_cleanup_loop()
    )


    telemetry_alert_persistence_task = (
        asyncio.create_task(
            telemetry_alert_persistence_loop()
        )
    )


    risk_task = asyncio.create_task(
        risk_update_loop()
    )


    yield


    sensor_task.cancel()

    history_task.cancel()

    history_cleanup_task.cancel()

    telemetry_alert_persistence_task.cancel()

    risk_task.cancel()


    for task in [
        sensor_task,
        history_task,
        history_cleanup_task,
        telemetry_alert_persistence_task,
        risk_task
    ]:

        try:

            await task

        except asyncio.CancelledError:

            pass


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(

    title=(
        "Infrastructure Situational Awareness Platform"
    ),

    version="6.6.0",

    description=(
        "Live infrastructure monitoring with "
        "project-local sensor telemetry, sensor health alerts, "
        "historical telemetry, trend alerting, persistent alert lifecycle, "
        "PostGIS, USGS read-only earthquake data and WebSockets."
    ),

    lifespan=lifespan
)


app.add_middleware(

    CORSMiddleware,

    allow_origins=[
        "*"
    ],

    allow_credentials=True,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ]
)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {

        "project":
            "Infrastructure Situational Awareness Platform",

        "version":
            "6.6.0",

        "sensor_mode":
            SENSOR_MODE,

        "sensor_data_external":
            False,

        "usgs_mode":
            "READ_ONLY",

        "phase":
            "6.6_ALERT_PERSISTENCE",

        "telemetry_history":
            True,

        "history_interval_seconds":
            TELEMETRY_HISTORY_INTERVAL_SECONDS,

        "history_retention_days":
            TELEMETRY_HISTORY_RETENTION_DAYS,


        "telemetry_alerting":
            True,

        "telemetry_alert_window_minutes":
            TELEMETRY_ALERT_WINDOW_MINUTES,


        "telemetry_alert_persistence":
            True,

        "telemetry_alert_persistence_seconds":
            TELEMETRY_ALERT_PERSISTENCE_SECONDS,

        "status":
            "running"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    database = "connected"


    try:

        with engine.connect() as conn:

            conn.execute(
                text(
                    "SELECT 1"
                )
            )


    except Exception:

        database = "disconnected"


    return {

        "status":
            (
                "healthy"
                if database
                ==
                "connected"
                else "degraded"
            ),

        "database":
            database,

        "sensor_mode":
            SENSOR_MODE,

        "sensor_external_push":
            False,

        "usgs":
            "read-only",

        "local_sensor_count":
            len(
                sensor_telemetry
            )
    }


# =========================================================
# LOCATIONS
# =========================================================

@app.get("/locations")
def locations():

    return load_locations()


# =========================================================
# LOCAL SENSOR TELEMETRY
# =========================================================

@app.get("/sensor-telemetry")
def sensor_status():

    return {

        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "update_interval_seconds":
            SENSOR_UPDATE_SECONDS,

        "count":
            len(
                get_sensor_snapshot()
            ),

        "sensors":
            get_sensor_snapshot()
    }


# =========================================================
# SINGLE SENSOR
# =========================================================

@app.get(
    "/sensor-telemetry/{asset_id}"
)
def sensor_by_id(
    asset_id: int
):

    initialise_sensor_telemetry()


    sensor = (
        sensor_telemetry.get(
            asset_id
        )
    )


    if sensor is None:

        raise HTTPException(
            status_code=404,
            detail="Sensor not found"
        )


    return sensor


# =========================================================
# PHASE 6.4
# TELEMETRY HISTORY API
# =========================================================

@app.get(
    "/telemetry-history/{asset_id}"
)
def telemetry_history(
    asset_id: int,

    hours: int = Query(
        default=24,
        ge=1,
        le=168
    ),

    limit: int = Query(
        default=1000,
        ge=1,
        le=5000
    )
):

    asset = load_asset_by_id(
        asset_id
    )

    if asset is None:

        raise HTTPException(
            status_code=404,
            detail="Infrastructure asset not found"
        )

    records = load_sensor_history(
        asset_id=asset_id,
        hours=hours,
        limit=limit
    )

    return {

        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "asset_id":
            asset_id,

        "asset_name":
            asset[
                "name"
            ],

        "hours":
            hours,

        "count":
            len(
                records
            ),

        "records":
            records
    }


@app.get(
    "/telemetry-summary/{asset_id}"
)
def telemetry_summary(
    asset_id: int,

    hours: int = Query(
        default=24,
        ge=1,
        le=168
    )
):

    asset = load_asset_by_id(
        asset_id
    )

    if asset is None:

        raise HTTPException(
            status_code=404,
            detail="Infrastructure asset not found"
        )

    summary = build_telemetry_summary(
        asset_id=asset_id,
        hours=hours
    )

    return {

        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "asset_id":
            asset_id,

        "asset_name":
            asset[
                "name"
            ],

        "hours":
            hours,

        "summary":
            summary
    }


# =========================================================
# PHASE 6.5
# TELEMETRY ALERTING API
# =========================================================

@app.get(
    "/telemetry-alerts"
)
def telemetry_alerts(
    severity: str | None = Query(
        default=None
    )
):

    snapshot = (
        build_telemetry_alert_snapshot()
    )

    result_alerts = snapshot[
        "alerts"
    ]

    if severity:

        normalized = (
            severity
            .strip()
            .lower()
        )

        if normalized not in {
            "critical",
            "high",
            "medium",
            "low"
        }:

            raise HTTPException(
                status_code=400,
                detail="Invalid severity filter"
            )

        result_alerts = [
            alert
            for alert in result_alerts
            if alert.get(
                "severity"
            )
            ==
            normalized
        ]

    return {
        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "window_minutes":
            snapshot[
                "window_minutes"
            ],

        "history_samples":
            snapshot[
                "history_samples"
            ],

        "count":
            len(
                result_alerts
            ),

        "summary":
            snapshot[
                "summary"
            ],

        "alerts":
            result_alerts,

        "generated_at":
            snapshot[
                "generated_at"
            ]
    }


@app.get(
    "/telemetry-alerts/{asset_id}"
)
def telemetry_alerts_by_asset(
    asset_id: int
):

    asset = load_asset_by_id(
        asset_id
    )

    if asset is None:

        raise HTTPException(
            status_code=404,
            detail="Infrastructure asset not found"
        )

    snapshot = (
        build_telemetry_alert_snapshot()
    )

    result_alerts = [
        alert
        for alert in snapshot[
            "alerts"
        ]
        if int(
            alert.get(
                "asset_id",
                0
            )
        )
        ==
        asset_id
    ]

    return {
        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "asset_id":
            asset_id,

        "asset_name":
            asset[
                "name"
            ],

        "count":
            len(
                result_alerts
            ),

        "alerts":
            result_alerts,

        "generated_at":
            snapshot[
                "generated_at"
            ]
    }


# =========================================================
# PHASE 6.6
# PERSISTED TELEMETRY ALERT API
# =========================================================

@app.get(
    "/telemetry-alert-history"
)
def telemetry_alert_history(
    status: str | None = Query(
        default=None
    ),

    severity: str | None = Query(
        default=None
    ),

    asset_id: int | None = Query(
        default=None,
        ge=1
    ),

    limit: int = Query(
        default=100,
        ge=1,
        le=1000
    )
):

    allowed_statuses = {
        "active",
        "acknowledged",
        "resolved"
    }

    allowed_severities = {
        "critical",
        "high",
        "medium",
        "low"
    }

    if (
        status
        is not None
        and
        status not in allowed_statuses
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid alert status"
        )

    if (
        severity
        is not None
        and
        severity not in allowed_severities
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid severity"
        )

    alerts = (
        load_persisted_telemetry_alerts(
            status=status,
            severity=severity,
            asset_id=asset_id,
            limit=limit
        )
    )

    return {
        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "count":
            len(
                alerts
            ),

        "alerts":
            alerts
    }


@app.get(
    "/telemetry-alert-history/{alert_id}/events"
)
def telemetry_alert_history_events(
    alert_id: int
):

    alert_rows = (
        load_persisted_telemetry_alerts(
            limit=1000
        )
    )

    exists = any(
        int(
            item[
                "id"
            ]
        )
        ==
        alert_id
        for item in alert_rows
    )

    if not exists:

        raise HTTPException(
            status_code=404,
            detail="Persisted telemetry alert not found"
        )

    history = (
        load_telemetry_alert_history_events(
            alert_id
        )
    )

    return {
        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "alert_id":
            alert_id,

        "count":
            len(
                history
            ),

        "history":
            history
    }


@app.post(
    "/telemetry-alerts/{alert_id}/acknowledge"
)
def acknowledge_telemetry_alert(
    alert_id: int,
    request_data: AlertActionRequest
):

    try:

        alert = (
            update_telemetry_alert_status(
                alert_id=alert_id,
                target_status="acknowledged",
                changed_by=request_data.changed_by,
                note=request_data.note
            )
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=409,
            detail=str(
                exc
            )
        )

    if alert is None:

        raise HTTPException(
            status_code=404,
            detail="Persisted telemetry alert not found"
        )

    return {
        "message":
            "Telemetry alert acknowledged",

        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "alert":
            alert
    }


@app.post(
    "/telemetry-alerts/{alert_id}/resolve"
)
def resolve_telemetry_alert(
    alert_id: int,
    request_data: AlertActionRequest
):

    try:

        alert = (
            update_telemetry_alert_status(
                alert_id=alert_id,
                target_status="resolved",
                changed_by=request_data.changed_by,
                note=request_data.note
            )
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=409,
            detail=str(
                exc
            )
        )

    if alert is None:

        raise HTTPException(
            status_code=404,
            detail="Persisted telemetry alert not found"
        )

    return {
        "message":
            "Telemetry alert resolved",

        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "alert":
            alert
    }


# =========================================================
# PHASE 6.3 SENSOR HEALTH
# =========================================================

@app.get("/sensor-health")
def sensor_health():

    snapshot = build_alert_snapshot()

    return {

        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        **snapshot[
            "sensor_health"
        ],

        "active_alerts":
            snapshot[
                "alert_summary"
            ][
                "total"
            ]
    }


# =========================================================
# PHASE 6.3 ALERTS
# =========================================================

@app.get("/alerts")
def alerts():

    snapshot = build_alert_snapshot()

    return {

        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "count":
            len(
                snapshot[
                    "alerts"
                ]
            ),

        "summary":
            snapshot[
                "alert_summary"
            ],

        "alerts":
            snapshot[
                "alerts"
            ]
    }


@app.get(
    "/alerts/{asset_id}"
)
def alerts_by_asset(
    asset_id: int
):

    initialise_sensor_telemetry()

    if asset_id not in sensor_telemetry:

        raise HTTPException(
            status_code=404,
            detail="Sensor not found"
        )

    snapshot = build_alert_snapshot()

    asset_alerts = [

        alert

        for alert
        in snapshot[
            "alerts"
        ]

        if alert[
            "asset_id"
        ]
        == asset_id
    ]

    return {

        "source":
            "LOCAL_PROJECT",

        "external":
            False,

        "asset_id":
            asset_id,

        "count":
            len(
                asset_alerts
            ),

        "summary":
            calculate_alert_summary(
                asset_alerts
            ),

        "alerts":
            asset_alerts
    }


# =========================================================
# EVENTS
# =========================================================

@app.get("/events")
def events():

    return (
        build_active_event_feed()
    )


# =========================================================
# TEST EVENT
# =========================================================

@app.get("/test-event")
def get_test_event():

    return {

        "active":
            test_event_state[
                "event"
            ]
            is not None,

        "project_only":
            True,

        "external":
            False,

        "event":
            test_event_state[
                "event"
            ]
    }


@app.post("/test-event")
def create_test_event(
    request_data:
        TestEventRequest
):

    event = create_test_event_object(
        request_data
    )


    test_event_state[
        "event"
    ] = event


    return {

        "message":
            "Internal project test event created",

        "external":
            False,

        "project_only":
            True,

        "event":
            event
    }


@app.delete("/test-event")
def remove_test_event():

    previous = (
        test_event_state[
            "event"
        ]
    )


    test_event_state[
        "event"
    ] = None


    return {

        "message":
            "Internal project test event removed",

        "external":
            False,

        "removed_event":
            previous
    }


# =========================================================
# IMPACT
# =========================================================

@app.get("/impact-analysis")
def impact_analysis():

    snapshot = (
        build_live_snapshot()
    )


    return {

        "project":
            "local",

        "external_sensor_data":
            False,

        "events":
            snapshot[
                "impacts"
            ]
    }


# =========================================================
# RISK
# =========================================================

@app.get("/risk")
def risk():

    snapshot = (
        build_live_snapshot()
    )


    return {

        "external_sensor_data":
            False,

        "affected_assets":
            len(
                snapshot[
                    "risk"
                ]
            ),

        "assets":
            snapshot[
                "risk"
            ]
    }


# =========================================================
# ANALYTICS
# =========================================================

@app.get("/analytics")
def analytics():

    locations_data = (
        load_locations()
    )


    sensor_data = (
        get_sensor_snapshot()
    )


    alert_snapshot = (
        build_alert_snapshot()
    )


    telemetry_alert_snapshot = (
        build_telemetry_alert_snapshot()
    )


    feed = (
        build_active_event_feed()
    )


    snapshot = (
        build_live_snapshot()
    )


    type_counts = {}


    for item in locations_data:

        type_name = (
            item[
                "infra_type"
            ]
            or "Unknown"
        )


        type_counts[
            type_name
        ] = (
            type_counts.get(
                type_name,
                0
            )
            + 1
        )


    high_risk = sum(

        1

        for asset
        in snapshot[
            "risk"
        ]

        if asset[
            "severity"
        ]
        in {
            "high",
            "critical"
        }
    )


    online_sensors = sum(

        1

        for sensor
        in sensor_data

        if sensor[
            "status"
        ]
        ==
        "online"
    )


    degraded_sensors = sum(

        1

        for sensor
        in sensor_data

        if sensor[
            "status"
        ]
        ==
        "degraded"
    )


    offline_sensors = sum(

        1

        for sensor
        in sensor_data

        if sensor[
            "status"
        ]
        ==
        "offline"
    )


    return {

        "total_infrastructure":
            len(
                locations_data
            ),

        "live_earthquakes":
            feed[
                "usgs_event_count"
            ],

        "test_events":
            feed[
                "test_event_count"
            ],

        "affected_assets":
            len(
                snapshot[
                    "risk"
                ]
            ),

        "high_risk_assets":
            high_risk,

        "critical_events":
            sum(

                1

                for event
                in feed[
                    "events"
                ]

                if event[
                    "severity"
                ]
                ==
                "critical"
            ),

        "sensor_source":
            "LOCAL_PROJECT",

        "sensor_data_external":
            False,

        "sensor_count":
            len(
                sensor_data
            ),

        "online_sensors":
            online_sensors,

        "degraded_sensors":
            degraded_sensors,

        "offline_sensors":
            offline_sensors,

        "average_sensor_health":
            alert_snapshot[
                "sensor_health"
            ][
                "average_health"
            ],

        "active_alerts":
            alert_snapshot[
                "alert_summary"
            ][
                "total"
            ],

        "critical_alerts":
            alert_snapshot[
                "alert_summary"
            ][
                "critical"
            ],

        "high_alerts":
            alert_snapshot[
                "alert_summary"
            ][
                "high"
            ],

        "medium_alerts":
            alert_snapshot[
                "alert_summary"
            ][
                "medium"
            ],

        "low_alerts":
            alert_snapshot[
                "alert_summary"
            ][
                "low"
            ],


        "telemetry_alerts":
            telemetry_alert_snapshot[
                "summary"
            ][
                "total"
            ],

        "telemetry_trend_alerts":
            telemetry_alert_snapshot[
                "summary"
            ][
                "trend_alerts"
            ],

        "telemetry_threshold_alerts":
            telemetry_alert_snapshot[
                "summary"
            ][
                "threshold_alerts"
            ],

        "telemetry_alert_affected_assets":
            telemetry_alert_snapshot[
                "summary"
            ][
                "affected_assets"
            ],

        "by_type":
            type_counts,

        "live":
            feed[
                "live"
            ]
    }


# =========================================================
# SEARCH
# =========================================================

@app.get("/search")
def search(
    q: str = Query(
        ...,
        min_length=1
    )
):

    search_text = q.lower()


    return [

        item

        for item
        in load_locations()

        if (

            search_text
            in (
                item[
                    "name"
                ]
                or ""
            )
            .lower()

            or

            search_text
            in (
                item[
                    "description"
                ]
                or ""
            )
            .lower()

            or

            search_text
            in (
                item[
                    "infra_type"
                ]
                or ""
            )
            .lower()
        )
    ]


# =========================================================
# NEAREST
# =========================================================

@app.get("/nearest")
def nearest(
    lat: float,
    lon: float
):

    query = text("""
        SELECT

            id,
            name,
            description,
            infra_type,
            status,
            risk_score,
            severity,

            ST_Y(
                location::geometry
            ) AS latitude,

            ST_X(
                location::geometry
            ) AS longitude,

            ST_Distance(

                location::geography,

                ST_SetSRID(
                    ST_MakePoint(
                        :lon,
                        :lat
                    ),
                    4326
                )::geography

            ) AS distance_meters

        FROM infrastructure_points

        ORDER BY

            location::geography

            <->

            ST_SetSRID(
                ST_MakePoint(
                    :lon,
                    :lat
                ),
                4326
            )::geography

        LIMIT 1;
    """)


    with engine.connect() as conn:

        row = (

            conn.execute(

                query,

                {
                    "lat":
                        lat,

                    "lon":
                        lon
                }
            )
            .fetchone()
        )


    if row is None:

        raise HTTPException(
            status_code=404,
            detail="No infrastructure found"
        )


    data = dict(
        row._mapping
    )


    data[
        "distance_meters"
    ] = float(
        data[
            "distance_meters"
        ]
    )


    data[
        "distance_km"
    ] = round(

        data[
            "distance_meters"
        ]
        /
        1000,

        2
    )


    return data


# =========================================================
# SENSOR WEBSOCKET
# =========================================================

@app.websocket(
    "/ws/sensors"
)
async def sensor_socket(
    websocket:
        WebSocket
):

    await websocket.accept()


    try:

        while True:

            await websocket.send_json({

                "type":
                    "sensor_telemetry",

                "source":
                    "LOCAL_PROJECT",

                "external":
                    False,

                "data":
                    get_sensor_snapshot()
            })


            await asyncio.sleep(
                SENSOR_UPDATE_SECONDS
            )


    except Exception:

        pass


# =========================================================
# PHASE 6.3 ALERT WEBSOCKET
# =========================================================

@app.websocket(
    "/ws/alerts"
)
async def alerts_socket(
    websocket:
        WebSocket
):

    await websocket.accept()


    try:

        while True:

            snapshot = build_alert_snapshot()

            await websocket.send_json({

                "type":
                    "sensor_alerts",

                "source":
                    "LOCAL_PROJECT",

                "external":
                    False,

                "sensor_health":
                    snapshot[
                        "sensor_health"
                    ],

                "summary":
                    snapshot[
                        "alert_summary"
                    ],

                "alerts":
                    snapshot[
                        "alerts"
                    ]
            })


            await asyncio.sleep(
                SENSOR_UPDATE_SECONDS
            )


    except Exception:

        pass


# =========================================================
# PHASE 6.5
# TELEMETRY ALERT WEBSOCKET
# =========================================================

@app.websocket(
    "/ws/telemetry-alerts"
)
async def telemetry_alert_socket(
    websocket:
        WebSocket
):

    await websocket.accept()

    try:

        while True:

            snapshot = (
                await asyncio.to_thread(
                    build_telemetry_alert_snapshot
                )
            )

            await websocket.send_json({

                "type":
                    "telemetry_alerts",

                "source":
                    "LOCAL_PROJECT",

                "external":
                    False,

                "window_minutes":
                    snapshot[
                        "window_minutes"
                    ],

                "summary":
                    snapshot[
                        "summary"
                    ],

                "alerts":
                    snapshot[
                        "alerts"
                    ],

                "generated_at":
                    snapshot[
                        "generated_at"
                    ]
            })

            await asyncio.sleep(
                TELEMETRY_ALERT_WEBSOCKET_SECONDS
            )

    except Exception:

        pass


# =========================================================
# LOCATION WEBSOCKET
# =========================================================

@app.websocket(
    "/ws/locations"
)
async def locations_socket(
    websocket:
        WebSocket
):

    await websocket.accept()


    try:

        while True:

            await websocket.send_json({

                "type":
                    "locations",

                "source":
                    "LOCAL_PROJECT",

                "external":
                    False,

                "data":
                    load_locations()
            })


            await asyncio.sleep(
                15
            )


    except Exception:

        pass


# =========================================================
# EVENT WEBSOCKET
# =========================================================

@app.websocket(
    "/ws/events"
)
async def events_socket(
    websocket:
        WebSocket
):

    await websocket.accept()


    try:

        while True:

            snapshot = (

                await asyncio.to_thread(
                    build_live_snapshot
                )
            )


            await websocket.send_json({

                "type":
                    "earthquakes",

                "usgs_read_only":
                    True,

                "test_event_external":
                    False,

                "data":
                    snapshot[
                        "impacts"
                    ],

                "risk":
                    snapshot[
                        "risk"
                    ]
            })


            await asyncio.sleep(
                USGS_CACHE_SECONDS
            )


    except Exception:

        pass
