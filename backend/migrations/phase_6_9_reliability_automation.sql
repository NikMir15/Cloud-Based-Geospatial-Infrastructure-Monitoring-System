-- ============================================================
-- GeoInfra
-- Phase 6.9 — Incident Automation & Reliability Engineering
-- ============================================================

BEGIN;

-- ============================================================
-- 1. AUTOMATION RUNBOOKS
-- ============================================================

CREATE TABLE IF NOT EXISTS automation_runbooks (
    id BIGSERIAL PRIMARY KEY,

    runbook_key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT,

    trigger_metric VARCHAR(100) NOT NULL,
    minimum_severity VARCHAR(20) NOT NULL,

    execution_mode VARCHAR(30)
        NOT NULL DEFAULT 'manual_approval',

    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    source VARCHAR(50)
        NOT NULL DEFAULT 'LOCAL_PROJECT',

    external BOOLEAN
        NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ
        NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ
        NOT NULL DEFAULT NOW(),

    CONSTRAINT automation_runbooks_severity_check
        CHECK (
            minimum_severity IN (
                'low',
                'medium',
                'high',
                'critical'
            )
        ),

    CONSTRAINT automation_runbooks_mode_check
        CHECK (
            execution_mode IN (
                'manual_approval',
                'automatic'
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_automation_runbooks_metric
    ON automation_runbooks(trigger_metric);

CREATE INDEX IF NOT EXISTS idx_automation_runbooks_enabled
    ON automation_runbooks(enabled);


-- ============================================================
-- 2. AUTOMATION EXECUTIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS automation_executions (
    id BIGSERIAL PRIMARY KEY,

    execution_key VARCHAR(150)
        NOT NULL UNIQUE,

    runbook_id BIGINT
        NOT NULL REFERENCES automation_runbooks(id)
        ON DELETE RESTRICT,

    incident_id BIGINT
        NOT NULL REFERENCES incidents(id)
        ON DELETE CASCADE,

    status VARCHAR(30)
        NOT NULL DEFAULT 'PENDING_APPROVAL',

    requested_by VARCHAR(150),
    approved_by VARCHAR(150),

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    result TEXT,
    verification_result TEXT,
    error_message TEXT,

    source VARCHAR(50)
        NOT NULL DEFAULT 'LOCAL_PROJECT',

    external BOOLEAN
        NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ
        NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ
        NOT NULL DEFAULT NOW(),

    CONSTRAINT automation_execution_status_check
        CHECK (
            status IN (
                'PENDING_APPROVAL',
                'APPROVED',
                'RUNNING',
                'SUCCESS',
                'FAILED',
                'CANCELLED'
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_automation_executions_incident
    ON automation_executions(incident_id);

CREATE INDEX IF NOT EXISTS idx_automation_executions_runbook
    ON automation_executions(runbook_id);

CREATE INDEX IF NOT EXISTS idx_automation_executions_status
    ON automation_executions(status);

CREATE INDEX IF NOT EXISTS idx_automation_executions_created
    ON automation_executions(created_at DESC);


-- ============================================================
-- 3. AUTOMATION EXECUTION HISTORY
-- ============================================================

CREATE TABLE IF NOT EXISTS automation_execution_history (
    id BIGSERIAL PRIMARY KEY,

    execution_id BIGINT
        NOT NULL REFERENCES automation_executions(id)
        ON DELETE CASCADE,

    action VARCHAR(100) NOT NULL,

    from_status VARCHAR(30),
    to_status VARCHAR(30),

    message TEXT,

    changed_by VARCHAR(150),

    changed_at TIMESTAMPTZ
        NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_automation_history_execution
    ON automation_execution_history(execution_id);

CREATE INDEX IF NOT EXISTS idx_automation_history_changed
    ON automation_execution_history(changed_at DESC);


-- ============================================================
-- 4. SERVICE LEVEL OBJECTIVES
-- ============================================================

CREATE TABLE IF NOT EXISTS service_objectives (
    id BIGSERIAL PRIMARY KEY,

    objective_key VARCHAR(150)
        NOT NULL UNIQUE,

    asset_id INTEGER
        NOT NULL REFERENCES infrastructure_points(id)
        ON DELETE CASCADE,

    name VARCHAR(200) NOT NULL,

    metric VARCHAR(100) NOT NULL,

    comparison_operator VARCHAR(10)
        NOT NULL,

    threshold NUMERIC NOT NULL,

    target_percentage NUMERIC(6,3)
        NOT NULL,

    window_minutes INTEGER
        NOT NULL DEFAULT 1440,

    enabled BOOLEAN
        NOT NULL DEFAULT TRUE,

    source VARCHAR(50)
        NOT NULL DEFAULT 'LOCAL_PROJECT',

    external BOOLEAN
        NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ
        NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ
        NOT NULL DEFAULT NOW(),

    CONSTRAINT service_objectives_operator_check
        CHECK (
            comparison_operator IN (
                '<',
                '<=',
                '>',
                '>=',
                '='
            )
        ),

    CONSTRAINT service_objectives_target_check
        CHECK (
            target_percentage > 0
            AND target_percentage <= 100
        ),

    CONSTRAINT service_objectives_window_check
        CHECK (window_minutes > 0)
);

CREATE INDEX IF NOT EXISTS idx_service_objectives_asset
    ON service_objectives(asset_id);

CREATE INDEX IF NOT EXISTS idx_service_objectives_metric
    ON service_objectives(metric);

CREATE INDEX IF NOT EXISTS idx_service_objectives_enabled
    ON service_objectives(enabled);


-- ============================================================
-- 5. SLO MEASUREMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS slo_measurements (
    id BIGSERIAL PRIMARY KEY,

    objective_id BIGINT
        NOT NULL REFERENCES service_objectives(id)
        ON DELETE CASCADE,

    good_observations INTEGER
        NOT NULL DEFAULT 0,

    total_observations INTEGER
        NOT NULL DEFAULT 0,

    sli_percentage NUMERIC(8,4),

    error_budget_percentage NUMERIC(8,4),

    error_budget_consumed_percentage NUMERIC(10,4),

    status VARCHAR(30)
        NOT NULL DEFAULT 'UNKNOWN',

    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,

    source VARCHAR(50)
        NOT NULL DEFAULT 'LOCAL_PROJECT',

    external BOOLEAN
        NOT NULL DEFAULT FALSE,

    evaluated_at TIMESTAMPTZ
        NOT NULL DEFAULT NOW(),

    CONSTRAINT slo_measurement_status_check
        CHECK (
            status IN (
                'HEALTHY',
                'AT_RISK',
                'BREACHED',
                'UNKNOWN'
            )
        ),

    CONSTRAINT slo_observation_check
        CHECK (
            good_observations >= 0
            AND total_observations >= 0
            AND good_observations <= total_observations
        ),

    CONSTRAINT slo_window_check
        CHECK (window_end >= window_start)
);

CREATE INDEX IF NOT EXISTS idx_slo_measurements_objective
    ON slo_measurements(objective_id);

CREATE INDEX IF NOT EXISTS idx_slo_measurements_evaluated
    ON slo_measurements(evaluated_at DESC);


-- ============================================================
-- 6. UPDATED_AT TRIGGERS
-- ============================================================

CREATE OR REPLACE FUNCTION set_phase_6_9_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS
    trg_automation_runbooks_updated_at
    ON automation_runbooks;

CREATE TRIGGER trg_automation_runbooks_updated_at
BEFORE UPDATE ON automation_runbooks
FOR EACH ROW
EXECUTE FUNCTION set_phase_6_9_updated_at();


DROP TRIGGER IF EXISTS
    trg_automation_executions_updated_at
    ON automation_executions;

CREATE TRIGGER trg_automation_executions_updated_at
BEFORE UPDATE ON automation_executions
FOR EACH ROW
EXECUTE FUNCTION set_phase_6_9_updated_at();


DROP TRIGGER IF EXISTS
    trg_service_objectives_updated_at
    ON service_objectives;

CREATE TRIGGER trg_service_objectives_updated_at
BEFORE UPDATE ON service_objectives
FOR EACH ROW
EXECUTE FUNCTION set_phase_6_9_updated_at();


-- ============================================================
-- 7. SAFE LOCAL DEMO RUNBOOKS
-- ============================================================
-- These represent simulated remediation workflows.
-- They DO NOT execute arbitrary operating-system commands.

INSERT INTO automation_runbooks (
    runbook_key,
    name,
    description,
    trigger_metric,
    minimum_severity,
    execution_mode
)
VALUES

(
    'RB-HIGH-CPU-001',
    'High CPU Remediation',
    'Validate CPU telemetry, simulate service recovery and verify asset health.',
    'cpu_percent',
    'high',
    'manual_approval'
),

(
    'RB-HIGH-TEMP-001',
    'High Temperature Remediation',
    'Validate temperature telemetry, simulate thermal remediation and verify recovery.',
    'temperature_c',
    'high',
    'manual_approval'
),

(
    'RB-LATENCY-001',
    'High Latency Remediation',
    'Validate latency telemetry, simulate network remediation and verify latency recovery.',
    'latency_ms',
    'high',
    'manual_approval'
),

(
    'RB-PACKET-LOSS-001',
    'Packet Loss Remediation',
    'Validate packet-loss telemetry, simulate network-path remediation and verify connectivity.',
    'packet_loss_percent',
    'high',
    'manual_approval'
),

(
    'RB-HEALTH-001',
    'Infrastructure Health Recovery',
    'Validate degraded health telemetry, simulate service recovery and verify health.',
    'health',
    'high',
    'manual_approval'
)

ON CONFLICT (runbook_key)
DO NOTHING;


-- ============================================================
-- 8. AUTOMATION SUMMARY VIEW
-- ============================================================

CREATE OR REPLACE VIEW automation_summary AS
SELECT
    COUNT(*) AS total_executions,

    COUNT(*) FILTER (
        WHERE status = 'PENDING_APPROVAL'
    ) AS pending_approval,

    COUNT(*) FILTER (
        WHERE status = 'RUNNING'
    ) AS running,

    COUNT(*) FILTER (
        WHERE status = 'SUCCESS'
    ) AS successful,

    COUNT(*) FILTER (
        WHERE status = 'FAILED'
    ) AS failed,

    COUNT(*) FILTER (
        WHERE status = 'CANCELLED'
    ) AS cancelled,

    ROUND(
        100.0 *
        COUNT(*) FILTER (WHERE status = 'SUCCESS')
        /
        NULLIF(
            COUNT(*) FILTER (
                WHERE status IN ('SUCCESS', 'FAILED')
            ),
            0
        ),
        2
    ) AS success_rate_percentage

FROM automation_executions;


COMMIT;
