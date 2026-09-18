# Cloud-Based Geospatial Infrastructure Monitoring System

A cloud-native geospatial infrastructure monitoring and situational awareness platform built with FastAPI, PostgreSQL/PostGIS, Docker, Kubernetes, Leaflet, WebSockets, and infrastructure automation concepts.

The platform combines geospatial infrastructure visualization, simulated infrastructure telemetry, alert management, incident operations, SRE intelligence, automation and reliability engineering, and predictive operational analysis.

## Project Overview

GeoInfra brings infrastructure inventory, telemetry, alerts, incidents, reliability engineering, automation, predictive analysis, and geospatial context into a single monitoring environment.

The system provides:

- Geospatial infrastructure visualization
- PostgreSQL/PostGIS spatial data storage
- Infrastructure health monitoring
- Local simulated sensor telemetry
- Historical telemetry persistence
- Alert detection and lifecycle management
- Incident management and SRE intelligence
- Reliability objectives and measurements
- Automation runbook workflows
- Predictive anomaly detection and trend analysis
- Predictive operational risk analysis
- Real-time WebSocket updates
- Docker-based development
- Kubernetes deployment
- Persistent Kubernetes database storage
- Version-controlled database migrations
- Deterministic bootstrap data

The project is an engineering and portfolio environment rather than a production monitoring product.

## Architecture

Phase 8 moves GeoInfra onto a Kubernetes-managed infrastructure foundation with persistent PostGIS storage, service discovery, configuration management, health probes, SQL migrations, and deterministic bootstrap data.

```text
                         GeoInfra Platform
                                |
                          Kubernetes
                     Namespace: geoinfra
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
      FastAPI Backend                      PostgreSQL/PostGIS
        Deployment                            StatefulSet
             |                                     |
             v                                     v
       geo-backend                           geodb Service
     ClusterIP Service                         Port 5432
             |                                     |
             |                                     v
             |                             PersistentVolumeClaim
             |                                postgis-data
             |
             +------------------+
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
         Telemetry         SRE Operations    Predictive Ops
         Monitoring        and Incidents
```

## Technology Stack

### Backend
- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- REST APIs
- WebSockets

### Database
- PostgreSQL
- PostGIS
- SQL migrations
- Geospatial `Point` geometry
- Persistent telemetry and operational records

### Frontend
- HTML
- CSS
- JavaScript
- Leaflet
- OpenStreetMap
- WebSocket-based updates

### Cloud and DevOps
- Docker
- Docker Compose
- Kubernetes
- Deployments
- StatefulSets
- Services
- PersistentVolumeClaims
- ConfigMaps
- Secrets
- Health probes
- Git and GitHub

## Kubernetes Architecture

The Kubernetes resources run inside the `geoinfra` namespace.

The FastAPI backend runs as a Kubernetes `Deployment` and is exposed internally through the `geo-backend` ClusterIP service on port `8000`.

PostgreSQL/PostGIS runs as a Kubernetes `StatefulSet` and is exposed internally through the `geodb` ClusterIP service on port `5432`.

```text
FastAPI Pod
    |
    v
geo-backend Service
    |
    | PostgreSQL connection
    v
geodb Service
    |
    v
PostGIS StatefulSet
    |
    v
PersistentVolumeClaim
```

The backend uses Kubernetes service discovery rather than depending on a database Pod IP.

## PostgreSQL and PostGIS

The primary geospatial infrastructure table is:

```text
public.infrastructure_points
```

Infrastructure locations use:

```text
geometry(Point, 4326)
```

Core fields include:

```text
id
name
description
infra_type
location
status
risk_score
severity
```

PostGIS supports coordinate extraction, spatial storage, distance calculations, nearest-infrastructure queries, and geographic exposure analysis.

## Persistent Kubernetes Storage

The PostGIS StatefulSet uses:

```text
PersistentVolumeClaim: postgis-data
Capacity: 5Gi
Access Mode: ReadWriteOnce (RWO)
```

Database state is therefore separated from the lifecycle of an individual PostGIS Pod.

## Kubernetes Services

Backend service:

```text
Service: geo-backend
Type: ClusterIP
Port: 8000
```

Database service:

```text
Service: geodb
Type: ClusterIP
Port: 5432
```

Backend database configuration:

```text
DB_HOST=geodb
DB_PORT=5432
DB_NAME=geospatialdb
DB_USER=postgres
```

## Configuration and Secrets

Runtime database configuration is supplied through a Kubernetes `ConfigMap`.

Configured values include:

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
```

Sensitive PostgreSQL credentials are supplied separately through a Kubernetes `Secret`.

An example Secret manifest documents the required structure without requiring real credentials to be committed to the repository.

## Database Migrations

Version-controlled SQL migrations are stored under:

```text
backend/migrations/
```

The migration chain covers:

- Base infrastructure schema
- Sensor telemetry history
- Alert persistence
- Incident management
- SRE intelligence
- Reliability and automation
- Predictive operations
- Deterministic infrastructure bootstrap data

Migration files include:

```text
phase_0_base_infrastructure.sql
phase_0_1_seed_infrastructure.sql
phase_6_4_sensor_history.sql
phase_6_6_alert_persistence.sql
phase_6_7_incident_management.sql
phase_6_8_sre_intelligence.sql
phase_6_9_reliability_automation.sql
phase_7_0_predictive_operations.sql
```

## Deterministic Infrastructure Seed

Phase 8 includes the idempotent migration:

```text
backend/migrations/phase_0_1_seed_infrastructure.sql
```

The current Kubernetes bootstrap asset is:

```text
Name: AWS London Region
Type: Cloud
Latitude: 51.5074
Longitude: -0.1276
Status: operational
Risk Score: 0
Severity: low
```

Final Phase 8 Kubernetes validation confirmed:

```text
Seeded infrastructure assets: 1
Operational assets: 1
```

The migration checks for an existing matching asset so repeated execution does not create duplicates.

## Kubernetes Deployment Flow

```text
Kubernetes Namespace
        |
        v
PostGIS StatefulSet
        |
        v
PersistentVolumeClaim
        |
        v
Database Service
        |
        v
Database Migrations
        |
        v
Base Infrastructure Seed
        |
        v
FastAPI Deployment
        |
        v
Backend Service
        |
        v
Health and API Validation
```

## Kubernetes Manifests

```text
kubernetes/
├── namespace.yaml
├── backend/
│   ├── backend-configmap.yaml
│   ├── backend-deployment.yaml
│   └── backend-service.yaml
└── database/
    ├── postgis-configmap.yaml
    ├── postgis-pvc.yaml
    ├── postgis-secret.example.yaml
    ├── postgis-service.yaml
    └── postgis-statefulset.yaml
```

## Monitoring Capabilities

GeoInfra includes:

- Interactive Leaflet infrastructure map
- Infrastructure health monitoring
- Live simulated telemetry
- Historical telemetry
- Sensor health evaluation
- Persistent alert lifecycle management
- Incident management
- P1-P4 priority handling
- SLA tracking and SRE intelligence
- Automation runbook workflows
- Reliability objectives and measurements
- Predictive anomaly detection
- Telemetry trend analysis
- Asset-level predictive operational risk

## Data Provenance

Simulated sensor telemetry is generated and processed locally.

```text
source: LOCAL_PROJECT
external: false
```

USGS earthquake information is consumed separately as read-only external data for geospatial exposure analysis. OpenStreetMap raster tiles provide map imagery.

Predictive risk is an operational heuristic based on project telemetry and is not a physical damage or real-world infrastructure failure forecast.

## Real-Time Communication

WebSocket channels include:

```text
/ws/events
/ws/locations
/ws/sensors
/ws/alerts
/ws/telemetry-alerts
/ws/incidents
```

## Representative REST APIs

```text
GET /health
GET /locations
GET /nearest
GET /analytics

GET /sensor-telemetry
GET /sensor-telemetry/{asset_id}
GET /sensor-health
GET /telemetry-history/{asset_id}
GET /telemetry-summary/{asset_id}

GET /alerts
GET /alerts/{asset_id}
GET /telemetry-alerts
GET /telemetry-alerts/{asset_id}

GET  /incidents
POST /incidents/synchronize
GET  /incidents/{incident_id}
POST /incidents/{incident_id}/acknowledge
POST /incidents/{incident_id}/assign
POST /incidents/{incident_id}/escalate
POST /incidents/{incident_id}/mitigate
POST /incidents/{incident_id}/resolve
POST /incidents/{incident_id}/reopen

GET  /sre/incident-metrics
GET  /sre/intelligence
GET  /sre/priority-policy
GET  /sre/sla-status
POST /sre/sla/evaluate

GET  /automation/runbooks
GET  /automation/executions
POST /automation/executions/request
GET  /automation/summary

GET  /reliability/objectives
GET  /reliability/measurements
POST /reliability/evaluate
GET  /reliability/summary

GET  /predictive/summary
GET  /anomaly-events
GET  /predictive/anomalies/{asset_id}
POST /predictive/anomalies/{asset_id}/evaluate
GET  /predictive/trends/{asset_id}
GET  /predictive/risk/{asset_id}
```

## Phase 8 Validation

Final Kubernetes validation confirmed:

```text
FastAPI backend Pod: Running
PostGIS Pod: Running
geo-backend Service: Available
geodb Service: Available
postgis-data PVC: Bound

Infrastructure assets: 1
Operational assets: 1
Database tables/views returned by validation query: 21
```

The following endpoints returned HTTP `200`:

```text
/health
/locations
/analytics
/sensor-telemetry
/sensor-health
/predictive/summary
/predictive/anomalies/1
/predictive/trends/1
/predictive/risk/1
```

This confirmed connectivity between the FastAPI application and the migrated PostGIS database in Kubernetes.

## Running with Docker Compose

```bash
docker compose up -d --build
docker compose ps
```

Test backend health:

```bash
curl http://127.0.0.1:8000/health
```

## Kubernetes Deployment

Create the namespace:

```bash
kubectl apply -f kubernetes/namespace.yaml
```

Apply database resources:

```bash
kubectl apply -n geoinfra -f kubernetes/database/postgis-configmap.yaml
kubectl apply -n geoinfra -f kubernetes/database/postgis-pvc.yaml
kubectl apply -n geoinfra -f kubernetes/database/postgis-service.yaml
kubectl apply -n geoinfra -f kubernetes/database/postgis-statefulset.yaml
```

Create the PostgreSQL Secret separately using appropriate credentials.

Apply backend resources:

```bash
kubectl apply -n geoinfra -f kubernetes/backend/backend-configmap.yaml
kubectl apply -n geoinfra -f kubernetes/backend/backend-service.yaml
kubectl apply -n geoinfra -f kubernetes/backend/backend-deployment.yaml
```

Check Kubernetes resources:

```bash
kubectl get pods -n geoinfra
kubectl get svc -n geoinfra
kubectl get pvc -n geoinfra
```

Apply the SQL migrations under `backend/migrations/` to a fresh database before full application validation.

## Security Notes

Do not commit real credentials, `.env` files, or populated Kubernetes Secret manifests.

The repository contains:

```text
kubernetes/database/postgis-secret.example.yaml
```

as an example credential structure.

## Repository Structure

```text
Cloud-Based-Geospatial-Infrastructure-Monitoring-System/
├── backend/
│   ├── main.py
│   ├── alert_engine.py
│   ├── trend_alert_engine.py
│   ├── incident_engine.py
│   ├── automation_engine.py
│   ├── reliability_engine.py
│   ├── anomaly_engine.py
│   ├── prediction_engine.py
│   ├── predictive_risk_engine.py
│   ├── migrations/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── Dockerfile
├── kubernetes/
│   ├── namespace.yaml
│   ├── backend/
│   └── database/
├── scripts/
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Engineering Concepts Demonstrated

- Cloud-native application architecture
- Kubernetes Deployments and StatefulSets
- Persistent Kubernetes storage
- Kubernetes service discovery
- ConfigMaps and Secrets
- Docker containerisation
- REST APIs and WebSockets
- PostgreSQL and PostGIS
- Geospatial queries
- SQL migrations
- Infrastructure monitoring
- Telemetry processing
- Alert lifecycle management
- Incident management
- SRE and SLA concepts
- Reliability objectives
- Controlled automation workflows
- Predictive operational analysis
- Git-based development workflows

## Current Status

Phase 8 Kubernetes cloud-native infrastructure is implemented and validated.

The Kubernetes deployment runs the FastAPI backend against a persistent PostgreSQL/PostGIS database with the required application migrations and deterministic bootstrap infrastructure data.

The project remains an engineering and portfolio environment for continued experimentation with cloud infrastructure, platform engineering, observability, reliability, and geospatial monitoring.

## Author

Nikunj Mirajkar

Cloud, DevOps, Platform and Infrastructure Engineering
