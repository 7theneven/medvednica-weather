import os
import json
import time
from datetime import datetime
import requests
from dotenv import load_dotenv
from pyairtable import Api
import logging
from pathlib import Path
import pandas as pd
import pytz

# Load environment variables
load_dotenv()

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
weather_log_file = log_dir / "weather_data.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(weather_log_file),
        logging.StreamHandler()  # Also print to console
    ]
)

class WeatherMonitor:
    def __init__(self):
        self.airtable = Api(os.getenv('AIRTABLE_TOKEN'))
        self.base_id = 'appSjGWibVPfELrIl'
        self.weather_logs_table_id = 'tbliCSyliEax9A91I'
        self.paths_table_id = 'tblvTBHvYgObv2Cio'  # Added paths table ID
        self.weather_api_key = os.getenv('WEATHERAPI_KEY')
        self.last_weather_data = {}  # Store last weather data for comparison
        self.last_log_time = {}  # Store last log time for each path
        self.paths_file = 'medvednica_paths_with_coords.csv'
        self.path_record_cache = {}  # Cache for path record IDs

    def get_all_paths(self):
        """Get all paths from the CSV file."""
        try:
            # Read the CSV file
            df = pd.read_csv(self.paths_file)
            logging.debug(f"Found {len(df)} total paths in CSV")
            
            # Filter paths with coordinates and convert to list of dicts
            paths = []
            for _, row in df.dropna(subset=['latitude', 'longitude']).iterrows():
                path = {
                    'path_number': str(row['number']),  # Ensure path_number is string
                    'name': row['name'],
                    'latitude': row['latitude'],
                    'longitude': row['longitude']
                }
                paths.append(path)
                logging.debug(f"Added path: #{path['path_number']} - {path['name']}")
            
            # Sort paths by number
            paths = sorted(paths, key=lambda x: int(x['path_number']))
            logging.info(f"Total paths with coordinates: {len(paths)}")
            return paths
            
        except Exception as e:
            logging.error(f"Error reading paths from CSV: {e}")
            return []

    def fetch_weather_data(self, path):
        """Fetch current weather data for a specific path."""
        try:
            # Using forecast API to get chance of rain
            url = f"http://api.weatherapi.com/v1/forecast.json"
            params = {
                'key': self.weather_api_key,
                'q': f"{path['latitude']},{path['longitude']}",
                'days': 1  # We need this to get chance of rain
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            weather_data = response.json()
            current = weather_data['current']
            forecast = weather_data['forecast']['forecastday'][0]
            
            # Get current hour's chance of rain from the hourly forecast
            current_hour = datetime.now().hour
            chance_of_rain = forecast['hour'][current_hour]['chance_of_rain']
            
            return {
                'temp_c': current['temp_c'],
                'wind_kph': current['wind_kph'],
                'precip_mm': current['precip_mm'],
                'chance_of_rain': chance_of_rain,
                'text': current['condition']['text'],
                'vis_km': current['vis_km'],
                'uv': current['uv'],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error fetching weather for path {path['path_number']}: {e}")
            return None

    def is_significant_change(self, old_data, new_data):
        """
        Compare old and new weather data to determine if changes are significant.
        Returns (bool, list of str) - is_significant and reasons for significance.
        """
        if not old_data:
            return True, ["Initial reading"]

        significant = False
        reasons = []

        # Chance of rain - increases by >50% (increased from 30%)
        old_rain_chance = float(old_data.get('chance_of_rain', 0))
        new_rain_chance = float(new_data.get('chance_of_rain', 0))
        if new_rain_chance - old_rain_chance >= 50:
            significant = True
            reasons.append(f"Rain chance increased from {old_rain_chance}% to {new_rain_chance}%")

        # Precipitation - increases by ≥5mm (increased from 2mm)
        old_precip = float(old_data.get('precip_mm', 0))
        new_precip = float(new_data.get('precip_mm', 0))
        if new_precip - old_precip >= 5:
            significant = True
            reasons.append(f"Precipitation increased from {old_precip}mm to {new_precip}mm")

        # Wind speed - exceeds 40 kph (removed change threshold)
        new_wind = float(new_data.get('wind_kph', 0))
        if new_wind >= 40:
            significant = True
            reasons.append(f"High wind speed: {new_wind} kph")

        # Weather condition text change - only for severe conditions
        old_text = old_data.get('text', '').lower()
        new_text = new_data.get('text', '').lower()
        severe_conditions = ['thunderstorm', 'storm', 'snow', 'sleet', 'hail', 'blizzard', 'heavy rain', 'fog']
        
        if new_text != old_text:
            # Check if new condition is severe
            if any(condition in new_text for condition in severe_conditions):
                significant = True
                reasons.append(f"Severe weather condition: {new_data.get('text', '')}")

        # Visibility - drops below 3 km (reduced from 5 km)
        old_vis = float(old_data.get('vis_km', 10))
        new_vis = float(new_data.get('vis_km', 10))
        if new_vis < 3 and old_vis >= 3:
            significant = True
            reasons.append(f"Low visibility: {new_vis} km")

        # UV index - goes above 8 (increased from 7)
        old_uv = float(old_data.get('uv', 0))
        new_uv = float(new_data.get('uv', 0))
        if new_uv > 8 and old_uv <= 8:
            significant = True
            reasons.append(f"Very high UV index: {new_uv}")

        return significant, reasons

    def get_path_record_id(self, path_number):
        """Get the Airtable record ID for a path number from the paths table."""
        try:
            # Ensure path_number is a string
            path_number = str(path_number)
            
            # Check cache first
            if path_number in self.path_record_cache:
                return self.path_record_cache[path_number]

            paths_table = self.airtable.table(self.base_id, self.paths_table_id)
            
            # Query Airtable for the path record
            records = paths_table.all(
                formula=f"{{PathNumber}} = '{path_number}'"
            )
            
            if records:
                record_id = records[0]['id']
                # Cache the result
                self.path_record_cache[path_number] = record_id
                return record_id
            else:
                logging.error(f"No matching path record found for path number {path_number}")
                return None
                
        except Exception as e:
            logging.error(f"Error fetching path record ID for path {path_number}: {e}")
            return None

    def get_latest_weather_record(self, path_number):
        """Fetch the most recent weather record for a path from Airtable."""
        try:
            # Ensure path_number is a string
            path_number = str(path_number)
            
            weather_logs_table = self.airtable.table(self.base_id, self.weather_logs_table_id)
            
            # Query Airtable for the latest record using PathNumberLookup
            formula = f"{{PathNumberLookup}} = '{path_number}'"
            logging.info(f"Querying Airtable with formula: {formula}")
            
            records = weather_logs_table.all(
                formula=formula,
                sort=['-Timestamp'],
                max_records=1
            )
            
            if records:
                record = records[0]
                logging.info(f"Found record: {json.dumps(record['fields'], indent=2)}")
                # Convert Airtable record to our weather data format
                return {
                    'temp_c': float(record['fields'].get('CurrentTemperature', 0)),
                    'wind_kph': float(record['fields'].get('CurrentWindSpeed', 0)),
                    'precip_mm': float(record['fields'].get('CurrentPrecipitation', 0)),
                    'chance_of_rain': float(record['fields'].get('ChanceOfRain', 0)),
                    'text': record['fields'].get('Conditions', ''),
                    'vis_km': float(record['fields'].get('CurrentVisibility', 10)),
                    'uv': float(record['fields'].get('CurrentUVIndex', 0)),
                    'timestamp': record['fields'].get('Timestamp')
                }
            
            logging.debug(f"No previous records found for path {path_number}")
            return None
            
        except Exception as e:
            logging.error(f"Error fetching latest weather record for path {path_number}: {str(e)}")
            return None

    def should_log_weather(self, path_number, weather_data):
        """
        Determine if weather data should be logged based on significance and time.
        Now compares against the latest Airtable record instead of cached data.
        """
        try:
            # Get the latest record from Airtable
            latest_record = self.get_latest_weather_record(path_number)
            
            if not latest_record:
                return True, ["Initial reading"]

            # Check time difference
            latest_time = datetime.fromisoformat(latest_record['timestamp'])
            current_time = datetime.now()
            
            # If it's been 8 hours since last log
            if (current_time - latest_time).total_seconds() >= 8 * 3600:
                return True, ["Regular 8-hour update"]

            # Check for significant changes
            return self.is_significant_change(latest_record, weather_data)
            
        except Exception as e:
            logging.error(f"Error in should_log_weather for path {path_number}: {e}")
            # If there's an error checking, better to log the data
            return True, ["Error checking previous record"]

    def log_to_airtable(self, path, weather_data, change_reasons=None):
        """Log weather data to Airtable with specified field mappings."""
        try:
            weather_logs_table = self.airtable.table(self.base_id, self.weather_logs_table_id)
            
            # Get the path record ID
            path_record_id = self.get_path_record_id(path['path_number'])
            if not path_record_id:
                logging.error(f"Cannot log weather data: No path record found for path {path['path_number']}")
                return
            
            # Create the log entry with proper field mappings
            log_data = {
                'ChanceOfRain': str(weather_data['chance_of_rain']),
                'CurrentPrecipitation': str(weather_data['precip_mm']),
                'CurrentTemperature': str(weather_data['temp_c']),
                'CurrentWindSpeed': str(weather_data['wind_kph']),
                'Conditions': weather_data['text'],
                'CurrentVisibility': str(weather_data['vis_km']),
                'CurrentUVIndex': str(weather_data['uv']),
                'Timestamp': weather_data['timestamp'],
                'PathRecord': [path_record_id]  # Link to the path record
            }
            
            # Create the record in Airtable
            created_record = weather_logs_table.create(log_data)
            logging.info(f"Weather data logged to Airtable for path {path['path_number']} - Record ID: {created_record['id']}")
            
        except Exception as e:
            logging.error(f"Error logging to Airtable: {e}")
            logging.error(f"Failed log data: {json.dumps(log_data)}")

    def monitor_weather(self):
        """Main monitoring loop."""
        while True:
            try:
                logging.info("Starting weather check cycle...")
                paths = self.get_all_paths()
                
                for path in paths:
                    path_number = path['path_number']
                    logging.info(f"Processing path {path_number}: {path['name']}")
                    
                    weather_data = self.fetch_weather_data(path)
                    
                    if weather_data:
                        # Check if we should log this data
                        should_log, reasons = self.should_log_weather(path_number, weather_data)
                        
                        if should_log:
                            logging.info(f"Logging weather for path {path_number}. Reasons: {', '.join(reasons)}")
                            # Pass reasons to log_to_airtable for notification
                            self.log_to_airtable(path, weather_data, reasons)
                        else:
                            logging.debug(f"No significant changes for path {path_number}")
                    
                    # Add a small delay between paths to avoid API rate limits
                    time.sleep(1)
                
                # Wait for 30 minutes before next check
                time.sleep(1800)  # 30 minutes in seconds
                
            except Exception as e:
                logging.error(f"Error in monitoring cycle: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying if there's an error

if __name__ == "__main__":
    logging.info("Weather monitoring service starting...")
    monitor = WeatherMonitor()
    monitor.monitor_weather() 