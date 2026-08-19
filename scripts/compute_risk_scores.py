"""
compute_risk_scores.py — recompute parking_risk_score and pedestrian_risk_score
for every neighborhood.

Implements the algorithm in docs/risk-scoring-design.md exactly: per-category
exponential decay (half-life varies by category, 36-month hard cutoff),
per-axis severity weights, area normalization, empirical Bayes shrinkage for
neighborhoods with fewer than 5 qualifying incidents, then a citywide
percentile rank. See that doc for the rationale behind each choice.

Re-runnable: this is a full recompute from the current incidents table each
run (not an incremental update), so re-running never accumulates — a
neighborhood's stored score always reflects exactly what's in the database
right now.

Usage:
    python scripts/compute_risk_scores.py

Requires DATABASE_URL in your .env file, e.g.:
    DATABASE_URL=postgresql://postgres:password@localhost:5432/autoshield
"""

import math
import os
import sys
from datetime import datetime, timedelta

import psycopg2
from dotenv import load_dotenv

# Load .env from the project root (one level up from scripts/).
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── scoring constants (docs/risk-scoring-design.md) ────────────────────────────

# Hard cutoff: incidents older than this never contribute, regardless of
# category. Expressed in days using the same 30-days/month convention as
# load_incidents.py's LOOKBACK_DAYS.
HARD_CUTOFF_DAYS = 36 * 30

# Half-life is keyed by category, not by axis — property crime decays faster
# (9mo) than violent crime (18mo) because violent-crime samples are rarer and
# need a longer memory to stay statistically meaningful.
HALFLIFE_DAYS = {
    "Motor Vehicle Theft":     9 * 30,
    "Larceny - From Vehicle":  9 * 30,
    "Burglary":                9 * 30,
    "Robbery":                 18 * 30,
    "Assault":                 18 * 30,
}

# Severity weights per axis. Cross-category weights are deliberately non-zero
# (e.g. Robbery still counts a little toward parking risk) — see the design
# doc's "Non-zero cross-category weights" section.
AXES = ("parking", "pedestrian")

WEIGHTS = {
    "parking": {
        "Motor Vehicle Theft":     1.0,
        "Larceny - From Vehicle":  1.0,
        "Burglary":                0.3,
        "Robbery":                 0.3,
        "Assault":                 0.1,
    },
    "pedestrian": {
        "Motor Vehicle Theft":     0.1,
        "Larceny - From Vehicle":  0.05,
        "Burglary":                0.2,
        "Robbery":                 1.0,
        "Assault":                 1.0,
    },
}

# Neighborhoods with fewer than this many qualifying incidents get their
# density shrunk toward the citywide mean instead of trusted as-is, and are
# flagged low_sample in the output.
LOW_SAMPLE_THRESHOLD = 5

# Empirical Bayes shrinkage strength — how many "phantom" citywide-mean
# incidents a low-sample neighborhood's estimate is blended against.
SHRINKAGE_K = 10


# ── data access ─────────────────────────────────────────────────────────────────

def fetch_qualifying_incidents(cur, cutoff):
    cur.execute(
        """
        SELECT category, incident_date, neighborhood_id
        FROM incidents
        WHERE neighborhood_id IS NOT NULL
          AND incident_date >= %s
        """,
        (cutoff,),
    )
    return cur.fetchall()


def fetch_neighborhood_areas(cur):
    # Geography-typed ST_Area returns square metres via a geodesic
    # calculation; /1e6 converts to square kilometres.
    cur.execute("SELECT id, ST_Area(boundary) / 1e6 AS area_km2 FROM neighborhoods;")
    return dict(cur.fetchall())


# ── scoring math ─────────────────────────────────────────────────────────────────

def percentile_rank(value, all_values):
    """Fraction of all_values <= value, as a 0-100 percentile."""
    at_or_below = sum(1 for v in all_values if v <= value)
    return at_or_below / len(all_values) * 100


def compute_scores(incident_rows, area_by_neighborhood, now):
    neighborhood_ids = list(area_by_neighborhood.keys())

    raw = {nid: {axis: 0.0 for axis in AXES} for nid in neighborhood_ids}
    n_qualifying = {nid: 0 for nid in neighborhood_ids}

    for category, incident_date, neighborhood_id in incident_rows:
        if neighborhood_id not in raw:
            continue  # neighborhood row missing/stale; skip defensively

        halflife = HALFLIFE_DAYS.get(category)
        if halflife is None:
            continue  # not one of the five scored categories

        age_days = (now - incident_date).days
        if age_days < 0 or age_days > HARD_CUTOFF_DAYS:
            continue

        decay = math.exp(-math.log(2) * age_days / halflife)
        n_qualifying[neighborhood_id] += 1
        for axis in AXES:
            raw[neighborhood_id][axis] += WEIGHTS[axis][category] * decay

    # density(N, axis) = raw(N, axis) / area_km2(N)
    density = {
        nid: {
            axis: (raw[nid][axis] / area_by_neighborhood[nid]) if area_by_neighborhood[nid] > 0 else 0.0
            for axis in AXES
        }
        for nid in neighborhood_ids
    }

    # citywide_mean_density(axis) — simple mean across neighborhoods, used as
    # the shrinkage target for low-sample neighborhoods.
    citywide_mean = {
        axis: sum(density[nid][axis] for nid in neighborhood_ids) / len(neighborhood_ids)
        for axis in AXES
    }

    shrunk = {nid: {} for nid in neighborhood_ids}
    for nid in neighborhood_ids:
        n = n_qualifying[nid]
        for axis in AXES:
            if n < LOW_SAMPLE_THRESHOLD:
                k = SHRINKAGE_K
                shrunk[nid][axis] = (n / (n + k)) * density[nid][axis] + (k / (n + k)) * citywide_mean[axis]
            else:
                shrunk[nid][axis] = density[nid][axis]

    scores = {nid: {} for nid in neighborhood_ids}
    for axis in AXES:
        all_shrunk = [shrunk[nid][axis] for nid in neighborhood_ids]
        for nid in neighborhood_ids:
            scores[nid][axis] = round(percentile_rank(shrunk[nid][axis], all_shrunk), 2)

    low_sample = {nid: n_qualifying[nid] < LOW_SAMPLE_THRESHOLD for nid in neighborhood_ids}

    return scores, low_sample, n_qualifying


# ── persistence ──────────────────────────────────────────────────────────────────

def write_scores(cur, scores, low_sample, n_qualifying):
    cur.executemany(
        """
        UPDATE neighborhoods
        SET parking_risk_score    = %s,
            pedestrian_risk_score = %s,
            low_sample            = %s,
            incident_count        = %s,
            last_updated          = NOW()
        WHERE id = %s;
        """,
        [
            (scores[nid]["parking"], scores[nid]["pedestrian"], low_sample[nid], n_qualifying[nid], nid)
            for nid in scores
        ],
    )


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

    now = datetime.now()
    cutoff = now - timedelta(days=HARD_CUTOFF_DAYS)

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    area_by_neighborhood = fetch_neighborhood_areas(cur)
    if not area_by_neighborhood:
        print("ERROR: neighborhoods table is empty — run load_neighborhoods.py first.", file=sys.stderr)
        sys.exit(1)

    incident_rows = fetch_qualifying_incidents(cur, cutoff)

    scores, low_sample, n_qualifying = compute_scores(incident_rows, area_by_neighborhood, now)

    write_scores(cur, scores, low_sample, n_qualifying)
    conn.commit()

    cur.close()
    conn.close()

    flagged = sum(1 for v in low_sample.values() if v)
    print("Done.")
    print(f"  Neighborhoods scored : {len(scores)}")
    print(f"  Incidents considered : {len(incident_rows)}")
    print(f"  Low-sample flagged   : {flagged}")


if __name__ == "__main__":
    main()
