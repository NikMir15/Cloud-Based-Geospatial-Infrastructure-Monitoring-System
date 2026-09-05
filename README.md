# Cloud-Based Geospatial Infrastructure Monitoring System

## Overview

The Cloud-Based Geospatial Infrastructure Monitoring System is a cloud-native platform designed to monitor, visualize, and analyze infrastructure assets across multiple geographic locations in real time.

The system leverages FastAPI, PostgreSQL/PostGIS, Docker, WebSockets, and Leaflet.js to provide interactive geospatial visualization, infrastructure analytics, real-time updates, and intelligent monitoring capabilities.

---

## Features

### Interactive Geospatial Map

* Global infrastructure visualization
* Real-time marker updates
* Dark-themed map interface
* Nearest infrastructure lookup

### Infrastructure Monitoring

* Sensor nodes
* Traffic monitoring points
* Environmental monitoring stations
* Grid infrastructure nodes
* Communication towers
* Bridge monitoring systems

### Risk Zone Visualization

* Dynamic city-based risk zones
* Infrastructure density analysis
* Visual risk assessment using colored zones
* Global monitoring coverage

### Real-Time Updates

* FastAPI WebSocket integration
* Live sensor data streaming
* Automatic frontend refresh
* Simulated infrastructure movement

### Analytics Dashboard

* Total infrastructure count
* Infrastructure categorization
* Live statistics panel
* Real-time monitoring metrics

### Cloud-Native Architecture

* Dockerized services
* Multi-container deployment
* PostGIS spatial database
* FastAPI backend services

---

## Technology Stack

### Frontend

* HTML5
* CSS3
* JavaScript (ES6)
* Leaflet.js

### Backend

* Python 3.12
* FastAPI
* SQLAlchemy
* WebSockets

### Database

* PostgreSQL
* PostGIS

### DevOps

* Docker
* Docker Compose
* GitHub

---

## System Architecture

Frontend (Leaflet.js Dashboard)
│
▼
FastAPI Backend
│
▼
PostgreSQL + PostGIS
│
▼
Geospatial Analytics Engine

---

## Project Structure

```text
Cloud-Based-Geospatial-Infrastructure-Monitoring-System/
│
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── favicon.ico
│   └── Dockerfile
│
├── docker-compose.yml
├── README.md
└── .gitignore
```

---

## Installation

### Clone Repository

```bash
git clone https://github.com/NikMir15/Cloud-Based-Geospatial-Infrastructure-Monitoring-System.git

cd Cloud-Based-Geospatial-Infrastructure-Monitoring-System
```

### Build Containers

```bash
docker compose build
```

### Start Application

```bash
docker compose up -d
```

### Verify Containers

```bash
docker ps
```

Expected Containers:

```text
geo-backend
geo-frontend
geodb
```

---

## Application URLs

### Frontend

```text
http://localhost:8080
```

### Backend API

```text
http://localhost:8000
```

### API Documentation

```text
http://localhost:8000/docs
```

---

## Available APIs

### Home

```http
GET /
```

Returns application status.

---

### Infrastructure Locations

```http
GET /locations
```

Returns all monitored infrastructure points.

---

### Analytics

```http
GET /analytics
```

Returns infrastructure statistics and summaries.

---

### Nearest Infrastructure

```http
GET /nearest?lat=<latitude>&lon=<longitude>
```

Returns the closest infrastructure asset to the selected coordinates.

---

### Live Updates

```http
WebSocket /ws/locations
```

Provides real-time infrastructure updates.

---

## Current Capabilities

* Global infrastructure visualization
* Geospatial database integration
* Infrastructure analytics dashboard
* Real-time WebSocket updates
* Dynamic risk zone visualization
* Dockerized deployment
* PostGIS spatial querying
* Nearest infrastructure search

---

## Future Enhancements

### Planned Features

* Sensor health monitoring
* Risk scoring engine
* AI anomaly detection
* Predictive infrastructure analytics
* Kubernetes deployment
* AWS cloud deployment
* CI/CD pipeline automation
* Alert management system
* Geo-fencing support
* Infrastructure Digital Twin capabilities

---

## Author

**Nikunj Mirajkar**

MSc Cloud & Enterprise Computing
Nottingham Trent University

LinkedIn:
https://www.linkedin.com/in/nikunjmirajkar/

GitHub:
https://github.com/NikMir15

---

## License

This project is developed for academic and research purposes and may be extended for enterprise geospatial infrastructure monitoring applications.
