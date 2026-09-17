# GeoInfra --- Cloud-Based Geospatial Infrastructure Monitoring System

A real-time infrastructure observability and Site Reliability
Engineering (SRE) platform combining geospatial monitoring, simulated
infrastructure telemetry, alerting, incident lifecycle management, SLA
tracking, and SRE intelligence in a unified command-center dashboard.

The project demonstrates practical Cloud, DevOps, Platform Engineering,
Observability, GIS, and SRE concepts using FastAPI, PostgreSQL/PostGIS,
Docker, WebSockets, Leaflet, JavaScript, and external earthquake data.

------------------------------------------------------------------------

## Project Overview

GeoInfra provides a real-time operational view of distributed
infrastructure assets through an interactive geospatial dashboard.

The platform monitors infrastructure locations, generates local
simulated telemetry, detects abnormal operating conditions, stores
historical telemetry, generates alerts, correlates alerts into
incidents, manages incident lifecycle operations, evaluates SLA
performance, and exposes SRE metrics through a command-center interface.

The system currently contains **56 monitored infrastructure assets**.

------------------------------------------------------------------------

## Current Release --- Phase 6.8

### SRE Intelligence & Incident Operations

Phase 6.8 extends the incident-management platform with:

-   P1--P4 incident priorities
-   Severity-to-priority mapping
-   Incident and team assignment
-   Incident escalation
-   Acknowledgement and resolution SLA deadlines
-   SLA breach detection and persistence
-   Incident acknowledgement, mitigation, resolution, and reopening
-   Incident history/audit trail
-   MTTA and MTTR
-   Priority distribution analytics
-   SRE Intelligence dashboard
-   Incident Operations queue
-   Interactive incident controls
-   SLA policy dashboard
-   Live incident synchronization

------------------------------------------------------------------------

## Technology Stack

**Backend:** Python, FastAPI, Uvicorn, SQLAlchemy, WebSockets\
**Database:** PostgreSQL, PostGIS\
**Frontend:** HTML5, CSS3, Vanilla JavaScript, Leaflet, OpenStreetMap\
**DevOps:** Docker, Docker Compose, Nginx, Git, GitHub, Linux / Ubuntu\
**External Integration:** USGS Earthquake GeoJSON API

------------------------------------------------------------------------

## Core Features

### Geospatial Monitoring

-   Interactive world map
-   Infrastructure type and risk filtering
-   Infrastructure markers and popups
-   Nearest-infrastructure calculation
-   PostGIS spatial queries
-   Real-time location updates

### Real-Time Sensor Telemetry

Telemetry includes health, CPU utilization, temperature, latency, packet
loss, signal strength, operational status, and timestamps.

Local telemetry uses:

``` json
{
  "source": "LOCAL_PROJECT",
  "external": false
}
```

### Historical Telemetry

-   Time-window queries
-   Telemetry summaries
-   Health, CPU, temperature, latency and packet-loss history
-   Automatic persistence
-   Retention management
-   Dashboard visualization

### Alerting

The platform detects threshold and trend conditions including high CPU,
temperature, latency, packet loss, health degradation, offline
infrastructure, and abnormal telemetry changes.

------------------------------------------------------------------------

## Alert Lifecycle --- Phase 6.6

``` text
ACTIVE → ACKNOWLEDGED → RESOLVED
```

Includes alert creation, acknowledgement, manual/automatic resolution,
reopening, severity updates, and persistent history.

------------------------------------------------------------------------

## Incident Management --- Phase 6.7

Related telemetry alerts can be correlated into incidents.

``` text
OPEN → INVESTIGATING → MITIGATED → RESOLVED
```

Capabilities include synchronization, assignment, escalation,
acknowledgement, mitigation, resolution, reopening, history, metrics,
and WebSocket updates.

------------------------------------------------------------------------

## SRE Intelligence --- Phase 6.8

### Priority Model

  Priority   Operational Level
  ---------- -------------------
  P1         Critical
  P2         High
  P3         Standard
  P4         Low

Default severity mapping:

``` text
critical → P1
high     → P2
medium   → P3
low      → P4
```

### SLA Policy

  Priority     Acknowledge        Resolve
  ---------- ------------- --------------
  P1            15 minutes    240 minutes
  P2            30 minutes    480 minutes
  P3            60 minutes   1440 minutes
  P4           240 minutes   4320 minutes

SLA fields include:

-   `acknowledgement_due_at`
-   `resolution_due_at`
-   `acknowledgement_sla_breached`
-   `resolution_sla_breached`

SRE metrics include MTTA, MTTR, open/resolved incidents, critical open
incidents, SLA breaches, and incident distribution by severity, status,
and priority.

------------------------------------------------------------------------

## Infrastructure Command Center

The frontend contains:

-   Infrastructure overview
-   KPI cards
-   Interactive world map
-   Infrastructure health
-   Real-time and historical telemetry
-   Sensor health alerts
-   Recent alerts
-   Persistent alert lifecycle
-   Incident Operations
-   SRE Intelligence
-   SLA Intelligence
-   Priority distribution
-   Analytics
-   Operational controls

Incident actions include:

``` text
View
Priority
Assign
Acknowledge
Escalate
Mitigate
Resolve
Reopen
```

------------------------------------------------------------------------

## REST API

### Infrastructure

``` http
GET /health
GET /locations
GET /nearest
GET /analytics
```

### Telemetry

``` http
GET /sensor-telemetry
GET /sensor-telemetry/{asset_id}
GET /telemetry-history/{asset_id}
GET /telemetry-summary/{asset_id}
```

### Alerts

``` http
GET /sensor-health
GET /alerts
GET /alerts/{asset_id}
GET /telemetry-alerts
GET /telemetry-alerts/{asset_id}
GET /telemetry-alert-history
GET /telemetry-alert-history/{alert_id}/events
POST /telemetry-alerts/{alert_id}/acknowledge
POST /telemetry-alerts/{alert_id}/resolve
```

### Incidents

``` http
GET  /incidents
POST /incidents/synchronize
GET  /incidents/{incident_id}
POST /incidents/{incident_id}/acknowledge
POST /incidents/{incident_id}/assign
POST /incidents/{incident_id}/escalate
GET  /incidents/{incident_id}/events
POST /incidents/{incident_id}/mitigate
POST /incidents/{incident_id}/reopen
POST /incidents/{incident_id}/resolve
```

### Phase 6.8 SRE APIs

``` http
POST /incidents/{incident_id}/priority
GET  /incidents/{incident_id}/sla
GET  /sre/incident-metrics
GET  /sre/intelligence
GET  /sre/priority-policy
GET  /sre/sla-status
POST /sre/sla/evaluate
```

------------------------------------------------------------------------

## WebSockets

``` text
/ws/events
/ws/locations
/ws/sensors
/ws/alerts
/ws/telemetry-alerts
/ws/incidents
```

------------------------------------------------------------------------

## Database

Primary objects include:

``` text
infrastructure_points
sensor_telemetry_history
telemetry_alerts
telemetry_alert_history
incidents
incident_alerts
incident_history
incident_sre_summary
```

------------------------------------------------------------------------

## Project Structure

``` text
Cloud-Based-Geospatial-Infrastructure-Monitoring-System/
├── backend/
│   ├── main.py
│   ├── alert_engine.py
│   ├── trend_alert_engine.py
│   ├── incident_engine.py
│   ├── requirements.txt
│   ├── migrations/
│   │   ├── phase_6_4_sensor_history.sql
│   │   ├── phase_6_6_alert_persistence.sql
│   │   ├── phase_6_7_incident_management.sql
│   │   └── phase_6_8_sre_intelligence.sql
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── Dockerfile
├── scripts/
│   ├── verify_phase_6_8_edit_d.py
│   └── test_phase_6_8_mutation.sh
├── docker-compose.yml
├── .gitignore
└── README.md
```

------------------------------------------------------------------------

## Running the Project

Requirements: Docker, Docker Compose, and Git.

``` bash
git clone git@github.com:NikMir15/Cloud-Based-Geospatial-Infrastructure-Monitoring-System.git
cd Cloud-Based-Geospatial-Infrastructure-Monitoring-System
docker compose up -d --build
docker compose ps
```

Frontend:

``` text
http://localhost:8080
```

Backend:

``` text
http://localhost:8000
```

FastAPI documentation:

``` text
http://localhost:8000/docs
```

------------------------------------------------------------------------

## Database Access

``` bash
docker exec -it geodb psql -U postgres -d geospatialdb
```

Verify PostGIS:

``` sql
SELECT PostGIS_Version();
```

------------------------------------------------------------------------

## Phase 6.8 Verification

``` bash
python3 -m py_compile backend/main.py
python3 -m py_compile backend/alert_engine.py
python3 -m py_compile backend/trend_alert_engine.py
python3 -m py_compile backend/incident_engine.py

node --check frontend/app.js

python3 scripts/verify_phase_6_8_edit_d.py
./scripts/test_phase_6_8_mutation.sh
```

------------------------------------------------------------------------

## Privacy & Data Provenance

Simulated infrastructure telemetry is generated, stored, and processed
locally by the project.

USGS earthquake information is retrieved through a read-only HTTP GET
integration. Local infrastructure telemetry is not sent to USGS.
OpenStreetMap is used for map tiles.

------------------------------------------------------------------------

## Risk Model

Infrastructure risk scoring is an **estimated operational exposure
heuristic** for monitoring and demonstration. It is not a physical
damage prediction, earthquake damage forecast, safety certification, or
production disaster-impact model.

------------------------------------------------------------------------

## Engineering Concepts Demonstrated

-   Cloud-native architecture
-   Containerization
-   REST APIs and WebSockets
-   PostgreSQL/PostGIS
-   Geospatial analysis
-   Real-time observability
-   Telemetry pipelines
-   Threshold and trend alerting
-   Alert lifecycle management
-   Incident correlation and management
-   SLA-oriented operations
-   MTTA and MTTR
-   SRE workflows
-   Operational dashboards
-   Linux and Git/GitHub workflows

------------------------------------------------------------------------

## Development Roadmap

Completed:

``` text
Phase 6.2  Local Sensor Telemetry
Phase 6.3  Sensor Health Alerting
Phase 6.4  Historical Telemetry
Phase 6.5  Telemetry Alerting & Trend Detection
Phase 6.6  Persistent Alert Lifecycle
Phase 6.7  Incident Management & SRE Analytics
Phase 6.8  SRE Intelligence & Incident Operations
```

Potential next milestone:

**Phase 6.9 --- Incident Automation & Reliability Engineering**

Possible future capabilities include automated remediation runbooks,
SLO/error-budget tracking, improved incident correlation, automated
incident response, runbook history, service dependency modelling, and
advanced infrastructure analytics.

------------------------------------------------------------------------

## Disclaimer

This project is an engineering portfolio and research/demo platform.
Infrastructure telemetry is simulated unless explicitly identified
otherwise. External earthquake information is obtained from the USGS
read-only feed.

The platform should not be used as a production emergency-response,
public-safety, or physical infrastructure damage-prediction system.

------------------------------------------------------------------------

## Author

**Nikunj Mirajkar**\
Cloud \| DevOps \| Platform & Infrastructure Engineering\
GitHub: **NikMir15**

------------------------------------------------------------------------

## Project Status

**Active Development**

Current milestone: **Phase 6.8 --- SRE Intelligence & Incident
Operations**
