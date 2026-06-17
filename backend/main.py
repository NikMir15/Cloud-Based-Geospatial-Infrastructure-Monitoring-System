from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {
        "project": "Cloud-Based Geospatial Infrastructure Monitoring System",
        "status": "Running"
    }
