-- ============================================================
-- PHASE 6.4
-- HISTORICAL SENSOR TELEMETRY
-- ============================================================

CREATE TABLE IF NOT EXISTS sensor_telemetry_history (

    id BIGSERIAL PRIMARY KEY,

    asset_id INTEGER NOT NULL,

    status VARCHAR(20) NOT NULL,

    health NUMERIC(5,2) NOT NULL,

    cpu_percent NUMERIC(5,2) NOT NULL,

    temperature_c NUMERIC(6,2) NOT NULL,

    latency_ms NUMERIC(10,2) NOT NULL,

    packet_loss_percent NUMERIC(6,2) NOT NULL,

    signal_strength NUMERIC(5,2) NOT NULL,

    source VARCHAR(50) NOT NULL DEFAULT 'LOCAL_PROJECT',

    external BOOLEAN NOT NULL DEFAULT FALSE,

    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_sensor_history_asset
        FOREIGN KEY (asset_id)
        REFERENCES infrastructure_points(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_sensor_history_status
        CHECK (
            status IN (
                'online',
                'degraded',
                'offline'
            )
        ),

    CONSTRAINT chk_sensor_history_health
        CHECK (
            health >= 0
            AND health <= 100
        ),

    CONSTRAINT chk_sensor_history_cpu
        CHECK (
            cpu_percent >= 0
            AND cpu_percent <= 100
        ),

    CONSTRAINT chk_sensor_history_packet_loss
        CHECK (
            packet_loss_percent >= 0
            AND packet_loss_percent <= 100
        ),

    CONSTRAINT chk_sensor_history_signal
        CHECK (
            signal_strength >= 0
            AND signal_strength <= 100
        )
);


-- Fast lookup for one infrastructure asset.

CREATE INDEX IF NOT EXISTS
idx_sensor_history_asset_id
ON sensor_telemetry_history(asset_id);


-- Fast time-based querying.

CREATE INDEX IF NOT EXISTS
idx_sensor_history_recorded_at
ON sensor_telemetry_history(recorded_at DESC);


-- Most important index for:
-- "give me asset 9 telemetry for the last 24 hours"

CREATE INDEX IF NOT EXISTS
idx_sensor_history_asset_time
ON sensor_telemetry_history(
    asset_id,
    recorded_at DESC
);
