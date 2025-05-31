# Medvednica Path Weather Tracker

A comprehensive web application that tracks weather conditions for hiking paths on Medvednica mountain, providing real-time weather updates and AI-powered hiking recommendations.

## Features

### Weather Tracking
- Real-time weather monitoring for all hiking paths on Medvednica
- Weather data updates every 15 minutes via WeatherAPI
- Detailed weather information including:
  - Temperature and feels-like temperature
  - Wind speed and direction
  - Precipitation
  - Humidity
  - UV index
  - Visibility
  - Cloud cover
  - Snow conditions

### AI-Powered Recommendations
- Smart hiking recommendations based on current weather conditions
- Considers multiple factors including:
  - Time of day
  - Safety conditions
  - Visibility
  - Extreme weather warnings
  - Hiker comfort and safety

### User Management
- Secure login system
- User profile management
- Path tracking functionality
- Personalized weather updates

### Path Tracking System
- Users can track specific paths
- Tracked paths are saved in Airtable database
- Background script checks for significant weather changes every 30 minutes
- Automated email notifications for tracked paths when significant weather changes occur

## Technical Stack

- **Backend**: Flask (Python)
- **Weather API**: WeatherAPI.com
- **AI Integration**: Groq API
- **Database**: Airtable
- **Authentication**: Flask-Session

## Environment Variables

The application requires the following environment variables to be set in a `.env` file:

```
WEATHERAPI_KEY=your_weather_api_key
GROQ_API_KEY=your_groq_api_key
AIRTABLE_TOKEN=your_airtable_token
AIRTABLE_BASE_ID=your_airtable_base_id
AIRTABLE_TABLE_NAME=your_airtable_table_name
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/medvednica-scraper.git
cd medvednica-scraper
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
- Create a `.env` file in the root directory
- Add the required environment variables as listed above

4. Run the application:
```bash
python app.py
```

## Usage

1. Access the web interface at `http://localhost:5000`
2. Log in with your credentials
3. Browse available paths and their current weather conditions
4. Track specific paths to receive weather updates
5. View AI-powered recommendations for each path

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
