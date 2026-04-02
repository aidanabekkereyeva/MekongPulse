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


MODEL_DISPATCH = {
    "holt_winters":       visualization.generate_holt_winters_prediction,
    "sarima":             visualization.generate_sarima_prediction,
    "random_forest":      visualization.generate_random_forest_prediction,
    "gradient_boosting":  visualization.generate_gradient_boosting_prediction,
    "linear_seasonal":    visualization.generate_linear_seasonal_prediction,
    "svr":                visualization.generate_svr_prediction,
}

@app.route('/generate_prediction', methods=['POST'])
def generate_prediction():
    import traceback
    try:
        data = request.json
        model_key = data.get('model', 'holt_winters')
        fn = MODEL_DISPATCH.get(model_key, visualization.generate_holt_winters_prediction)
        result = fn(
            category_name=data['category_name'],
            station_name=data['station_name'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            forecast_months=int(data.get('forecast_months', 12)),
        )
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/analyze_with_ai', methods=['POST'])
def analyze_with_ai():
    try:
        import os
        from google import genai
        try:
            from config import GEMINI_API_KEY as api_key
        except ImportError:
            api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key or api_key == "paste-your-key-here":
            return jsonify({'error': 'Please add your Gemini API key to config.py'}), 500
        client = genai.Client(api_key=api_key)
        data = request.json
        summary = data.get('summary', {})
        graph_type = data.get('graph_type', 'Unknown')
        stations = data.get('stations', [])
        categories = data.get('categories', [])
        ranking = data.get('ranking', [])

        station = summary.get('station_name', ', '.join(stations) if stations else 'Unknown')
        category = summary.get('category_name', ', '.join(categories) if categories else 'Unknown')
        mean_val = summary.get('mean', '--')
        min_val = summary.get('min', '--')
        max_val = summary.get('max', '--')
        std_val = summary.get('std', '--')
        trend = summary.get('trend', '--')
        first_year = summary.get('first_year', '--')
        last_year = summary.get('last_year', '--')
        record_count = summary.get('record_count', '--')
        coverage_pct = summary.get('coverage_pct', '--')

        ranking_text = ""
        if ranking:
            ranking_text = ", ".join(
                f"{r.get('station_name','?')}={r.get('mean','?')}"
                for r in ranking[:5]
            )

        prompt = f"""Mekong basin hydrological analyst. Write a structured report using these section headers on their own line followed by a colon. No markdown symbols.

Data: {graph_type} | {station} | {category} | {first_year}-{last_year} | {record_count} records | {coverage_pct}% coverage | mean={mean_val} min={min_val} max={max_val} std={std_val} trend={trend}{f' | ranking: {ranking_text}' if ranking_text else ''}

Sections to write (2-3 sentences each):

Data Quality and Coverage Assessment:
Statistical Overview and Interpretation:
Trend Analysis and Temporal Patterns:
{f'Comparative Station Analysis:' if ranking_text else ''}
Key Findings and Anomalies:
Research Recommendations:

Academic language. Only use the numbers provided."""

        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
        )
        analysis = response.text
        return jsonify({'analysis': analysis})
    except Exception as e:
        print(f"AI analysis error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
