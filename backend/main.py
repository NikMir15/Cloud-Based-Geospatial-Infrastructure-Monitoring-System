from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import get_connection

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Home Endpoint
@app.get("/")
def home():
    return {
        "project": "Cloud-Based Geospatial Infrastructure Monitoring System",
        "status": "Running"
    }

# Health Check
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database": "connected"
    }

# Get All Infrastructure Locations
@app.get("/locations")
def get_locations():

    conn = get_connection()

    result = conn.execute(
        text("""
            SELECT
                id,
                name,
                description,
                infra_type,
                ST_Y(location::geometry) AS latitude,
                ST_X(location::geometry) AS longitude
            FROM infrastructure_points
        """)
    )

    locations = []

    for row in result:

        locations.append({
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "infra_type": row.infra_type,
            "latitude": row.latitude,
            "longitude": row.longitude
        })

    conn.close()

    return locations


# Find Nearest Infrastructure
@app.get("/nearest")
def get_nearest(
    lat: float = Query(...),
    lon: float = Query(...)
):

    conn = get_connection()

    result = conn.execute(
        text("""
            SELECT
                id,
                name,
                description,
                infra_type,

                ROUND(
                    CAST(
                        ST_Distance(
                            location::geography,
                            ST_SetSRID(
                                ST_MakePoint(:lon, :lat),
                                4326
                            )::geography
                        ) / 1000 AS numeric
                    ),
                    2
                ) AS distance_km

            FROM infrastructure_points

            ORDER BY
                location <-> ST_SetSRID(
                    ST_MakePoint(:lon, :lat),
                    4326
                )

            LIMIT 1
        """),
        {
            "lat": lat,
            "lon": lon
        }
    )

    row = result.fetchone()

    conn.close()

    if row is None:
        return {
            "message": "No infrastructure points found"
        }

    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "infra_type": row.infra_type,
        "distance_km": float(row.distance_km)
    }
