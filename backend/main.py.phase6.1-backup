from fastapi import FastAPI, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from datetime import datetime, timezone
from contextlib import asynccontextmanager

import asyncio
import json
import os
import time


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
# DATABASE
# =========================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


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
# EARTHQUAKE HELPERS
# =========================================================

def magnitude_severity(magnitude: float) -> str:

    if magnitude >= 6.0:
        return "critical"

    if magnitude >= 5.0:
        return "high"

    if magnitude >= 4.0:
        return "medium"

    return "low"


def estimated_impact_radius(magnitude: float) -> float:
    """
    Project heuristic only.

    This is an estimated geographic exposure radius used
    for demonstrating infrastructure correlation.

    It is NOT an official USGS damage radius.
    """

    if magnitude >= 7.0:
        return 600

    if magnitude >= 6.0:
        return 450

    if magnitude >= 5.0:
        return 300

    if magnitude >= 4.0:
        return 175

    if magnitude >= 3.0:
        return 90

    return 45


def milliseconds_to_iso(value):

    if value is None:
        return None

    return datetime.fromtimestamp(
        value / 1000,
        tz=timezone.utc
    ).isoformat()


# =========================================================
# FETCH LIVE USGS DATA
# =========================================================

def fetch_usgs_earthquakes(force=False):

    now = time.time()

    cache_age = (
        now - usgs_cache["fetched_at"]
        if usgs_cache["fetched_at"]
        else None
    )


    if (
        not force
        and usgs_cache["events"]
        and cache_age is not None
        and cache_age < USGS_CACHE_SECONDS
    ):
        return {
            "source": "USGS",
            "live": True,
            "cache": True,
            "generated_at": usgs_cache["generated_at"],
            "events": usgs_cache["events"],
            "error": None
        }


    request = Request(
        USGS_FEED_URL,
        headers={
            "User-Agent":
                "GeoInfrastructureMonitoring/1.0"
        }
    )


    try:

        with urlopen(
            request,
            timeout=15
        ) as response:

            payload = json.loads(
                response.read().decode("utf-8")
            )


        events = []


        for feature in payload.get(
            "features",
            []
        ):

            properties = (
                feature.get("properties")
                or {}
            )

            geometry = (
                feature.get("geometry")
                or {}
            )

            coordinates = (
                geometry.get("coordinates")
                or []
            )


            if len(coordinates) < 2:
                continue


            longitude = coordinates[0]
            latitude = coordinates[1]

            depth = (
                coordinates[2]
                if len(coordinates) >= 3
                else None
            )


            magnitude = properties.get(
                "mag"
            )


            if magnitude is None:
                continue


            magnitude = float(
                magnitude
            )


            event = {
                "id":
                    feature.get("id"),

                "event_type":
                    "earthquake",

                "title":
                    properties.get("title")
                    or "Earthquake",

                "place":
                    properties.get("place")
                    or "Unknown location",

                "magnitude":
                    magnitude,

                "depth_km":
                    (
                        float(depth)
                        if depth is not None
                        else None
                    ),

                "latitude":
                    float(latitude),

                "longitude":
                    float(longitude),

                "timestamp":
                    milliseconds_to_iso(
                        properties.get("time")
                    ),

                "updated_at":
                    milliseconds_to_iso(
                        properties.get("updated")
                    ),

                "severity":
                    magnitude_severity(
                        magnitude
                    ),

                "radius_km":
                    estimated_impact_radius(
                        magnitude
                    ),

                "url":
                    properties.get("url"),

                "status":
                    properties.get("status"),

                "tsunami":
                    bool(
                        properties.get(
                            "tsunami",
                            0
                        )
                    ),

                "source":
                    "USGS",

                "live":
                    True
            }


            events.append(
                event
            )


        generated_ms = (
            payload
            .get("metadata", {})
            .get("generated")
        )


        generated_at = (
            milliseconds_to_iso(
                generated_ms
            )
            if generated_ms
            else datetime.now(
                timezone.utc
            ).isoformat()
        )


        usgs_cache["events"] = events

        usgs_cache["fetched_at"] = now

        usgs_cache["generated_at"] = (
            generated_at
        )

        usgs_cache["error"] = None


        return {
            "source": "USGS",
            "live": True,
            "cache": False,
            "generated_at": generated_at,
            "events": events,
            "error": None
        }


    except (
        URLError,
        HTTPError,
        TimeoutError,
        json.JSONDecodeError,
        OSError
    ) as exc:

        error_message = str(
            exc
        )

        usgs_cache["error"] = (
            error_message
        )


        # Use last successful result
        # if USGS temporarily becomes unavailable.

        if usgs_cache["events"]:

            return {
                "source": "USGS",
                "live": False,
                "cache": True,
                "generated_at":
                    usgs_cache[
                        "generated_at"
                    ],
                "events":
                    usgs_cache["events"],
                "error":
                    error_message
            }


        return {
            "source": "USGS",
            "live": False,
            "cache": False,
            "generated_at": None,
            "events": [],
            "error": error_message
        }


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
            )
            AS latitude,

            ST_X(
                location::geometry
            )
            AS longitude

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
        dict(row._mapping)
        for row in rows
    ]


# =========================================================
# POSTGIS EVENT → ASSET CORRELATION
# =========================================================

def infrastructure_in_event_radius(
    event
):

    radius_meters = (
        event["radius_km"]
        * 1000
    )


    query = text("""
        SELECT

            id,

            name,

            description,

            infra_type,

            status,

            ST_Y(
                location::geometry
            )
            AS latitude,

            ST_X(
                location::geometry
            )
            AS longitude,

            ST_Distance(

                location::geography,

                ST_SetSRID(
                    ST_MakePoint(
                        :longitude,
                        :latitude
                    ),
                    4326
                )::geography

            )
            AS distance_meters

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

        ORDER BY
            distance_meters ASC;
    """)


    with engine.connect() as conn:

        rows = (
            conn
            .execute(
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
                        radius_meters
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
            / 1000
        )


        score = calculate_exposure_score(
            event["magnitude"],
            distance_km,
            event["radius_km"]
        )


        severity = (
            score_to_severity(
                score
            )
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
        ] = severity


        assets.append(
            asset
        )


    return assets


# =========================================================
# ESTIMATED EXPOSURE SCORE
# =========================================================

def calculate_exposure_score(
    magnitude,
    distance_km,
    radius_km
):

    if radius_km <= 0:
        return 0


    magnitude_component = min(
        70,
        max(
            10,
            20
            + (
                magnitude - 2.5
            )
            * 18
        )
    )


    proximity_ratio = max(
        0,
        1
        - (
            distance_km
            / radius_km
        )
    )


    proximity_component = (
        proximity_ratio
        * 30
    )


    score = int(
        round(
            magnitude_component
            +
            proximity_component
        )
    )


    return max(
        0,
        min(
            score,
            100
        )
    )


def score_to_severity(score):

    if score >= 75:
        return "critical"

    if score >= 55:
        return "high"

    if score >= 30:
        return "medium"

    return "low"


# =========================================================
# COMPLETE IMPACT ANALYSIS
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


        event_result = {
            **event,

            "affected_count":
                len(assets),

            "affected_assets":
                assets
        }


        results.append(
            event_result
        )


    return results


# =========================================================
# AGGREGATE RISK BY ASSET
# =========================================================

def build_asset_risk_snapshot(
    impact_analysis
):

    asset_risk = {}


    for event in impact_analysis:

        for asset in event[
            "affected_assets"
        ]:

            asset_id = asset["id"]


            risk = {
                "id":
                    asset_id,

                "name":
                    asset["name"],

                "infra_type":
                    asset["infra_type"],

                "status":
                    asset["status"],

                "latitude":
                    asset["latitude"],

                "longitude":
                    asset["longitude"],

                "risk_score":
                    asset[
                        "estimated_risk_score"
                    ],

                "severity":
                    asset[
                        "estimated_severity"
                    ],

                "hazard":
                    event["title"],

                "event_id":
                    event["id"],

                "magnitude":
                    event[
                        "magnitude"
                    ],

                "distance_km":
                    asset[
                        "distance_km"
                    ]
            }


            existing = (
                asset_risk.get(
                    asset_id
                )
            )


            if (
                existing is None
                or
                risk[
                    "risk_score"
                ]
                >
                existing[
                    "risk_score"
                ]
            ):

                asset_risk[
                    asset_id
                ] = risk


    return sorted(
        asset_risk.values(),
        key=lambda item:
            item["risk_score"],
        reverse=True
    )


# =========================================================
# STORE ESTIMATED RISK
# =========================================================

def persist_risk_snapshot(
    risk_snapshot
):

    with engine.begin() as conn:

        # Reset estimated exposure values

        conn.execute(
            text("""
                UPDATE
                    infrastructure_points
                SET
                    risk_score = 0,
                    severity = 'low';
            """)
        )


        update_query = text("""
            UPDATE
                infrastructure_points

            SET
                risk_score =
                    :risk_score,

                severity =
                    :severity

            WHERE
                id = :id;
        """)


        for asset in risk_snapshot:

            conn.execute(
                update_query,
                {
                    "id":
                        asset["id"],

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
        fetch_usgs_earthquakes()
    )


    events = feed["events"]


    impacts = (
        build_impact_analysis(
            events
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
# BACKGROUND LIVE UPDATE
# =========================================================

async def live_update_loop():

    while True:

        try:

            snapshot = (
                await asyncio.to_thread(
                    build_live_snapshot
                )
            )


            await asyncio.to_thread(
                persist_risk_snapshot,
                snapshot["risk"]
            )

        except Exception as exc:

            print(
                "Live update error:",
                exc
            )


        await asyncio.sleep(
            USGS_CACHE_SECONDS
        )


# =========================================================
# APPLICATION LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    task = asyncio.create_task(
        live_update_loop()
    )


    yield


    task.cancel()


    try:

        await task

    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=(
        "Infrastructure Situational "
        "Awareness Platform"
    ),

    description=(
        "Live geospatial infrastructure "
        "monitoring using FastAPI, "
        "PostgreSQL/PostGIS, USGS and "
        "WebSockets."
    ),

    version="6.0.0",

    lifespan=lifespan
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
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "project":
            "Infrastructure Situational "
            "Awareness Platform",

        "phase":
            6,

        "version":
            "6.0.0",

        "status":
            "running",

        "live_source":
            "USGS Earthquake Hazards Program"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    database_status = (
        "connected"
    )


    try:

        with engine.connect() as conn:

            conn.execute(
                text("SELECT 1")
            )

    except Exception:

        database_status = (
            "disconnected"
        )


    cache_age = None


    if usgs_cache[
        "fetched_at"
    ]:

        cache_age = round(
            time.time()
            -
            usgs_cache[
                "fetched_at"
            ],
            1
        )


    return {
        "status":
            (
                "healthy"
                if database_status
                == "connected"
                else "degraded"
            ),

        "database":
            database_status,

        "usgs_source":
            "configured",

        "usgs_cache_age_seconds":
            cache_age,

        "last_usgs_error":
            usgs_cache[
                "error"
            ]
    }


# =========================================================
# LOCATIONS
# =========================================================

@app.get("/locations")
def locations():

    return load_locations()


# =========================================================
# LIVE EVENTS
# =========================================================

@app.get("/events")
def events():

    return (
        fetch_usgs_earthquakes()
    )


# =========================================================
# IMPACT ANALYSIS
# =========================================================

@app.get("/impact-analysis")
def impact_analysis():

    feed = (
        fetch_usgs_earthquakes()
    )


    impacts = (
        build_impact_analysis(
            feed["events"]
        )
    )


    return {
        "source":
            feed["source"],

        "live":
            feed["live"],

        "generated_at":
            feed["generated_at"],

        "event_count":
            len(
                feed["events"]
            ),

        "events":
            impacts
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
        "source":
            "USGS",

        "live":
            snapshot[
                "feed"
            ][
                "live"
            ],

        "affected_assets":
            len(
                snapshot["risk"]
            ),

        "assets":
            snapshot["risk"]
    }


# =========================================================
# ANALYTICS
# =========================================================

@app.get("/analytics")
def analytics():

    with engine.connect() as conn:

        total = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM infrastructure_points;
            """)
        ).scalar()


        type_rows = (
            conn.execute(
                text("""
                    SELECT
                        infra_type,
                        COUNT(*) AS count

                    FROM
                        infrastructure_points

                    GROUP BY
                        infra_type

                    ORDER BY
                        count DESC;
                """)
            )
            .fetchall()
        )


    by_type = {
        row.infra_type:
            row.count

        for row in type_rows
    }


    snapshot = (
        build_live_snapshot()
    )


    events = (
        snapshot[
            "feed"
        ][
            "events"
        ]
    )


    risk_assets = (
        snapshot[
            "risk"
        ]
    )


    high_risk = sum(
        1
        for asset in risk_assets
        if asset[
            "severity"
        ]
        in {
            "high",
            "critical"
        }
    )


    critical_events = sum(
        1
        for event in events
        if event[
            "severity"
        ]
        ==
        "critical"
    )


    return {
        "total_infrastructure":
            total,

        "live_earthquakes":
            len(events),

        "affected_assets":
            len(
                risk_assets
            ),

        "high_risk_assets":
            high_risk,

        "critical_events":
            critical_events,

        "by_type":
            by_type,

        "data_source":
            "USGS",

        "live":
            snapshot[
                "feed"
            ][
                "live"
            ],

        "generated_at":
            snapshot[
                "feed"
            ][
                "generated_at"
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
            )
            AS latitude,

            ST_X(
                location::geometry
            )
            AS longitude

        FROM infrastructure_points

        WHERE

            LOWER(name)
            LIKE LOWER(:search)

            OR

            LOWER(
                COALESCE(
                    description,
                    ''
                )
            )
            LIKE LOWER(:search)

            OR

            LOWER(
                COALESCE(
                    infra_type,
                    ''
                )
            )
            LIKE LOWER(:search)

        ORDER BY name

        LIMIT 50;
    """)


    with engine.connect() as conn:

        rows = (
            conn.execute(
                query,
                {
                    "search":
                        f"%{q}%"
                }
            )
            .fetchall()
        )


    return [
        dict(row._mapping)
        for row in rows
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
            )
            AS latitude,

            ST_X(
                location::geometry
            )
            AS longitude,

            ST_Distance(

                location::geography,

                ST_SetSRID(
                    ST_MakePoint(
                        :lon,
                        :lat
                    ),
                    4326
                )::geography

            )
            AS distance_meters

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
                    "lat": lat,
                    "lon": lon
                }
            )
            .fetchone()
        )


    if row is None:

        return {
            "message":
                "No infrastructure found"
        }


    data = dict(
        row._mapping
    )


    data[
        "distance_meters"
    ] = float(
        data[
            "distance_meters"
        ]
        or 0
    )


    data[
        "distance_km"
    ] = round(
        data[
            "distance_meters"
        ]
        / 1000,
        2
    )


    return data


# =========================================================
# WEBSOCKET - LOCATIONS
# =========================================================

@app.websocket(
    "/ws/locations"
)
async def locations_socket(
    websocket: WebSocket
):

    await websocket.accept()


    try:

        while True:

            await websocket.send_json(
                {
                    "type":
                        "locations",

                    "data":
                        load_locations()
                }
            )


            await asyncio.sleep(
                15
            )


    except Exception:
        pass


# =========================================================
# WEBSOCKET - LIVE EARTHQUAKES
# =========================================================

@app.websocket(
    "/ws/events"
)
async def events_socket(
    websocket: WebSocket
):

    await websocket.accept()


    try:

        while True:

            feed = (
                await asyncio.to_thread(
                    fetch_usgs_earthquakes
                )
            )


            impacts = (
                await asyncio.to_thread(
                    build_impact_analysis,
                    feed["events"]
                )
            )


            await websocket.send_json(
                {
                    "type":
                        "earthquakes",

                    "source":
                        "USGS",

                    "live":
                        feed["live"],

                    "generated_at":
                        feed[
                            "generated_at"
                        ],

                    "data":
                        impacts
                }
            )


            await asyncio.sleep(
                USGS_CACHE_SECONDS
            )


    except Exception:
        pass
