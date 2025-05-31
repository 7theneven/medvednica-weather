import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import urllib.parse

def clean_text(text):
    return text.strip()

def extract_distance(text):
    # Extract distance value (e.g., "6.5 km" -> 6.5)
    match = re.search(r'(\d+(?:\.\d+)?)\s*km', text)
    return float(match.group(1)) if match else None

def extract_map_coordinates(soup):
    """Extract coordinates from Google Maps iframe."""
    try:
        # Find all iframes
        iframes = soup.find_all('iframe')
        print(f"Found {len(iframes)} iframes")
        
        for iframe in iframes:
            src = iframe.get('src', '')
            print(f"Found iframe with src: {src}")
            
            if 'maps.google' in src:
                # Try to extract coordinates from the URL
                # First try ll parameter (center coordinates)
                ll_match = re.search(r'[?&]ll=([-\d.]+),([-\d.]+)', src)
                if ll_match:
                    lat = float(ll_match.group(1))
                    lng = float(ll_match.group(2))
                    print(f"Found coordinates from ll parameter: {lat}, {lng}")
                    return lat, lng
                
                # Try to get mid (map ID) parameter
                mid_match = re.search(r'[?&]msid=([\w.]+)', src)
                if mid_match:
                    map_id = mid_match.group(1)
                    print(f"Found map ID: {map_id}")
                    # You could potentially fetch the map data using the map ID
                    # but this would require additional API calls
                
                # If we have center parameter
                center_match = re.search(r'[?&]center=([-\d.]+),([-\d.]+)', src)
                if center_match:
                    lat = float(center_match.group(1))
                    lng = float(center_match.group(2))
                    print(f"Found coordinates from center parameter: {lat}, {lng}")
                    return lat, lng
                    
        print("No coordinates found in any iframe")
        return None, None
    except Exception as e:
        print(f"Error extracting coordinates: {e}")
        return None, None

def scrape_path_details(url):
    """Scrape details from individual path page."""
    try:
        print(f"\nFetching page: {url}")
        
        # Add delay to be nice to the server
        time.sleep(1)
        
        response = requests.get(url)
        response.raise_for_status()
        
        print("Page fetched successfully")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract coordinates
        latitude, longitude = extract_map_coordinates(soup)
        
        if latitude and longitude:
            print(f"Successfully extracted coordinates: {latitude}, {longitude}")
        else:
            print("No coordinates found on page")
            
        return {
            'latitude': latitude,
            'longitude': longitude
        }
    except requests.RequestException as e:
        print(f"Error fetching path page {url}: {e}")
        return {'latitude': None, 'longitude': None}
    except Exception as e:
        print(f"Error processing path page {url}: {e}")
        return {'latitude': None, 'longitude': None}

def scrape_hiking_paths():
    # URL of the main page with hiking paths
    url = "http://www.medvednica.info/p/planinarske-staze.html"
    
    try:
        # Send GET request to the URL
        response = requests.get(url)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the table with hiking paths
        paths_data = []
        
        # Find all table rows (each row contains a hiking path)
        rows = soup.find_all('tr')
        
        # Process all paths
        for row in rows:
            # Find the link element which contains path number and name
            link = row.find('a')
            if not link:
                continue
                
            # Extract cells (columns) from the row
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
            
            # Extract path information
            path_text = link.text
            path_url = link.get('href')
            
            # Extract path number and name
            path_match = re.match(r'(\d+)\s*-\s*(.+)', path_text)
            if not path_match:
                continue
                
            path_number = int(path_match.group(1))
            path_name = clean_text(path_match.group(2))
            
            # Extract distance and duration
            distance = clean_text(cells[1].text)
            duration = clean_text(cells[2].text)
            
            # Get path details from individual page
            print(f"\nScraping details for path {path_number}: {path_name}")
            path_details = scrape_path_details(path_url)
            
            # Store the data
            path_data = {
                'number': path_number,
                'name': path_name,
                'distance': distance,
                'duration_mins': duration,
                'url': path_url,
                'latitude': path_details['latitude'],
                'longitude': path_details['longitude']
            }
            
            print(f"Adding path data: {path_data}")
            paths_data.append(path_data)
        
        # Convert to DataFrame and sort by path number
        df = pd.DataFrame(paths_data)
        df = df.sort_values('number')
        
        # Save to CSV
        df.to_csv('medvednica_paths_with_coords.csv', index=False, encoding='utf-8')
        print(f"\nSuccessfully scraped {len(paths_data)} hiking paths!")
        print("Data saved to 'medvednica_paths_with_coords.csv'")
        
        # Print the first few rows to verify
        print("\nFirst few rows of the data:")
        print(df.head())
        
    except requests.RequestException as e:
        print(f"Error fetching the webpage: {e}")
    except Exception as e:
        print(f"Error occurred: {e}")
        raise  # Re-raise the exception to see the full traceback

if __name__ == "__main__":
    scrape_hiking_paths() 