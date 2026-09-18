-- ============================================================
-- GeoInfra
-- Phase 0 - Base Infrastructure Schema
--
-- Purpose:
--   Creates the core infrastructure_points table required by
--   telemetry, alerting, incident management, reliability,
--   automation and predictive operations.
--
-- Properties:
--   - PostgreSQL / PostGIS
--   - Idempotent
--   - Safe to execute repeatedly
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- PostGIS
-- ------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS postgis;


-- ------------------------------------------------------------
-- Core infrastructure table
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.infrastructure_points (
    id SERIAL PRIMARY KEY,

    name TEXT NOT NULL,

    description TEXT,

    infra_type TEXT NOT NULL,

    location geometry(Point, 4326) NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'operational',

    risk_score INTEGER NOT NULL DEFAULT 0,

    severity VARCHAR(20) NOT NULL DEFAULT 'low'
);


-- ------------------------------------------------------------
-- Compatibility upgrades
--
-- These statements allow this migration to be executed against
-- an older infrastructure_points table without failing.
-- ------------------------------------------------------------

ALTER TABLE public.infrastructure_points
    ADD COLUMN IF NOT EXISTS name TEXT;

ALTER TABLE public.infrastructure_points
    ADD COLUMN IF NOT EXISTS description TEXT;

ALTER TABLE public.infrastructure_points
    ADD COLUMN IF NOT EXISTS infra_type TEXT;

ALTER TABLE public.infrastructure_points
    ADD COLUMN IF NOT EXISTS location geometry(Point, 4326);

ALTER TABLE public.infrastructure_points
    ADD COLUMN IF NOT EXISTS status VARCHAR(20)
        DEFAULT 'operational';

ALTER TABLE public.infrastructure_points
    ADD COLUMN IF NOT EXISTS risk_score INTEGER
        DEFAULT 0;

ALTER TABLE public.infrastructure_points
    ADD COLUMN IF NOT EXISTS severity VARCHAR(20)
        DEFAULT 'low';


-- ------------------------------------------------------------
-- Defaults
-- ------------------------------------------------------------

ALTER TABLE public.infrastructure_points
    ALTER COLUMN status SET DEFAULT 'operational';

ALTER TABLE public.infrastructure_points
    ALTER COLUMN risk_score SET DEFAULT 0;

ALTER TABLE public.infrastructure_points
    ALTER COLUMN severity SET DEFAULT 'low';


-- ------------------------------------------------------------
-- Repair nullable operational values in older databases
-- ------------------------------------------------------------

UPDATE public.infrastructure_points
SET status = 'operational'
WHERE status IS NULL;

UPDATE public.infrastructure_points
SET risk_score = 0
WHERE risk_score IS NULL;

UPDATE public.infrastructure_points
SET severity = 'low'
WHERE severity IS NULL;


-- ------------------------------------------------------------
-- Spatial index
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_infrastructure_points_location
    ON public.infrastructure_points
    USING GIST (location);


-- ------------------------------------------------------------
-- Operational indexes
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_infrastructure_points_infra_type
    ON public.infrastructure_points (infra_type);

CREATE INDEX IF NOT EXISTS idx_infrastructure_points_status
    ON public.infrastructure_points (status);

CREATE INDEX IF NOT EXISTS idx_infrastructure_points_severity
    ON public.infrastructure_points (severity);

CREATE INDEX IF NOT EXISTS idx_infrastructure_points_risk_score
    ON public.infrastructure_points (risk_score);


COMMIT;
