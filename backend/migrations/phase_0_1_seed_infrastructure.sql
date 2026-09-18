-- ============================================================
-- GeoInfra
-- Phase 0.1 - Base Infrastructure Seed
--
-- Purpose:
--   Provide deterministic bootstrap data for a fresh database.
--
-- Historical source:
--   AWS London Region is the infrastructure asset recoverable
--   from the project's Git history / README.
--
-- Idempotency:
--   Existing matching assets are not duplicated.
-- ============================================================

BEGIN;

INSERT INTO public.infrastructure_points (
    name,
    description,
    infra_type,
    location,
    status,
    risk_score,
    severity
)
SELECT
    'AWS London Region',
    'Cloud Infrastructure',
    'Cloud',
    ST_SetSRID(
        ST_MakePoint(-0.1276, 51.5074),
        4326
    )::geometry(Point,4326),
    'operational',
    0,
    'low'
WHERE NOT EXISTS (
    SELECT 1
    FROM public.infrastructure_points
    WHERE name = 'AWS London Region'
);

COMMIT;
