
from pathlib import Path
from flask import Blueprint, render_template, request
import pandas as pd
import folium
from folium.plugins import MarkerCluster

views = Blueprint('views', __name__)

BASE_DIR = Path(__file__).parent
DATASET_PATH = BASE_DIR / 'static' / 'data' / 'SFdata.csv'
MAP_SAVE_PATH = BASE_DIR / 'static' / 'maps' / 'sf_map.html'

@views.route('/')
def home():
    generate_map()
    return render_template('home.html')

@views.route('/about')
def about():
    return render_template('about.html')

@views.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Handle form submission
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']
        # You can add logic to send the message here
        return 'Message sent!'
    return render_template('contact.html')

def generate_map():
    autoBurglaryData = pd.read_csv(DATASET_PATH)
    
    # Print column names to debug
    print(autoBurglaryData.columns)
    
    # Print first few rows to debug
    print(autoBurglaryData.head())
    
    # Ensure the column name is correct
    if 'incident_date' not in autoBurglaryData.columns:
        raise KeyError("'incident_date' column not found in the CSV file")
    
    autoBurglaryData.sort_values(by=['incident_date'], inplace=True)

    target_categories = ['Motor Vehicle Theft', 'Larceny - From Vehicle']
    subset = autoBurglaryData.head(12000)
    CleanedData = subset[subset['incident_subcategory'].isin(target_categories)].reset_index(drop=True)

    CleanedData = CleanedData.dropna(subset=['latitude', 'longitude'])

    # Marker Cluster Map
    map_center = [CleanedData['latitude'].mean(), CleanedData['longitude'].mean()]
    sf_map = folium.Map(location=map_center, zoom_start=12)

    # Create a MarkerCluster object
    marker_cluster = MarkerCluster().add_to(sf_map)

    # Add markers to the cluster
    for idx, row in CleanedData.iterrows():
        folium.Marker(location=[row['latitude'], row['longitude']]).add_to(marker_cluster)

    MAP_SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    sf_map.save(MAP_SAVE_PATH)