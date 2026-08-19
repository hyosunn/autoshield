"""
load_incidents.py — ingest SFPD incident records for risk scoring.

Pulls the five crime categories used by the scoring algorithm from the SFPD
Socrata endpoint (dataset wg3w-h783) into the incidents table, going back
36 months (the hard cutoff used by compute_risk_scores.py).

Idempotent: ON CONFLICT (incident_id) DO NOTHING means re-running is safe.

Usage:
    python scripts/load_incidents.py

Requires DATABASE_URL in your .env file, and optionally SOCRATA_APP_TOKEN
to raise the Socrata rate limit:
    DATABASE_URL=postgresql://postgres:password@localhost:5432/autoshield
    SOCRATA_APP_TOKEN=your_token_here
"""

import os
import sys
from datetime import datetime, timedelta

import psycopg2
import requests
from dotenv import load_dotenv

# Load .env from the project root (one level up from scripts/).
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

API_URL       = "https://data.sfgov.org/resource/wg3w-h783.json"
PAGE_SIZE     = 50_000
LOOKBACK_DAYS = 36 * 30   # 36-month hard cutoff from the scoring algorithm

# Motor Vehicle Theft and Larceny - From Vehicle appear as incident_subcategory;
# Burglary, Robbery, Assault appear as incident_category (their subcategories
# are things like "Burglary - Commercial", "Simple Assault", etc.).
SUBCATEGORY_VALUES = ("Motor Vehicle Theft", "Larceny - From Vehicle")
CATEGORY_VALUES    = ("Burglary", "Robbery", "Assault")


def _soql_where(cutoff: str) -> str:
    sub_list = ", ".join(f"'{v}'" for v in SUBCATEGORY_VALUES)
    cat_list = ", ".join(f"'{v}'" for v in CATEGORY_VALUES)
    return (
        f"(incident_subcategory in({sub_list})"
        f" OR incident_category in({cat_list}))"
        f" AND incident_datetime >= '{cutoff}'"
        f" AND latitude IS NOT NULL AND longitude IS NOT NULL"
    )


def main():
    # ── 1. validate environment ────────────────────────────────────────────────
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print(
            "ERROR: DATABASE_URL is not set.\n"
            "Add it to your .env file, e.g.:\n"
            "  DATABASE_URL=postgresql://postgres:password@localhost:5432/autoshield",
            file=sys.stderr,
        )
        sys.exit(1)

    token   = os.getenv("SOCRATA_APP_TOKEN", "")
    headers = {"X-App-Token": token} if token else {}

    cutoff = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT00:00:00")
    where  = _soql_where(cutoff)

    print(f"Loading incidents since {cutoff[:10]} from:\n  {API_URL}\n")

    # ── 2. connect ────────────────────────────────────────────────────────────
    conn = psycopg2.connect(database_url)
    cur  = conn.cursor()

    # POINT geometry: WKT uses "longitude latitude" order, matching GeoJSON
    # and GPS coordinates (x = east/west, y = north/south).
    insert_sql = """
        INSERT INTO incidents (incident_id, category, incident_date, location)
        VALUES (
            %s,
            %s,
            %s,
            ST_GeogFromText('SRID=4326;POINT(' || %s || ' ' || %s || ')')
        )
        ON CONFLICT (incident_id) DO NOTHING;
    """

    # ── 3. paginate and insert ────────────────────────────────────────────────
    inserted = 0
    skipped  = 0
    errors   = 0
    offset   = 0

    while True:
        try:
            resp = requests.get(API_URL, headers=headers, params={
                "$limit":  PAGE_SIZE,
                "$offset": offset,
                "$where":  where,
                "$select": "row_id,incident_subcategory,incident_category,incident_datetime,latitude,longitude",
                "$order":  "incident_datetime DESC",
            }, timeout=60)
            resp.raise_for_status()
            page = resp.json()
        except requests.RequestException as exc:
            print(f"  [ERROR] Socrata request failed at offset={offset}: {exc}", file=sys.stderr)
            sys.exit(1)

        if not page:
            break

        print(f"  Page offset={offset}: {len(page)} records")

        for row in page:
            incident_id = row.get("row_id")
            if not incident_id:
                errors += 1
                continue

            # Resolve the canonical category name that matches the scoring weight
            # table — subcategory field takes priority when both fields are present.
            sub = row.get("incident_subcategory", "")
            cat = row.get("incident_category", "")
            if sub in SUBCATEGORY_VALUES:
                category = sub
            elif cat in CATEGORY_VALUES:
                category = cat
            else:
                errors += 1
                continue

            dt_str = row.get("incident_datetime")
            lat    = row.get("latitude")
            lon    = row.get("longitude")

            if not (dt_str and lat and lon):
                skipped += 1
                continue

            try:
                dt    = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                dt_pg = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                errors += 1
                continue

            try:
                cur.execute(insert_sql, (incident_id, category, dt_pg, lon, lat))
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    skipped += 1
            except psycopg2.Error as exc:
                print(f"  [ERROR] row_id={incident_id}: {exc}", file=sys.stderr)
                conn.rollback()
                errors += 1
                continue

        # Commit per page so a mid-run failure doesn't discard all prior work.
        conn.commit()

        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    # ── 4. summary ────────────────────────────────────────────────────────────
    cur.close()
    conn.close()

    print(f"\nDone.")
    print(f"  Inserted : {inserted}")
    print(f"  Skipped  : {skipped}  (already existed or missing data)")
    print(f"  Errors   : {errors}")


if __name__ == "__main__":
    main()
