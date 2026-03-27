import pandas as pd    #used for handling structured data (like tables or spreadsheets) and provides data structures like DataFrame and Series
import glob  #used for file pattern matching and retrieving lists of file paths in directories.
import re   #used to search, match, and manipulate strings based on specific patterns
import os   #used for tasks like file and directory management (creating, deleting, navigating, etc.)
from datetime import datetime   #used to create, parse, format, and manipulate date and time data

def change_format_category_name(category_name):
  if category_name == "Discharge.Daily":
    return "Water Discharge Daily"
  if category_name == "Rainfall.Manual":
    return "Rainfall Manual"
  if category_name == "Sediment.Concentration":
    return "Sediment Concentration"
  if category_name == "Sediment.Concentration (DSMP)":
    return "Sediment Concentration (DSMP)"
  if category_name == "Total.Suspended.Solids":
    return "Total Suspended Solids"
  if category_name == "Water.Level":
    return "Water Level"

def extract_station_details(txt_content):
  station_data = {}

  station_name = re.search(r'\[(.*?)\]', txt_content).group(1).strip()
  station_code = re.search(r'_(.*?)_', txt_content).group(1).strip()
  station_country = re.search(r'Country:(.*)', content).group(1).strip()
  station_latitude = float(re.search(r'Latitude:(.*)', content).group(1).strip())
  station_longitude = float(re.search(r'Longitude:(.*)', content).group(1).strip())

  if station_name and station_code and station_country and station_latitude and station_longitude:
    station_data['Station_Name'] = station_name
    station_data['Station_Code'] = station_code
    station_data['Country'] = station_country
    station_data['Latitude'] = round(station_latitude, 3)
    station_data['Longitude'] = round(station_longitude, 3)
    return station_data
    
  return None

base_path = os.path.join(os.path.dirname(__file__), '..', '..', 'Mekong_database')
csv_name = 'station_details'
category_name_list = ['Discharge.Daily', 'Rainfall.Manual', 'Sediment.Concentration', 'Sediment.Concentration (DSMP)', 'Total.Suspended.Solids', 'Water.Level']

txt_files = glob.glob(os.path.join(base_path, 'Water.Level', '*.txt'))

summary_data = []
start_date_list = []
end_date_list = []

for category_name in category_name_list:
  txt_files = glob.glob(os.path.join(base_path, category_name, '*.txt'))
  category_name = change_format_category_name(category_name)
  for file in txt_files:
    with open(file, 'r') as f:
      content = f.read() 
      station_metadata = extract_station_details(content)
      
      if(station_metadata != None):

        existing_station = next((item for item in summary_data if item['Station_Name'] == station_metadata['Station_Name']), None)
        if existing_station:
          existing_station['Available_Categories'] += f", {category_name}"
        else: 
          summary_data.append({
            'Station_Name' : station_metadata['Station_Name'],
            'Station_Code' : station_metadata['Station_Code'],
            'Country' : station_metadata['Country'],
            'Latitude' : station_metadata['Latitude'],
            'Longitude' : station_metadata['Longitude'],
            'Available_Categories': category_name
          })
print(summary_data)

summary_df = pd.DataFrame(summary_data)
summary_df.to_csv(f'{csv_name}.csv', index = False)