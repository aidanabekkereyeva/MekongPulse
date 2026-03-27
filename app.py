from flask import Flask, render_template, request, jsonify
import json
from visualization import generate_single_category_single_station_visualizations
from visualization import generate_multiple_categories_single_station_visualizations 
from visualization import generate_single_category_multiple_stations_visualizations
from visualization import generate_multiple_categories_multiple_stations_visualizations
from visualization import generate_year_over_year_comparison_visualizations
from visualization import generate_annual_monthly_totals_visualizations
from visualization import generate_visualizations_with_summary

app = Flask(__name__)

# Route to render the main index.html page 
@app.route('/')
def index(): 
    return render_template('index.html')

# Route to serve the GeoJSON file for the Mekong Basin map
@app.route('/mekong_geojson')
def mekong_geojson():
    try: 
        with open('data/Mekong_Setup/geojson/mekong_basin.geojson') as f:  # Make sure this path is correct
            geojson_data = json.load(f)
        return jsonify(geojson_data)  # Send the GeoJSON as a JSON response
    except FileNotFoundError:
        print("GeoJSON file not found.")
        return jsonify({"error": "GeoJSON file not found"}), 404

# Route to generate visualizations
@app.route('/generate_visualization', methods=['POST'])
def generate_visualization():
    try:
        selected_visualizations = request.json
        print("Received visualizations data:", selected_visualizations)

        all_charts = []
        latest_summary = None
        latest_ranking = []

        for visualization in selected_visualizations:
            graph_type = visualization.get('graph_type')
            selected_data = visualization.get('data')

            if not graph_type or not selected_data:
                print("Missing graph_type or data in visualization:", visualization)
                continue

            result = generate_visualizations_with_summary(graph_type, selected_data)
            all_charts.extend(result["charts"])
            latest_summary = result["summary"]
            latest_ranking = result.get("ranking", [])

        return jsonify({
            'charts': all_charts,
            'summary': latest_summary,
            'ranking': latest_ranking
        })

    except Exception as e:
        print(f"Error generating visualizations: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
