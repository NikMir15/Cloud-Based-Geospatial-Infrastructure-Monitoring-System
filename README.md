# Cloud-Based Geospatial Infrastructure Monitoring System

A cloud-native infrastructure situational-awareness and monitoring platform built with **FastAPI, PostgreSQL/PostGIS, Docker, Kubernetes, Leaflet, WebSockets, telemetry analytics, SRE incident management, automation, reliability engineering, and predictive operations**.

The platform combines geospatial infrastructure visualization with live telemetry, alerting, incident operations, SRE intelligence, reliability objectives, automation workflows, anomaly detection, trend analysis, and predictive operational risk.

---

## Overview

The project began as a geospatial infrastructure monitoring application and has evolved into an infrastructure operations platform capable of:

- Visualizing infrastructure assets geographically
- Monitoring simulated project-local telemetry
- Processing infrastructure health signals
- Generating telemetry alerts
- Persisting alert lifecycle history
- Managing operational incidents
- Tracking incident priority and SLA performance
- Measuring SRE and reliability objectives
- Managing automation/runbook workflows
- Detecting telemetry anomalies
- Analysing infrastructure trends
- Calculating predictive operational risk
- Processing external earthquake data using PostGIS
- Streaming updates using WebSockets
- Running as containerized services
- Deploying backend and PostgreSQL/PostGIS workloads to Kubernetes

---

# Architecture

```text
                         ┌─────────────────────────────┐
                         │          Browser            │
                         │ Leaflet + JavaScript + CSS  │
                         └──────────────┬──────────────┘
                                        │
                                   HTTP / WebSocket
                                        │
                         ┌──────────────▼──────────────┐
                         │       FastAPI Backend        │
                         │                              │
                         │ REST APIs                    │
                         │ WebSocket streams            │
                         │ Telemetry engine             │
                         │ Alert engine                 │
                         │ Incident engine              │
                         │ Automation engine            │
                         │ Reliability engine           │
                         │ Anomaly detection            │
                         │ Trend prediction             │
                         │ Predictive risk engine       │
                         └──────────────┬──────────────┘
                                        │
                                      SQL
                                        │
                         ┌──────────────▼──────────────┐
                         │     PostgreSQL + PostGIS     │
                         │                              │
                         │ Infrastructure assets        │
                         │ Telemetry history            │
                         │ Alerts                       │
                         │ Incidents                    │
                         │ Automation                   │
                         │ Reliability measurements     │
                         │ Predictive anomaly events    │
                         └─────────────────────────────┘

External read-only data:
USGS Earthquake GeoJSON API ───────────► FastAPI / PostGIS analysis
```

---

# Technology Stack

## Backend

- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- PostgreSQL
- PostGIS
- WebSockets

## Frontend

- HTML5
- CSS3
- JavaScript
- Leaflet
- OpenStreetMap tiles
- WebSocket clients
- SVG-based telemetry visualization

## Infrastructure

- Docker
- Docker Compose
- Kubernetes
- Minikube
- ConfigMaps
- Secrets
- StatefulSets
- Deployments
- Services
- PersistentVolumeClaims

## Engineering Concepts

- REST API design
- Geospatial querying
- Real-time telemetry
- Alert lifecycle management
- Incident management
- SRE operations
- SLA tracking
- Reliability engineering
- Runbook automation
- Predictive operations
- Infrastructure health monitoring
- Container orchestration

---

# Project Evolution

## Phase 6.2 — Live Sensor Telemetry

Introduced project-local simulated infrastructure telemetry.

Telemetry includes metrics such as:

- Health
- CPU utilisation
- Temperature
- Latency
- Packet loss
- Signal strength

Telemetry is generated locally by the project and is not sent to external services.

Core interfaces include:

```text
GET /sensor-telemetry
GET /sensor-telemetry/{asset_id}

WS /ws/sensors
```

---

## Phase 6.3 — Sensor Health Alerting

Added telemetry-based health evaluation and operational alerts.

Core interfaces:

```text
GET /sensor-health
GET /alerts
GET /alerts/{asset_id}

WS /ws/alerts
```

---

## Phase 6.4 — Historical Telemetry

Added PostgreSQL-backed telemetry history.

Historical telemetry enables:

- Time-series inspection
- Telemetry summaries
- Trend calculations
- Predictive analysis

Core interfaces:

```text
GET /telemetry-history/{asset_id}
GET /telemetry-summary/{asset_id}
```

Telemetry history is stored in:

```text
sensor_telemetry_history
```

---

## Phase 6.5 — Telemetry Trend Alerts

Added metric threshold and trend-based telemetry alerting.

Core interfaces:

```text
GET /telemetry-alerts
GET /telemetry-alerts/{asset_id}

WS /ws/telemetry-alerts
```

---

## Phase 6.6 — Persistent Alert Lifecycle

Introduced persisted operational alert management.

Capabilities include:

- Active alerts
- Alert history
- Alert acknowledgement
- Alert resolution
- Alert lifecycle tracking

Primary database objects include:

```text
telemetry_alerts
telemetry_alert_history
```

---

## Phase 6.7 — Incident Management

Introduced an SRE-style incident management layer.

Capabilities include:

- Automatic incident synchronization
- Incident acknowledgement
- Assignment
- Escalation
- Mitigation
- Reopening
- Resolution
- Incident history
- Incident metrics

Core interfaces include:

```text
GET  /incidents
POST /incidents/synchronize

GET  /incidents/{incident_id}

POST /incidents/{incident_id}/acknowledge
POST /incidents/{incident_id}/assign
POST /incidents/{incident_id}/escalate
POST /incidents/{incident_id}/mitigate
POST /incidents/{incident_id}/reopen
POST /incidents/{incident_id}/resolve

GET /incidents/{incident_id}/events

GET /sre/incident-metrics
```

Real-time incident updates are available through:

```text
WS /ws/incidents
```

Primary database objects:

```text
incidents
incident_alerts
incident_history
```

---

## Phase 6.8 — Incident Operations & SRE Intelligence

Extended incident management with operational priority and SLA intelligence.

Capabilities include:

- P1-P4 incident priorities
- Assigned operational teams
- Acknowledgement deadlines
- Resolution deadlines
- SLA breach tracking
- Priority mutation history
- SRE intelligence metrics

Core interfaces include:

```text
POST /incidents/{incident_id}/priority

GET /incidents/{incident_id}/sla

GET /sre/intelligence
GET /sre/priority-policy
GET /sre/sla-status

POST /sre/sla/evaluate
```

SLA resolution targets currently include:

| Priority | Resolution Target |
|---|---:|
| P1 | 240 minutes |
| P2 | 480 minutes |
| P3 | 1440 minutes |
| P4 | 4320 minutes |

---

## Phase 6.9 — Automation + Reliability Engineering

Added controlled operational automation and service reliability monitoring.

### Automation

Capabilities include:

- Runbook definitions
- Automation matching
- Execution requests
- Approval workflow
- Controlled execution
- Cancellation
- Execution history

Core interfaces:

```text
GET  /automation/runbooks
GET  /automation/runbooks/{runbook_id}

GET  /automation/match
POST /automation/matches

GET  /automation/executions
POST /automation/executions/request

GET  /automation/executions/{execution_id}
POST /automation/executions/{execution_id}/approve
POST /automation/executions/{execution_id}/cancel
POST /automation/executions/{execution_id}/execute

GET /automation/executions/{execution_id}/history
GET /automation/summary
```

### Reliability Engineering

Capabilities include:

- Service objectives
- SLO evaluation
- Reliability measurements
- Error-budget analysis
- Reliability summaries

Core interfaces:

```text
GET /reliability/objectives
GET /reliability/objectives/{objective_id}

POST /reliability/objectives/{objective_id}/evaluate

GET /reliability/measurements
POST /reliability/evaluate

GET /reliability/summary
```

---

# Phase 7 — Predictive Operations

Phase 7 introduces predictive infrastructure intelligence using locally generated telemetry and historical operational data.

The objective is not to predict physical infrastructure failure with certainty. Instead, the system provides an **operational risk heuristic** that can help prioritise infrastructure requiring attention.

Capabilities include:

- Telemetry anomaly detection
- Historical trend analysis
- Predictive operational risk scoring
- Persisted anomaly events
- Per-asset predictive analysis
- Predictive dashboard visualization

Core interfaces:

```text
GET /predictive/summary

GET /anomaly-events

GET /predictive/anomalies/{asset_id}
POST /predictive/anomalies/{asset_id}/evaluate

GET /predictive/trends/{asset_id}

GET /predictive/risk/{asset_id}
```

Backend components:

```text
backend/anomaly_engine.py
backend/prediction_engine.py
backend/predictive_risk_engine.py
```

The frontend contains a dedicated **Predictive Ops** command-center section showing:

- Anomaly events
- Affected assets
- Selected asset risk
- Risk level
- Telemetry anomalies
- Telemetry trends
- Operational risk
- Recent anomaly events

Predictive results are derived from project-local operational telemetry.

They should be interpreted as monitoring and prioritisation signals rather than physical failure or damage forecasts.

---

# Phase 8 — Kubernetes Deployment

Phase 8 introduces Kubernetes orchestration for the platform.

The current Kubernetes implementation deploys the **FastAPI backend and PostgreSQL/PostGIS database** into a dedicated Kubernetes namespace.

Development and validation are performed locally using Minikube.

## Kubernetes Components

The deployment uses:

- Kubernetes Deployment for FastAPI
- Kubernetes StatefulSet for PostgreSQL/PostGIS
- ConfigMaps for application/database configuration
- Kubernetes Secret for PostgreSQL credentials
- PersistentVolumeClaim for database persistence
- ClusterIP Services for internal networking
- Readiness probes
- Liveness probes
- CPU and memory resource requests
- CPU and memory limits

Current namespace:

```text
geoinfra
```

Current backend service:

```text
geo-backend
```

Current PostgreSQL pod:

```text
geodb-0
```

---

# Kubernetes Project Structure

```text
kubernetes/
├── backend/
│   ├── backend-configmap.yaml
│   ├── backend-deployment.yaml
│   └── backend-service.yaml
│
└── database/
    ├── postgis-configmap.yaml
    ├── postgis-pvc.yaml
    ├── postgis-secret.example.yaml
    ├── postgis-service.yaml
    └── postgis-statefulset.yaml
```

Real credentials should not be committed to Git.

Use the example secret manifest as a template and provide credentials through an appropriate local or deployment-specific secret-management workflow.

---

# Kubernetes Backend Deployment

Apply the backend resources:

```bash
kubectl apply \
  -f kubernetes/backend/backend-configmap.yaml \
  -f kubernetes/backend/backend-deployment.yaml \
  -f kubernetes/backend/backend-service.yaml
```

Monitor backend pods:

```bash
kubectl get pods -n geoinfra -w
```

Inspect the deployment:

```bash
kubectl describe deployment geo-backend -n geoinfra
```

Inspect backend logs:

```bash
kubectl logs -n geoinfra deployment/geo-backend --tail=100
```

---

# Kubernetes Health Checks

The backend exposes:

```text
GET /health
```

Kubernetes uses this endpoint for readiness and liveness checks.

The backend container listens on:

```text
8000/TCP
```

Example readiness configuration:

```text
HTTP GET /health
```

The deployment also defines resource requests and limits to make container resource requirements explicit.

---

# PostgreSQL/PostGIS on Kubernetes

PostgreSQL/PostGIS runs as a Kubernetes StatefulSet.

Check the database pod:

```bash
kubectl get pods -n geoinfra
```

Connect to PostgreSQL:

```bash
kubectl exec -it -n geoinfra geodb-0 -- \
  psql -U postgres -d geospatialdb
```

Verify PostGIS:

```sql
SELECT PostGIS_Version();
```

---

# Database Foundation

The platform uses PostgreSQL with PostGIS for infrastructure and operational data.

The base infrastructure table is:

```text
public.infrastructure_points
```

The current verified columns are:

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

The `location` column uses the PostGIS spatial point type with SRID `4326`.

The base migration is:

```text
backend/migrations/phase_0_base_infrastructure.sql
```

The migration is designed to be **idempotent**, allowing it to be executed safely against both new and existing project databases.

It:

- Enables PostGIS if required
- Creates `infrastructure_points` when absent
- Adds required columns when absent
- Establishes expected defaults
- Creates supporting indexes when absent
- Preserves existing infrastructure rows

The migration does not intentionally seed synthetic infrastructure records.

---

# Database Migration Order

Database migrations have dependencies and should be applied in order.

```text
phase_0_base_infrastructure.sql
phase_6_4_sensor_history.sql
phase_6_6_alert_persistence.sql
phase_6_7_incident_management.sql
phase_6_8_sre_intelligence.sql
phase_6_9_reliability_automation.sql
phase_7_0_predictive_operations.sql
```

Later migrations reference `infrastructure_points`, so the Phase 0 base migration must be applied first when provisioning a fresh database.

---

# Applying the Base Migration in Kubernetes

From the repository root:

```bash
kubectl exec -i -n geoinfra geodb-0 -- \
  psql \
  -v ON_ERROR_STOP=1 \
  -U postgres \
  -d geospatialdb \
  < backend/migrations/phase_0_base_infrastructure.sql
```

Successful execution should return:

```text
COMMIT
```

and an exit code of:

```text
0
```

Running the migration again should also succeed, demonstrating idempotency.

---

# Verify the Infrastructure Table

```bash
kubectl exec -n geoinfra geodb-0 -- \
  psql -U postgres -d geospatialdb -c \
  '\d+ public.infrastructure_points'
```

Check the number of infrastructure records:

```bash
kubectl exec -n geoinfra geodb-0 -- \
  psql -U postgres -d geospatialdb -c \
  'SELECT COUNT(*) FROM public.infrastructure_points;'
```

A newly provisioned Kubernetes database may contain zero infrastructure records until infrastructure data is seeded or imported.

---

# Geospatial Capabilities

PostGIS provides the spatial foundation for the platform.

Infrastructure coordinates are stored as spatial points using SRID:

```text
4326
```

The backend uses PostGIS operations including:

```text
ST_MakePoint
ST_SetSRID
ST_X
ST_Y
ST_DWithin
```

These enable:

- Infrastructure mapping
- Nearest-asset searches
- Distance calculations
- Hazard exposure analysis
- Geospatial filtering

---

# Historical Infrastructure Example

An early documented API response included:

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

This historical example documents the early data model and should not be interpreted as an automatic seed performed by the current Kubernetes database migration.

---

# External Hazard Monitoring

The platform integrates a read-only USGS earthquake GeoJSON feed.

External data is retrieved from the USGS API and analysed against infrastructure locations using PostGIS.

The application does **not** send project infrastructure data to USGS.

The external earthquake feed is used for:

- Nearby-event analysis
- Infrastructure exposure estimation
- Geospatial risk visualization

Risk values represent operational exposure heuristics and should not be interpreted as physical damage predictions.

---

# Real-Time Communication

The application uses WebSockets for live operational updates.

Available streams include:

```text
/ws/events
/ws/locations
/ws/sensors
/ws/alerts
/ws/telemetry-alerts
/ws/incidents
```

These streams support live dashboard updates without requiring full page refreshes.

---

# Command Center Frontend

The frontend is designed as a dark infrastructure operations command center.

Major dashboard areas include:

- Infrastructure map
- Infrastructure health
- Recent alerts
- Live sensor telemetry
- Sensor health
- Alert lifecycle
- SRE operations
- Automation
- Reliability engineering
- Predictive operations
- Analytics

The map uses Leaflet and OpenStreetMap raster tiles.

Infrastructure markers are rendered geographically using coordinates returned by the FastAPI backend.

---

# Main API Groups

## Platform

```text
GET /
GET /health
GET /locations
GET /nearest
GET /analytics
```

## Telemetry

```text
GET /sensor-telemetry
GET /sensor-telemetry/{asset_id}

GET /telemetry-history/{asset_id}
GET /telemetry-summary/{asset_id}
```

## Alerts

```text
GET /sensor-health

GET /alerts
GET /alerts/{asset_id}

GET /telemetry-alerts
GET /telemetry-alerts/{asset_id}
```

## Incidents

```text
GET  /incidents
POST /incidents/synchronize

GET  /incidents/{incident_id}
GET  /incidents/{incident_id}/events
GET  /incidents/{incident_id}/sla

POST /incidents/{incident_id}/acknowledge
POST /incidents/{incident_id}/assign
POST /incidents/{incident_id}/priority
POST /incidents/{incident_id}/escalate
POST /incidents/{incident_id}/mitigate
POST /incidents/{incident_id}/reopen
POST /incidents/{incident_id}/resolve
```

## SRE

```text
GET /sre/incident-metrics
GET /sre/intelligence
GET /sre/priority-policy
GET /sre/sla-status

POST /sre/sla/evaluate
```

## Automation

```text
GET /automation/runbooks
GET /automation/runbooks/{runbook_id}

GET /automation/match
POST /automation/matches

GET /automation/executions
POST /automation/executions/request

GET /automation/executions/{execution_id}
POST /automation/executions/{execution_id}/approve
POST /automation/executions/{execution_id}/cancel
POST /automation/executions/{execution_id}/execute

GET /automation/executions/{execution_id}/history

GET /automation/summary
```

## Reliability

```text
GET /reliability/objectives
GET /reliability/objectives/{objective_id}

POST /reliability/objectives/{objective_id}/evaluate

GET /reliability/measurements

POST /reliability/evaluate

GET /reliability/summary
```

## Predictive Operations

```text
GET /predictive/summary
GET /anomaly-events

GET  /predictive/anomalies/{asset_id}
POST /predictive/anomalies/{asset_id}/evaluate

GET /predictive/trends/{asset_id}
GET /predictive/risk/{asset_id}
```

---

# Docker Deployment

The platform can also run using Docker Compose.

Start the services:

```bash
docker compose up -d --build
```

Check status:

```bash
docker compose ps
```

Backend:

```text
http://localhost:8000
```

Frontend:

```text
http://localhost:8080
```

FastAPI documentation:

```text
http://localhost:8000/docs
```

Backend logs:

```bash
docker compose logs --tail=100 backend
```

Stop the environment:

```bash
docker compose down
```

---

# Local Development

Clone the repository:

```bash
git clone git@github.com:NikMir15/Cloud-Based-Geospatial-Infrastructure-Monitoring-System.git

cd Cloud-Based-Geospatial-Infrastructure-Monitoring-System
```

Create a Python virtual environment:

```bash
python3 -m venv backend/venv
source backend/venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

Run FastAPI:

```bash
cd backend
uvicorn main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

---

# Project Structure

```text
Cloud-Based-Geospatial-Infrastructure-Monitoring-System/
│
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
│   ├── requirements.txt
│   ├── Dockerfile
│   │
│   └── migrations/
│       ├── phase_0_base_infrastructure.sql
│       ├── phase_6_4_sensor_history.sql
│       ├── phase_6_6_alert_persistence.sql
│       ├── phase_6_7_incident_management.sql
│       ├── phase_6_8_sre_intelligence.sql
│       ├── phase_6_9_reliability_automation.sql
│       └── phase_7_0_predictive_operations.sql
│
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── Dockerfile
│
├── kubernetes/
│   ├── backend/
│   │   ├── backend-configmap.yaml
│   │   ├── backend-deployment.yaml
│   │   └── backend-service.yaml
│   │
│   └── database/
│       ├── postgis-configmap.yaml
│       ├── postgis-pvc.yaml
│       ├── postgis-secret.example.yaml
│       ├── postgis-service.yaml
│       └── postgis-statefulset.yaml
│
├── scripts/
│
├── docker-compose.yml
├── README.md
└── .gitignore
```

---

# Data Provenance

The platform distinguishes between project-local operational data and external data.

## Local Project Data

Simulated infrastructure telemetry is generated locally by the project.

Where provenance metadata is exposed, local telemetry uses:

```json
{
  "source": "LOCAL_PROJECT",
  "external": false
}
```

Local telemetry is used for:

- Health monitoring
- Alert generation
- Incident management
- Reliability calculations
- Anomaly detection
- Trend analysis
- Predictive operational risk

## External Data

USGS earthquake information is retrieved using read-only HTTP requests.

OpenStreetMap tiles are retrieved by the browser for map visualization.

---

# Security Considerations

The project follows several infrastructure security practices:

- Database credentials are separated from application configuration
- Kubernetes Secrets are used for sensitive database values
- Example secret manifests can be committed without real credentials
- PostgreSQL is exposed internally through Kubernetes services
- Application containers define resource limits
- Readiness and liveness probes monitor backend health
- Database storage uses a PersistentVolumeClaim
- External hazard integration is read-only

Production deployments should additionally use:

- Managed secret storage
- TLS
- Kubernetes NetworkPolicies
- RBAC
- Image vulnerability scanning
- Restricted container security contexts
- Managed PostgreSQL backups
- Centralized monitoring and logging
- CI/CD-controlled deployments

---

# Current Kubernetes Status

The Kubernetes backend and PostgreSQL/PostGIS workload have been successfully deployed and validated locally using Minikube.

The backend pod reaches:

```text
READY 1/1
STATUS Running
```

and passes its `/health` readiness and liveness checks.

The PostgreSQL/PostGIS database is operational and the base `infrastructure_points` schema can be provisioned successfully using the Phase 0 migration.

Infrastructure dataset restoration/seeding is handled separately from the base schema migration.

---

# Engineering Goals

This project is designed to demonstrate practical experience across:

- Cloud-native application architecture
- Linux
- Docker
- Kubernetes
- FastAPI
- PostgreSQL/PostGIS
- Infrastructure monitoring
- Real-time WebSockets
- Incident response
- SRE principles
- SLA management
- Reliability engineering
- Operational automation
- Predictive monitoring
- Geospatial systems
- Infrastructure-as-code-style deployment configuration

---

# Roadmap

Potential future enhancements include:

- Complete Kubernetes deployment of the frontend
- Kubernetes Ingress
- Horizontal Pod Autoscaling
- Prometheus metrics
- Grafana dashboards
- Centralized Kubernetes logging
- NetworkPolicies
- Kubernetes RBAC
- Helm packaging
- CI/CD deployment to Kubernetes
- Managed cloud Kubernetes deployment
- Database backup/restore automation
- Infrastructure dataset bootstrap
- Predictive model evaluation
- Extended observability and tracing

---

# Disclaimer

Telemetry generated by the project is simulated operational data intended for development, demonstration, and engineering analysis.

Predictive risk scores and hazard exposure values are operational heuristics.

They should not be interpreted as physical infrastructure failure predictions, safety guarantees, or real-world damage forecasts.

---

# Author

**Nikunj Mirajkar**

Cloud | DevOps | Platform & Infrastructure Engineering

GitHub: `NikMir15`

---

## Project Status

**Active Development**

Current development focus:

```text
Phase 8 — Kubernetes / Cloud-Native Infrastructure
```
