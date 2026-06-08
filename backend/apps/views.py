import os
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
import requests as http

from apps import cache

SOCRATA_TOKEN = os.environ.get('SOCRATA_APP_TOKEN', '')

views = Blueprint('views', __name__)

API_URL = 'https://data.sfgov.org/resource/wg3w-h783.json'

DATE_RANGE_DAYS = {
    '1month': 30,
    '3months': 90,
    '1year': 365,
}

TIME_RANGES = {
    'morning':   ('06:00:00', '11:59:59'),
    'afternoon': ('12:00:00', '17:59:59'),
    'evening':   ('18:00:00', '23:59:59'),
    'night':     ('00:00:00', '05:59:59'),
}


def _build_where(date_range, days, times, categories):
    clauses = []

    # Date range
    days_back = DATE_RANGE_DAYS.get(date_range, 90)
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    clauses.append(f"incident_datetime >= '{cutoff}'")

    # Days of week (API uses full names: Monday, Tuesday, ...)
    if days:
        quoted = ', '.join(f"'{d}'" for d in days)
        clauses.append(f'incident_day_of_week in({quoted})')

    # Time of day — OR together each selected window
    if times:
        time_clauses = []
        for t in times:
            if t in TIME_RANGES:
                lo, hi = TIME_RANGES[t]
                time_clauses.append(
                    f"(incident_time >= '{lo}' AND incident_time <= '{hi}')"
                )
        if time_clauses:
            clauses.append('(' + ' OR '.join(time_clauses) + ')')

    # Categories
    if categories:
        quoted = ', '.join(f"'{c}'" for c in categories)
        clauses.append(f'incident_subcategory in({quoted})')
    else:
        # Default: only vehicle crime
        clauses.append(
            "incident_subcategory in('Motor Vehicle Theft','Larceny - From Vehicle')"
        )

    return ' AND '.join(clauses)


@views.route('/api/incidents')
def get_incidents():
    date_range = request.args.get('date_range', '3months')
    days       = request.args.getlist('days')
    times      = request.args.getlist('times')
    categories = request.args.getlist('categories')

    cache_key = f'incidents:{date_range}:{",".join(sorted(days))}:{",".join(sorted(times))}:{",".join(sorted(categories))}'

    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached)

    where = _build_where(date_range, days, times, categories)

    try:
        headers = {'X-App-Token': SOCRATA_TOKEN} if SOCRATA_TOKEN else {}
        resp = http.get(API_URL, params={
            '$limit': 5000,
            '$order': 'incident_datetime DESC',
            '$where': where,
            '$select': 'incident_subcategory,latitude,longitude,incident_datetime,incident_date,incident_day_of_week,incident_time,incident_category',
        }, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except http.RequestException as e:
        print(f'SFPD API error: {e}')
        return jsonify({'error': 'Could not reach the SFPD data API. Please try again later.'}), 503

    # Drop records missing coordinates
    clean = [
        r for r in data
        if r.get('latitude') and r.get('longitude')
    ]

    cache.set(cache_key, clean, timeout=3600)
    return jsonify(clean)
