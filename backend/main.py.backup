from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import random
import asyncio

load_dotenv()

app = FastAPI()

# -------------------------
# CORS
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# DATABASE
# -------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# -------------------------
# CACHE
# -------------------------
sensor_data = []


# -------------------------
# LOAD DATA
# -------------------------
def load_from_db():
    conn = engine.connect()

    result = conn.execute(text("""
        SELECT id, name, description, infra_type,
               ST_Y(location::geometry) AS latitude,
               ST_X(location::geometry) AS longitude
        FROM infrastructure_points
    """))

    return [dict(row._mapping) for row in result]


# -------------------------
# HOME
# -------------------------
@app.get("/")
def home():
    return {
        "project": "Cloud-Based Geospatial Infrastructure Monitoring System",
        "status": "Running"
    }


# -------------------------
# LOCATIONS
# -------------------------
@app.get("/locations")
def get_locations():
    global sensor_data
    sensor_data = load_from_db()
    return sensor_data


# -------------------------
# ANALYTICS
# -------------------------
@app.get("/analytics")
def get_analytics():
    conn = engine.connect()

    total = conn.execute(text("""
        SELECT COUNT(*) FROM infrastructure_points
    """)).fetchone()[0]

    by_type = conn.execute(text("""
        SELECT infra_type, COUNT(*)
        FROM infrastructure_points
        GROUP BY infra_type
    """)).fetchall()

    return {
        "total_points": total,
        "by_type": [
            {"type": row[0], "count": row[1]}
            for row in by_type
        ]
    }


# -------------------------
# NEAREST (FIXED VERSION)
# -------------------------
@app.get("/nearest")
def get_nearest(lat: float, lon: float):
    conn = engine.connect()

    query = text("""
        SELECT
            id,
            name,
            infra_type,
            ST_Y(location::geometry) AS latitude,
            ST_X(location::geometry) AS longitude,
            ST_Distance(
                location::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) AS distance_meters
        FROM infrastructure_points
        ORDER BY distance_meters ASC
        LIMIT 1;
    """)

    result = conn.execute(query, {"lat": lat, "lon": lon})
    row = result.fetchone()

    if not row:
        return {"message": "No data found"}

    data = dict(row._mapping)

    # FORCE SAFE VALUE
    data["distance_meters"] = float(data.get("distance_meters") or 0)

    return data


# -------------------------
# LIVE SIMULATION
# -------------------------
async def simulate_movement():
    global sensor_data

    while True:
        await asyncio.sleep(5)

        for point in sensor_data:
            point["latitude"] += random.uniform(-0.001, 0.001)
            point["longitude"] += random.uniform(-0.001, 0.001)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulate_movement())


# -------------------------
# WEBSOCKET
# -------------------------
@app.websocket("/ws/locations")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            await asyncio.sleep(3)
            data = load_from_db()
            await websocket.send_json(data)

    except:
        pass
