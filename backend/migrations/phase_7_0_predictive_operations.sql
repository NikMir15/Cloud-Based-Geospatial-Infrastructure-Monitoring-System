-- =====================================================================
-- GeoInfra Phase 7.0A
-- Predictive Operations — Telemetry Anomaly Persistence
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS anomaly_events (
    id                  BIGSERIAL PRIMARY KEY,
    asset_id            INTEGER NOT NULL,
    metric              VARCHAR(64) NOT NULL,

    current_value       NUMERIC NOT NULL,
    baseline_mean       NUMERIC NOT NULL,
    baseline_stddev     NUMERIC NOT NULL DEFAULT 0,
    deviation           NUMERIC NOT NULL,
    deviation_percent   NUMERIC,
    z_score             NUMERIC NOT NULL,
    anomaly_score       NUMERIC NOT NULL,

    status              VARCHAR(20) NOT NULL,
    sample_count        INTEGER NOT NULL,

    source              VARCHAR(64) NOT NULL DEFAULT 'LOCAL_PROJECT',
    external            BOOLEAN NOT NULL DEFAULT FALSE,

    detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_anomaly_event_asset
        FOREIGN KEY (asset_id)
        REFERENCES infrastructure_points(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_anomaly_event_status
        CHECK (status IN ('WATCH', 'ANOMALOUS', 'CRITICAL')),

    CONSTRAINT chk_anomaly_event_sample_count
        CHECK (sample_count >= 1),

    CONSTRAINT chk_anomaly_event_score
        CHECK (anomaly_score >= 0),

    CONSTRAINT chk_anomaly_event_provenance
        CHECK (source = 'LOCAL_PROJECT' AND external = FALSE)
);

CREATE INDEX IF NOT EXISTS idx_anomaly_events_asset
    ON anomaly_events(asset_id);

CREATE INDEX IF NOT EXISTS idx_anomaly_events_asset_time
    ON anomaly_events(asset_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_anomaly_events_status
    ON anomaly_events(status);

CREATE INDEX IF NOT EXISTS idx_anomaly_events_metric
    ON anomaly_events(metric);

CREATE INDEX IF NOT EXISTS idx_anomaly_events_detected_at
    ON anomaly_events(detected_at DESC);


CREATE OR REPLACE VIEW anomaly_event_summary AS
SELECT
    asset_id,
    COUNT(*) AS event_count,
    COUNT(*) FILTER (WHERE status = 'WATCH') AS watch_count,
    COUNT(*) FILTER (WHERE status = 'ANOMALOUS') AS anomalous_count,
    COUNT(*) FILTER (WHERE status = 'CRITICAL') AS critical_count,
    MAX(anomaly_score) AS maximum_anomaly_score,
    MAX(detected_at) AS latest_detected_at
FROM anomaly_events
GROUP BY asset_id;


COMMENT ON TABLE anomaly_events IS
'Phase 7.0A locally derived statistical telemetry anomaly events.';

COMMENT ON COLUMN anomaly_events.anomaly_score IS
'Absolute statistical anomaly score derived from the metric Z-score.';

COMMENT ON COLUMN anomaly_events.external IS
'Always FALSE for Phase 7.0A because anomaly analysis is locally derived.';

COMMIT;
