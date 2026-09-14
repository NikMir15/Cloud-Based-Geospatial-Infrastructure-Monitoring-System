CREATE TABLE IF NOT EXISTS telemetry_alerts (

    id BIGSERIAL PRIMARY KEY,

    alert_key VARCHAR(255) NOT NULL,

    asset_id INTEGER NOT NULL,

    asset_name TEXT NOT NULL,

    metric VARCHAR(50) NOT NULL,

    metric_label VARCHAR(100),

    alert_kind VARCHAR(30) NOT NULL,

    severity VARCHAR(20) NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'active',

    message TEXT NOT NULL,

    latest_value NUMERIC(12,4),

    reference_value NUMERIC(12,4),

    threshold NUMERIC(12,4),

    delta NUMERIC(12,4),

    unit VARCHAR(20),

    source VARCHAR(50) NOT NULL DEFAULT 'LOCAL_PROJECT',

    external BOOLEAN NOT NULL DEFAULT FALSE,

    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    acknowledged_at TIMESTAMPTZ,

    resolved_at TIMESTAMPTZ,

    acknowledged_by VARCHAR(100),

    resolved_by VARCHAR(100),

    resolution_note TEXT,

    CONSTRAINT fk_telemetry_alert_asset
        FOREIGN KEY (asset_id)
        REFERENCES infrastructure_points(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_telemetry_alert_severity
        CHECK (
            severity IN (
                'low',
                'medium',
                'high',
                'critical'
            )
        ),

    CONSTRAINT chk_telemetry_alert_status
        CHECK (
            status IN (
                'active',
                'acknowledged',
                'resolved'
            )
        ),

    CONSTRAINT uq_telemetry_alert_key
        UNIQUE (alert_key)
);


CREATE TABLE IF NOT EXISTS telemetry_alert_history (

    id BIGSERIAL PRIMARY KEY,

    alert_id BIGINT NOT NULL,

    action VARCHAR(30) NOT NULL,

    from_status VARCHAR(20),

    to_status VARCHAR(20),

    severity VARCHAR(20),

    note TEXT,

    changed_by VARCHAR(100),

    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_telemetry_alert_history_alert
        FOREIGN KEY (alert_id)
        REFERENCES telemetry_alerts(id)
        ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS idx_telemetry_alerts_asset
ON telemetry_alerts(asset_id);


CREATE INDEX IF NOT EXISTS idx_telemetry_alerts_status
ON telemetry_alerts(status);


CREATE INDEX IF NOT EXISTS idx_telemetry_alerts_severity
ON telemetry_alerts(severity);


CREATE INDEX IF NOT EXISTS idx_telemetry_alerts_last_seen
ON telemetry_alerts(last_seen_at DESC);


CREATE INDEX IF NOT EXISTS idx_telemetry_alert_history_alert
ON telemetry_alert_history(alert_id);


CREATE INDEX IF NOT EXISTS idx_telemetry_alert_history_time
ON telemetry_alert_history(changed_at DESC);
