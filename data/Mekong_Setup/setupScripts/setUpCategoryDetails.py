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

def extract_station_name(file_name):
  match = re.search(r'\[(.*?)\]', file_name)
  if match:
      return match.group(1)
  return None 

base_path = os.path.join(os.path.dirname(__file__), '..', '..', 'Mekong_database')
csv_name = 'category_details'
category_name_list = ['Discharge.Daily', 'Rainfall.Manual', 'Sediment.Concentration', 'Sediment.Concentration (DSMP)', 'Total.Suspended.Solids', 'Water.Level']
 
summary_data = []

for category_name in category_name_list:
  print(category_name)
  csv_files = glob.glob(os.path.join(base_path, category_name, '*.csv'))
  category_name = change_format_category_name(category_name)
  for file in csv_files:
    station_name = extract_station_name(file)
    if station_name != None:
      df = pd.read_csv(file)
      # Convert 'timestamp' column to datetime
      df['Timestamp (UTC+07:00)'] = pd.to_datetime(df['Timestamp (UTC+07:00)'], errors='coerce')
      # Drop rows with invalid or missing timestamps
      df.dropna(subset=['Timestamp (UTC+07:00)'], inplace=True)
      if df.empty:
        continue  # Skip if the dataframe is empty after dropping NaN
      # Get start and end date
      start_date = df['Timestamp (UTC+07:00)'].min().date()
      end_date = df['Timestamp (UTC+07:00)'].max().date()
      # Calculate length of data recorded in years
      length_of_data_years = end_date.year - start_date.year + (1 if (end_date.month, end_date.day) >= (start_date.month, start_date.day) else 0)

      summary_data.append({
        'Category_Name' : category_name,
        'Station_Name' : station_name,
        'Start_Date' : start_date,
        'End_Date' : end_date
      })
print(summary_data)

summary_df = pd.DataFrame(summary_data)
summary_df.to_csv(f'{csv_name}.csv', index = False) 