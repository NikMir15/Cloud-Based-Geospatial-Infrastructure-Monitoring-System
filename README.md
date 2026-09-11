# Cloud-Based Geospatial Infrastructure Monitoring System

## Overview

The Cloud-Based Geospatial Infrastructure Monitoring System is a cloud-native situational-awareness platform designed to monitor, visualize, and analyze infrastructure assets across multiple geographic locations in real time.

The system combines FastAPI, PostgreSQL/PostGIS, Docker, WebSockets, Leaflet.js, OpenStreetMap, and live USGS earthquake data to provide interactive geospatial visualization, infrastructure analytics, real-time event monitoring, estimated exposure analysis, and project-local simulated sensor telemetry.

The platform demonstrates how geospatial engineering, cloud technologies, DevOps practices, real-time communication, and infrastructure monitoring can be integrated into a single end-to-end system.

> **Important:** Sensor telemetry and test earthquakes are simulated inside this project. They are not transmitted to USGS or another external monitoring system. USGS earthquake information is consumed as a read-only external data source.

---

## Features

### Interactive Geospatial Map

- Global infrastructure visualization
- Dark-themed monitoring interface
- Infrastructure marker clustering
- Real-time marker updates
- Interactive infrastructure popups
- Earthquake event visualization
- Earthquake exposure-radius visualization
- Nearest infrastructure lookup
- Search and filtering
- Risk-based infrastructure highlighting

### Infrastructure Monitoring

The platform monitors multiple infrastructure categories, including:

- Sensor nodes
- Traffic monitoring points
- Environmental monitoring stations
- Grid infrastructure nodes
- Communication towers
- Bridge monitoring systems
- Transport infrastructure
- Cloud infrastructure
- Healthcare infrastructure
- Coastal infrastructure

### Live USGS Earthquake Monitoring

- Live earthquake data from the USGS GeoJSON feed
- Earthquake magnitude visualization
- Geographic event positioning
- Earthquake depth information
- Event timestamps
- Severity classification
- Estimated exposure-radius calculation
- Infrastructure-to-earthquake correlation
- Read-only external data integration

The USGS integration follows this direction:

```text
USGS
  |
  | Read-only earthquake data
  v
FastAPI Backend
```

The project does not send simulated earthquakes, sensor telemetry, infrastructure information, or calculated risk information back to USGS.

### Infrastructure Exposure and Risk Analysis

- PostGIS spatial correlation
- Infrastructure distance calculation
- Earthquake exposure-radius analysis
- Estimated operational exposure scoring
- Severity classification
- Risk-based map visualization
- Affected infrastructure identification

Infrastructure can be classified into estimated exposure levels:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

The calculated score represents estimated operational exposure for demonstration purposes.

It is not a scientific earthquake damage prediction or structural engineering assessment.

### Real-Time Updates

- FastAPI WebSocket integration
- Real-time infrastructure updates
- Real-time earthquake updates
- Local sensor telemetry streaming
- Automatic frontend updates
- WebSocket reconnection support
- Live infrastructure health information

### Local Live Sensor Telemetry

The project contains an internal sensor simulation engine that generates telemetry for monitored infrastructure.

Available telemetry includes:

- Health percentage
- CPU usage
- Temperature
- Network latency
- Packet loss
- Signal strength
- Sensor status
- Last updated timestamp

Sensor states include:

```text
ONLINE
DEGRADED
OFFLINE
```

Example telemetry:

```json
{
  "asset_id": 9,
  "name": "London Bridge Sensor",
  "source": "LOCAL_PROJECT",
  "external": false,
  "status": "online",
  "health": 94,
  "cpu_percent": 31.7,
  "temperature_c": 36.2,
  "latency_ms": 16.4,
  "packet_loss_percent": 0.08,
  "signal_strength": 93
}
```

The telemetry is generated inside the project and is explicitly identified as:

```text
source: LOCAL_PROJECT
external: false
```

It is simulated monitoring data and should not be interpreted as measurements from real physical infrastructure.

### Analytics Dashboard

- Total infrastructure count
- Infrastructure categorization
- Live earthquake count
- Affected infrastructure count
- High-risk asset count
- Critical event count
- Live feed status
- Infrastructure distribution
- Estimated exposure information
- Local sensor health information

### Cloud-Native Architecture

- Dockerized backend
- Dockerized frontend
- PostgreSQL/PostGIS database
- Multi-container deployment
- FastAPI backend services
- Nginx frontend
- Environment-based configuration
- REST API architecture
- WebSocket communication

---

## Technology Stack

### Frontend

- HTML5
- CSS3
- JavaScript (ES6)
- Leaflet.js
- Leaflet MarkerCluster
- OpenStreetMap

### Backend

- Python 3.12
- FastAPI
- Uvicorn
- SQLAlchemy
- Psycopg2
- AsyncIO
- WebSockets

### Database

- PostgreSQL
- PostGIS

### DevOps

- Docker
- Docker Compose
- Nginx
- Linux / Ubuntu
- Git
- GitHub

### External Data Source

- USGS Earthquake GeoJSON Feed

---

## System Architecture

```text
                         Internet
                            |
                            | Read Only
                            v
                    USGS Earthquake Feed
                            |
                            v
                   FastAPI Backend
                    /            \
                   /              \
                  v                v
        USGS Event Engine    Local Sensor Engine
                  \                /
                   \              /
                    v            v
                  Risk / Impact Engine
                         |
                         v
                PostgreSQL + PostGIS
                         |
                  +------+------+
                  |             |
                  v             v
               REST API     WebSockets
                  |             |
                  +------+------+
                         |
                         v
                Leaflet.js Dashboard
```

### Local Sensor Data Flow

```text
Infrastructure Database
          |
          v
Local Sensor Simulator
          |
          v
FastAPI Backend
          |
     +----+--------------------+
     |                         |
     v                         v
REST API                 WebSocket
/sensor-telemetry        /ws/sensors
     |                         |
     +------------+------------+
                  |
                  v
             Dashboard
```

Sensor telemetry remains within the project data flow and is not uploaded to USGS.

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
│   ├── style.css
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

Using HTTPS:

```bash
git clone https://github.com/NikMir15/Cloud-Based-Geospatial-Infrastructure-Monitoring-System.git

cd Cloud-Based-Geospatial-Infrastructure-Monitoring-System
```

Or using SSH:

```bash
git clone git@github.com:NikMir15/Cloud-Based-Geospatial-Infrastructure-Monitoring-System.git

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

Alternatively, build and start in one command:

```bash
docker compose up -d --build
```

### Verify Containers

```bash
docker compose ps
```

Expected containers:

```text
geo-backend
geo-frontend
geodb
```

### View Backend Logs

```bash
docker logs geo-backend --tail 50
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

```text
GET /
```

Returns application and monitoring status.

---

### Health

```text
GET /health
```

Returns backend, database, USGS, and local sensor monitoring status.

---

### Infrastructure Locations

```text
GET /locations
```

Returns all monitored infrastructure points with geographic coordinates and infrastructure information.

---

### Analytics

```text
GET /analytics
```

Returns infrastructure statistics, earthquake statistics, estimated exposure information, and local sensor monitoring statistics.

---

### Search Infrastructure

```text
GET /search?q=<search-term>
```

Searches monitored infrastructure using name, description, or infrastructure information.

---

### Nearest Infrastructure

```text
GET /nearest?lat=<latitude>&lon=<longitude>
```

Returns the closest infrastructure asset to the selected geographic coordinates.

---

### Live Earthquake Events

```text
GET /events
```

Returns normalized live USGS earthquake events together with any active project-local test event.

---

### Impact Analysis

```text
GET /impact-analysis
```

Performs geospatial correlation between earthquake events and infrastructure assets.

---

### Estimated Risk

```text
GET /risk
```

Returns infrastructure exposure information and estimated risk classifications.

---

### Local Sensor Telemetry

```text
GET /sensor-telemetry
```

Returns project-local simulated telemetry for monitored infrastructure.

Telemetry is explicitly identified as:

```json
{
  "source": "LOCAL_PROJECT",
  "external": false
}
```

---

### Individual Sensor Telemetry

```text
GET /sensor-telemetry/{asset_id}
```

Returns local simulated telemetry for a specific infrastructure asset.

Example:

```text
GET /sensor-telemetry/9
```

---

### Test Earthquake

```text
GET /test-event
```

Returns the currently active project-local simulated earthquake.

Create a simulated earthquake:

```text
POST /test-event
```

Remove the simulated earthquake:

```text
DELETE /test-event
```

Test earthquakes are clearly identified as simulated project data and are never presented as real USGS earthquakes.

---

## WebSocket APIs

### Infrastructure Updates

```text
WebSocket /ws/locations
```

Provides real-time infrastructure updates.

### Earthquake Updates

```text
WebSocket /ws/events
```

Provides real-time earthquake and estimated exposure updates.

### Sensor Telemetry

```text
WebSocket /ws/sensors
```

Provides project-local simulated infrastructure telemetry.

---

## Phase 6.1 - Risk Engine Test Mode

Real earthquakes do not necessarily occur close to infrastructure contained in the demonstration database.

To test the complete geospatial exposure pipeline, the project includes an internal simulated earthquake mode.

A test event can be created near a selected infrastructure asset.

Example configuration:

```text
Target Infrastructure:
London Bridge Sensor

Magnitude:
6.2

Exposure Radius:
200 km
```

The test event follows the same processing pipeline:

```text
Simulated Earthquake
        |
        v
PostGIS Spatial Analysis
        |
        v
Affected Infrastructure
        |
        v
Estimated Exposure
        |
        v
Risk Classification
        |
        v
Dashboard Visualization
```

Every simulated event contains identifiers such as:

```text
source: TEST
simulated: true
external: false
project_only: true
```

This prevents simulated events from being confused with real USGS earthquake data.

---

## Phase 6.2 - Local Sensor Monitoring

Phase 6.2 introduces project-local simulated infrastructure telemetry.

The FastAPI backend generates changing monitoring values and distributes them to the dashboard through REST and WebSockets.

Example dashboard information:

```text
London Bridge Sensor

Infrastructure Type: Sensor
Asset Status: operational

Estimated Exposure: Low

LOCAL LIVE TELEMETRY
ONLINE

Health:       94%
CPU:          31.7%
Temperature:  36.2 C
Latency:      16.4 ms
Packet Loss:  0.08%
Signal:       93%

Source: LOCAL PROJECT SIMULATION
Updated: just now
```

The local monitoring engine can simulate:

- Normal operation
- Degraded infrastructure
- Offline infrastructure
- CPU changes
- Temperature changes
- Network latency changes
- Packet loss
- Signal-quality changes

This provides a controlled environment for demonstrating real-time infrastructure monitoring without connecting to real physical infrastructure.

---

## Current Capabilities

- Global infrastructure visualization
- PostgreSQL/PostGIS geospatial database
- Infrastructure analytics dashboard
- Live USGS earthquake monitoring
- Read-only external earthquake integration
- PostGIS spatial correlation
- Earthquake exposure-radius analysis
- Estimated infrastructure risk scoring
- Real-time WebSocket updates
- Local simulated sensor telemetry
- Infrastructure health monitoring
- Test earthquake simulation
- Risk-based infrastructure visualization
- Infrastructure search and filtering
- Nearest infrastructure search
- Marker clustering
- Dockerized deployment
- Nginx frontend
- FastAPI REST API
- Real-time sensor WebSocket

---

## Data and Privacy

The platform uses three primary types of data.

### Infrastructure Data

Infrastructure records are stored in the project's PostgreSQL/PostGIS database.

```text
PostgreSQL/PostGIS
        |
        v
FastAPI
        |
        v
Dashboard
```

### Local Sensor Data

Sensor telemetry is generated by the local project simulator.

```text
Local Sensor Simulator
        |
        v
FastAPI
        |
        v
Dashboard
```

It is identified as:

```text
source = LOCAL_PROJECT
external = false
```

The application does not send this simulated telemetry to USGS.

### Earthquake Data

Earthquake information is retrieved from the public USGS earthquake feed.

```text
USGS
  |
  v
Project
```

This is external data entering the application.

The USGS integration does not send project sensor data, simulated events, infrastructure information, or exposure calculations back to USGS.

---

## Security Considerations

The current project is designed primarily as a development, research, and portfolio platform.

Before public or production deployment, the following should be implemented:

- Authentication
- Authorization
- Admin-only test controls
- Restricted test endpoints
- Test mode disabled by default
- HTTPS
- Secure environment variables
- Restricted CORS configuration
- Reverse proxy security
- API rate limiting
- Database network restrictions
- Secrets management
- Monitoring and audit logging

Sensitive information must never be committed to Git.

Examples include:

```text
.env
Database passwords
API keys
Admin API keys
Cloud credentials
Private SSH keys
```

---

## Future Enhancements

### Planned Features

- Sensor health overview panel
- Historical telemetry storage
- Historical telemetry charts
- Incident management workflow
- Alert management system
- Authentication and authorization
- Admin-only simulation controls
- AI anomaly detection
- Predictive infrastructure analytics
- Multi-hazard monitoring
- Geo-fencing support
- Infrastructure Digital Twin capabilities
- Kubernetes deployment
- AWS cloud deployment
- CI/CD pipeline automation
- Prometheus and Grafana monitoring
- Centralized application logging
- Production security hardening

---

## What This Project Demonstrates

### Cloud and DevOps

- Docker
- Docker Compose
- Linux
- Nginx
- Multi-container architecture
- Environment-based configuration
- Git
- GitHub

### Backend Engineering

- FastAPI
- REST APIs
- WebSockets
- Async background processing
- External API consumption
- Application state management

### Database Engineering

- PostgreSQL
- PostGIS
- Spatial queries
- Geographic distance calculations
- Geospatial data storage

### Real-Time Systems

- WebSocket communication
- Live dashboard updates
- Simulated telemetry streams
- Event-driven monitoring concepts

### Geospatial Engineering

- Leaflet.js
- OpenStreetMap
- Geographic coordinates
- Spatial correlation
- Exposure-radius visualization
- Nearest-location analysis

### Infrastructure Monitoring

- Infrastructure health metrics
- Estimated exposure scoring
- Event correlation
- Situational awareness
- Local telemetry simulation
- Failure-state simulation

---

## Disclaimer

This project is developed for academic, research, portfolio, and engineering demonstration purposes.

The earthquake exposure model and local sensor telemetry are designed to demonstrate geospatial processing, infrastructure monitoring architecture, real-time communication, backend engineering, and cloud/DevOps concepts.

The system must not be used as:

- An official earthquake warning system
- An emergency response system
- A structural damage prediction system
- A substitute for authoritative emergency information
- A real physical infrastructure monitoring system without appropriate integrations and validation

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

This project is developed for academic, research, portfolio, and demonstration purposes and may be extended for enterprise geospatial infrastructure monitoring applications.
