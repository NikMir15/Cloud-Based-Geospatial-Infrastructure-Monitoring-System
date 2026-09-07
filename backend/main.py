from fastapi import FastAPI, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from datetime import datetime, timezone

import asyncio
import os
import random


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not configured"
    )


# =========================================================
# DATABASE
# =========================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="Infrastructure Situational Awareness Platform",
    description=(
        "Cloud-Based Geospatial Infrastructure Monitoring System "
        "using FastAPI, PostgreSQL/PostGIS, Docker and Leaflet."
    ),
    version="3.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# DATABASE HELPERS
# =========================================================

def load_locations():

    query = text("""
        SELECT
            id,
            name,
            description,
            infra_type,
            ST_Y(location::geometry) AS latitude,
            ST_X(location::geometry) AS longitude
        FROM infrastructure_points
        ORDER BY id;
    """)

    with engine.connect() as conn:

        rows = conn.execute(query).fetchall()

    return [
        dict(row._mapping)
        for row in rows
    ]


def load_type_statistics():

    query = text("""
        SELECT
            infra_type,
            COUNT(*) AS count
        FROM infrastructure_points
        GROUP BY infra_type
        ORDER BY count DESC, infra_type;
    """)

    with engine.connect() as conn:

        rows = conn.execute(query).fetchall()

    return {
        row.infra_type: row.count
        for row in rows
    }


# =========================================================
# SIMULATED HAZARD EVENTS
# =========================================================
#
# These are intentionally simulated for now.
# Later we can replace these with real external feeds.
#
# =========================================================

hazard_events = [
    {
        "id": "EQ-001",
        "event_type": "earthquake",
        "title": "Seismic Activity",
        "severity": "high",
        "latitude": 28.60,
        "longitude": 77.20,
        "radius_km": 180,
        "description": "Simulated magnitude 5.4 seismic event"
    },
    {
        "id": "FL-001",
        "event_type": "flood",
        "title": "Flood Warning",
        "severity": "medium",
        "latitude": 53.48,
        "longitude": -2.24,
        "radius_km": 90,
        "description": "Simulated regional flood warning"
    },
    {
        "id": "ST-001",
        "event_type": "storm",
        "title": "Severe Storm",
        "severity": "critical",
        "latitude": 51.50,
        "longitude": -0.12,
        "radius_km": 120,
        "description": "Simulated severe weather system"
    }
]


def get_hazard_events():

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    return [
        {
            **event,
            "timestamp": timestamp
        }
        for event in hazard_events
    ]


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "project": "Infrastructure Situational Awareness Platform",
        "version": "3.0.0",
        "status": "Running"
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    try:

        with engine.connect() as conn:
            conn.execute(
                text("SELECT 1")
            )

        return {
            "status": "healthy",
            "database": "connected",
            "event_service": "available"
        }

    except Exception as exc:

        return {
            "status": "unhealthy",
            "database": "disconnected",
            "event_service": "unknown",
            "error": str(exc)
        }


# =========================================================
# INFRASTRUCTURE LOCATIONS
# =========================================================

@app.get("/locations")
def get_locations():

    return load_locations()


# =========================================================
# ANALYTICS
# =========================================================

@app.get("/analytics")
def get_analytics():

    with engine.connect() as conn:

        total = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM infrastructure_points;
            """)
        ).scalar()

    by_type = load_type_statistics()

    events = get_hazard_events()

    active_alerts = len(events)

    high_risk_assets = sum(
        1
        for event in events
        if event["severity"] in {
            "high",
            "critical"
        }
    )

    critical_events = sum(
        1
        for event in events
        if event["severity"] == "critical"
    )

    return {
        "total_infrastructure": total,
        "active_alerts": active_alerts,
        "high_risk_assets": high_risk_assets,
        "critical_events": critical_events,
        "by_type": by_type
    }


# =========================================================
# SEARCH
# =========================================================

@app.get("/search")
def search_infrastructure(
    q: str = Query(
        ...,
        min_length=1
    )
):

    query = text("""
        SELECT
            id,
            name,
            description,
            infra_type,
            ST_Y(location::geometry) AS latitude,
            ST_X(location::geometry) AS longitude
        FROM infrastructure_points
        WHERE
            LOWER(name) LIKE LOWER(:search)
            OR
            LOWER(COALESCE(description, ''))
                LIKE LOWER(:search)
            OR
            LOWER(COALESCE(infra_type, ''))
                LIKE LOWER(:search)
        ORDER BY name
        LIMIT 50;
    """)

    with engine.connect() as conn:

        rows = conn.execute(
            query,
            {
                "search": f"%{q}%"
            }
        ).fetchall()

    return [
        dict(row._mapping)
        for row in rows
    ]


# =========================================================
# NEAREST INFRASTRUCTURE
# =========================================================

@app.get("/nearest")
def nearest_infrastructure(
    lat: float,
    lon: float
):

    query = text("""
        SELECT
            id,
            name,
            description,
            infra_type,

            ST_Y(location::geometry)
                AS latitude,

            ST_X(location::geometry)
                AS longitude,

            ST_Distance(
                location::geography,
                ST_SetSRID(
                    ST_MakePoint(:lon, :lat),
                    4326
                )::geography
            )
                AS distance_meters

        FROM infrastructure_points

        ORDER BY
            location::geography
            <->
            ST_SetSRID(
                ST_MakePoint(:lon, :lat),
                4326
            )::geography

        LIMIT 1;
    """)

    with engine.connect() as conn:

        row = conn.execute(
            query,
            {
                "lat": lat,
                "lon": lon
            }
        ).fetchone()

    if row is None:

        return {
            "message": "No infrastructure found"
        }

    data = dict(
        row._mapping
    )

    data["distance_meters"] = float(
        data.get(
            "distance_meters"
        )
        or 0
    )

    data["distance_km"] = round(
        data["distance_meters"]
        / 1000,
        2
    )

    return data


# =========================================================
# HAZARD EVENTS
# =========================================================

@app.get("/events")
def events():

    return get_hazard_events()


# =========================================================
# INFRASTRUCTURE WEBSOCKET
# =========================================================

@app.websocket("/ws/locations")
async def locations_websocket(
    websocket: WebSocket
):

    await websocket.accept()

    try:

        while True:

            await asyncio.sleep(
                5
            )

            await websocket.send_json(
                {
                    "type": "locations",
                    "data": load_locations()
                }
            )

    except Exception:

        try:
            await websocket.close()
        except Exception:
            pass


# =========================================================
# EVENT WEBSOCKET
# =========================================================

@app.websocket("/ws/events")
async def events_websocket(
    websocket: WebSocket
):

    await websocket.accept()

    try:

        while True:

            await asyncio.sleep(
                8
            )

            events = get_hazard_events()

            simulated_events = []

            for event in events:

                updated_event = {
                    **event
                }

                # Small movement to demonstrate
                # a live event data stream.

                updated_event[
                    "latitude"
                ] += random.uniform(
                    -0.03,
                    0.03
                )

                updated_event[
                    "longitude"
                ] += random.uniform(
                    -0.03,
                    0.03
                )

                simulated_events.append(
                    updated_event
                )

            await websocket.send_json(
                {
                    "type": "events",
                    "data": simulated_events
                }
            )

    except Exception:

        try:
            await websocket.close()
        except Exception:
            pass
