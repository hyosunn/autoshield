
from flask import Blueprint, render_template, request
import pandas as pd
import folium
from folium.plugins import MarkerCluster

views = Blueprint('views', __name__)

# Path to your dataset
DATASET_PATH = 'C:\VS Codes\Ashield\hello_app\static\data\SFdata.csv'  # Update this path

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

    CleanedData = pd.DataFrame()
    for index, row in autoBurglaryData.head(12000).iterrows():
        if row['incident_subcategory'] in ['Motor Vehicle Theft', 'Larceny - From Vehicle']:
            CleanedData = pd.concat([CleanedData, row.to_frame().transpose()], ignore_index=True)

    CleanedData = CleanedData.dropna(subset=['latitude', 'longitude'])

    # Marker Cluster Map
    map_center = [CleanedData['latitude'].mean(), CleanedData['longitude'].mean()]
    sf_map = folium.Map(location=map_center, zoom_start=12)

    # Create a MarkerCluster object
    marker_cluster = MarkerCluster().add_to(sf_map)

    # Add markers to the cluster
    for idx, row in CleanedData.iterrows():
        folium.Marker(location=[row['latitude'], row['longitude']]).add_to(marker_cluster)

    # Save the map to an HTML file
    sf_map.save('C:\VS Codes\Ashield\hello_app\static\maps\sf_map.html')