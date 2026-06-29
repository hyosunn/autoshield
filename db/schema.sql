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

    -- risk_score is recomputed periodically from incident data.
    -- NUMERIC(5,2) holds values like 999.99 — five digits, two after the
    -- decimal. DEFAULT 0 until the first scoring run has been performed.
    risk_score      NUMERIC(5,2)  DEFAULT 0,

    -- Denormalised count kept in sync when incidents are loaded, so the
    -- frontend can display it without a COUNT() query each time.
    incident_count  INTEGER       DEFAULT 0,

    last_updated    TIMESTAMP     DEFAULT NOW()
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

    -- Broad crime category (e.g. "THEFT", "ASSAULT") from the source API.
    category        TEXT NOT NULL,

    -- Free-text description of the specific incident.
    description     TEXT,

    incident_date   TIMESTAMP NOT NULL,

    -- A multiplier applied when computing a neighborhood's risk_score.
    -- Violent crimes might get 1.5 while minor infractions get 0.5.
    -- NUMERIC(3,2) covers the range 0.00–9.99.
    severity_weight NUMERIC(3,2) NOT NULL,

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
-- e.g. "incidents in the last 30 days" for rolling risk-score windows.
CREATE INDEX IF NOT EXISTS idx_incidents_date
    ON incidents (incident_date);
