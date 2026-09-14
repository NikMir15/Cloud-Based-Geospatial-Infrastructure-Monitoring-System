-- =========================================================
-- PHASE 6.7
-- INCIDENT MANAGEMENT + SRE ANALYTICS
-- =========================================================
--
-- Prerequisite:
--   Phase 6.6 telemetry_alerts table must already exist.
--
-- All incident records are project-local.
-- =========================================================

BEGIN;

CREATE TABLE IF NOT EXISTS incidents (
    id BIGSERIAL PRIMARY KEY,

    incident_key VARCHAR(255) UNIQUE NOT NULL,

    title TEXT NOT NULL,
    summary TEXT,

    primary_asset_id INTEGER
        REFERENCES infrastructure_points(id)
        ON DELETE SET NULL,

    primary_asset_name TEXT,

    severity VARCHAR(20) NOT NULL DEFAULT 'low'
        CHECK (
            severity IN (
                'low',
                'medium',
                'high',
                'critical'
            )
        ),

    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (
            status IN (
                'open',
                'investigating',
                'mitigated',
                'resolved'
            )
        ),

    owner VARCHAR(150),

    source VARCHAR(50) NOT NULL DEFAULT 'LOCAL_PROJECT',
    external BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    acknowledged_at TIMESTAMPTZ,
    mitigated_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    resolution_note TEXT
);


CREATE TABLE IF NOT EXISTS incident_alerts (
    id BIGSERIAL PRIMARY KEY,

    incident_id BIGINT NOT NULL
        REFERENCES incidents(id)
        ON DELETE CASCADE,

    alert_id BIGINT NOT NULL
        REFERENCES telemetry_alerts(id)
        ON DELETE CASCADE,

    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    link_reason TEXT,

    UNIQUE (alert_id),
    UNIQUE (incident_id, alert_id)
);


CREATE TABLE IF NOT EXISTS incident_history (
    id BIGSERIAL PRIMARY KEY,

    incident_id BIGINT NOT NULL
        REFERENCES incidents(id)
        ON DELETE CASCADE,

    action VARCHAR(50) NOT NULL,

    from_status VARCHAR(20),
    to_status VARCHAR(20),

    severity VARCHAR(20),

    owner VARCHAR(150),

    note TEXT,

    changed_by VARCHAR(100) NOT NULL DEFAULT 'SYSTEM',

    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_incidents_status
    ON incidents(status);

CREATE INDEX IF NOT EXISTS idx_incidents_severity
    ON incidents(severity);

CREATE INDEX IF NOT EXISTS idx_incidents_asset
    ON incidents(primary_asset_id);

CREATE INDEX IF NOT EXISTS idx_incidents_last_seen
    ON incidents(last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_incidents_owner
    ON incidents(owner);

CREATE INDEX IF NOT EXISTS idx_incident_alerts_incident
    ON incident_alerts(incident_id);

CREATE INDEX IF NOT EXISTS idx_incident_alerts_alert
    ON incident_alerts(alert_id);

CREATE INDEX IF NOT EXISTS idx_incident_history_incident
    ON incident_history(incident_id);

CREATE INDEX IF NOT EXISTS idx_incident_history_changed_at
    ON incident_history(changed_at DESC);


-- Keep updated_at current even when records are modified outside
-- the FastAPI application.
CREATE OR REPLACE FUNCTION set_incident_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


DROP TRIGGER IF EXISTS trg_incidents_updated_at
ON incidents;


CREATE TRIGGER trg_incidents_updated_at
BEFORE UPDATE ON incidents
FOR EACH ROW
EXECUTE FUNCTION set_incident_updated_at();


COMMIT;
