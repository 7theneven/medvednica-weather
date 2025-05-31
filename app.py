from flask import Flask, jsonify, send_file, request, session, redirect
import pandas as pd
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
from groq import Client, GroqError
from pyairtable import Api
from flask_session import Session

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Flask-Session
app.config['SECRET_KEY'] = os.urandom(24)  # For session encryption
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Initialize Airtable client
airtable = Api(os.getenv('AIRTABLE_TOKEN'))
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_ID = os.getenv('AIRTABLE_TABLE_NAME')  # This is actually the table ID
TRACKING_TABLE_ID = 'tblE2BfYjzdf1sygI'  # Table for tracking instances

# Separate caches for different types of weather data
weather_cache = {}  # For general weather data
wind_cache = {}    # Separate cache for wind data
CACHE_DURATION = timedelta(minutes=15)  # Cache general weather data for 15 minutes
WIND_CACHE_DURATION = timedelta(minutes=1)  # Cache wind data for only 1 minute

# Initialize Groq client
groq_client = Client(api_key=os.getenv('GROQ_API_KEY'))

def get_or_create_user(email, firstname):
    """Get or create a user in Airtable."""
    table = airtable.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID)
    
    # Search for existing user
    existing_users = table.all(formula=f"{{Email}} = '{email}'")
    
    if existing_users:
        return existing_users[0]
    
    # Create new user
    new_user = table.create({
        'Email': email,
        'FirstName': firstname,
        'CreatedAt': datetime.now().isoformat()
    })
    
    return new_user

@app.route('/api/login', methods=['POST'])
def login():
    """Handle user login."""
    data = request.json
    email = data.get('email')
    firstname = data.get('firstname')
    
    if not email or not firstname:
        return jsonify({'error': 'Email and firstname are required'}), 400
    
    try:
        user = get_or_create_user(email, firstname)
        session['user'] = {
            'id': user['id'],
            'email': user['fields']['Email'],
            'firstname': user['fields']['FirstName']
        }
        return jsonify({'message': 'Login successful'})
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Failed to process login'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Handle user logout."""
    session.pop('user', None)
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/user')
def get_user():
    """Get current user info."""
    user = session.get('user')
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    return jsonify(user)

@app.route('/')
def index():
    """Serve the frontend HTML."""
    return send_file('frontend.html')

@app.route('/logged_in')
def logged_in():
    """Serve the logged-in frontend HTML."""
    if not session.get('user'):
        return redirect('/')
    return send_file('frontend_logged_in.html')

def generate_hiking_recommendation(weather_data):
    """Generate hiking recommendation using Groq API."""
    try:
        # Create a prompt with the weather data
        time_context = "during the day" if weather_data.get('is_day', 0) == 1 else "at night"
        
        prompt = f"""Based on the following weather conditions, provide a 2-3 sentence recommendation on whether it's suitable for hiking {time_context}. Consider safety and enjoyment factors in your response.

Weather conditions:
- Time: {time_context}
- Temperature: {weather_data.get('temp_c', 'N/A')}°C (Feels like: {weather_data.get('feelslike_c', 'N/A')}°C)
- Condition: {weather_data.get('text', 'N/A')}
- Wind: {weather_data.get('wind_kph', 'N/A')} km/h (Gusts: {weather_data.get('gust_kph', 'N/A')} km/h)
- Precipitation: {weather_data.get('precip_mm', 'N/A')}mm
- Humidity: {weather_data.get('humidity', 'N/A')}%
- UV Index: {weather_data.get('uv', 'N/A')}
- Visibility: {weather_data.get('vis_km', 'N/A')} km
- Cloud Cover: {weather_data.get('cloud', 'N/A')}%
- Snow: {weather_data.get('totalsnow_cm', 0)} cm

Important considerations:
- If it's nighttime, emphasize safety concerns
- Consider visibility conditions
- Account for extreme weather conditions
- Focus on hiker safety and comfort

Keep your response concise and clear."""

        # Call Groq API
        chat_completion = groq_client.chat.completions.create(
            messages=[{
                "role": "user",
                "content": prompt
            }],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=150,
        )
        
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating recommendation: {e}")
        return "Unable to generate hiking recommendation at this time."

def load_trails():
    """Load trail data from CSV file."""
    try:
        df = pd.read_csv('medvednica_paths_with_coords.csv')
        # Filter only trails with coordinates
        return df.dropna(subset=['latitude', 'longitude']).to_dict('records')
    except Exception as e:
        print(f"Error loading trails: {e}")
        return []

def get_wind_data(lat, lon):
    """Get wind data with shorter cache duration."""
    cache_key = f"{lat},{lon}"
    
    # Check if we have cached wind data that's still valid
    if cache_key in wind_cache:
        cached_data = wind_cache[cache_key]
        if datetime.now() - cached_data['timestamp'] < WIND_CACHE_DURATION:
            return {
                'data': cached_data['data'],
                'timestamp': cached_data['timestamp'].isoformat()
            }
    
    # If no valid cache, return None (will trigger a new API call)
    return None

def get_weather(lat, lon):
    """Get weather data from WeatherAPI.com with separate wind caching."""
    cache_key = f"{lat},{lon}"
    current_time = datetime.now()
    
    # Initialize response components
    weather_data = None
    weather_timestamp = None
    wind_data = None
    wind_timestamp = None
    
    # Check regular weather cache
    if cache_key in weather_cache:
        cached_data = weather_cache[cache_key]
        if current_time - cached_data['timestamp'] < CACHE_DURATION:
            weather_data = cached_data['data']
            weather_timestamp = cached_data['timestamp']
    
    # Check wind cache separately
    wind_cache_result = get_wind_data(lat, lon)
    if wind_cache_result:
        wind_data = wind_cache_result['data']
        wind_timestamp = wind_cache_result['timestamp']
    
    # If either cache is invalid, fetch new data
    if weather_data is None or wind_data is None:
        try:
            api_key = os.getenv('WEATHERAPI_KEY')
            if not api_key:
                raise ValueError("WeatherAPI key not found in environment variables")
                
            url = f"http://api.weatherapi.com/v1/forecast.json?key={api_key}&q={lat},{lon}&aqi=no"
            response = requests.get(url)
            response.raise_for_status()
            
            api_data = response.json()
            current = api_data['current']
            forecast = api_data['forecast']['forecastday'][0]
            
            # If we need new weather data
            if weather_data is None:
                weather_data = {
                    'temp_c': current['temp_c'],
                    'feelslike_c': current['feelslike_c'],
                    'text': current['condition']['text'],
                    'icon': current['condition']['icon'],
                    'humidity': current['humidity'],
                    'precip_mm': current['precip_mm'],
                    'is_day': current['is_day'],
                    'uv': current['uv'],
                    'vis_km': current['vis_km'],
                    'cloud': current['cloud'],
                    'sunrise': forecast['astro']['sunrise'],
                    'sunset': forecast['astro']['sunset'],
                    'totalsnow_cm': forecast.get('totalsnow_cm', 0),
                    'snow_cm': current.get('snow_cm', 0)
                }
                
                weather_timestamp = current_time
                
                # Cache the general weather data
                weather_cache[cache_key] = {
                    'data': weather_data,
                    'timestamp': current_time
                }
            
            # If we need new wind data
            if wind_data is None:
                wind_data = {
                    'wind_kph': current['wind_kph'],
                    'wind_degree': current['wind_degree'],
                    'wind_dir': current['wind_dir'],
                    'gust_kph': current['gust_kph'],
                    'windchill_c': current.get('windchill_c', current['feelslike_c'])
                }
                
                wind_timestamp = current_time
                
                # Cache the wind data separately with shorter duration
                wind_cache[cache_key] = {
                    'data': wind_data,
                    'timestamp': current_time
                }
            
        except Exception as e:
            print(f"Error fetching weather for {lat},{lon}: {e}")
            if weather_data is None:
                weather_data = {}
            if wind_data is None:
                wind_data = {}
    
    # Combine the data with timestamps
    return {
        **weather_data,
        **(wind_data or {}),  # Use empty dict if wind_data is None
        'weather_updated': weather_timestamp.isoformat() if weather_timestamp else None,
        'wind_updated': wind_timestamp if isinstance(wind_timestamp, str) else (wind_timestamp.isoformat() if wind_timestamp else None)
    }

@app.route('/api/trails')
def get_trails_with_weather():
    """Get all trails with their current weather data."""
    trails = load_trails()
    
    for trail in trails:
        if trail.get('latitude') and trail.get('longitude'):
            weather = get_weather(trail['latitude'], trail['longitude'])
            trail['weather'] = weather
    
    return jsonify(trails)

@app.route('/api/recommendation/<lat>/<lon>')
def get_recommendation(lat, lon):
    """Get AI recommendation for a specific location."""
    if groq_client is None:
        return jsonify({"recommendation": "AI recommendations are currently disabled."}), 503
        
    try:
        weather = get_weather(float(lat), float(lon))
        recommendation = generate_hiking_recommendation(weather)
        return jsonify({"recommendation": recommendation})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/track/<path_number>', methods=['POST'])
def track_path(path_number):
    """Handle path tracking for logged-in users."""
    print(f"Received tracking request for path {path_number}")
    
    user = session.get('user')
    if not user:
        print("No user in session")
        return jsonify({'error': 'You need to log in first to get weather updates'}), 401
    
    try:
        # Step 1: Find user record by email
        print("Step 1: Searching for user in users table (tblCWQVFr9q8eqGLU)")
        users_table = airtable.table(AIRTABLE_BASE_ID, 'tblCWQVFr9q8eqGLU')
        
        user_email = user['email']  # Email is stored directly in the session user object
        user_search_formula = f"{{Email}} = '{user_email}'"
        print(f"User search formula: {user_search_formula}")
        
        users = users_table.all(formula=user_search_formula)
        print(f"User search results: {users}")
        
        if not users:
            print(f"No matching user found for email {user_email}")
            return jsonify({'error': 'User not found in Airtable'}), 404
            
        user_record = users[0]
        user_record_id = user_record['id']
        print(f"Found user record - ID: {user_record_id}")
        
        # Step 2: Find path record
        print("Step 2: Searching for path in paths table (tblvTBHvYgObv2Cio)")
        paths_table = airtable.table(AIRTABLE_BASE_ID, 'tblvTBHvYgObv2Cio')
        
        path_search_formula = f"{{PathNumber}} = '{path_number}'"
        print(f"Path search formula: {path_search_formula}")
        
        paths = paths_table.all(formula=path_search_formula)
        print(f"Path search results: {paths}")
        
        if not paths:
            print(f"No matching path found for path number {path_number}")
            return jsonify({'error': 'Path not found'}), 404
            
        path_record = paths[0]
        path_record_id = path_record['id']
        print(f"Found path record - ID: {path_record_id}")
        
        # Step 3: Create tracking record with both links
        print("Step 3: Creating tracking record in tracking table (tblE2BfYjzdf1sygI)")
        tracking_table = airtable.table(AIRTABLE_BASE_ID, TRACKING_TABLE_ID)
        
        record_data = {
            'PathNumbers': [path_record_id],
            'Users': [user_record_id]
        }
        print(f"Creating record with data: {record_data}")
        
        new_record = tracking_table.create(record_data)
        print(f"Successfully created tracking record: {new_record}")
        
        return jsonify({
            'message': 'Successfully tracking path',
            'record': new_record
        })
    except Exception as e:
        error_msg = str(e)
        print(f"Error tracking path: {error_msg}")
        print(f"Error details:")
        print(f"- Path number being searched: {path_number}")
        print(f"- User email being searched: {user.get('email', 'Not found')}")
        print(f"- Base ID being used: {AIRTABLE_BASE_ID}")
        print(f"- Tracking table ID being used: {TRACKING_TABLE_ID}")
        return jsonify({
            'error': f'Failed to track path: {error_msg}'
        }), 500

@app.route('/api/user/tracked-paths', methods=['GET'])
def get_tracked_paths():
    """Get all paths that the current user is tracking."""
    user = session.get('user')
    if not user:
        print("No user in session")
        return jsonify({'error': 'You need to log in first'}), 401
    
    try:
        # Find user record by email
        print(f"Finding user record for email: {user['email']}")
        users_table = airtable.table(AIRTABLE_BASE_ID, 'tblCWQVFr9q8eqGLU')
        users = users_table.all(formula=f"{{Email}} = '{user['email']}'")
        
        if not users:
            print(f"No matching user found for email {user['email']}")
            return jsonify({'error': 'User not found in Airtable'}), 404
            
        user_record = users[0]
        
        # Get the linked path records from TrackedPaths field
        tracked_path_ids = user_record['fields'].get('TrackedPaths', [])
        print(f"Found tracked path IDs: {tracked_path_ids}")
        
        # Get the path numbers for these paths
        paths_table = airtable.table(AIRTABLE_BASE_ID, 'tblvTBHvYgObv2Cio')
        tracked_paths = []
        
        for path_id in tracked_path_ids:
            path_record = paths_table.get(path_id)
            if path_record and 'PathNumber' in path_record['fields']:
                tracked_paths.append(path_record['fields']['PathNumber'])
        
        print(f"Found tracked path numbers: {tracked_paths}")
        return jsonify({
            'tracked_paths': tracked_paths
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error getting tracked paths: {error_msg}")
        return jsonify({
            'error': f'Failed to get tracked paths: {error_msg}'
        }), 500

@app.route('/api/untrack/<path_number>', methods=['POST'])
def untrack_path(path_number):
    """Remove tracking for a specific path."""
    print(f"Received untracking request for path {path_number}")
    
    user = session.get('user')
    if not user:
        print("No user in session")
        return jsonify({'error': 'You need to log in first'}), 401
    
    try:
        # Find the tracking record that matches both the user's email and path number
        print("Finding tracking record to delete")
        tracking_table = airtable.table(AIRTABLE_BASE_ID, TRACKING_TABLE_ID)
        paths_table = airtable.table(AIRTABLE_BASE_ID, 'tblvTBHvYgObv2Cio')
        
        # First, get all records for this user's email
        user_email = user['email']
        search_formula = f"{{UserEmail}} = '{user_email}'"
        print(f"Searching with formula: {search_formula}")
        
        tracking_records = tracking_table.all(formula=search_formula)
        print(f"Found {len(tracking_records)} records for user {user_email}")
        
        # Then find the record where PathNumbers matches our path_number
        record_to_delete = None
        for record in tracking_records:
            print(f"\nChecking record: {record['id']}")
            print(f"Record fields: {json.dumps(record['fields'], indent=2)}")
            
            if 'PathNumbers' in record['fields']:
                path_record_id = record['fields']['PathNumbers'][0]  # Get the first linked record ID
                print(f"Path record ID: {path_record_id}")
                
                # Fetch the actual path record using the ID
                try:
                    path_record = paths_table.get(path_record_id)
                    print(f"Retrieved path record: {json.dumps(path_record, indent=2)}")
                    
                    if path_record and 'fields' in path_record:
                        record_path_number = path_record['fields'].get('PathNumber')
                        print(f"Comparing path numbers: record={record_path_number} vs target={path_number}")
                        if str(record_path_number) == str(path_number):
                            record_to_delete = record
                            print("Found matching record!")
                            break
                except Exception as e:
                    print(f"Error fetching path record: {e}")
                    continue
            else:
                print("No PathNumbers field in record")
        
        if not record_to_delete:
            print("No tracking record found to delete")
            return jsonify({'error': 'No tracking record found'}), 404
        
        # Delete the tracking record
        tracking_table.delete(record_to_delete['id'])
        
        print(f"Successfully deleted tracking record: {record_to_delete['id']}")
        return jsonify({
            'message': 'Successfully untracked path'
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error untracking path: {error_msg}")
        print(f"Error details:")
        print(f"- Path number: {path_number}")
        print(f"- User email: {user_email}")
        print(f"- Search formula used: {search_formula if 'search_formula' in locals() else 'Not created yet'}")
        if 'tracking_records' in locals():
            print(f"- Found records: {json.dumps(tracking_records, indent=2)}")
        return jsonify({
            'error': f'Failed to untrack path: {error_msg}'
        }), 500

if __name__ == '__main__':
    # Check if required environment variables are set
    if not os.getenv('WEATHERAPI_KEY'):
        print("Warning: WEATHERAPI_KEY not set. Please set it in .env file")
    if not os.getenv('GROQ_API_KEY'):
        print("Warning: GROQ_API_KEY not set. Please set it in .env file")
    if not os.getenv('AIRTABLE_TOKEN'):
        print("Warning: AIRTABLE_TOKEN not set. Please set it in .env file")
    if not os.getenv('AIRTABLE_BASE_ID'):
        print("Warning: AIRTABLE_BASE_ID not set. Please set it in .env file")
    
    app.run(debug=True) 