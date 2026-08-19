# AutoShield — Codebase Overview

AutoShield is an SF vehicle-crime and neighborhood-risk visualization tool. This document describes how the codebase is structured and why, for anyone (including future-you) picking it up without prior context. It assumes familiarity with programming generally but not with this specific stack (Flask, React, Leaflet, PostGIS).

---

## Architecture

Two services communicate over HTTP:

- **`backend/`** — a Flask app exposing a JSON API. `/api/incidents` proxies and filters live SF open-data crime records. `/api/neighborhoods` (risk-scoring subsystem — see `docs/risk-scoring-design.md`) serves precomputed, PostGIS-backed neighborhood risk scores.
- **`frontend/`** — a React SPA that calls those endpoints and renders results as a map (Leaflet), a trend chart (Recharts), and a stats bar.

A **PostgreSQL + PostGIS** database (`db/`, `scripts/`) backs the risk-scoring subsystem specifically — it is not in the request path of `/api/incidents`, which talks directly to SF's open-data API instead.

In development, Vite's dev server (frontend) proxies `/api/*` to Flask on port 5001. There is no production deployment configuration yet.

---

## Backend (Flask)

### Application factory (`backend/apps/__init__.py`)

The app is built via a factory function (`create_app()`) rather than a module-level `app = Flask(__name__)`. This avoids circular imports between the app object and the blueprint that depends on it, and allows multiple independent app instances (useful for testing).

Two extensions are initialized here: **Flask-Caching** (`cache`, in-memory `SimpleCache`, 1-hour default timeout) caches upstream API responses so repeated filter combinations don't re-hit SF's open-data API; **Flask-CORS** allows the frontend's dev-server origin to call `/api/*` — the current config (`origins: '*'`) is intentionally open for local development and should be restricted before any public deployment.

### Entry point (`backend/wsgi.py`)

The canonical entry point. Loads `.env` via `python-dotenv` before `create_app()` runs (required since route code reads `os.environ` at import time), then runs the dev server on port 5001.

### Routes (`backend/apps/views.py`)

Routes are grouped in a Flask **Blueprint** (`views`), registered onto the app in the factory. `GET /api/incidents` builds a SoQL `WHERE` clause from query params (date range, day-of-week, time-of-day, category — validated against a fixed allowlist before being interpolated) and proxies it to SF's Socrata-hosted open-data API (`data.sfgov.org`, dataset `wg3w-h783`), returning cached, coordinate-filtered JSON. See `docs/risk-scoring-design.md` for `/api/neighborhoods`, which queries Postgres directly instead.

---

## Frontend (React + Vite)

### Build tooling

**Vite** is the dev server and bundler; `vite.config.js` proxies `/api/*` to Flask on port 5001 during development, and pre-bundles the marker-clustering dependency (`optimizeDeps.include`) since it doesn't declare itself cleanly as an ES module. **Tailwind CSS** (via PostCSS) provides utility-class styling; `tailwind.config.js` scans `index.html` and `src/**/*.jsx` to generate only the classes actually used.

### State and data flow

`App.jsx` is the single source of truth for application state (`incidents`, `filters`, `viewMode`, loading/error state) and fetches from `/api/incidents` in a `useEffect` keyed on `filters`. State is passed down to `Sidebar`, `Map`, `StatsBar`, and `TrendChart` as props; child components call setter functions passed down to them rather than managing shared state independently. There is no external state-management library — the state tree is shallow enough that lifting state to `App` is sufficient.

### Map (`src/components/Map.jsx`)

Built on **Leaflet** via **react-leaflet**. `MarkerClusterGroup` (from `@changey/react-leaflet-markercluster`, chosen over the more common `react-leaflet-cluster` package due to a remount bug in the latter) clusters incident markers to keep thousands of points renderable. The heatmap layer uses `leaflet.heat`, which has no react-leaflet wrapper — it's applied imperatively via `useMap()` (react-leaflet's escape hatch to the underlying Leaflet map instance) inside a controller component that renders no JSX of its own.

### Charting (`src/components/TrendChart.jsx`)

**Recharts**, driven by incident data grouped client-side into monthly buckets, each bar colored by that month's dominant crime subcategory.

---

## Database layer (PostgreSQL + PostGIS)

`db/schema.sql` defines two tables:

- **`neighborhoods`** — one row per SF Realtor neighborhood polygon (`boundary GEOGRAPHY(MULTIPOLYGON, 4326)`), plus `parking_risk_score` and `pedestrian_risk_score` (both recomputed periodically — see `docs/risk-scoring-design.md`) and a denormalized `incident_count` for display.
- **`incidents`** — one row per crime record, with `category`, `severity_weight` (reserved; current scoring applies weights at query time rather than storage time — see the design doc), a `GEOGRAPHY(POINT, 4326)` location, and a `neighborhood_id` foreign key populated by a spatial join (`ST_Within`).

`GEOGRAPHY` (rather than `GEOMETRY`) is used throughout because it treats coordinates as points on a sphere, giving correct real-world distance/area calculations for lat/lng data without manual projection handling — appropriate at city scale. `4326` is the SRID for WGS-84 (standard GPS coordinates). GiST indexes on both spatial columns are required for PostGIS spatial queries (`ST_Within`, `ST_DWithin`, etc.) to avoid full-table scans.

`scripts/load_neighborhoods.py` seeds the `neighborhoods` table from SF's open-data neighborhood-boundary GeoJSON, hand-converting GeoJSON geometry to WKT (Well-Known Text, PostGIS's native text format) rather than depending on a heavier geometry library. Inserts are idempotent (`ON CONFLICT (name) DO NOTHING`), so the script is safe to re-run.

Loading, spatially joining, and scoring `incidents` is the risk-scoring subsystem — see `docs/risk-scoring-design.md` for the full design and rationale.

---

## Known limitations

- No production deployment configuration (dev-only Vite proxy + Flask dev server).
- `/api/incidents`' CORS policy is intentionally open (`origins: '*'`) for local development.
- The risk-scoring subsystem's normalization by land area (rather than population or parking-supply data) is a known, documented tradeoff — see the limitations section of `docs/risk-scoring-design.md`.
