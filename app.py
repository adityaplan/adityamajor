from flask import Flask, request, jsonify
from flask_cors import CORS
from satellite_core import process_satellite_data
import geopy.geocoders
from geopy.geocoders import Nominatim
import time
import os

app = Flask(__name__)
CORS(app, resources={r"/map/*": {"origins": "*"}})  # Enable CORS for map endpoint

# Geocoder setup
geolocator = Nominatim(user_agent="satellite_app")

# Simulate progress tracking
progress = {}

@app.route('/analyze', methods=['POST'])
def analyze_city():
    data = request.get_json()
    city_name = data.get('city')
    radius_km = data.get('radius', 10)
    request_id = str(time.time())
    progress[request_id] = 0
    
    try:
        location = geolocator.geocode(city_name)
        if not location:
            if city_name.lower() == 'delhi':
                location = geolocator.geocode('New Delhi')
            if not location:
                progress[request_id] = -1
                return jsonify({'error': 'City not found', 'request_id': request_id}), 404
        center = [location.latitude, location.longitude]
    except Exception as e:
        progress[request_id] = -1
        return jsonify({'error': f'Geocoding error: {str(e)}', 'request_id': request_id}), 500
    
    try:
        for i in range(10, 100, 10):
            progress[request_id] = i
            time.sleep(0.5)
        map_data = process_satellite_data(center, radius_km)
        progress[request_id] = 100
        return jsonify({
            'center': center,
            'map_data': map_data,
            'request_id': request_id
        })
    except Exception as e:
        progress[request_id] = -1
        return jsonify({'error': f'Satellite data error: {str(e)}', 'request_id': request_id}), 500

@app.route('/progress/<request_id>', methods=['GET'])
def get_progress(request_id):
    return jsonify({'progress': progress.get(request_id, 0)})

@app.route('/map/<city>/<float:lat>/<float:lon>')
def serve_map(city, lat, lon):
    try:
        map_file = '/home/adityadm2110/mysite/static/map.html'  # Absolute path
        app.logger.info(f'Attempting to serve file: {map_file}')
        if not os.path.exists(map_file):
            app.logger.error(f'File not found: {map_file}')
            return jsonify({'error': 'map.html not found'}), 404
        with open(map_file, 'r') as file:
            html_content = file.read()
        html_content = html_content.replace('{{centerLat}}', str(lat))
        html_content = html_content.replace('{{centerLon}}', str(lon))
        html_content = html_content.replace('{{city}}', city)
        app.logger.info('Successfully read and processed map.html')
        return html_content, 200, {'Content-Type': 'text/html'}
    except Exception as e:
        app.logger.error(f'Error serving map.html: {str(e)}')
        return jsonify({'error': f'Failed to serve map: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)