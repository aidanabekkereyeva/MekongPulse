from dotenv import load_dotenv
load_dotenv(override=True)

from flask import Flask, render_template, request, jsonify, Response
import json
import os
import pandas as pd
import re

import visualization
from data_loader import DataRepository
from visualization import generate_visualizations_with_summary
from services.analysis_ai import _gemini_generate, gemini_available, gemini_generate_safe
from services import ml_prediction_service
from services import seasonal_service

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
ml_prediction_service.repo = _repo
seasonal_service.repo = _repo
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


def _safe_download_name(value: str) -> str:
    value = str(value or "").strip().replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9._-]+", "", value)
    return value or "export"


@app.route('/export_station_data', methods=['POST'])
def export_station_data():
    try:
        data = request.json or {}
        station = data['station_name']
        category = data['category_name']
        start = pd.to_datetime(data['start_date'], dayfirst=True).strftime('%Y-%m-%d')
        end = pd.to_datetime(data['end_date'], dayfirst=True).strftime('%Y-%m-%d')

        df = visualization.get_feature_series_df(category, station, data['start_date'], data['end_date'])
        if df is None or df.empty:
            return jsonify({'error': 'No filtered data available for this export request.'}), 404

        export_df = df.copy()
        export_df['Timestamp'] = pd.to_datetime(export_df['Timestamp']).dt.strftime('%Y-%m-%d')
        export_df = export_df[['Timestamp', 'Station', 'Feature', 'Value', 'Unit', 'Imputed']]

        csv_body = export_df.to_csv(index=False)
        filename = (
            f"{_safe_download_name(station)}_"
            f"{_safe_download_name(category)}_"
            f"{start}_to_{end}.csv"
        )

        return Response(
            csv_body,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        print(f"Error exporting station data: {e}")
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
        include_analysis = bool(data.get('include_analysis', False))
        model_key = data.get('model', 'holt_winters')
        fn = MODEL_DISPATCH.get(model_key, visualization.generate_holt_winters_prediction)
        result = fn(
            category_name=data['category_name'],
            station_name=data['station_name'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            forecast_months=int(data.get('forecast_months', 12)),
        )
        info = result.get('model_info', {})
        result['analysis'] = None
        result['analysis_source'] = None
        if include_analysis:
            analysis, source = _generate_prediction_analysis(
                station=data['station_name'],
                category=data['category_name'],
                model=info.get('model_type', 'Holt-Winters'),
                horizon=info.get('forecast_months', data.get('forecast_months', 12)),
                rmse=info.get('rmse', 'n/a'),
                mape=info.get('mape', 'n/a'),
                last_historical=info.get('last_historical', '--'),
                forecast_end=info.get('forecast_end', '--'),
                source_type='statistical',
                extra_info={
                    'aic': info.get('aic'),
                    'alpha': info.get('alpha'),
                    'beta': info.get('beta'),
                    'gamma': info.get('gamma'),
                },
            )
            result['analysis'] = analysis
            result['analysis_source'] = source
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/ml_stations')
def ml_stations():
    return jsonify(ml_prediction_service.build_ml_station_map())


def _build_prediction_fallback_analysis(station, category, model, horizon, rmse, mape,
                                         last_historical, forecast_end, source_type,
                                         extra_info=None):
    """Structured prediction analysis report used when Gemini is unavailable."""
    extra_info = extra_info or {}

    rmse_str = str(rmse) if rmse not in (None, 'n/a', '--') else 'n/a'
    mape_str = str(mape) if mape not in (None, 'n/a', '--') else 'n/a'

    try:
        mape_f = float(str(mape_str).replace('%', ''))
        conf = 'high' if mape_f < 10 else 'moderate' if mape_f < 20 else 'low'
        conf_sent = (
            f'A MAPE of {mape_str} places this forecast in the '
            f'{"strong" if conf == "high" else "moderate" if conf == "moderate" else "weak"} '
            f'accuracy band, indicating {conf} confidence in point estimates.'
        )
    except (ValueError, TypeError):
        conf = 'indeterminate'
        conf_sent = 'Model accuracy metrics are not available for this station-feature combination.'

    if source_type == 'trained_model':
        model_desc = (
            f'{model} is a pre-trained deep learning model evaluated on rolling historical windows '
            f'across this station. It operates on daily resolution and produces forecasts '
            f'up to {horizon} days ahead without requiring manual parameter tuning.'
        )
    else:
        model_desc = (
            f'Holt-Winters triple exponential smoothing decomposes the time series into level, '
            f'trend, and seasonal components. It is well-suited to data with regular seasonal cycles '
            f'such as those driven by the Mekong monsoon regime.'
        )

    aic_line = ''
    if extra_info.get('aic'):
        aic_line = f' The Akaike Information Criterion (AIC = {extra_info["aic"]}) provides a relative measure of model fit penalised for complexity.'

    report = f"""Model Overview:
{model_desc} The forecast spans from {last_historical} to {forecast_end}, covering a {horizon}-{'day' if source_type == 'trained_model' else 'month'} horizon for {category} at {station}.

Performance Assessment:
RMSE = {rmse_str} and MAPE = {mape_str} quantify the average magnitude of prediction errors on held-out historical data. {conf_sent}{aic_line} These metrics are derived from rolling backtesting windows and reflect out-of-sample generalisation rather than in-sample fit.

Forecast Interpretation:
The {model} forecast for {category} at {station} should be interpreted as a probabilistic projection based on learned historical patterns. The Mekong basin exhibits strong seasonal cyclicity driven by the South Asian monsoon; forecasts that fall within the expected seasonal envelope carry higher reliability than those projecting anomalous departures. Confidence intervals, where shown, represent 1.96σ propagated residual uncertainty.

Operational Considerations:
This forecast is intended as a decision-support tool for research and planning purposes. It does not account for real-time upstream events, dam operation changes, or extreme meteorological anomalies outside the training distribution. For high-stakes operational use, model output should be cross-referenced with field observations and ensemble forecasts from hydrometeorological services.

Research Recommendations:
Future work should evaluate model performance disaggregated by season, as error characteristics may differ substantially between wet and dry periods in the Mekong basin. Incorporating upstream discharge data and remote sensing precipitation products as exogenous inputs may improve forecast skill, particularly at longer horizons where auto-regressive skill degrades."""

    return report


def _generate_prediction_analysis(station, category, model, horizon, rmse, mape,
                                   last_historical, forecast_end, source_type, extra_info=None):
    """Try Gemini; fall back to structured static report on any failure."""
    extra_info = extra_info or {}
    api_key = os.getenv('GEMINI_API_KEY', '').strip()

    horizon_unit = 'days' if source_type == 'trained_model' else 'months'
    aic_part = f' | AIC={extra_info.get("aic", "n/a")}' if extra_info.get('aic') else ''
    alpha_part = (
        f' | α={extra_info.get("alpha", "n/a")} β={extra_info.get("beta", "n/a")}'
        + (f' γ={extra_info.get("gamma")}' if extra_info.get('gamma') else '')
        if extra_info.get('alpha') else ''
    )

    prompt = f"""Mekong basin hydrological forecasting analyst. Write a structured forecast report using these section headers on their own line followed by a colon. No markdown symbols.

Data: {model} | {station} | {category} | horizon={horizon} {horizon_unit} | {last_historical} → {forecast_end} | RMSE={rmse} | MAPE={mape}{aic_part}{alpha_part}

Sections to write (2-3 sentences each):

Model Overview:
Performance Assessment:
Forecast Interpretation:
Operational Considerations:
Research Recommendations:

Academic language. Only use the numbers provided."""

    result = gemini_generate_safe(api_key, prompt)
    if result is not None:
        print('[AI] Prediction analysis from Gemini.')
        return result, 'gemini'

    print('[AI] Using fallback prediction analysis.')
    return _build_prediction_fallback_analysis(
        station, category, model, horizon, rmse, mape,
        last_historical, forecast_end, source_type, extra_info
    ), 'fallback'


@app.route('/generate_ml_prediction', methods=['POST'])
def generate_ml_prediction():
    import traceback
    try:
        data = request.json
        include_analysis = bool(data.get('include_analysis', False))
        result = ml_prediction_service.generate_ml_prediction(
            category_name=data['category_name'],
            station_name=data['station_name'],
            model=data.get('model', 'FlowNet'),
            horizon=int(data.get('horizon_days', 14)),
        )
        info = result['model_info']
        result['analysis'] = None
        result['analysis_source'] = None
        if include_analysis:
            analysis, source = _generate_prediction_analysis(
                station=data['station_name'],
                category=data['category_name'],
                model=info['model'],
                horizon=info['horizon_days'],
                rmse=info['rmse'],
                mape=info['mape'],
                last_historical=info['last_historical'],
                forecast_end=info['forecast_end'],
                source_type='trained_model',
            )
            result['analysis'] = analysis
            result['analysis_source'] = source
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/compare_models', methods=['POST'])
def compare_models():
    import traceback
    try:
        data = request.json
        result = ml_prediction_service.generate_model_comparison(
            category_name=data['category_name'],
            station_name=data['station_name'],
            horizon=int(data.get('horizon_days', 14)),
        )
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def _build_fallback_analysis(station, category, graph_type, first_year, last_year,
                              record_count, coverage_pct, mean_val, min_val, max_val,
                              std_val, trend, ranking_text=""):
    """
    Generate a structured data-driven analysis report without Gemini.
    Uses actual data values so the report is still meaningful and specific.
    """
    try:
        cov = float(str(coverage_pct).replace('%', ''))
        cov_quality = "high" if cov >= 80 else "moderate" if cov >= 50 else "limited"
        cov_confidence = "reliable" if cov >= 80 else "adequate" if cov >= 50 else "constrained"
    except (ValueError, TypeError):
        cov_quality = "variable"
        cov_confidence = "variable"

    trend_str = str(trend).lower()
    if "increas" in trend_str or "upward" in trend_str or "rising" in trend_str:
        trend_interp = (f"An increasing trend in {category} has been identified at {station}, "
                        "suggesting progressive changes in basin hydrology that may reflect "
                        "upstream land-use modification, altered precipitation patterns, or "
                        "long-term climatic shifts within the Mekong watershed.")
    elif "decreas" in trend_str or "downward" in trend_str or "falling" in trend_str:
        trend_interp = (f"A decreasing trend in {category} has been observed at {station}, "
                        "which may indicate reduced upstream contributions, increased abstractions, "
                        "or shifts in monsoon intensity affecting hydrological fluxes in this reach.")
    else:
        trend_interp = (f"No statistically dominant directional trend was detected for {category} "
                        f"at {station} across the observation period, suggesting relative stationarity "
                        "in the hydrological signal, though inter-annual variability remains present.")

    ranking_section = ""
    if ranking_text:
        ranking_section = (
            f"\n\nComparative Station Analysis:\n"
            f"Cross-station comparison reveals the following mean values across monitored sites: "
            f"{ranking_text}. This ranking contextualises {station} within the broader Mekong "
            f"monitoring network, highlighting spatial gradients in {category} that reflect "
            f"differences in catchment area, tributary contributions, and local geomorphological conditions. "
            f"Stations with elevated mean values may be subject to greater upstream discharge volumes "
            f"or sediment loading, warranting targeted comparative investigation."
        )

    report = f"""Data Quality and Coverage Assessment:
The dataset for {station} ({category}) spans {first_year} to {last_year}, comprising {record_count} recorded observations with {coverage_pct}% temporal coverage. This {cov_quality} data coverage indicates {cov_confidence} analytical confidence for trend detection and statistical inference within this monitoring period. Gaps in the observational record, if present, may introduce uncertainty into derived statistics and should be considered when interpreting temporal patterns.

Statistical Overview and Interpretation:
Across the full observation period, {category} at {station} recorded a mean value of {mean_val}, with values ranging from a minimum of {min_val} to a maximum of {max_val} and a standard deviation of {std_val}. The observed range reflects the dynamic hydrological regime characteristic of the Mekong basin, which is strongly governed by the seasonal monsoon cycle and upstream snowmelt contributions from the Tibetan Plateau. The standard deviation value of {std_val} quantifies the degree of dispersion around the mean, providing insight into the variability structure of this hydrological variable.

Trend Analysis and Temporal Patterns:
{trend_interp} Seasonal cyclicity is expected given the Mekong's pronounced wet-dry season alternation, and multi-year oscillations may correspond to large-scale climate drivers such as the El Niño–Southern Oscillation (ENSO) and the Indian Ocean Dipole. Continued monitoring is essential to distinguish anthropogenic signals from natural climate variability in this data record.{ranking_section}

Key Findings and Anomalies:
The observed range of {min_val} to {max_val} at {station} represents substantial hydrological variability that merits attention in both operational water management and academic research contexts. Extreme values at either bound may correspond to anomalous flood or drought events, and cross-referencing with regional rainfall records and upstream dam operation schedules is recommended to contextualise these observations. The {coverage_pct}% data coverage over {first_year}–{last_year} provides a {cov_quality}-quality baseline for future change detection studies.

Research Recommendations:
Future research should prioritise gap-filling of missing observations using interpolation or remote-sensing-derived proxies to improve the temporal completeness of this station record. Multivariate analysis incorporating concurrent rainfall, temperature, and land-cover change data would strengthen the mechanistic understanding of the observed {category} dynamics at {station}. Regional comparison across the Mekong monitoring network, particularly under projected climate change scenarios, would further elucidate the drivers and trajectories of hydrological change in this internationally significant river basin."""

    return report


@app.route('/analyze_with_ai', methods=['POST'])
def analyze_with_ai():
    try:
        data = request.json
        summary = data.get('summary', {})
        graph_type = data.get('graph_type', 'Unknown')
        stations = data.get('stations', [])
        categories = data.get('categories', [])
        ranking = data.get('ranking', [])

        station      = summary.get('station_name', ', '.join(stations) if stations else 'Unknown')
        category     = summary.get('category_name', ', '.join(categories) if categories else 'Unknown')
        mean_val     = summary.get('mean', '--')
        min_val      = summary.get('min', '--')
        max_val      = summary.get('max', '--')
        std_val      = summary.get('std', '--')
        trend        = summary.get('trend', '--')
        first_year   = summary.get('first_year', '--')
        last_year    = summary.get('last_year', '--')
        record_count = summary.get('record_count', '--')
        coverage_pct = summary.get('coverage_pct', '--')

        ranking_text = ""
        if ranking:
            ranking_text = ", ".join(
                f"{r.get('station_name','?')}={r.get('mean','?')}"
                for r in ranking[:5]
            )

        # --- Attempt Gemini ---
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        gemini_result = None

        if gemini_available():
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

            gemini_result = gemini_generate_safe(api_key, prompt)
        else:
            print("[AI] Gemini API key not configured — using fallback analysis.")

        # --- Return Gemini result or fallback ---
        if gemini_result is not None:
            return jsonify({'analysis': gemini_result, 'source': 'gemini'})

        print("[AI] Serving pre-plan fallback analysis.")
        fallback = _build_fallback_analysis(
            station, category, graph_type, first_year, last_year,
            record_count, coverage_pct, mean_val, min_val, max_val,
            std_val, trend, ranking_text,
        )
        return jsonify({'analysis': fallback, 'source': 'fallback'})

    except Exception as e:
        print(f"[AI] Unexpected error in analyze_with_ai: {e}")
        return jsonify({'error': str(e)}), 500


def _build_seasonal_fallback_analysis(station, category, trend_direction, trend_strength,
                                       seasonal_strength, peak_month, trough_month,
                                       anomaly_count, seasonal_amplitude, n_obs,
                                       start_date, end_date, unit, period):
    period_label = "annual" if period == 12 else f"{period}-month"
    ts_pct = round(trend_strength * 100, 1)
    ss_pct = round(seasonal_strength * 100, 1)

    if trend_direction == "Increasing":
        trend_sent = (
            f"The trend component reveals a statistically increasing signal in {category} at {station}. "
            f"This progressive elevation may reflect upstream land-use change, altered dam operation "
            f"regimes, or a long-term climatic shift affecting hydrological fluxes in this reach."
        )
    elif trend_direction == "Decreasing":
        trend_sent = (
            f"The trend component exhibits a progressive decline in {category} at {station}, which may "
            f"indicate reduced upstream contributions, increased abstraction pressure, or a sustained "
            f"shift in monsoon intensity over the observation window."
        )
    else:
        trend_sent = (
            f"The trend component is approximately stable, suggesting {category} at {station} is "
            f"stationary in the long-term mean once seasonal cyclicity is isolated. "
            f"This stationarity may facilitate classical statistical modelling approaches."
        )

    if ss_pct >= 75:
        seas_sent = f"A seasonal strength of {ss_pct}% confirms a dominant {period_label} monsoon-driven cycle."
    elif ss_pct >= 40:
        seas_sent = f"A seasonal strength of {ss_pct}% indicates a moderate but discernible {period_label} cycle."
    else:
        seas_sent = f"A seasonal strength of only {ss_pct}% suggests a relatively weak {period_label} seasonal signal."

    report = f"""Decomposition Overview:
STL (Seasonal and Trend decomposition using Loess) was applied to {n_obs} monthly observations of {category} at {station} spanning {start_date} to {end_date}, using a {period_label} seasonal period (period={period}). The decomposition separates the original series into three additive components: a long-term trend, a repeating seasonal cycle, and an irregular residual that captures unexplained variation. The LOESS smoother used is robust to outliers, making it well-suited to hydrological data with intermittent extreme values.

Trend Component Analysis:
{trend_sent} The trend strength index of {ts_pct}% quantifies the proportion of variance attributable to the trend relative to the combined trend-residual signal. Values approaching 100% indicate a smooth, dominant directional change, while lower values suggest greater irregularity in the underlying trend.

Seasonal Component Analysis:
{seas_sent} The seasonal amplitude of {seasonal_amplitude} {unit} — the peak-to-trough swing of the extracted seasonal cycle — confirms that {peak_month} marks the seasonal maximum and {trough_month} the seasonal minimum for {category} at this station. This pattern aligns with the Mekong basin's characteristic monsoon-driven wet-dry alternation, with peak flows typically coinciding with the South Asian summer monsoon (June–October).

Residual Component and Anomalies:
The residual component captures variation unexplained by trend and seasonality. A total of {anomaly_count} monthly residuals exceed ±2 standard deviations, flagging potential anomalous events such as extreme floods, droughts, or data quality issues. Cross-referencing these anomaly months with regional rainfall records, ENSO indices, and upstream dam operation schedules is recommended to contextualise whether they represent genuine hydrological extremes or observational artefacts.

Research Recommendations:
The seasonal decomposition provides a foundation for isolating anthropogenic signals from natural variability in {category} dynamics at {station}. Future analysis should compare extracted seasonal cycles across multiple stations to detect spatial propagation of monsoon signals along the Mekong mainstem. Trend components should be evaluated against upstream dam commissioning timelines and regional land-cover change datasets to attribute observed directional shifts to specific drivers. Spectral analysis of the residual component may reveal multi-year oscillatory modes linked to ENSO and the Indian Ocean Dipole."""

    return report


def _generate_seasonal_analysis(station, category, trend_direction, trend_strength,
                                 seasonal_strength, peak_month, trough_month,
                                 anomaly_count, seasonal_amplitude, n_obs,
                                 start_date, end_date, unit, period):
    """Try Gemini; fall back to structured static report."""
    api_key = os.getenv('GEMINI_API_KEY', '').strip()
    period_label = "annual (12-month)" if period == 12 else f"{period}-month"

    prompt = f"""Mekong basin hydrological analyst. Write a structured seasonal decomposition report using these section headers on their own line followed by a colon. No markdown symbols.

Data: STL decomposition | {station} | {category} | {start_date} to {end_date} | {n_obs} monthly obs | period={period} ({period_label}) | trend={trend_direction} | trend_strength={trend_strength} | seasonal_strength={seasonal_strength} | peak_month={peak_month} | trough_month={trough_month} | seasonal_amplitude={seasonal_amplitude} {unit} | anomaly_count={anomaly_count}

Sections to write (2-3 sentences each):

Decomposition Overview:
Trend Component Analysis:
Seasonal Component Analysis:
Residual Component and Anomalies:
Research Recommendations:

Academic language. Only use the numbers provided."""

    result = gemini_generate_safe(api_key, prompt)
    if result is not None:
        print('[AI] Seasonal decomposition analysis from Gemini.')
        return result, 'gemini'

    print('[AI] Using fallback seasonal analysis.')
    return _build_seasonal_fallback_analysis(
        station, category, trend_direction, trend_strength,
        seasonal_strength, peak_month, trough_month,
        anomaly_count, seasonal_amplitude, n_obs,
        start_date, end_date, unit, period,
    ), 'fallback'


@app.route('/generate_seasonal', methods=['POST'])
def generate_seasonal():
    import traceback
    try:
        data    = request.json
        station  = data['station_name']
        category = data['category_name']
        start    = data['start_date']
        end      = data['end_date']
        period   = int(data.get('period', 12))

        result = seasonal_service.generate_stl_decomposition(
            station=station,
            category=category,
            start_date=pd.to_datetime(start, dayfirst=True).strftime('%Y-%m-%d'),
            end_date=pd.to_datetime(end, dayfirst=True).strftime('%Y-%m-%d'),
            period=period,
        )

        s = result['summary']
        analysis, source = _generate_seasonal_analysis(
            station=station,
            category=category,
            trend_direction=s['trend_direction'],
            trend_strength=s['trend_strength'],
            seasonal_strength=s['seasonal_strength'],
            peak_month=s['peak_month'],
            trough_month=s['trough_month'],
            anomaly_count=s['anomaly_count'],
            seasonal_amplitude=s['seasonal_amplitude'],
            n_obs=s['n_obs'],
            start_date=s['start_date'],
            end_date=s['end_date'],
            unit=s['unit'],
            period=s['period'],
        )
        result['analysis'] = analysis
        result['analysis_source'] = source
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/generate_correlation', methods=['POST'])
def generate_correlation():
    import traceback
    try:
        data = request.json
        result = visualization.generate_correlation_explorer(
            station_name=data['station_name'],
            category_a=data['category_a'],
            category_b=data['category_b'],
            start_date=data['start_date'],
            end_date=data['end_date'],
        )
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/generate_quality', methods=['POST'])
def generate_quality():
    import traceback
    try:
        data = request.json
        result = visualization.generate_data_quality_explorer(
            station_name=data['station_name'],
            category_name=data['category_name'],
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
        )
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/generate_station_linkage', methods=['POST'])
def generate_station_linkage():
    import traceback
    try:
        data = request.json
        result = visualization.generate_station_linkage_explorer(
            station_a=data['station_a'],
            station_b=data['station_b'],
            category_name=data['category_name'],
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
        )
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/generate_extremes', methods=['POST'])
def generate_extremes():
    import traceback
    try:
        data = request.json
        result = visualization.generate_extreme_event_explorer(
            station_name=data['station_name'],
            category_name=data['category_name'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            threshold_mode=data.get('threshold_mode', 'percentile'),
            threshold_value=float(data.get('threshold_value', 90)),
            direction=data.get('direction', 'above'),
        )
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/generate_scenario_compare', methods=['POST'])
def generate_scenario_compare():
    import traceback
    try:
        data = request.json
        result = visualization.generate_scenario_compare(
            station_name=data['station_name'],
            category_name=data['category_name'],
            start_a=data['start_a'],
            end_a=data['end_a'],
            start_b=data['start_b'],
            end_b=data['end_b'],
        )
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/generate_forecast_diagnostics', methods=['POST'])
def generate_forecast_diagnostics():
    import traceback
    try:
        data = request.json
        result = visualization.generate_forecast_diagnostics(
            category_name=data['category_name'],
            station_name=data['station_name'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            model_key=data.get('model_key', 'holt_winters'),
            horizon=int(data.get('horizon', 12)),
        )
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
