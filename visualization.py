from __future__ import annotations

import json
from typing import Optional

import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots

from data_loader import DataRepository, SeriesRequest

# Set by app.py at startup
repo: Optional[DataRepository] = None

# Maps display category name (used by frontend) → schema feature key
CATEGORY_TO_FEATURE = {
    "Water Level": "Water_Level",
    "Discharge": "Discharge",
    "Total Suspended Solids": "Total_Suspended_Solids",
    "Rainfall": "Rainfall",
}

FEATURE_DISPLAY_UNITS = {
    "Water Level": "Water Level (m)",
    "Discharge": "Discharge (m³/s)",
    "Total Suspended Solids": "Total Suspended Solids (mg/l)",
    "Rainfall": "Rainfall (mm)",
}


def get_category_units(category_name: str) -> str:
    return FEATURE_DISPLAY_UNITS.get(category_name, "Value")


def station_key(station_name: str) -> str:
    """Convert display name (spaces) to repo key (underscores)."""
    return station_name.replace(" ", "_")


def station_display(station_key_str: str) -> str:
    """Convert repo key (underscores) to display name (spaces)."""
    return station_key_str.replace("_", " ")


def get_feature_series_df(category_name: str, station_name: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Return a filtered DataFrame with Timestamp+Value columns, or None on any error.
    Accepts dates in DD-MM-YYYY or YYYY-MM-DD format. Station name may use spaces or underscores."""
    feature = CATEGORY_TO_FEATURE.get(category_name)
    if not feature or repo is None:
        return None
    try:
        start_iso = pd.to_datetime(start_date, dayfirst=True).strftime('%Y-%m-%d')
        end_iso = pd.to_datetime(end_date, dayfirst=True).strftime('%Y-%m-%d')
        request = SeriesRequest(station=station_key(station_name), feature=feature, start_date=start_iso, end_date=end_iso)
        return repo.get_feature_series(request)
    except Exception:
        return None


# ------------------------------
# LAYOUT / SHARED HELPERS
# ------------------------------

def normalize_series(series: pd.Series) -> pd.Series:
    series = pd.to_numeric(series, errors="coerce")
    min_val, max_val = series.min(), series.max()
    if pd.isna(min_val) or pd.isna(max_val) or min_val == max_val:
        return pd.Series([0.5] * len(series), index=series.index)
    return (series - min_val) / (max_val - min_val)


def apply_clean_layout(fig, title: str, yaxis_title: str = "Value", xaxis_title: str = "Date"):
    fig.update_layout(
        title={"text": title, "x": 0.5, "xanchor": "center", "font": dict(size=20, color="#1f2d3d")},
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=50, r=30, t=80, b=50),
        font=dict(family="Segoe UI, Arial, sans-serif", size=12, color="#223142"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title=xaxis_title, showline=True, linecolor="#9fb3c8", showgrid=True, gridcolor="#e7edf3", tickformat="%Y"),
        yaxis=dict(title=yaxis_title, showline=True, linecolor="#9fb3c8", showgrid=True, gridcolor="#e7edf3"),
    )
    return fig


def create_no_data_chart(title: str, message: str = "No data available for the selected range.") -> str:
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(size=16, color="#5f7082"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig = apply_clean_layout(fig, title, "", "")
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


def fig_to_json(fig) -> str:
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


# ------------------------------
# CHART 1: Single Category, Single Station Timeline
# ------------------------------

def plot_single_category_single_station_chart(df_filtered, station_name, category_name):
    chart_title = f"{category_name} Trend at {station_name}"
    fig = px.area(df_filtered, x="Timestamp", y="Value", title=chart_title, labels={"Value": get_category_units(category_name)})
    fig.update_traces(
        mode="lines",
        line=dict(width=2, color="#2f6da3"),
        fill="tozeroy",
        hovertemplate="Date: %{x|%d-%b-%Y}<br>Value: %{y:.2f}<extra></extra>",
    )
    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name))
    return fig_to_json(fig)


def generate_single_category_single_station_visualizations(selected_data):
    charts = []
    for data in selected_data:
        category_name = data["category_name"]
        station_name = data["station_name"]
        chart_title = f"{category_name} Trend at {station_name}"
        df = get_feature_series_df(category_name, station_name, data["start_date"], data["end_date"])
        if df is None or df.empty:
            charts.append(create_no_data_chart(chart_title, "No data available for the selected range."))
            continue
        charts.append(plot_single_category_single_station_chart(df, station_name, category_name))
    return charts


# ------------------------------
# CHART 2: Multiple Categories, Single Station Timeline
# ------------------------------

def plot_multiple_categories_single_station_chart(categories_data, station_name):
    colors = px.colors.qualitative.Plotly
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    any_data = False
    overall_start = None
    overall_end = None

    for i, data in enumerate(categories_data):
        category_name = data["category_name"]
        start_dt = pd.to_datetime(data["start_date"], dayfirst=True)
        end_dt = pd.to_datetime(data["end_date"], dayfirst=True)
        overall_start = start_dt if overall_start is None else min(overall_start, start_dt)
        overall_end = end_dt if overall_end is None else max(overall_end, end_dt)

        df = get_feature_series_df(category_name, station_name, data["start_date"], data["end_date"])
        if df is None or df.empty:
            continue

        df["Normalized Value"] = normalize_series(df["Value"])
        any_data = True
        fig.add_trace(
            go.Scatter(
                x=df["Timestamp"], y=df["Normalized Value"], mode="lines",
                name=category_name, line=dict(color=colors[i % len(colors)], width=2),
                hovertemplate="Date: %{x|%d-%b-%Y}<br>Normalized value: %{y:.2f}<extra></extra>",
            ),
            secondary_y=(i % 2 != 0),
        )

    chart_title = f"Multi-Category Timeline for {station_name}"
    if not any_data:
        return create_no_data_chart(chart_title)

    fig = apply_clean_layout(fig, chart_title, "Normalized Value")
    fig.update_xaxes(range=[overall_start, overall_end])
    return fig_to_json(fig)


def generate_multiple_categories_single_station_visualizations(selected_data):
    charts = []
    grouped = {}
    for data in selected_data:
        grouped.setdefault(data["station_name"], []).append(data)
    for station_name, categories_data in grouped.items():
        charts.append(plot_multiple_categories_single_station_chart(categories_data, station_name))
    return charts


# ------------------------------
# CHART 3: Single Category Across Multiple Stations
# ------------------------------

def plot_single_category_multiple_stations_chart(category_name, stations_data):
    colors = px.colors.qualitative.Plotly
    fig = go.Figure()
    any_data = False
    start_dts = [pd.to_datetime(d["start_date"], dayfirst=True) for d in stations_data]
    end_dts = [pd.to_datetime(d["end_date"], dayfirst=True) for d in stations_data]
    overall_start = min(start_dts) if start_dts else None
    overall_end = max(end_dts) if end_dts else None

    for i, data in enumerate(stations_data):
        station_name = data["station_name"]
        df = get_feature_series_df(category_name, station_name, data["start_date"], data["end_date"])
        if df is None or df.empty:
            continue
        any_data = True
        fig.add_trace(go.Scatter(
            x=df["Timestamp"], y=df["Value"], mode="lines", name=station_name,
            line=dict(color=colors[i % len(colors)], width=2),
            hovertemplate="Date: %{x|%d-%b-%Y}<br>Value: %{y:.2f}<extra></extra>",
        ))

    chart_title = f"{category_name} Comparison Across Stations"
    if not any_data:
        return create_no_data_chart(chart_title)

    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name))
    fig.update_xaxes(range=[overall_start, overall_end])
    return fig_to_json(fig)


def generate_single_category_multiple_stations_visualizations(selected_data):
    charts = []
    grouped = {}
    for data in selected_data:
        grouped.setdefault(data["category_name"], []).append(data)
    for category_name, stations_data in grouped.items():
        charts.append(plot_single_category_multiple_stations_chart(category_name, stations_data))
    return charts


# ------------------------------
# CHART 4: Multiple Categories Across Multiple Stations
# ------------------------------

def plot_multiple_categories_multiple_stations_chart(group_data):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = px.colors.qualitative.Plotly
    any_data = False
    overall_start = None
    overall_end = None
    trace_index = 0

    for station_name, categories_data in group_data.items():
        for data in categories_data:
            category_name = data["category_name"]
            start_dt = pd.to_datetime(data["start_date"], dayfirst=True)
            end_dt = pd.to_datetime(data["end_date"], dayfirst=True)
            overall_start = start_dt if overall_start is None else min(overall_start, start_dt)
            overall_end = end_dt if overall_end is None else max(overall_end, end_dt)

            df = get_feature_series_df(category_name, station_name, data["start_date"], data["end_date"])
            if df is None or df.empty:
                continue

            df["Normalized Value"] = normalize_series(df["Value"])
            any_data = True
            fig.add_trace(
                go.Scatter(
                    x=df["Timestamp"], y=df["Normalized Value"], mode="lines",
                    name=f"{station_name} - {category_name}",
                    line=dict(color=colors[trace_index % len(colors)], width=2),
                    hovertemplate="Date: %{x|%d-%b-%Y}<br>Normalized value: %{y:.2f}<extra></extra>",
                ),
                secondary_y=(trace_index % 2 != 0),
            )
            trace_index += 1

    chart_title = "Multi-Category and Multi-Station Comparison"
    if not any_data:
        return create_no_data_chart(chart_title)

    fig = apply_clean_layout(fig, chart_title, "Normalized Value")
    fig.update_xaxes(range=[overall_start, overall_end])
    return fig_to_json(fig)


def generate_multiple_categories_multiple_stations_visualizations(selected_data):
    group_data = {}
    for data in selected_data:
        group_data.setdefault(data["station_name"], []).append(data)
    return [plot_multiple_categories_multiple_stations_chart(group_data)]


# ------------------------------
# CHART 5: Year-over-Year Comparison
# ------------------------------

def plot_year_over_year_comparison_chart(station_name, category_name, start_date, end_date):
    chart_title = f"Year-over-Year {category_name} Comparison at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy()
    df["Year"] = df["Timestamp"].dt.year
    df["Month"] = df["Timestamp"].dt.month
    monthly_data = df.groupby(["Year", "Month"])["Value"].mean().reset_index()

    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    for i, year in enumerate(sorted(monthly_data["Year"].unique())):
        year_data = monthly_data[monthly_data["Year"] == year]
        fig.add_trace(go.Scatter(
            x=year_data["Month"], y=year_data["Value"], mode="lines+markers", name=str(year),
            line=dict(color=colors[i % len(colors)], width=2),
            hovertemplate="Month: %{x}<br>Value: %{y:.2f}<extra></extra>",
        ))

    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Month")
    fig.update_xaxes(tickmode="array", tickvals=list(range(1, 13)),
                     ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    return fig_to_json(fig)


def generate_year_over_year_comparison_visualizations(selected_data):
    return [
        plot_year_over_year_comparison_chart(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 6: Annual Monthly Totals Overview
# ------------------------------

def plot_annual_monthly_totals_chart(station_name, category_name, start_date, end_date):
    chart_title = f"Monthly Total Analysis for {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy()
    df["Month"] = df["Timestamp"].dt.month
    monthly_totals = round(df.groupby("Month")["Value"].sum().reindex(range(1, 13), fill_value=0), 2)

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    fig = go.Figure(data=[go.Bar(
        x=month_labels, y=monthly_totals.values, text=monthly_totals.values, textposition="auto",
        marker=dict(color="#7aa6d1"),
        hovertemplate="Month: %{x}<br>Total: %{y:.2f}<extra></extra>",
    )])
    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Month")
    return fig_to_json(fig)


def generate_annual_monthly_totals_visualizations(selected_data):
    return [
        plot_annual_monthly_totals_chart(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 7: Flow Duration Curve
# ------------------------------

def plot_flow_duration_curve(station_name, category_name, start_date, end_date):
    chart_title = f"Flow Duration Curve — {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    sorted_values = df["Value"].sort_values(ascending=False).reset_index(drop=True)
    exceedance = (sorted_values.index + 1) / len(sorted_values) * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=exceedance, y=sorted_values, mode="lines",
        line=dict(color="#2f6da3", width=2),
        fill="tozeroy", fillcolor="rgba(47, 109, 163, 0.1)",
        hovertemplate="Exceedance: %{x:.1f}%<br>Value: %{y:.2f}<extra></extra>",
    ))
    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Exceedance Probability (%)")
    fig.update_xaxes(tickformat=".0f", range=[0, 100], ticksuffix="%")
    return fig_to_json(fig)


def generate_flow_duration_curve_visualizations(selected_data):
    return [
        plot_flow_duration_curve(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 8: Monthly Distribution Box Plot
# ------------------------------

def plot_monthly_distribution_boxplot(station_name, category_name, start_date, end_date):
    chart_title = f"Monthly Distribution — {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy()
    df["Month"] = df["Timestamp"].dt.month
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    fig = go.Figure()
    for month_num in range(1, 13):
        month_data = df[df["Month"] == month_num]["Value"]
        fig.add_trace(go.Box(
            y=month_data, name=month_names[month_num - 1],
            marker_color="#2f6da3", line_color="#1e4f7a", boxmean=True,
            hovertemplate=f"Month: {month_names[month_num - 1]}<br>Value: %{{y:.2f}}<extra></extra>",
        ))

    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name), "Month")
    fig.update_layout(showlegend=False, hovermode="closest")
    return fig_to_json(fig)


def generate_monthly_distribution_boxplot_visualizations(selected_data):
    return [
        plot_monthly_distribution_boxplot(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# CHART 9: Multi-Station Temporal Heatmap
# ------------------------------

def plot_multi_station_temporal_heatmap(category_name, stations_data):
    chart_title = f"{category_name} — Multi-Station Temporal Heatmap"
    station_names = []
    year_values: dict = {}

    for data in stations_data:
        station_name = data["station_name"]
        df = get_feature_series_df(category_name, station_name, data["start_date"], data["end_date"])
        if df is None or df.empty:
            continue

        df = df.copy()
        df["Year"] = df["Timestamp"].dt.year
        yearly_avg = df.groupby("Year")["Value"].mean()
        station_names.append(station_name)
        for year, val in yearly_avg.items():
            year_values.setdefault(year, {})[station_name] = round(val, 2)

    if not station_names:
        return create_no_data_chart(chart_title)

    years = sorted(year_values.keys())
    z_matrix = [[year_values.get(year, {}).get(station, None) for year in years] for station in station_names]

    fig = go.Figure(data=go.Heatmap(
        z=z_matrix, x=[str(y) for y in years], y=station_names,
        colorscale="Blues", colorbar=dict(title=get_category_units(category_name)),
        hovertemplate="Year: %{x}<br>Station: %{y}<br>Avg Value: %{z:.2f}<extra></extra>",
    ))
    fig = apply_clean_layout(fig, chart_title, "", "Year")
    fig.update_layout(yaxis_title="Station", hovermode="closest")
    return fig_to_json(fig)


def generate_multi_station_heatmap_visualizations(selected_data):
    charts = []
    grouped = {}
    for data in selected_data:
        grouped.setdefault(data["category_name"], []).append(data)
    for category_name, stations_data in grouped.items():
        charts.append(plot_multi_station_temporal_heatmap(category_name, stations_data))
    return charts


# ------------------------------
# CHART 10: Correlation Scatter Plot
# ------------------------------

def plot_correlation_scatter(station_name, categories_data):
    if len(categories_data) < 2:
        return create_no_data_chart("Correlation Scatter Plot", "Two categories are required for this chart.")

    data_a, data_b = categories_data[0], categories_data[1]
    cat_a, cat_b = data_a["category_name"], data_b["category_name"]
    chart_title = f"Correlation: {cat_a} vs {cat_b} at {station_name}"

    df_a = get_feature_series_df(cat_a, station_name, data_a["start_date"], data_a["end_date"])
    df_b = get_feature_series_df(cat_b, station_name, data_b["start_date"], data_b["end_date"])

    if df_a is None or df_b is None or df_a.empty or df_b.empty:
        return create_no_data_chart(chart_title)

    series_a = df_a.set_index(df_a["Timestamp"].dt.date)["Value"].rename(cat_a)
    series_b = df_b.set_index(df_b["Timestamp"].dt.date)["Value"].rename(cat_b)
    merged = pd.concat([series_a, series_b], axis=1).dropna()

    if merged.empty:
        return create_no_data_chart(chart_title, "No overlapping dates found between the two categories.")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged[cat_a], y=merged[cat_b], mode="markers",
        marker=dict(color="#2f6da3", size=5, opacity=0.65),
        hovertemplate=f"{cat_a}: %{{x:.2f}}<br>{cat_b}: %{{y:.2f}}<extra></extra>",
    ))
    fig = apply_clean_layout(fig, chart_title, get_category_units(cat_b), get_category_units(cat_a))
    fig.update_layout(hovermode="closest")
    return fig_to_json(fig)


def generate_correlation_scatter_visualizations(selected_data):
    charts = []
    grouped = {}
    for data in selected_data:
        grouped.setdefault(data["station_name"], []).append(data)
    for station_name, categories_data in grouped.items():
        charts.append(plot_correlation_scatter(station_name, categories_data))
    return charts


# ------------------------------
# CHART 11: Anomaly Detection Chart
# ------------------------------

def plot_anomaly_detection_chart(station_name, category_name, start_date, end_date):
    chart_title = f"Anomaly Detection — {category_name} at {station_name}"
    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return create_no_data_chart(chart_title)

    df = df.copy()
    mean_val = df["Value"].mean()
    std_val = df["Value"].std()
    df["ZScore"] = (df["Value"] - mean_val) / std_val if std_val > 0 else 0.0
    df["IsAnomaly"] = df["ZScore"].abs() > 2.5

    normal = df[~df["IsAnomaly"]]
    anomalies = df[df["IsAnomaly"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=normal["Timestamp"], y=normal["Value"], mode="lines", name="Normal",
        line=dict(color="#2f6da3", width=1.5),
        hovertemplate="Date: %{x|%d-%b-%Y}<br>Value: %{y:.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=anomalies["Timestamp"], y=anomalies["Value"], mode="markers",
        name=f"Anomaly ({len(anomalies)})",
        marker=dict(color="#c0392b", size=7, symbol="circle-open", line=dict(width=2)),
        hovertemplate="Date: %{x|%d-%b-%Y}<br>Value: %{y:.2f} (anomaly)<extra></extra>",
    ))
    fig = apply_clean_layout(fig, chart_title, get_category_units(category_name))
    return fig_to_json(fig)


def generate_anomaly_detection_visualizations(selected_data):
    return [
        plot_anomaly_detection_chart(d["station_name"], d["category_name"], d["start_date"], d["end_date"])
        for d in selected_data
    ]


# ------------------------------
# SUMMARY & RANKING
# ------------------------------

def build_summary_for_selection(selected_data):
    if not selected_data:
        return {
            "station": "--", "category": "--", "date_range": "--",
            "mean": "--", "min": "--", "max": "--",
            "first_year": "--", "last_year": "--", "record_count": "--",
            "coverage_note": "Awaiting visualization selection",
        }

    first = selected_data[0]
    station_name = first["station_name"]
    category_name = first["category_name"]
    start_date = first["start_date"]
    end_date = first["end_date"]

    df = get_feature_series_df(category_name, station_name, start_date, end_date)
    if df is None or df.empty:
        return {
            "station": station_display(station_name), "category": category_name,
            "date_range": f"{start_date} -> {end_date}",
            "mean": "--", "min": "--", "max": "--",
            "first_year": "--", "last_year": "--", "record_count": 0,
            "coverage_note": "No data available for selected range",
        }

    return {
        "station": station_display(station_name),
        "category": category_name,
        "date_range": f"{start_date} -> {end_date}",
        "mean": round(df["Value"].mean(), 2),
        "min": round(df["Value"].min(), 2),
        "max": round(df["Value"].max(), 2),
        "first_year": int(df["Timestamp"].dt.year.min()),
        "last_year": int(df["Timestamp"].dt.year.max()),
        "record_count": int(len(df)),
        "coverage_note": "Based on current visualization selection",
    }


def build_station_ranking_for_category(category_name: str, top_n: int = 5):
    feature = CATEGORY_TO_FEATURE.get(category_name)
    if not feature or repo is None:
        return []

    ranking_rows = []
    for station_name, station_meta in repo.station_index.items():
        if feature not in station_meta.get("features", []):
            continue
        try:
            df = repo.get_station_dataframe(station_name)
            if feature not in df.columns:
                continue
            series = pd.to_numeric(df[feature], errors="coerce").dropna()
            if series.empty:
                continue
            ranking_rows.append({
                "station": station_display(station_name),
                "average_value": round(float(series.mean()), 2),
                "maximum_value": round(float(series.max()), 2),
                "record_count": int(len(series)),
            })
        except Exception:
            continue

    ranking_rows.sort(key=lambda r: r["average_value"], reverse=True)
    return ranking_rows[:top_n]


# ------------------------------
# MAIN ENTRY POINT
# ------------------------------

GRAPH_DISPATCH = {
    "Single Category, Single Station Timeline": generate_single_category_single_station_visualizations,
    "Multiple Categories, Single Station Timeline": generate_multiple_categories_single_station_visualizations,
    "Single Category Across Multiple Stations Comparison": generate_single_category_multiple_stations_visualizations,
    "Multiple Categories Across Multiple Stations Comparison": generate_multiple_categories_multiple_stations_visualizations,
    "Year-over-Year Comparison": generate_year_over_year_comparison_visualizations,
    "Annual Monthly Totals Overview": generate_annual_monthly_totals_visualizations,
    "Flow Duration Curve": generate_flow_duration_curve_visualizations,
    "Monthly Distribution Box Plot": generate_monthly_distribution_boxplot_visualizations,
    "Multi-Station Temporal Heatmap": generate_multi_station_heatmap_visualizations,
    "Correlation Scatter Plot": generate_correlation_scatter_visualizations,
    "Anomaly Detection Chart": generate_anomaly_detection_visualizations,
}


def generate_visualizations_with_summary(graph_type: str, selected_data: list) -> dict:
    generator = GRAPH_DISPATCH.get(graph_type)
    charts = generator(selected_data) if generator else []

    summary = build_summary_for_selection(selected_data)
    ranking = build_station_ranking_for_category(summary["category"]) if summary["category"] != "--" else []

    return {"charts": charts, "summary": summary, "ranking": ranking}
