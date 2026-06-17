from fastapi import FastAPI
from sqlalchemy import text
from app.database import get_connection

app = FastAPI()

@app.get("/")
def home():
    return {
        "project": "Cloud-Based Geospatial Infrastructure Monitoring System",
        "status": "Running"
    }

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {
        "project": "Cloud-Based Geospatial Infrastructure Monitoring System",
        "status": "Running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database": "connected"
    }

@app.get("/locations")
def get_locations():

    conn = get_connection()

    result = conn.execute(
        text("""
            SELECT
                id,
                name,
                description
            FROM infrastructure_points
        """)
    )

    locations = []

    for row in result:
        locations.append({
            "id": row.id,
            "name": row.name,
            "description": row.description
        })

    conn.close()

    return locations
