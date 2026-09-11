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


    risk_task = asyncio.create_task(
        risk_update_loop()
    )


    yield


    sensor_task.cancel()

    risk_task.cancel()


    for task in [
        sensor_task,
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

    version="6.2.0",

    description=(
        "Live infrastructure monitoring with "
        "project-local sensor telemetry, PostGIS, "
        "USGS read-only earthquake data and WebSockets."
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
            "6.2.0",

        "sensor_mode":
            SENSOR_MODE,

        "sensor_data_external":
            False,

        "usgs_mode":
            "READ_ONLY",

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
