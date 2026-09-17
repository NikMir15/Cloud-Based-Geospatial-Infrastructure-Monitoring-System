-- ============================================================
-- Phase 6.8 - Incident Operations & SRE Intelligence
-- Cloud-Based Geospatial Infrastructure Monitoring System
--
-- Extends Phase 6.7 incident management with:
--   * Incident priority
--   * Team assignment
--   * Escalation tracking
--   * Acknowledgement / resolution SLA deadlines
--   * SLA breach tracking
--   * MTTA / MTTR support
--
-- Safe/idempotent migration.
-- Existing Phase 6.7 incident data is preserved.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. Extend incidents table
-- ------------------------------------------------------------

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS priority VARCHAR(10);

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS assigned_team VARCHAR(150);

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS escalated BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMPTZ;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS escalation_level INTEGER NOT NULL DEFAULT 0;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS acknowledgement_due_at TIMESTAMPTZ;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS resolution_due_at TIMESTAMPTZ;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS acknowledgement_sla_breached BOOLEAN
        NOT NULL DEFAULT FALSE;

ALTER TABLE incidents
    ADD COLUMN IF NOT EXISTS resolution_sla_breached BOOLEAN
        NOT NULL DEFAULT FALSE;


-- ------------------------------------------------------------
-- 2. Priority validation
-- ------------------------------------------------------------

UPDATE incidents
SET priority =
    CASE severity
        WHEN 'critical' THEN 'P1'
        WHEN 'high'     THEN 'P2'
        WHEN 'medium'   THEN 'P3'
        ELSE 'P4'
    END
WHERE priority IS NULL;


ALTER TABLE incidents
    ALTER COLUMN priority SET DEFAULT 'P4';

ALTER TABLE incidents
    ALTER COLUMN priority SET NOT NULL;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'incidents_priority_check'
    ) THEN
        ALTER TABLE incidents
            ADD CONSTRAINT incidents_priority_check
            CHECK (priority IN ('P1', 'P2', 'P3', 'P4'));
    END IF;
END
$$;


-- ------------------------------------------------------------
-- 3. Escalation-level validation
-- ------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'incidents_escalation_level_check'
    ) THEN
        ALTER TABLE incidents
            ADD CONSTRAINT incidents_escalation_level_check
            CHECK (escalation_level >= 0 AND escalation_level <= 4);
    END IF;
END
$$;


-- ------------------------------------------------------------
-- 4. Populate assignment timestamps for existing incidents
-- ------------------------------------------------------------

UPDATE incidents
SET assigned_at = COALESCE(acknowledged_at, created_at)
WHERE owner IS NOT NULL
  AND assigned_at IS NULL;


-- ------------------------------------------------------------
-- 5. Populate SLA deadlines for existing incidents
--
-- P1: acknowledge 15 min / resolve 4 hr
-- P2: acknowledge 30 min / resolve 8 hr
-- P3: acknowledge 60 min / resolve 24 hr
-- P4: acknowledge 4 hr  / resolve 72 hr
-- ------------------------------------------------------------

UPDATE incidents
SET
    acknowledgement_due_at =
        created_at +
        CASE priority
            WHEN 'P1' THEN INTERVAL '15 minutes'
            WHEN 'P2' THEN INTERVAL '30 minutes'
            WHEN 'P3' THEN INTERVAL '1 hour'
            ELSE INTERVAL '4 hours'
        END,

    resolution_due_at =
        created_at +
        CASE priority
            WHEN 'P1' THEN INTERVAL '4 hours'
            WHEN 'P2' THEN INTERVAL '8 hours'
            WHEN 'P3' THEN INTERVAL '24 hours'
            ELSE INTERVAL '72 hours'
        END
WHERE acknowledgement_due_at IS NULL
   OR resolution_due_at IS NULL;


-- ------------------------------------------------------------
-- 6. Calculate current SLA breach state
-- ------------------------------------------------------------

UPDATE incidents
SET acknowledgement_sla_breached =
    CASE
        WHEN acknowledged_at IS NOT NULL
            THEN acknowledged_at > acknowledgement_due_at
        ELSE NOW() > acknowledgement_due_at
    END
WHERE acknowledgement_due_at IS NOT NULL;


UPDATE incidents
SET resolution_sla_breached =
    CASE
        WHEN resolved_at IS NOT NULL
            THEN resolved_at > resolution_due_at
        ELSE NOW() > resolution_due_at
    END
WHERE resolution_due_at IS NOT NULL;


-- ------------------------------------------------------------
-- 7. Indexes for operations/SRE queries
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_incidents_priority
    ON incidents(priority);

CREATE INDEX IF NOT EXISTS idx_incidents_assigned_team
    ON incidents(assigned_team);

CREATE INDEX IF NOT EXISTS idx_incidents_assigned_at
    ON incidents(assigned_at DESC);

CREATE INDEX IF NOT EXISTS idx_incidents_escalated
    ON incidents(escalated);

CREATE INDEX IF NOT EXISTS idx_incidents_escalation_level
    ON incidents(escalation_level);

CREATE INDEX IF NOT EXISTS idx_incidents_ack_due
    ON incidents(acknowledgement_due_at);

CREATE INDEX IF NOT EXISTS idx_incidents_resolution_due
    ON incidents(resolution_due_at);

CREATE INDEX IF NOT EXISTS idx_incidents_ack_sla_breach
    ON incidents(acknowledgement_sla_breached);

CREATE INDEX IF NOT EXISTS idx_incidents_resolution_sla_breach
    ON incidents(resolution_sla_breached);


-- ------------------------------------------------------------
-- 8. SRE analytics view
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW incident_sre_metrics AS
SELECT
    id,
    incident_key,
    title,
    severity,
    priority,
    status,
    owner,
    assigned_team,
    escalated,
    escalation_level,

    created_at,
    acknowledged_at,
    mitigated_at,
    resolved_at,

    acknowledgement_due_at,
    resolution_due_at,

    acknowledgement_sla_breached,
    resolution_sla_breached,

    CASE
        WHEN acknowledged_at IS NOT NULL
        THEN EXTRACT(
            EPOCH FROM (acknowledged_at - created_at)
        )
    END AS time_to_acknowledge_seconds,

    CASE
        WHEN mitigated_at IS NOT NULL
        THEN EXTRACT(
            EPOCH FROM (mitigated_at - created_at)
        )
    END AS time_to_mitigate_seconds,

    CASE
        WHEN resolved_at IS NOT NULL
        THEN EXTRACT(
            EPOCH FROM (resolved_at - created_at)
        )
    END AS time_to_resolve_seconds

FROM incidents;


-- ------------------------------------------------------------
-- 9. Operational summary view
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW incident_sre_summary AS
SELECT
    COUNT(*) AS total_incidents,

    COUNT(*) FILTER (
        WHERE status <> 'resolved'
    ) AS open_incidents,

    COUNT(*) FILTER (
        WHERE status = 'resolved'
    ) AS resolved_incidents,

    COUNT(*) FILTER (
        WHERE priority = 'P1'
    ) AS p1_incidents,

    COUNT(*) FILTER (
        WHERE priority = 'P2'
    ) AS p2_incidents,

    COUNT(*) FILTER (
        WHERE priority = 'P3'
    ) AS p3_incidents,

    COUNT(*) FILTER (
        WHERE priority = 'P4'
    ) AS p4_incidents,

    COUNT(*) FILTER (
        WHERE escalated = TRUE
    ) AS escalated_incidents,

    COUNT(*) FILTER (
        WHERE acknowledgement_sla_breached = TRUE
    ) AS acknowledgement_sla_breaches,

    COUNT(*) FILTER (
        WHERE resolution_sla_breached = TRUE
    ) AS resolution_sla_breaches,

    ROUND(
        AVG(
            EXTRACT(EPOCH FROM (acknowledged_at - created_at))
        ) FILTER (
            WHERE acknowledged_at IS NOT NULL
        ),
        2
    ) AS mean_time_to_acknowledge_seconds,

    ROUND(
        AVG(
            EXTRACT(EPOCH FROM (resolved_at - created_at))
        ) FILTER (
            WHERE resolved_at IS NOT NULL
        ),
        2
    ) AS mean_time_to_resolve_seconds

FROM incidents;


COMMIT;
