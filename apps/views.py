
from flask import Blueprint, render_template, request
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import requests

from apps import cache

views = Blueprint('views', __name__)

API_URL = 'https://data.sfgov.org/resource/wg3w-h783.json'
TARGET_CATEGORIES = ['Motor Vehicle Theft', 'Larceny - From Vehicle']


@views.route('/')
def home():
    map_html = generate_map()
    if map_html is None:
        return render_template('error.html', message=(
            'Could not reach the SFPD data API. Please try again later.'
        ))
    return render_template('home.html', map_html=map_html)


@views.route('/about')
def about():
    return render_template('about.html')


@views.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']
        return 'Message sent!'
    return render_template('contact.html')


@cache.cached(timeout=3600, key_prefix='sfpd_map')
def generate_map():
    # Fetch live data from the SFPD Socrata API
    try:
        response = requests.get(API_URL, params={
            '$limit': 5000,
            '$order': 'incident_datetime DESC',
            '$where': "incident_subcategory in('Motor Vehicle Theft','Larceny - From Vehicle')",
        }, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f'SFPD API error: {e}')
        return None

    # Load into DataFrame and cast lat/lon from string to float
    df = pd.DataFrame(data)

    if df.empty or 'latitude' not in df.columns or 'longitude' not in df.columns:
        print('API returned no usable data.')
        return None

    df = df[df['incident_subcategory'].isin(TARGET_CATEGORIES)].copy()
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df = df.dropna(subset=['latitude', 'longitude'])

    if df.empty:
        print('No valid coordinates after cleaning.')
        return None

    # Build the Folium map
    map_center = [df['latitude'].mean(), df['longitude'].mean()]
    sf_map = folium.Map(location=map_center, zoom_start=12)
    marker_cluster = MarkerCluster().add_to(sf_map)

    for _, row in df.iterrows():
        folium.Marker(location=[row['latitude'], row['longitude']]).add_to(marker_cluster)

    return sf_map._repr_html_()
