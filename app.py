from flask import Flask, render_template, request, jsonify
import json
import os
import pandas as pd

import visualization
from data_loader import DataRepository
from visualization import generate_visualizations_with_summary

app = Flask(__name__)

# ------------------------------
# FEATURE KEY → DISPLAY NAME
# ------------------------------
FEATURE_DISPLAY_NAMES = {
    "Water_Level": "Water Level",
    "Discharge": "Discharge",
    "Total_Suspended_Solids": "Total Suspended Solids",
    "Rainfall": "Rainfall",
}


def feature_to_display(feature_key: str) -> str:
    return FEATURE_DISPLAY_NAMES.get(feature_key, feature_key)


# ------------------------------
# GENERATE FRONTEND CSVs FROM SCHEMA
# ------------------------------
def generate_static_csvs(repo: DataRepository) -> None:
    os.makedirs("static/data-outputs", exist_ok=True)

    # station_details.csv
    station_rows = []
    for station_name, meta in repo.station_index.items():
        display_categories = ", ".join(
            feature_to_display(f) for f in meta.get("features", [])
        )
        station_rows.append({
            "Station_Name": station_name.replace("_", " "),
            "Station_Code": station_name,
            "Country": meta.get("country", ""),
            "Latitude": meta.get("lat", ""),
            "Longitude": meta.get("lon", ""),
            "Available_Categories": display_categories,
        })
    pd.DataFrame(station_rows).to_csv("static/data-outputs/station_details.csv", index=False)
    print(f"[startup] station_details.csv written ({len(station_rows)} stations)")

    # category_details.csv
    category_rows = []
    for station_name, meta in repo.station_index.items():
        for feature_key, detail in meta.get("feature_details", {}).items():
            category_rows.append({
                "Category_Name": feature_to_display(feature_key),
                "Station_Name": station_name.replace("_", " "),
                "Start_Date": detail["start_date"],
                "End_Date": detail["end_date"],
            })
    pd.DataFrame(category_rows).to_csv("static/data-outputs/category_details.csv", index=False)
    print(f"[startup] category_details.csv written ({len(category_rows)} entries)")


# ------------------------------
# STARTUP: init DataRepository
# ------------------------------
print("[startup] Initialising DataRepository…")
_repo = DataRepository(
    dataset_dir="data/Mekong_database",
    schema_path="data/data_schema.py",
    geojson_path="data/Mekong_Setup/geojson/mekong_basin.geojson",
)
visualization.repo = _repo
generate_static_csvs(_repo)
print("[startup] Ready.")


# ------------------------------
# ROUTES
# ------------------------------
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/mekong_geojson')
def mekong_geojson():
    try:
        with open('data/Mekong_Setup/geojson/mekong_basin.geojson') as f:
            geojson_data = json.load(f)
        return jsonify(geojson_data)
    except FileNotFoundError:
        return jsonify({"error": "GeoJSON file not found"}), 404


@app.route('/generate_visualization', methods=['POST'])
def generate_visualization():
    try:
        selected_visualizations = request.json
        print("Received visualizations data:", selected_visualizations)

        all_charts = []
        latest_summary = None
        latest_ranking = []

        for viz in selected_visualizations:
            graph_type = viz.get('graph_type')
            selected_data = viz.get('data')
            if not graph_type or not selected_data:
                continue
            result = generate_visualizations_with_summary(graph_type, selected_data)
            all_charts.extend(result["charts"])
            latest_summary = result["summary"]
            latest_ranking = result.get("ranking", [])

        return jsonify({'charts': all_charts, 'summary': latest_summary, 'ranking': latest_ranking})

    except Exception as e:
        print(f"Error generating visualizations: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
