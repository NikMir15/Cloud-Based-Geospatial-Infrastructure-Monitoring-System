# Cloud-Based Geospatial Infrastructure Monitoring System

A cloud-native geospatial analytics platform built using **Linux, FastAPI, PostgreSQL, and PostGIS** to store, manage, and visualize infrastructure data using geographic coordinates.

---

## Project Overview

This project demonstrates a **real-world geospatial backend system** capable of:

* Storing infrastructure locations using spatial databases
* Processing geospatial data with PostGIS
* Serving data through REST APIs using FastAPI
* Preparing for cloud deployment and interactive mapping

It simulates a foundation for **smart city systems, cloud infrastructure mapping, and urban analytics platforms**.

---

## Key Features

* REST API built with FastAPI
* PostgreSQL database integration
* PostGIS support for geospatial data
* Infrastructure location storage (latitude/longitude)
* Real-time API responses
* Linux-based development environment

---

## Tech Stack

* **Backend:** FastAPI (Python)
* **Database:** PostgreSQL + PostGIS
* **ORM/DB Layer:** SQLAlchemy
* **Environment:** Linux (Ubuntu)
* **Future Add-ons:** Docker, AWS, Leaflet.js

---

## Project Structure

```
Cloud-Based-Geospatial-Infrastructure-Monitoring-System/
│
├── backend/
│   ├── app/
│   │   ├── database.py
│   │   └── models.py (optional future)
│   ├── main.py
│   ├── .env
│   └── requirements.txt
│
├── infrastructure/
├── frontend/ (future)
├── scripts/
├── docs/
└── README.md
```

---

## Setup Instructions

### 1. Clone Repository

```bash
git clone https://github.com/NikMir15/Cloud-Based-Geospatial-Infrastructure-Monitoring-System.git
cd Cloud-Based-Geospatial-Infrastructure-Monitoring-System/backend
```

---

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install Dependencies

```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-dotenv
```

---

### 4. Setup PostgreSQL + PostGIS

```sql
CREATE DATABASE geospatialdb;
\c geospatialdb;
CREATE EXTENSION postgis;
```

---

### 5. Configure Environment Variables

Create `.env` file:

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost/geospatialdb
```

---

### 6. Run the API

```bash
uvicorn main:app --reload
```

Open:

* http://127.0.0.1:8000
* http://127.0.0.1:8000/docs

---

## API Endpoints

### Root

```
GET /
```

### Health Check

```
GET /health
```

### Get Infrastructure Locations

```
GET /locations
```

Response example:

```json
[
  {
    "id": 1,
    "name": "AWS London Region",
    "description": "Cloud Infrastructure",
    "latitude": 51.5074,
    "longitude": -0.1276
  }
]
```

---

## Geospatial Capability

This project uses **PostGIS** to handle spatial data types:

* Stores coordinates as `GEOGRAPHY(POINT, 4326)`
* Supports real-world mapping applications
* Enables future integration with Leaflet / Mapbox

---

## Future Enhancements

* Interactive map UI (Leaflet.js)
* AWS deployment (EC2 + RDS)
* Docker containerization
* Grafana monitoring dashboards
* Real-time IoT location streaming
* AI-based urban planning insights

---

## Learning Outcomes

This project demonstrates:

* Linux system administration
* Cloud-native architecture design
* Backend API development
* Database design with spatial data
* DevOps-ready project structuring
* Real-world geospatial systems understanding

---

## Author

**Nikunj Mirajkar**
MSc Cloud & Enterprise Computing
GitHub: https://github.com/NikMir15

---

## If you like this project

Give it a star and feel free to contribute or fork!
