import os
from weather_monitor import WeatherMonitor
import logging
import json
from dotenv import load_dotenv
import time
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(message)s',  # Simplified format for clearer output
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_weather_monitor.log')
    ]
)

def test_environment():
    """Test if all required environment variables are set."""
    required_vars = {
        'AIRTABLE_TOKEN': os.getenv('AIRTABLE_TOKEN'),
        'WEATHERAPI_KEY': os.getenv('WEATHERAPI_KEY')
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        logging.error(f"Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    logging.debug("Environment variables check passed")
    for var in required_vars:
        token = required_vars[var]
        logging.debug(f"{var} found: {token[:4]}...{token[-4:]}")
    return True

def test_weather_api(monitor, test_coords=None):
    """Test Weather API connection with a single location."""
    if test_coords is None:
        test_coords = {
            'path_number': 'TEST',
            'name': 'Test Location',
            'latitude': 45.856662,  # Example coordinates from your data
            'longitude': 15.896358
        }
    
    logging.debug(f"Testing Weather API with coordinates: {test_coords['latitude']}, {test_coords['longitude']}")
    
    try:
        weather_data = monitor.fetch_weather_data(test_coords)
        if weather_data:
            logging.debug(f"Weather API test successful. Response: {json.dumps(weather_data, indent=2)}")
            return True
        else:
            logging.error("Weather API test failed - no data returned")
            return False
    except Exception as e:
        logging.error(f"Weather API test failed with error: {e}")
        return False

def test_airtable_logging(monitor):
    """Test Airtable weather logging."""
    try:
        # Test weather logs table access
        logging.debug("Testing Airtable weather logs table access...")
        weather_logs_table = monitor.airtable.table(monitor.base_id, monitor.weather_logs_table_id)
        paths_table = monitor.airtable.table(monitor.base_id, monitor.paths_table_id)
        
        # Test paths table access
        logging.debug("Testing Airtable paths table access...")
        test_path_records = paths_table.all(max_records=1)
        if not test_path_records:
            logging.error("No path records found in paths table")
            return False
            
        # Test weather logs table access
        test_records = weather_logs_table.all(max_records=1)
        logging.debug("Successfully accessed both tables")
        return True
    except Exception as e:
        logging.error(f"Airtable logging test failed: {e}")
        return False

def test_path_record_lookup(monitor, path_number):
    """Test path record ID lookup and weather record retrieval."""
    try:
        # Test getting path record ID for writing
        record_id = monitor.get_path_record_id(path_number)
        if record_id:
            logging.info(f"Found path record ID for path {path_number}: {record_id}")
            
            # Try to get latest weather record using PathNumberLookup
            latest = monitor.get_latest_weather_record(path_number)
            if latest:
                logging.info(f"Found previous weather record from {latest['timestamp']}")
                logging.debug(f"Weather data: {json.dumps(latest, indent=2)}")
            else:
                logging.info("No previous weather records found")
                
            return True
        else:
            logging.error(f"Could not find record ID for path {path_number}")
            return False
    except Exception as e:
        logging.error(f"Path record lookup test failed: {e}")
        return False

def test_csv_reading(monitor):
    """Test reading paths from CSV file."""
    try:
        logging.info("Testing CSV path reading...")
        paths = monitor.get_all_paths()
        logging.info(f"Successfully read {len(paths)} paths from CSV")
        if paths:
            sample_path = paths[0]
            logging.debug(f"Sample path data: {json.dumps(sample_path, indent=2)}")
        return bool(paths)
    except Exception as e:
        logging.error(f"CSV reading test failed: {e}")
        return False

def test_single_cycle():
    """Test a single cycle of weather monitoring to establish baseline data."""
    try:
        logging.info("=== Starting Baseline Data Collection ===")
        
        # Create monitor instance
        monitor = WeatherMonitor()
        
        # Test 1: Environment Variables
        logging.info("1. Testing environment variables...")
        if not test_environment():
            return
        
        # Test 2: CSV Reading
        logging.info("2. Testing CSV path reading...")
        if not test_csv_reading(monitor):
            return
        
        # Test 3: Weather API
        logging.info("3. Testing Weather API...")
        if not test_weather_api(monitor):
            return
        
        # Test 4: Airtable Logging
        logging.info("4. Testing Airtable logging...")
        if not test_airtable_logging(monitor):
            return
        
        # Test 5: Initial Data Collection
        logging.info("5. Collecting baseline weather data for all paths...")
        
        # Get all paths
        paths = monitor.get_all_paths()
        logging.info(f"Found {len(paths)} paths in CSV")
        
        # Clear any existing cached data to ensure fresh baseline
        monitor.last_weather_data = {}
        monitor.last_log_time = {}
        
        # Process each path
        successful_logs = 0
        failed_logs = 0
        
        for path in paths:
            try:
                logging.info(f"Processing path {path['path_number']}: {path['name']}")
                
                weather_data = monitor.fetch_weather_data(path)
                
                if weather_data:
                    # Force logging by treating as initial data
                    monitor.log_to_airtable(path, weather_data)
                    successful_logs += 1
                    logging.info(f"Successfully logged baseline data for path {path['path_number']}")
                else:
                    failed_logs += 1
                    logging.error(f"Failed to fetch weather data for path {path['path_number']}")
                
                # Small delay to avoid hitting API rate limits
                time.sleep(1)
                
            except Exception as e:
                failed_logs += 1
                logging.error(f"Error processing path {path['path_number']}: {str(e)}")
        
        logging.info("=== Baseline Data Collection Complete ===")
        logging.info(f"Successfully logged data for {successful_logs} paths")
        if failed_logs > 0:
            logging.warning(f"Failed to log data for {failed_logs} paths")
        
    except Exception as e:
        logging.error(f"Error in baseline data collection: {str(e)}", exc_info=True)

def test_comparison_cycle():
    """Test a single weather monitoring cycle to verify comparison logic."""
    try:
        logging.info("=== Starting Comparison Test Cycle ===")
        
        # Create monitor instance
        monitor = WeatherMonitor()
        
        # Test 1: Environment Variables
        logging.info("1. Testing environment variables...")
        if not test_environment():
            return
        
        # Test 2: CSV Reading
        logging.info("2. Testing CSV path reading...")
        if not test_csv_reading(monitor):
            return
        
        # Test 3: Weather API
        logging.info("3. Testing Weather API...")
        if not test_weather_api(monitor):
            return
        
        # Test 4: Airtable Logging
        logging.info("4. Testing Airtable logging...")
        if not test_airtable_logging(monitor):
            return
            
        # Test 5: Path Record Lookup
        logging.info("5. Testing path record lookup...")
        # Test with first path from CSV
        paths = monitor.get_all_paths()
        if paths:
            if not test_path_record_lookup(monitor, paths[0]['path_number']):
                return
        
        # Test 6: Run Comparison Cycle
        logging.info("6. Running comparison cycle...")
        
        # Get all paths
        logging.info(f"Found {len(paths)} paths in CSV")
        
        # Process each path
        updates_needed = 0
        no_changes = 0
        
        for path in paths:
            try:
                logging.info(f"\nProcessing path {path['path_number']}: {path['name']}")
                
                # Verify path record exists
                path_record_id = monitor.get_path_record_id(path['path_number'])
                if not path_record_id:
                    logging.error(f"Skipping path {path['path_number']}: No matching record in Airtable")
                    continue
                
                # Get latest record first
                latest = monitor.get_latest_weather_record(path['path_number'])
                if latest:
                    logging.info(f"Latest record found from: {latest['timestamp']}")
                    logging.info(f"Current conditions: {latest['text']}, {latest['temp_c']}°C, {latest['wind_kph']} kph")
                
                # Get current weather
                weather_data = monitor.fetch_weather_data(path)
                
                if weather_data:
                    # Log current weather data for comparison
                    logging.info(f"New weather data: {weather_data['text']}, {weather_data['temp_c']}°C, {weather_data['wind_kph']} kph")
                    
                    # Check if we should log this data
                    should_log, reasons = monitor.should_log_weather(path['path_number'], weather_data)
                    
                    if should_log:
                        updates_needed += 1
                        logging.info(f"Update needed for path {path['path_number']}. Reasons: {', '.join(reasons)}")
                        monitor.log_to_airtable(path, weather_data)
                    else:
                        no_changes += 1
                        logging.info(f"No significant changes for path {path['path_number']}")
                
                # Small delay between paths to avoid API rate limits
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"Error processing path {path['path_number']}: {str(e)}")
        
        logging.info("\n=== Comparison Test Cycle Complete ===")
        logging.info(f"Paths needing updates: {updates_needed}")
        logging.info(f"Paths with no significant changes: {no_changes}")
        
    except Exception as e:
        logging.error(f"Error in comparison test cycle: {str(e)}", exc_info=True)

def test_webhook_notification(monitor):
    """Test webhook notification with simulated severe weather."""
    try:
        logging.info("Testing webhook notification...")
        
        # Create test path
        test_path = {
            'path_number': 'TEST',
            'name': 'Test Path',
            'latitude': 45.856662,
            'longitude': 15.896358
        }
        
        # Simulate severe weather data
        severe_weather = {
            'temp_c': 25.0,
            'wind_kph': 45.0,  # Above 40 kph threshold
            'precip_mm': 10.0,  # Above 5mm threshold
            'chance_of_rain': 80,
            'text': 'Thunderstorm',  # Severe condition
            'vis_km': 2.0,  # Below 3km threshold
            'uv': 9.0,  # Above 8 threshold
            'timestamp': datetime.now().isoformat()
        }
        
        # Test notification
        reasons = ["High wind speed: 45.0 kph", "Severe weather condition: Thunderstorm", "Low visibility: 2.0 km", "Very high UV index: 9.0"]
        monitor.notify_weather_change(test_path, severe_weather, reasons)
        
        logging.info("Webhook test completed")
        return True
        
    except Exception as e:
        logging.error(f"Webhook test failed: {e}")
        return False

def test_webhook_at_different_times(monitor):
    """Test webhook notifications at different times of day."""
    logging.info("\n=== Testing Webhook at Different Times ===")
    
    # Store original method
    original_is_daytime = monitor.is_daytime_cet
    
    try:
        # Test at 8 PM (20:00) - Should NOT send notification
        def mock_nighttime():
            return False  # Simulates 20:00 CET
        
        monitor.is_daytime_cet = mock_nighttime
        logging.info("\nTesting notification at 20:00 CET (should be skipped):")
        test_webhook_notification(monitor)
        
        # Test at 11 AM - Should send notification
        def mock_daytime():
            return True  # Simulates 11:00 CET
        
        monitor.is_daytime_cet = mock_daytime
        logging.info("\nTesting notification at 11:00 CET (should be sent):")
        test_webhook_notification(monitor)
        
    finally:
        # Restore original method
        monitor.is_daytime_cet = original_is_daytime

def test_threshold_conditions():
    """Test weather monitoring with simulated threshold conditions for paths 21, 29, and 70."""
    try:
        print("\n=== Testing Threshold Conditions ===")
        monitor = WeatherMonitor()
        
        # Test paths with full data needed for Airtable logging
        test_paths = [
            {
                'path_number': '21',
                'name': 'Path 21',
                'latitude': 45.856662,
                'longitude': 15.896358
            },
            {
                'path_number': '29',
                'name': 'Path 29',
                'latitude': 45.857771,
                'longitude': 15.897442
            },
            {
                'path_number': '70',
                'name': 'Path 70',
                'latitude': 45.917250,  # Example coordinates for path 70
                'longitude': 15.968333
            }
        ]
        
        # Test conditions
        test_conditions = [
            {
                'path': '21',
                'condition': {
                    'temp_c': 25.0,
                    'wind_kph': 45.0,  # Above 40 kph threshold
                    'precip_mm': 2.0,
                    'chance_of_rain': 85,  # High chance of rain
                    'text': 'Strong winds',
                    'vis_km': 8.0,
                    'uv': 5.0,
                    'timestamp': datetime.now().isoformat()
                }
            },
            {
                'path': '29',
                'condition': {
                    'temp_c': 22.0,
                    'wind_kph': 30.0,
                    'precip_mm': 12.0,  # Increased from 8.0
                    'chance_of_rain': 95,  # Increased from 90
                    'text': 'Severe Thunderstorm',  # Changed from Thunderstorm
                    'vis_km': 1.0,  # Decreased from 2.0
                    'uv': 10.0,  # Increased from 9.0
                    'timestamp': datetime.now().isoformat()
                }
            },
            {
                'path': '70',
                'condition': {
                    'temp_c': 18.0,
                    'wind_kph': 55.0,  # Severe wind conditions
                    'precip_mm': 15.0,  # Heavy precipitation
                    'chance_of_rain': 100,  # Maximum chance of rain
                    'text': 'Heavy rain with storm',  # Severe condition
                    'vis_km': 0.5,  # Very low visibility
                    'uv': 11.0,  # Extreme UV index
                    'timestamp': datetime.now().isoformat()
                }
            }
        ]
        
        # Process each path
        for test_path in test_paths:
            path_number = test_path['path_number']
            print(f"\nProcessing path {path_number}")
            print("-" * 50)
            
            # Find matching test condition
            test_condition = next(tc['condition'] for tc in test_conditions if tc['path'] == path_number)
            
            # Get the latest record to compare against
            latest = monitor.get_latest_weather_record(path_number)
            if latest:
                print(f"Found previous record from {latest['timestamp']}")
                print(f"Previous conditions: {latest['text']}")
            else:
                print("No previous record found")
            
            # Check if we should log this data
            should_log, reasons = monitor.should_log_weather(path_number, test_condition)
            
            print(f"\nNew conditions for path {path_number}:")
            print(f"Weather: {test_condition['text']}")
            print(f"Wind: {test_condition['wind_kph']} kph")
            print(f"Precipitation: {test_condition['precip_mm']} mm")
            print(f"Rain chance: {test_condition['chance_of_rain']}%")
            print(f"Visibility: {test_condition['vis_km']} km")
            print(f"UV Index: {test_condition['uv']}")
            
            if should_log:
                print("\nLogging to Airtable because:")
                for reason in reasons:
                    print(f"✓ {reason}")
                    
                # Log to Airtable
                monitor.log_to_airtable(test_path, test_condition)
                print("Successfully logged to Airtable")
            else:
                print("\nNo significant changes, skipping Airtable log")
            
    except Exception as e:
        logging.error(f"Error in threshold test: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        logging.info("=== Starting Weather Monitor Tests ===")
        test_threshold_conditions()
        
    except Exception as e:
        logging.error(f"Test suite failed: {e}", exc_info=True) 