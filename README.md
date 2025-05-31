# Medvednica Hiking Paths Scraper

This script scrapes hiking path information from the Medvednica.info blog and saves it to a CSV file.

## Features

- Scrapes all hiking paths from http://www.medvednica.info/p/planinarske-staze.html
- Extracts path number, name, distance, duration, and URL
- Saves data to a CSV file

## Requirements

- Python 3.7+
- Required packages listed in `requirements.txt`

## Installation

1. Clone this repository or download the files
2. Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage

Simply run the script:

```bash
python scrape_medvednica.py
```

The script will create a file named `medvednica_paths.csv` containing all the hiking path data.

## Output Format

The CSV file will contain the following columns:
- number: Path number
- name: Path name
- distance: Distance in kilometers
- duration_mins: Duration in minutes
- url: URL to the detailed path description

## Error Handling

The script includes error handling for:
- Network connection issues
- Invalid webpage structure
- Data parsing errors 