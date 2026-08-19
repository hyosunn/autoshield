-- AutoShield schema migration — neighborhood risk scoring
-- Run with: psql -d autoshield -f db/schema.sql
--
-- Requires the PostGIS extension. If it isn't installed yet, run this once
-- as a superuser before applying this file:
--   CREATE EXTENSION IF NOT EXISTS postgis;


-- ── neighborhoods ────────────────────────────────────────────────────────────
--
-- One row per SF Realtor neighborhood polygon. The boundary column stores a
-- MULTIPOLYGON because some neighborhoods are made up of non-contiguous
-- pieces (e.g. islands, split districts). GEOGRAPHY(…, 4326) means the
-- coordinate system is WGS-84 (standard GPS lat/lng) and distance/area
-- calculations automatically use metres on the Earth's surface rather than
-- degrees (which would give nonsense results with plain GEOMETRY).

CREATE TABLE IF NOT EXISTS neighborhoods (
    id              SERIAL PRIMARY KEY,

    -- Human-readable name sourced from the SF open-data boundary file.
    -- UNIQUE ensures we can safely re-run the load script with ON CONFLICT.
    name            TEXT UNIQUE NOT NULL,

    -- The polygon (or set of polygons) that defines the neighborhood border.
    boundary        GEOGRAPHY(MULTIPOLYGON, 4326) NOT NULL,

    -- Two independent percentile-rank scores (0–100) recomputed by
    -- scripts/compute_risk_scores.py.  See docs/risk-scoring-design.md for
    -- the full algorithm (decay, Bayes shrinkage, area normalisation).
    -- DEFAULT 0 until the first scoring run has been performed.
    parking_risk_score    NUMERIC(5,2) DEFAULT 0,
    pedestrian_risk_score NUMERIC(5,2) DEFAULT 0,

    -- True when fewer than 5 qualifying incidents were available for this
    -- neighborhood in the scoring window; the score is shrunk toward the
    -- citywide mean and the flag is exposed in the API for UI transparency.
    low_sample      BOOLEAN DEFAULT FALSE,

    -- Denormalised count kept in sync when incidents are loaded, so the
    -- frontend can display it without a COUNT() query each time.
    incident_count  INTEGER DEFAULT 0,

    last_updated    TIMESTAMP DEFAULT NOW()
);

-- GiST (Generalized Search Tree) is the index type PostGIS requires for
-- spatial queries such as ST_Within, ST_Intersects, and ST_DWithin.
-- Without this index, every spatial lookup would be a full-table scan.
CREATE INDEX IF NOT EXISTS idx_neighborhoods_boundary
    ON neighborhoods
    USING GIST (boundary);


-- ── incidents ─────────────────────────────────────────────────────────────────
--
-- One row per crime/incident record fetched from the SF open-data API.
-- Keeping incidents in their own table (rather than pre-aggregating them into
-- neighborhoods) lets us recompute risk scores with different weights later
-- without re-fetching the raw data.

CREATE TABLE IF NOT EXISTS incidents (
    id              SERIAL PRIMARY KEY,

    -- The source system's own identifier. UNIQUE + idempotent loads mean
    -- we can re-run the ingestion script without creating duplicates.
    incident_id     TEXT UNIQUE NOT NULL,

    -- Broad crime category as it appears in the SFPD Socrata feed.
    -- The five categories used by the scoring algorithm are:
    --   Motor Vehicle Theft, Larceny - From Vehicle  (incident_subcategory)
    --   Burglary, Robbery, Assault                   (incident_category)
    category        TEXT NOT NULL,

    incident_date   TIMESTAMP NOT NULL,

    -- Severity weights are applied at scoring time (in compute_risk_scores.py),
    -- not stored per-row — so scores can be recomputed with revised weights
    -- without re-ingesting raw data.  This column is reserved for future use.
    severity_weight NUMERIC(3,2) NOT NULL DEFAULT 1.0,

    -- Single lat/lng point. Same GEOGRAPHY/WGS-84 rationale as boundary above.
    location        GEOGRAPHY(POINT, 4326) NOT NULL,

    -- Foreign key set after a spatial join assigns the incident to the
    -- neighborhood whose boundary contains the incident's location.
    -- NULL until that join has run (newly loaded incidents start unassigned).
    neighborhood_id INTEGER REFERENCES neighborhoods(id),

    created_at      TIMESTAMP DEFAULT NOW()
);

-- Spatial index on incident locations — used by the ST_Within join that
-- assigns neighborhood_id and by map queries that filter by visible area.
CREATE INDEX IF NOT EXISTS idx_incidents_location
    ON incidents
    USING GIST (location);

-- B-tree index on the date column — used by queries that filter by time range,
-- e.g. "incidents in the last 36 months" for rolling risk-score windows.
CREATE INDEX IF NOT EXISTS idx_incidents_date
    ON incidents (incident_date);


-- ── migration: apply to an existing database ──────────────────────────────────
--
-- The blocks below are no-ops on a fresh schema (the columns already exist).
-- Run the full file against an existing DB to pick up the schema changes.

ALTER TABLE neighborhoods
    ADD COLUMN IF NOT EXISTS parking_risk_score    NUMERIC(5,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS pedestrian_risk_score NUMERIC(5,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS low_sample            BOOLEAN      DEFAULT FALSE;

-- Drop the old single-axis column if it survived from an earlier schema version.
ALTER TABLE neighborhoods
    DROP COLUMN IF EXISTS risk_score;
