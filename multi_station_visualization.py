import glob
import pandas as pd
import plotly.express as px 
import json
import re  # For regular expressions
import plotly

# Define paths for each category
CATEGORY_PATHS = {
    'Water Level': './static/data/mekong_data/Water.Level/*.csv',
    'Discharge Daily': './static/data/mekong_data/Discharge.Daily/*.csv',
    'Sediment Concentration': './static/data/mekong_data/Sediment.Concentration/*.csv',
    'Sediment Concentration (DSMP)': './static/data/mekong_data/Sediment.Concentration(DSMP)/*.csv',
    'Total Suspended Solids': './static/data/mekong_data/Total.Suspended.Solids/*.csv',
    'Rainfall Manual': './static/data/mekong_data/Rainfall.Manual/*.csv',
}

# Function to extract station name from filename
def extract_station_name(filename):
    match = re.search(r'\[(.*?)\]', filename)
    if match:
        return match.group(1)
    return os.path.basename(filename)

# Function to generate comparison charts for multiple stations
def plot_comparison_chart(df_list, station_names, start_date, end_date, y_label, title):
    # Combine data from multiple stations
    combined_df = pd.concat(df_list, keys=station_names, names=['Station', 'Index'])
    combined_df = combined_df.reset_index(level='Station').reset_index(drop=True)

    # Filter data based on date range
    combined_df['Timestamp'] = pd.to_datetime(combined_df['Timestamp (UTC+07:00)'], utc=True)
    combined_df_filtered = combined_df[(combined_df['Timestamp'] >= pd.to_datetime(start_date).tz_localize('UTC')) &
                                       (combined_df['Timestamp'] <= pd.to_datetime(end_date).tz_localize('UTC'))]

    # Create an area plot with Plotly for comparison
    fig = px.line(combined_df_filtered,
                  x='Timestamp',
                  y='Value',
                  color='Station',
                  title=title,
                  labels={'Value': y_label},
                  template="plotly_white")

    # Customize title and axis fonts
    fig.update_layout(
        autosize=True,  # Make the chart resize based on the container
        title={
            'text': title,
            'y': 0.9,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(size=18, color='black')  # You can use percentages or default sizes
        },
        margin=dict(l=0, r=0, t=70, b=40),  # Adjust margins for dynamic scaling
        xaxis_title='Time (years)',
        yaxis_title=y_label,
        font=dict(
            family="Arial, sans-serif",
            size=12,  # General font size
            color="black"
        ),
        plot_bgcolor="white",
        hovermode="x unified",
        xaxis=dict(
            showline=True,
            showgrid=True,
            linecolor='black',
            gridcolor='LightGrey',
            tickformat="%Y"
        ),
        yaxis=dict(
            showline=True,
            showgrid=True,
            linecolor='black',
            gridcolor='LightGrey'
        )
    )

    fig.update_traces(
        mode='lines',
        line=dict(width=2),
        hovertemplate='Date: %{x|%d-%b-%Y}<br>Value: %{y}<extra></extra>'
    )

    # Convert plot to JSON
    graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return graph_json

# Function to generate multi-station visualizations
def generate_multi_station_visualizations(selectedCategories):
    charts = []

    for category in selectedCategories:
        category_name = category['categoryName']
        start_date = category['startDate']
        end_date = category['endDate']
        stations = category['stations']

        df_list = []
        station_names = []

        if category_name in CATEGORY_PATHS:
            csv_files = glob.glob(CATEGORY_PATHS[category_name])

            # Process each station
            for file in csv_files:
                station_name = extract_station_name(file)
                if station_name in stations:
                    df = pd.read_csv(file)
                    df_list.append(df)
                    station_names.append(station_name)

            if df_list:
                # Handle different categories
                if category_name == 'Water Level':
                    graph_json = plot_comparison_chart(df_list, station_names, start_date, end_date, y_label="Water Level (m)", title=f"Comparison - Water Level")
                elif category_name == 'Discharge Daily':
                    graph_json = plot_comparison_chart(df_list, station_names, start_date, end_date, y_label="Discharge (m³/s)", title=f"Comparison - Discharge Daily")
                elif category_name == 'Sediment Concentration':
                    graph_json = plot_comparison_chart(df_list, station_names, start_date, end_date, y_label="Sediment Concentration (mg/l)", title=f"Comparison - Sediment Concentration")
                elif category_name == 'Sediment Concentration (DSMP)':
                    graph_json = plot_comparison_chart(df_list, station_names, start_date, end_date, y_label="Sediment Concentration (mg/l)", title=f"Comparison - Sediment Concentration (DSMP)")
                elif category_name == 'Total Suspended Solids':
                    graph_json = plot_comparison_chart(df_list, station_names, start_date, end_date, y_label="Total Suspended Solids (mg/l)", title=f"Comparison - Total Suspended Solids")
                elif category_name == 'Rainfall Manual':
                    graph_json = plot_comparison_chart(df_list, station_names, start_date, end_date, y_label="Rainfall (mm)", title=f"Comparison - Rainfall")
                charts.append(graph_json)

    return charts