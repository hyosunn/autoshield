"""
assign_neighborhoods.py — spatial join assigning neighborhood_id to incidents.

For every incident where neighborhood_id IS NULL, finds the neighborhood
polygon that contains the incident's location (ST_Within) and sets the FK.

Re-runnable: only touches unassigned rows, so running it again after a fresh
load_incidents.py run picks up just the new incidents rather than redoing
the whole table.

Usage:
    python scripts/assign_neighborhoods.py

Requires DATABASE_URL in your .env file, e.g.:
    DATABASE_URL=postgresql://postgres:password@localhost:5432/autoshield
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

# Load .env from the project root (one level up from scripts/).
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ST_Within has no geography overload, so both sides are cast to geometry.
# Coordinates are WGS-84 (SRID 4326) on both columns, so the cast doesn't
# change what "within" means here — it's the same lon/lat plane either way.
ASSIGN_SQL = """
    UPDATE incidents
    SET neighborhood_id = neighborhoods.id
    FROM neighborhoods
    WHERE incidents.neighborhood_id IS NULL
      AND ST_Within(incidents.location::geometry, neighborhoods.boundary::geometry);
"""

UNASSIGNED_COUNT_SQL = "SELECT COUNT(*) FROM incidents WHERE neighborhood_id IS NULL;"


def main():
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

    cur.execute(ASSIGN_SQL)
    assigned = cur.rowcount
    conn.commit()

    cur.execute(UNASSIGNED_COUNT_SQL)
    still_unassigned = cur.fetchone()[0]

    cur.close()
    conn.close()

    print("Done.")
    print(f"  Assigned        : {assigned}")
    print(f"  Still unassigned: {still_unassigned}  (location falls outside every neighborhood boundary)")


if __name__ == "__main__":
    main()
