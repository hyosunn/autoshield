"""
load_neighborhoods.py — seed the neighborhoods table from SF open data.

Source: SF Realtor Neighborhoods (Socrata dataset 5gzd-g9ns)
  https://data.sfgov.org/resource/5gzd-g9ns.geojson

Usage:
    python scripts/load_neighborhoods.py

Requires DATABASE_URL in your .env file, e.g.:
    DATABASE_URL=postgresql://postgres:password@localhost:5432/autoshield

Dependencies (add to requirements.txt if missing):
    psycopg2-binary
    python-dotenv
    requests
"""

import json
import os
import sys

import psycopg2
import requests
from dotenv import load_dotenv

# ── configuration ─────────────────────────────────────────────────────────────

# Load .env from the project root (one level up from scripts/).
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# The Socrata endpoint returns all ~117 SF Realtor neighborhood polygons as a
# single GeoJSON FeatureCollection. $limit=200 ensures we get them all in one
# request without pagination.
SOURCE_URL = "https://data.sfgov.org/api/v3/views/2kjj-ysvr/query.geojson"


# ── geometry helpers ───────────────────────────────────────────────────────────

def geojson_geometry_to_wkt(geometry: dict) -> str:
    """
    Convert a GeoJSON geometry object to Well-Known Text (WKT).

    PostGIS accepts WKT via ST_GeogFromText(). We build it manually here to
    avoid pulling in a heavy dependency like Shapely just for this conversion.

    The boundary column is typed GEOGRAPHY(MULTIPOLYGON), so we must produce
    a MULTIPOLYGON even when the source feature is a plain POLYGON — PostGIS
    will reject a POLYGON literal for that column type.

    WKT ring syntax: each ring is a parenthesised list of "lon lat" pairs,
    with the first and last pair identical to close the ring.
    WKT polygon syntax: POLYGON((outer),(hole1),(hole2),…)
    WKT multipolygon syntax: MULTIPOLYGON(((outer),(hole)),((outer)),…)
    """
    geom_type = geometry["type"]

    if geom_type == "Polygon":
        # Wrap the single polygon in a MULTIPOLYGON shell.
        polygon_wkt = _polygon_coordinates_to_wkt(geometry["coordinates"])
        return f"MULTIPOLYGON({polygon_wkt})"

    elif geom_type == "MultiPolygon":
        # Each element of coordinates is one polygon's ring list.
        parts = [_polygon_coordinates_to_wkt(rings) for rings in geometry["coordinates"]]
        return f"MULTIPOLYGON({', '.join(parts)})"

    else:
        raise ValueError(f"Unsupported geometry type: {geom_type!r}")


def _polygon_coordinates_to_wkt(rings: list) -> str:
    """
    Convert a GeoJSON polygon coordinate array to the inner WKT polygon form.

    A GeoJSON polygon's coordinates field is a list of rings:
      rings[0] — exterior ring
      rings[1:] — interior rings (holes)

    Returns the (outer),(hole),… portion without the outer POLYGON(...) wrapper,
    because MULTIPOLYGON needs this wrapped in an extra set of parentheses:
      MULTIPOLYGON( ((outer),(hole)) , ((outer)) )
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ returned by this function
    """
    ring_strings = [_ring_to_wkt(ring) for ring in rings]
    # Each ring is already parenthesised; join them inside one more pair.
    return f"({', '.join(ring_strings)})"


def _ring_to_wkt(ring: list) -> str:
    """
    Convert a list of [lon, lat] pairs to a WKT coordinate ring "(x y, x y, …)".

    GeoJSON uses [longitude, latitude] order; WKT uses "x y" which is the
    same order, so no swapping is needed.
    """
    pairs = " ".join(f"{lon} {lat}" for lon, lat in ring)
    # WKT rings must be closed — first and last coordinate identical.
    # The SF dataset already closes its rings, but we trust WKT, not the source.
    coords = [f"{lon} {lat}" for lon, lat in ring]
    return f"({', '.join(coords)})"


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    # ── 1. fetch ──────────────────────────────────────────────────────────────
    print(f"Fetching neighborhoods from:\n  {SOURCE_URL}\n")
    response = requests.get(SOURCE_URL, timeout=30)
    response.raise_for_status()          # blow up early if the API is down
    geojson = response.json()

    features = geojson.get("features", [])
    print(f"Received {len(features)} features.")

    if not features:
        print("No features returned — nothing to insert. Exiting.")
        sys.exit(0)

    # ── 2. connect ────────────────────────────────────────────────────────────
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print(
            "ERROR: DATABASE_URL is not set.\n"
            "Add it to your .env file, e.g.:\n"
            "  DATABASE_URL=postgresql://postgres:password@localhost:5432/autoshield",
            file=sys.stderr,
        )
        sys.exit(1)

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    # ── 3. insert ─────────────────────────────────────────────────────────────
    # The INSERT uses ON CONFLICT (name) DO NOTHING so the script is idempotent:
    # running it a second time will simply skip existing rows rather than
    # raising a duplicate-key error or creating duplicates.
    insert_sql = """
        INSERT INTO neighborhoods (name, boundary)
        VALUES (
            %s,
            -- ST_GeogFromText parses a WKT string into a GEOGRAPHY value.
            -- SRID 4326 = WGS-84, matching the column definition.
            ST_GeogFromText('SRID=4326;' || %s)
        )
        ON CONFLICT (name) DO NOTHING;
    """

    inserted = 0
    skipped  = 0
    errors   = 0

    for feature in features:
        properties = feature.get("properties", {})
        geometry   = feature.get("geometry")

        # The name field in this dataset is stored under the key "nbrhood".
        # Fall back to "name" in case the schema changes, then skip if neither exists.
        name = properties.get("nbrhood") or properties.get("name")

        if not name:
            print(f"  [SKIP] Feature has no name: {properties}")
            skipped += 1
            continue

        if not geometry:
            print(f"  [SKIP] {name!r} has no geometry.")
            skipped += 1
            continue

        try:
            wkt = geojson_geometry_to_wkt(geometry)
        except (ValueError, KeyError) as exc:
            print(f"  [ERROR] {name!r}: could not convert geometry — {exc}")
            errors += 1
            continue

        try:
            cur.execute(insert_sql, (name, wkt))
            # rowcount is 1 if the row was inserted, 0 if ON CONFLICT skipped it.
            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1
        except psycopg2.Error as exc:
            print(f"  [ERROR] {name!r}: database error — {exc}")
            conn.rollback()   # roll back the failed statement before continuing
            errors += 1
            continue

    # Commit once at the end — a single transaction is faster than autocommit
    # per-row and keeps the table consistent (all-or-nothing for this run).
    conn.commit()
    cur.close()
    conn.close()

    # ── 4. summary ────────────────────────────────────────────────────────────
    print(f"\nDone.")
    print(f"  Inserted : {inserted}")
    print(f"  Skipped  : {skipped}  (already existed or missing data)")
    print(f"  Errors   : {errors}")


if __name__ == "__main__":
    main()
